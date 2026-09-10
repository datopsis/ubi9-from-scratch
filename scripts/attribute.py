#!/usr/bin/env python3
"""Attribute every file in the layer to the package that owns it.

WP4, completed. Decodes the full file manifest each package declares in the
rpmdb and compares it against the inventory taken from the tar headers. That
yields three sets the reconstruction needs to be honest about:

- attributed: present in the image and claimed by a package;
- unattributed: present in the image and claimed by nobody;
- trimmed: claimed by a package and absent from the image.

The third set is the one that matters most. Installing the recorded package
set reproduces what the packages declare, not what Red Hat shipped, so every
trimmed path is a deletion a reconstruction has to repeat deliberately.

Requires only the standard library.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import struct
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

TYPE_INT16, TYPE_INT32, TYPE_STRING, TYPE_BIN, TYPE_STRING_ARRAY, TYPE_I18N = 3, 4, 6, 7, 8, 9

TAGS = {
    1000: "name",
    1001: "version",
    1002: "release",
    1003: "epoch",
    1009: "size",
    1014: "license",
    1022: "arch",
    1044: "sourcerpm",
    1028: "filesizes",
    1030: "filemodes",
    1036: "filelinktos",
    1037: "fileflags",
    1039: "fileusername",
    1040: "filegroupname",
    1096: "fileinodes",
    1116: "dirindexes",
    1117: "basenames",
    1118: "dirnames",
}

# rpmfileAttrs, from rpmfiles.h
FLAG_DOC = 1 << 1
FLAG_LICENSE = 1 << 7
FLAG_GHOST = 1 << 6
FLAG_MISSINGOK = 1 << 3


def parse_header(blob: bytes) -> dict[str, object]:
    """Decode an RPM header, including the array tags carrying file manifests."""
    count, data_size = struct.unpack(">II", blob[0:8])
    if 8 + count * 16 + data_size != len(blob):
        raise ValueError("header length does not match declared size")
    index = blob[8 : 8 + count * 16]
    store = blob[8 + count * 16 : 8 + count * 16 + data_size]

    out: dict[str, object] = {}
    for n in range(count):
        tag, rtype, offset, items = struct.unpack(">IIII", index[n * 16 : (n + 1) * 16])
        field = TAGS.get(tag)
        if field is None:
            continue
        if rtype in (TYPE_STRING, TYPE_I18N):
            out[field] = store[offset : store.index(b"\x00", offset)].decode("utf-8", "replace")
        elif rtype == TYPE_STRING_ARRAY:
            values, cursor = [], offset
            for _ in range(items):
                end = store.index(b"\x00", cursor)
                values.append(store[cursor:end].decode("utf-8", "replace"))
                cursor = end + 1
            out[field] = values
        elif rtype == TYPE_INT32:
            values = struct.unpack(f">{items}I", store[offset : offset + 4 * items])
            out[field] = list(values) if items > 1 else values[0]
        elif rtype == TYPE_INT16:
            values = struct.unpack(f">{items}H", store[offset : offset + 2 * items])
            out[field] = list(values) if items > 1 else values[0]
    return out


def file_manifest(pkg: dict[str, object]) -> list[dict[str, object]]:
    """Rebuild the absolute path list a package declares."""
    basenames = pkg.get("basenames") or []
    dirnames = pkg.get("dirnames") or []
    dirindexes = pkg.get("dirindexes")
    if not basenames:
        return []
    if isinstance(dirindexes, int):
        dirindexes = [dirindexes]
    dirindexes = dirindexes or [0] * len(basenames)

    def column(key: str, default: object) -> list[object]:
        value = pkg.get(key)
        if value is None:
            return [default] * len(basenames)
        if not isinstance(value, list):
            return [value]
        return value

    sizes = column("filesizes", 0)
    modes = column("filemodes", 0)
    flags = column("fileflags", 0)
    links = column("filelinktos", "")
    inodes = column("fileinodes", 0)

    manifest = []
    for n, base in enumerate(basenames):
        directory = dirnames[dirindexes[n]] if dirindexes[n] < len(dirnames) else "/"
        manifest.append(
            {
                "path": directory + base,
                "size": sizes[n] if n < len(sizes) else 0,
                "mode": modes[n] if n < len(modes) else 0,
                "flags": flags[n] if n < len(flags) else 0,
                "link": links[n] if n < len(links) else "",
                "inode": inodes[n] if n < len(inodes) else 0,
            }
        )
    return manifest


def alias_map(inventory: list[dict[str, object]]) -> list[tuple[str, str]]:
    """Build the directory-symlink prefix map the image actually declares.

    RHEL 9 is /usr-merged: /bin, /sbin, /lib and /lib64 are symlinks into
    /usr. Packages declare file paths under the pre-merge names, so a literal
    comparison against the inventory reports merged files as both trimmed and
    unattributed. The map is derived from the image rather than hardcoded, so
    it stays correct if the layout changes.
    """
    aliases = []
    for row in inventory:
        if row["type"] != "symlink":
            continue
        target = row["link"]
        if target.startswith("/"):
            resolved = target
        else:
            resolved = str(PurePosixPath(row["path"]).parent / target)
        resolved = str(PurePosixPath(resolved))
        if any(r["path"] == resolved and r["type"] == "dir" for r in inventory):
            aliases.append((row["path"], resolved))
    # Longest prefix first, so /lib64 wins over /lib.
    return sorted(aliases, key=lambda pair: -len(pair[0]))


def canonical(path: str, aliases: list[tuple[str, str]]) -> str:
    """Rewrite a declared path through the image's directory symlinks."""
    for source, target in aliases:
        if path == source:
            return target
        if path.startswith(source + "/"):
            return target + path[len(source) :]
    return path


