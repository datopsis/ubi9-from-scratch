#!/usr/bin/env python3
"""Assert properties of a built image by inspecting its filesystem.

Verification that works for every rung of the ladder, including images with no
shell. A `podman run ... /bin/sh -c ...` check cannot verify an image whose
whole point is that it contains one binary; exporting the filesystem and
reading it can.

Produce the input with:

    podman create --name check <image>
    podman export check -o rootfs.tar
    podman rm check

Requires only the standard library.
"""

from __future__ import annotations

import argparse
import json
import sys
import tarfile
from pathlib import Path

# Anything that could install packages. Their absence is what "micro" means.
PACKAGE_MANAGERS = ("rpm", "dnf", "dnf-3", "microdnf", "yum", "apt", "apk")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rootfs", type=Path, help="tar produced by podman export")
    parser.add_argument("--max-entries", type=int, help="fail if more entries than this")
    parser.add_argument("--max-bytes", type=int, help="fail if apparent bytes exceed this")
    parser.add_argument("--expect-entries", type=int, help="fail unless exactly this many")
    parser.add_argument(
        "--allow-package-manager",
        action="store_true",
        help="skip the package-manager check (for builder images)",
    )
    parser.add_argument("--json", type=Path, help="write the report here")
    args = parser.parse_args()

    entries = []
    with tarfile.open(args.rootfs, "r:") as tar:
        for member in tar:
            entries.append(
                {
                    "path": "/" + member.name.lstrip("./").lstrip("/"),
                    "type": (
                        "dir" if member.isdir()
                        else "symlink" if member.issym()
                        else "hardlink" if member.islnk()
                        else "file" if member.isfile()
                        else "other"
                    ),
                    "mode": member.mode,
                    "size": member.size,
                    "uid": member.uid,
                    "gid": member.gid,
                }
            )

    files = [e for e in entries if e["type"] == "file"]
    total = sum(e["size"] for e in files)
    setuid = [e for e in entries if e["mode"] & 0o4000]
    setgid = [e for e in entries if e["mode"] & 0o2000]
    nonroot = [e for e in entries if e["uid"] or e["gid"]]

    managers = [
        e["path"]
        for e in entries
        if e["type"] in ("file", "symlink")
        and e["path"].rsplit("/", 1)[-1] in PACKAGE_MANAGERS
    ]

    print(f"entries        : {len(entries):,}")
    print(f"  files        : {len(files):,}")
    print(f"apparent bytes : {total:,}")
    print(f"setuid         : {len(setuid)}")
    print(f"setgid         : {len(setgid)}")
    print(f"non-root owned : {len(nonroot)}")
    print(f"package mgrs   : {len(managers)}")

    failures: list[str] = []
    if setuid:
        failures.append(f"setuid entries present: {[e['path'] for e in setuid]}")
    if setgid:
        failures.append(f"setgid entries present: {[e['path'] for e in setgid]}")
    if managers and not args.allow_package_manager:
        failures.append(f"package manager present: {managers}")
    if args.expect_entries is not None and len(entries) != args.expect_entries:
        failures.append(f"expected exactly {args.expect_entries} entries, found {len(entries)}")
    if args.max_entries is not None and len(entries) > args.max_entries:
        failures.append(f"expected at most {args.max_entries} entries, found {len(entries)}")
    if args.max_bytes is not None and total > args.max_bytes:
        failures.append(f"expected at most {args.max_bytes:,} bytes, found {total:,}")

    if args.json:
        args.json.write_text(
            json.dumps(
                {
                    "entries": len(entries),
                    "files": len(files),
                    "apparent_bytes": total,
                    "setuid": [e["path"] for e in setuid],
                    "setgid": [e["path"] for e in setgid],
                    "package_managers": managers,
                    "failures": failures,
                },
                indent=1,
            )
            + "\n"
        )

    if failures:
        print("\nFAILED:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1

    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
