#!/usr/bin/env python3
"""Extract /etc/yum.repos.d/ubi.repo from the official image layer.

The repo file is not installed by any package — the official Containerfile
copies it in — so a reconstruction has to obtain it. It is extracted from the
official image rather than committed to this repository, because Red Hat
content is downloaded from Red Hat.

Run scripts/fetch_image.py first so work/layer-0.tar exists.

Requires only the standard library.
"""

from __future__ import annotations

import argparse
import hashlib
import tarfile
from pathlib import Path

SOURCE = "etc/yum.repos.d/ubi.repo"

# Observed in the pinned subject. A change here means the reconstruction would
# be built against a different repository set than the one that was dissected.
EXPECTED_SIZE = 2474


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layer", type=Path, default=Path("work/layer-0.tar"))
    parser.add_argument("--out", type=Path, default=Path("reconstruction/ubi.repo"))
    args = parser.parse_args()

    if not args.layer.exists():
        raise SystemExit(f"{args.layer} not found — run scripts/fetch_image.py first")

    with tarfile.open(args.layer, "r:") as tar:
        members = {m.name.lstrip("./"): m for m in tar.getmembers()}
        member = members.get(SOURCE)
        if member is None:
            raise SystemExit(f"{SOURCE} is not present in {args.layer}")
        data = tar.extractfile(member).read()

    if len(data) != EXPECTED_SIZE:
        print(f"WARNING: {SOURCE} is {len(data)} B, expected {EXPECTED_SIZE} B")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(data)
    print(f"wrote {args.out}  ({len(data)} B)")
    print(f"sha256:{hashlib.sha256(data).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
