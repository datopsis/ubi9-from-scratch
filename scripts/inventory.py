#!/usr/bin/env python3
"""Produce a complete file inventory of an image layer.

WP3. Reads metadata from the tar headers rather than extracting to a
filesystem. That is deliberate: the tar header is the record of what the image
declares, whereas an extracted tree only shows what the extracting filesystem
happened to preserve. It also makes the inventory reproducible on any host.

Requires only the standard library.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import tarfile
from pathlib import Path

TYPE_NAMES = {
    tarfile.REGTYPE: "file",
    tarfile.AREGTYPE: "file",
    tarfile.LNKTYPE: "hardlink",
    tarfile.SYMTYPE: "symlink",
    tarfile.DIRTYPE: "dir",
    tarfile.FIFOTYPE: "fifo",
    tarfile.CHRTYPE: "chardev",
    tarfile.BLKTYPE: "blockdev",
}


def decompress(src: Path, dst: Path) -> str:
    """Decompress a layer blob and return the diff_id of the result."""
    digest = hashlib.sha256()
    with gzip.open(src, "rb") as fin, dst.open("wb") as fout:
        while chunk := fin.read(1 << 20):
            digest.update(chunk)
            fout.write(chunk)
    return "sha256:" + digest.hexdigest()


def xattrs_of(member: tarfile.TarInfo) -> dict[str, str]:
    prefix = "SCHILY.xattr."
    return {
        key[len(prefix) :]: value
        for key, value in (member.pax_headers or {}).items()
        if key.startswith(prefix)
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=Path("work"))
    parser.add_argument("--layer", type=int, default=0)
    args = parser.parse_args()

    blob = args.work / f"layer-{args.layer}.tar.gz"
    plain = args.work / f"layer-{args.layer}.tar"
    config = json.loads((args.work / "config.json").read_bytes())

    diff_id = decompress(blob, plain)
    expected = config["rootfs"]["diff_ids"][args.layer]
    status = "VERIFIED" if diff_id == expected else "MISMATCH"
    print(f"diff_id  {diff_id}  {status}")
    if status == "MISMATCH":
        print(f"         expected {expected}", file=sys.stderr)
        return 1

    print(f"blob     {blob.stat().st_size:,} B compressed")
    print(f"tar      {plain.stat().st_size:,} B uncompressed")

    rows = []
    with tarfile.open(plain, "r:") as tar:
        for member in tar:
            rows.append(
                {
                    "path": "/" + member.name.lstrip("./").lstrip("/"),
                    "type": TYPE_NAMES.get(member.type, f"other:{member.type!r}"),
                    "mode": f"{member.mode:04o}",
                    "uid": member.uid,
                    "gid": member.gid,
                    "uname": member.uname,
                    "gname": member.gname,
                    "size": member.size,
                    "mtime": member.mtime,
                    "link": member.linkname,
                    "xattrs": xattrs_of(member),
                }
            )

    rows.sort(key=lambda r: r["path"])
    out = args.work / "inventory.json"
    out.write_text(json.dumps(rows, indent=1, sort_keys=True) + "\n")

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["type"]] = counts.get(row["type"], 0) + 1

    apparent = sum(r["size"] for r in rows if r["type"] == "file")
    setuid = [r for r in rows if int(r["mode"], 8) & 0o4000]
    setgid = [r for r in rows if int(r["mode"], 8) & 0o2000]
    caps = [r for r in rows if any(k == "security.capability" for k in r["xattrs"])]
    nonroot = [r for r in rows if r["uid"] or r["gid"]]
    mtimes = {r["mtime"] for r in rows}

    print(f"\nentries  {len(rows):,}")
    for kind in sorted(counts):
        print(f"  {kind:<10} {counts[kind]:,}")
    print(f"\napparent file bytes  {apparent:,}")
    print(f"distinct mtimes      {len(mtimes)}")
    print(f"setuid entries       {len(setuid)}")
    print(f"setgid entries       {len(setgid)}")
    print(f"file capabilities    {len(caps)}")
    print(f"non-root owned       {len(nonroot)}")

    for label, group in (("setuid", setuid), ("setgid", setgid), ("caps", caps)):
        for row in group:
            extra = row["xattrs"].get("security.capability", "")
            print(f"  {label:<7} {row['mode']} {row['path']} {extra}")

    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
