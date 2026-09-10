#!/usr/bin/env python3
"""Compute what a binary actually needs from an image.

WP9 tooling, static half. Reads ELF headers directly out of the layer tar,
follows DT_NEEDED recursively, resolves each library against the image's own
search paths and symlinks, and reports the closure — plus its complement, which
is the set of files a tailored image could drop.

This runs anywhere Python does. It needs no container runtime, no Linux, and
never executes the binary it analyses.

WHAT THIS CANNOT SEE
--------------------
Static analysis finds libraries named in ELF headers. It cannot find anything
loaded at runtime by name:

- `dlopen` targets, including OpenSSL provider modules — the FIPS provider is
  loaded this way, so a FIPS build's most important component is invisible here;
- NSS modules behind getaddrinfo / getpwnam (libnss_files, libnss_dns);
- configuration, certificate bundles, locale and timezone data;
- anything a program shells out to.

A closure from this tool is a lower bound and a starting point. It is not
evidence that an image is complete. `scripts/trace_runtime.sh` covers the
dynamic half and requires an actual run.

Requires only the standard library.
"""

from __future__ import annotations

import argparse
import json
import posixpath
import struct
import tarfile
from pathlib import Path

# ELF constants, from elf.h
PT_LOAD, PT_DYNAMIC = 1, 2
DT_NULL, DT_NEEDED, DT_STRTAB, DT_RPATH, DT_RUNPATH, DT_SONAME = 0, 1, 5, 15, 29, 14

# Default search path for a glibc system. The image's own ld.so.conf could be
# parsed, but these cover UBI's layout and the resolver reports anything it
# fails to find rather than silently dropping it.
DEFAULT_SEARCH = ("/usr/lib64", "/lib64", "/usr/lib", "/lib")


class Image:
    """Random access to a layer tar, with symlink resolution."""

    def __init__(self, layer: Path) -> None:
        self.tar = tarfile.open(layer, "r:")
        self.members: dict[str, tarfile.TarInfo] = {}
        for member in self.tar.getmembers():
            self.members["/" + member.name.lstrip("./").lstrip("/")] = member

    def resolve(self, path: str, depth: int = 0) -> str | None:
        """Resolve a path through directory and file symlinks."""
        if depth > 40:
            return None
        path = posixpath.normpath(path)
        member = self.members.get(path)
        if member is not None and not member.issym():
            return path
        if member is not None and member.issym():
            target = member.linkname
            if not target.startswith("/"):
                target = posixpath.join(posixpath.dirname(path), target)
            return self.resolve(target, depth + 1)

        # No exact entry: an ancestor may be a symlink, as with /lib64 -> usr/lib64.
        parts = path.strip("/").split("/")
        for cut in range(len(parts) - 1, 0, -1):
            prefix = "/" + "/".join(parts[:cut])
            entry = self.members.get(prefix)
            if entry is not None and entry.issym():
                target = entry.linkname
                if not target.startswith("/"):
                    target = posixpath.join(posixpath.dirname(prefix), target)
                rest = "/".join(parts[cut:])
                return self.resolve(posixpath.join(target, rest), depth + 1)
        return None

    def read(self, path: str) -> bytes | None:
        real = self.resolve(path)
        if real is None:
            return None
        member = self.members.get(real)
        if member is None or not member.isfile():
            return None
        handle = self.tar.extractfile(member)
        return handle.read() if handle else None

    def size(self, path: str) -> int:
        member = self.members.get(path)
        return member.size if member else 0


def parse_elf(data: bytes) -> dict[str, object] | None:
    """Extract DT_NEEDED, DT_SONAME and DT_RUNPATH from an ELF image."""
    if len(data) < 64 or data[:4] != b"\x7fELF":
        return None
    is64 = data[4] == 2
    little = data[5] == 1
    if not is64:
        return None  # UBI 9 is 64-bit only; a 32-bit binary is worth reporting loudly
    end = "<" if little else ">"

    e_phoff, = struct.unpack_from(end + "Q", data, 32)
    e_phentsize, e_phnum = struct.unpack_from(end + "HH", data, 54)

    loads: list[tuple[int, int, int]] = []  # (vaddr, offset, filesz)
    dynamic: tuple[int, int] | None = None
    for n in range(e_phnum):
        base = e_phoff + n * e_phentsize
        if base + 56 > len(data):
            return None
        p_type, = struct.unpack_from(end + "I", data, base)
        p_offset, p_vaddr = struct.unpack_from(end + "QQ", data, base + 8)
        p_filesz, = struct.unpack_from(end + "Q", data, base + 32)
        if p_type == PT_LOAD:
            loads.append((p_vaddr, p_offset, p_filesz))
        elif p_type == PT_DYNAMIC:
            dynamic = (p_offset, p_filesz)

    if dynamic is None:
        return {"needed": [], "soname": None, "runpath": None, "static": True}

    def to_offset(vaddr: int) -> int | None:
        for base_vaddr, offset, size in loads:
            if base_vaddr <= vaddr < base_vaddr + size:
                return offset + (vaddr - base_vaddr)
        return None

    entries: list[tuple[int, int]] = []
    offset, size = dynamic
    for pos in range(offset, min(offset + size, len(data)) - 15, 16):
        tag, val = struct.unpack_from(end + "qQ", data, pos)
        if tag == DT_NULL:
            break
        entries.append((tag, val))

    strtab_addr = next((v for t, v in entries if t == DT_STRTAB), None)
    if strtab_addr is None:
        return {"needed": [], "soname": None, "runpath": None, "static": False}
    strtab = to_offset(strtab_addr)
    if strtab is None:
        return {"needed": [], "soname": None, "runpath": None, "static": False}

    def string_at(index: int) -> str:
        start = strtab + index
        stop = data.index(b"\x00", start)
        return data[start:stop].decode("utf-8", "replace")

    needed = [string_at(v) for t, v in entries if t == DT_NEEDED]
    soname = next((string_at(v) for t, v in entries if t == DT_SONAME), None)
    runpath = next(
        (string_at(v) for t, v in entries if t in (DT_RUNPATH, DT_RPATH)), None
    )
    return {"needed": needed, "soname": soname, "runpath": runpath, "static": False}


