#!/usr/bin/env python3
"""Compare a reconstruction against the official image, path by path.

WP7. The totals landing close together is not evidence that the contents
match — WP4 already showed two large errors cancelling almost exactly. This
compares the file inventories directly and dispositions every difference.

Dispositions, following docs/COMPARISON.md:

  resolved  — the two agree
  accepted  — differs for a known structural reason, quantified here
  open      — not understood, and reported as such

Produce the candidate with:

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

# Paths the container runtime injects into an exported filesystem. They are
# not part of the image and are excluded from both sides rather than being
# reported as differences.
RUNTIME_INJECTED = (
    "/etc/hostname",
    "/etc/hosts",
    "/etc/resolv.conf",
    "/.dockerenv",
    "/run/.containerenv",
)

# Content known to differ for reasons established during the dissection.
# Each entry carries the finding that explains it.
ACCEPTED_PREFIXES = (
    ("/var/lib/rpm/", "F7/WP6: rpmdb bytes differ per transaction; size is comparable"),
    ("/var/lib/dnf/", "F7: dnf history records this build, not Red Hat's"),
    ("/var/log/hawkey.log", "build log of this transaction"),
    ("/usr/share/buildinfo/", "F11: Red Hat build metadata, deliberately not reproduced"),
    ("/root/buildinfo/", "F11: Red Hat build metadata, deliberately not reproduced"),
    ("/var/lib/rhsm/", "subscription state written by the transaction"),
)


def read_tar_inventory(path: Path) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    with tarfile.open(path, "r:") as tar:
        for member in tar:
            key = "/" + member.name.lstrip("./").lstrip("/")
            out[key] = {
                "path": key,
                "type": (
                    "dir" if member.isdir()
                    else "symlink" if member.issym()
                    else "hardlink" if member.islnk()
                    else "file" if member.isfile()
                    else "other"
                ),
                "mode": f"{member.mode:04o}",
                "size": member.size,
                "uid": member.uid,
                "gid": member.gid,
                "link": member.linkname,
            }
    return out


def accepted_reason(path: str) -> str | None:
    for prefix, reason in ACCEPTED_PREFIXES:
        if path == prefix or path.startswith(prefix):
            return reason
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("candidate", type=Path, help="rootfs tar from podman export")
    parser.add_argument("--official", type=Path, default=Path("work/inventory.json"))
    parser.add_argument("--json", type=Path)
    parser.add_argument("--fail-on-open", action="store_true", help="exit non-zero if any difference is unexplained")
    args = parser.parse_args()

    official = {row["path"]: row for row in json.loads(args.official.read_text())}
    candidate = read_tar_inventory(args.candidate)

    for noise in RUNTIME_INJECTED:
        official.pop(noise, None)
        candidate.pop(noise, None)

    only_official = sorted(set(official) - set(candidate))
    only_candidate = sorted(set(candidate) - set(official))
    shared = sorted(set(official) & set(candidate))

    open_items: list[tuple[str, str]] = []
    accepted: list[tuple[str, str]] = []

    for path in only_official:
        reason = accepted_reason(path)
        (accepted if reason else open_items).append(
            (path, reason or f"missing from reconstruction ({official[path]['type']}, {official[path]['size']:,} B)")
        )
    for path in only_candidate:
        reason = accepted_reason(path)
        (accepted if reason else open_items).append(
            (path, reason or f"extra in reconstruction ({candidate[path]['type']}, {candidate[path]['size']:,} B)")
        )

    # Metadata differences on paths present in both.
    mode_diff, size_diff, owner_diff = [], [], []
    for path in shared:
        a, b = official[path], candidate[path]
        if a["mode"] != b["mode"]:
            mode_diff.append((path, a["mode"], b["mode"]))
        if a["type"] == "file" and a["size"] != b["size"] and accepted_reason(path) is None:
            size_diff.append((path, a["size"], b["size"]))
        if (a["uid"], a["gid"]) != (b["uid"], b["gid"]):
            owner_diff.append((path, f"{a['uid']}:{a['gid']}", f"{b['uid']}:{b['gid']}"))

    print(f"official    : {len(official):,} entries")
    print(f"candidate   : {len(candidate):,} entries")
    print(f"in both     : {len(shared):,}")
    print(f"only official: {len(only_official)}")
    print(f"only candidate: {len(only_candidate)}\n")

    if accepted:
        print(f"ACCEPTED ({len(accepted)}) — differ for reasons the dissection established:")
        shown: set[str] = set()
        for path, reason in accepted:
            if reason not in shown:
                count = sum(1 for _, r in accepted if r == reason)
                print(f"  [{count:>3}] {reason}")
                shown.add(reason)

    if open_items:
        print(f"\nOPEN ({len(open_items)}) — not explained:")
        for path, reason in open_items:
            print(f"  {path}  — {reason}")

    if mode_diff:
        print(f"\nMODE DIFFERENCES ({len(mode_diff)}):")
        for path, a, b in mode_diff[:40]:
            print(f"  {path}  official={a} candidate={b}")

    if owner_diff:
        print(f"\nOWNERSHIP DIFFERENCES ({len(owner_diff)}):")
        for path, a, b in owner_diff[:40]:
            print(f"  {path}  official={a} candidate={b}")

    if size_diff:
        print(f"\nSIZE DIFFERENCES ({len(size_diff)}), largest first:")
        for path, a, b in sorted(size_diff, key=lambda r: -abs(r[1] - r[2]))[:25]:
            print(f"  {path}  official={a:,} candidate={b:,} delta={b - a:+,}")

    total_official = sum(r["size"] for r in official.values())
    total_candidate = sum(r["size"] for r in candidate.values())
    print(f"\napparent bytes: official {total_official:,}  candidate {total_candidate:,}  delta {total_candidate - total_official:+,}")

    if args.json:
        args.json.write_text(
            json.dumps(
                {
                    "counts": {
                        "official": len(official),
                        "candidate": len(candidate),
                        "shared": len(shared),
                    },
                    "open": [{"path": p, "reason": r} for p, r in open_items],
                    "accepted": len(accepted),
                    "mode_differences": [{"path": p, "official": a, "candidate": b} for p, a, b in mode_diff],
                    "owner_differences": [{"path": p, "official": a, "candidate": b} for p, a, b in owner_diff],
                    "size_differences": [{"path": p, "official": a, "candidate": b} for p, a, b in size_diff],
                    "apparent_bytes": {"official": total_official, "candidate": total_candidate},
                },
                indent=1,
            )
            + "\n"
        )
        print(f"wrote {args.json}")

    if open_items and args.fail_on_open:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
