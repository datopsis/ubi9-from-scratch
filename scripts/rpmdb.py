#!/usr/bin/env python3
"""Read the RPM database carried inside the image layer.

WP4. UBI Micro ships no package manager, but it does ship the rpmdb that the
external build transaction produced. That makes package attribution a matter
of reading the image's own record rather than inferring one, so the package
set for a reconstruction can be stated exactly.

Parses the RPM header blob directly; requires only the standard library.
"""

from __future__ import annotations

import argparse
import sqlite3
import struct
import tarfile
import tempfile
from pathlib import Path

HEADER_MAGIC = b"\x8e\xad\xe8"

# RPM tag numbers we care about, from rpmtag.h.
TAGS = {
    1000: "name",
    1001: "version",
    1002: "release",
    1003: "epoch",
    1004: "summary",
    1009: "size",
    1014: "license",
    1022: "arch",
    1044: "sourcerpm",
    1106: "sourcepackage",
}

TYPE_INT16, TYPE_INT32, TYPE_STRING, TYPE_STRING_ARRAY, TYPE_I18NSTRING = 3, 4, 6, 8, 9


def parse_header(blob: bytes) -> dict[str, object]:
    """Decode the subset of an RPM header needed for package identity.

    The sqlite backend stores the header region without the 8-byte lead magic
    that prefixes a header on disk, so the blob opens directly on the index
    count and data-store size.
    """
    count, data_size = struct.unpack(">II", blob[0:8])
    expected = 8 + count * 16 + data_size
    if expected != len(blob):
        raise ValueError(f"header length {len(blob)} does not match declared {expected}")
    index = blob[8 : 8 + count * 16]
    store = blob[8 + count * 16 : 8 + count * 16 + data_size]

    out: dict[str, object] = {}
    for n in range(count):
        tag, rtype, offset, items = struct.unpack(">IIII", index[n * 16 : (n + 1) * 16])
        field = TAGS.get(tag)
        if field is None:
            continue
        if rtype in (TYPE_STRING, TYPE_I18NSTRING, TYPE_STRING_ARRAY):
            end = store.index(b"\x00", offset)
            out[field] = store[offset:end].decode("utf-8", "replace")
        elif rtype == TYPE_INT32:
            out[field] = struct.unpack(">I", store[offset : offset + 4])[0]
        elif rtype == TYPE_INT16:
            out[field] = struct.unpack(">H", store[offset : offset + 2])[0]
    return out


def extract_rpmdb(layer: Path, into: Path) -> Path:
    """Pull the sqlite rpmdb and its journal out of the layer tar."""
    wanted = ("var/lib/rpm/rpmdb.sqlite", "var/lib/rpm/rpmdb.sqlite-wal", "var/lib/rpm/rpmdb.sqlite-shm")
    with tarfile.open(layer, "r:") as tar:
        members = {m.name.lstrip("./"): m for m in tar.getmembers()}
        for name in wanted:
            member = members.get(name)
            if member is None or not member.isfile():
                continue
            (into / Path(name).name).write_bytes(tar.extractfile(member).read())
    return into / "rpmdb.sqlite"


def nevra(pkg: dict[str, object]) -> str:
    """Format package identity.

    `gpg-pubkey` entries are imported keys rather than installed packages and
    carry no architecture, so the architecture suffix is omitted for them
    instead of being invented.
    """
    epoch = pkg.get("epoch")
    prefix = f"{epoch}:" if epoch not in (None, 0) else ""
    stem = f"{pkg.get('name', '?')}-{prefix}{pkg.get('version', '?')}-{pkg.get('release', '?')}"
    arch = pkg.get("arch")
    return f"{stem}.{arch}" if arch else stem


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=Path("work"))
    parser.add_argument("--layer", type=int, default=0)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        db = extract_rpmdb(args.work / f"layer-{args.layer}.tar", Path(tmp))
        connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        blobs = [row[0] for row in connection.execute("SELECT blob FROM Packages")]
        connection.close()

    packages = []
    for blob in blobs:
        try:
            packages.append(parse_header(blob))
        except (ValueError, IndexError, struct.error) as exc:
            print(f"  skipped an unparsable header: {exc}")

    packages.sort(key=lambda p: p["name"])
    total = sum(int(p.get("size") or 0) for p in packages)

    print(f"packages installed : {len(packages)}")
    print(f"declared unpacked  : {total:,} B\n")

    width = max(len(nevra(p)) for p in packages)
    print(f"{'NEVRA'.ljust(width)}  {'SIZE':>10}  SOURCE RPM")
    for pkg in packages:
        print(f"{nevra(pkg).ljust(width)}  {int(pkg.get('size') or 0):>10,}  {pkg.get('sourcerpm', '-')}")

    sources = sorted({p.get("sourcerpm", "-") for p in packages})
    print(f"\ndistinct source RPMs : {len(sources)}")
    licenses = sorted({str(p.get("license", "-")) for p in packages})
    print(f"distinct licences    : {len(licenses)}")
    for lic in licenses:
        print(f"  {lic}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