def compute_closure(
    image: Image, entrypoints: list[str], search: tuple[str, ...]
) -> tuple[dict[str, list[str]], list[str]]:
    """Walk DT_NEEDED from each entrypoint. Returns (resolved, unresolved)."""
    resolved: dict[str, list[str]] = {}
    unresolved: list[str] = []
    queue = list(entrypoints)

    while queue:
        path = queue.pop(0)
        real = image.resolve(path)
        if real is None:
            unresolved.append(path)
            continue
        if real in resolved:
            continue
        data = image.read(real)
        if data is None:
            resolved[real] = []
            continue
        elf = parse_elf(data)
        if elf is None:
            resolved[real] = []  # not an ELF: a script, data file or symlink target
            continue

        found = []
        for soname in elf["needed"]:
            candidates = []
            if elf["runpath"]:
                candidates += [
                    posixpath.join(part, soname)
                    for part in elf["runpath"].replace("$ORIGIN", posixpath.dirname(real)).split(":")
                ]
            candidates += [posixpath.join(part, soname) for part in search]
            hit = next((c for c in candidates if image.resolve(c)), None)
            if hit is None:
                unresolved.append(f"{soname} (needed by {real})")
            else:
                found.append(image.resolve(hit))
                queue.append(hit)
        resolved[real] = found

    return resolved, unresolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("entrypoints", nargs="+", help="paths inside the image, e.g. /usr/bin/bash")
    parser.add_argument("--layer", type=Path, default=Path("work/layer-0.tar"))
    parser.add_argument("--inventory", type=Path, default=Path("work/inventory.json"))
    parser.add_argument("--json", type=Path, help="write the closure to this file")
    parser.add_argument("--show-droppable", action="store_true", help="list what is not needed")
    args = parser.parse_args()

    image = Image(args.layer)
    resolved, unresolved = compute_closure(image, args.entrypoints, DEFAULT_SEARCH)

    # A resolved path may be reached through symlinks that must also be kept.
    keep: set[str] = set()
    for path in resolved:
        keep.add(path)
        for entry in args.entrypoints:
            link = posixpath.normpath(entry)
            if image.resolve(link) == path:
                keep.add(link)

    inventory = json.loads(args.inventory.read_text()) if args.inventory.exists() else []
    sizes = {row["path"]: row["size"] for row in inventory}
    total_image = sum(sizes.values())
    closure_bytes = sum(sizes.get(path, image.size(path)) for path in keep)

    print(f"entrypoints : {', '.join(args.entrypoints)}")
    print(f"closure     : {len(keep)} files, {closure_bytes:,} B\n")

    for path in sorted(resolved):
        deps = resolved[path]
        print(f"  {sizes.get(path, 0):>10,}  {path}")
        for dep in deps:
            print(f"              -> {dep}")

    if unresolved:
        print(f"\nUNRESOLVED ({len(unresolved)}) — these break the closure:")
        for item in unresolved:
            print(f"  {item}")

    if total_image:
        share = closure_bytes / total_image * 100
        print(f"\nclosure is {share:.1f}% of {total_image:,} apparent file bytes")
        print(f"not in closure: {total_image - closure_bytes:,} B across {len(sizes) - len(keep)} entries")

    if args.show_droppable:
        print("\nlargest entries NOT in the closure:")
        droppable = sorted(
            ((size, path) for path, size in sizes.items() if path not in keep),
            reverse=True,
        )
        for size, path in droppable[:20]:
            print(f"  {size:>10,}  {path}")

    if args.json:
        args.json.write_text(
            json.dumps(
                {
                    "entrypoints": args.entrypoints,
                    "closure": sorted(keep),
                    "closure_bytes": closure_bytes,
                    "unresolved": unresolved,
                    "graph": {k: v for k, v in sorted(resolved.items())},
                },
                indent=1,
            )
            + "\n"
        )
        print(f"\nwrote {args.json}")

    print(
        "\nNOTE: static closure only. dlopen targets (OpenSSL providers, NSS "
        "modules), certificates, locale and timezone data are NOT included. "
        "See the module docstring."
    )
    return 1 if unresolved else 0


if __name__ == "__main__":
    raise SystemExit(main())
