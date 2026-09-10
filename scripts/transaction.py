#!/usr/bin/env python3
"""Recover the package transaction that built the image.

Closes U1. The rpmdb records what ended up installed; the dnf history database
records how it got there — the command line of each transaction, the repository
it drew from, and whether each package was named by the operator or pulled in
by the dependency resolver.

That distinction decides the reconstruction. Naming every installed package
would freeze versions Red Hat left to resolution, producing an image that looks
identical today and diverges at the next rebuild.

The history database ships with a populated write-ahead log, so the WAL and
shared-memory files are extracted alongside it and the connection is opened
read-write to let sqlite replay them. Opening the main database alone reports
an incomplete transaction record.

Requires only the standard library.
"""

from __future__ import annotations

import argparse
import sqlite3
import tarfile
import tempfile
from pathlib import Path

# libdnf transaction enums, from libdnf/transaction/Types.hpp
REASONS = {
    0: "unknown",
    1: "dependency",
    2: "user",
    3: "clean",
    4: "weak-dependency",
    5: "group",
}

ACTIONS = {
    1: "install",
    2: "downgrade",
    3: "obsolete",
    4: "upgrade",
    5: "remove",
    6: "reinstall",
    7: "reason-change",
}

DB_FILES = (
    "var/lib/dnf/history.sqlite",
    "var/lib/dnf/history.sqlite-wal",
    "var/lib/dnf/history.sqlite-shm",
)


def extract_history(layer: Path, into: Path) -> Path:
    with tarfile.open(layer, "r:") as tar:
        members = {m.name.lstrip("./"): m for m in tar.getmembers()}
        for name in DB_FILES:
            member = members.get(name)
            if member is not None and member.isfile():
                (into / Path(name).name).write_bytes(tar.extractfile(member).read())
    return into / "history.sqlite"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=Path("work"))
    parser.add_argument("--layer", type=int, default=0)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        database = extract_history(args.work / f"layer-{args.layer}.tar", Path(tmp))
        # Read-write so sqlite replays the shipped WAL before we query.
        connection = sqlite3.connect(database)

        repos = dict(connection.execute("SELECT id, repoid FROM repo"))
        transactions = list(
            connection.execute(
                "SELECT id, releasever, cmdline, state FROM trans ORDER BY id"
            )
        )
        items = list(
            connection.execute(
                """SELECT ti.trans_id, r.name, r.version, r.release, r.arch,
                          ti.action, ti.reason, ti.repo_id
                   FROM trans_item ti JOIN rpm r ON r.item_id = ti.item_id
                   ORDER BY ti.trans_id, ti.reason DESC, r.name"""
            )
        )
        connection.close()

    print(f"repositories: {', '.join(sorted(repos.values()))}\n")

    for trans_id, releasever, cmdline, state in transactions:
        print(f"=== transaction {trans_id} (releasever {releasever}, state {state}) ===")
        print(f"  microdnf {cmdline}\n")

    named, pulled = [], []
    for trans_id, name, version, release, arch, action, reason, repo_id in items:
        nevra = f"{name}-{version}-{release}.{arch}"
        entry = (trans_id, nevra, ACTIONS.get(action, action), repos.get(repo_id, "?"))
        (named if REASONS.get(reason) == "user" else pulled).append(entry)

    print(f"named on the command line ({len(named)}):")
    for trans_id, nevra, action, repo in named:
        print(f"  [trans {trans_id}] {action:<8} {nevra}")

    print(f"\npulled in by the resolver ({len(pulled)}):")
    for trans_id, nevra, action, repo in pulled:
        print(f"  [trans {trans_id}] {action:<8} {nevra}")

    print(
        f"\n{len(named)} named, {len(pulled)} resolved, {len(named) + len(pulled)} installed total"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