def load_packages(layer: Path) -> list[dict[str, object]]:
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "rpmdb.sqlite"
        with tarfile.open(layer, "r:") as tar:
            members = {m.name.lstrip("./"): m for m in tar.getmembers()}
            member = members["var/lib/rpm/rpmdb.sqlite"]
            target.write_bytes(tar.extractfile(member).read())
        connection = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
        blobs = [row[0] for row in connection.execute("SELECT blob FROM Packages")]
        connection.close()

    packages = []
    for blob in blobs:
        try:
            parsed = parse_header(blob)
        except (ValueError, IndexError, struct.error):
            continue
        if parsed.get("name", "").startswith("gpg-pubkey"):
            continue
        packages.append(parsed)
    return sorted(packages, key=lambda p: p["name"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=Path("work"))
    parser.add_argument("--layer", type=int, default=0)
    parser.add_argument("--show", type=int, default=25, help="trimmed paths to list per package")
    args = parser.parse_args()

    inventory = json.loads((args.work / "inventory.json").read_text())
    present = {row["path"]: row for row in inventory}
    packages = load_packages(args.work / f"layer-{args.layer}.tar")
    aliases = alias_map(inventory)

    owner: dict[str, str] = {}
    report = []
    trimmed_all: list[tuple[str, dict[str, object]]] = []

    for pkg in packages:
        manifest = file_manifest(pkg)
        here, gone, gone_bytes = 0, [], 0
        counted_inodes: set[int] = set()
        for entry in manifest:
            declared = entry["path"].rstrip("/") or "/"
            # An exact match always wins; the alias map is a fallback for
            # paths declared under the pre-/usr-merge names.
            path = declared if declared in present else canonical(declared, aliases)
            if path in present:
                here += 1
                owner.setdefault(path, pkg["name"])
            elif entry["flags"] & FLAG_GHOST:
                continue  # %ghost files are declared but never shipped
            else:
                gone.append(entry)
                # RPM's SIZE tag counts a hardlink group once; FILESIZES
                # repeats the size for every link. Deduplicate by inode so
                # trimmed bytes describe reclaimable space, not apparent size.
                if entry["inode"] not in counted_inodes:
                    counted_inodes.add(entry["inode"])
                    gone_bytes += entry["size"]
                trimmed_all.append((pkg["name"], entry))
        report.append(
            {
                "name": pkg["name"],
                "declared_files": len(manifest),
                "present": here,
                "trimmed": len(gone),
                "trimmed_bytes": gone_bytes,
                "declared_size": int(pkg.get("size") or 0),
                "license": pkg.get("license", "-"),
                "sourcerpm": pkg.get("sourcerpm", "-"),
                "examples": [entry["path"] for entry in gone[: args.show]],
            }
        )

    unattributed = [row for row in inventory if row["path"] not in owner]

    width = max(len(r["name"]) for r in report)
    print(f"{'PACKAGE'.ljust(width)}  DECL  HERE  TRIM   TRIMMED BYTES")
    for row in sorted(report, key=lambda r: -r["trimmed_bytes"]):
        print(
            f"{row['name'].ljust(width)}  {row['declared_files']:>4}  {row['present']:>4}  "
            f"{row['trimmed']:>4}  {row['trimmed_bytes']:>14,}"
        )

    total_trimmed = sum(r["trimmed_bytes"] for r in report)
    total_declared = sum(r["declared_size"] for r in report)
    print(f"\ndeclared unpacked total : {total_declared:,} B")
    print(f"trimmed away            : {total_trimmed:,} B")
    print(f"attributed paths        : {len(owner):,} of {len(inventory):,} inventory entries")
    print(f"unattributed paths      : {len(unattributed):,}")

    unattributed_bytes = sum(row["size"] for row in unattributed)
    print(f"unattributed bytes      : {unattributed_bytes:,}")

    print("\n=== unattributed entries carrying bytes ===")
    for row in sorted((r for r in unattributed if r["size"]), key=lambda r: -r["size"]):
        print(f"  {row['size']:>10,}  {row['path']}")

    out = args.work / "attribution.json"
    out.write_text(
        json.dumps(
            {
                "packages": report,
                "owner": owner,
                "unattributed": [r["path"] for r in unattributed],
                "totals": {
                    "declared_unpacked": total_declared,
                    "trimmed_bytes": total_trimmed,
                    "attributed_paths": len(owner),
                    "unattributed_paths": len(unattributed),
                    "unattributed_bytes": unattributed_bytes,
                },
            },
            indent=1,
            sort_keys=True,
        )
        + "\n"
    )
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
