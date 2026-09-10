# Method

How the dissection is performed. Every finding in `docs/FINDINGS.md` is
reproducible from the commands here. `docs/JOURNEY.md` narrates why the method
took this shape.

## Tools

The dissection deliberately requires no container runtime and no Linux. It uses
the Python 3 standard library only, and talks to the registry over HTTPS. This
keeps the method portable and, more importantly, keeps runtime behaviour out of
results that are supposed to describe the image itself.

Recorded with Python 3.12.10 on Windows 11. The reconstruction (WP6) will need
a Linux container runtime; the dissection does not.

## Pinning the subject

All recorded work refers to one digest-pinned reference. To discover the digest
a tag currently points at, without recording anything against the tag:

```
python scripts/fetch_image.py --ref latest --resolve-only
```

The pinned subject of this study is set as `PINNED_INDEX` in
`scripts/fetch_image.py`. Changing it starts a new study; it is not a routine
update.

## Stage 1 — Acquire (WP1)

```
python scripts/fetch_image.py
```

Fetches the manifest list, the per-architecture manifest, the config blob and
every layer into `work/`, verifying each object by recomputing SHA-256 over the
retrieved bytes. The registry's `Docker-Content-Digest` header is cross-checked
but never trusted alone. A mismatch is fatal rather than a warning.

Writes `work/subject.json` recording exactly what was acquired.

## Stage 2 — Structure (WP2)

The config and manifest are plain JSON in `work/`. The history is the
informative part:

```
python -c "import json;print(json.dumps(json.load(open('work/config.json'))['history'],indent=2))"
```

## Stage 3 — Inventory (WP3)

```
python scripts/inventory.py
```

Decompresses the layer, verifies the resulting `diff_id` against the config's
`rootfs.diff_ids`, and records every tar member — path, type, mode, uid, gid,
uname, gname, size, mtime, link target and extended attributes — to
`work/inventory.json`.

Metadata is read from tar headers rather than by extracting to a filesystem.
An extracted tree reports what the extracting filesystem preserved, which on
Windows or as a non-root user is materially less than the image declares.

## Stage 4 — Package attribution (WP4)

```
python scripts/rpmdb.py
```

Extracts `/var/lib/rpm/rpmdb.sqlite` from the layer and decodes the RPM header
blob of every row in `Packages`, giving the installed set with NEVRA, declared
unpacked size, licence and source RPM.

Note that the sqlite backend stores each header without the 8-byte lead magic
that prefixes a header on disk, so the blob opens directly on the index count
and data-store size. The parser validates that
`8 + count * 16 + data_size == len(blob)` and refuses anything else.

Still outstanding at this stage: mapping individual files to owning packages
via the `Basenames` table, and separating explicitly named packages from
resolver-pulled dependencies via `Requirename` and `Providename`.

## Stages 5-7

Reconstruction and comparison are not yet implemented. See `docs/ROADMAP.md`.

## Reproducibility notes

Record the tool versions used for each stage alongside its output. Extraction
and comparison results depend on the tool as much as on the image, and a result
without its tool version cannot be re-checked later.

`work/` is regenerable and is not committed. Everything in it can be rebuilt
from the pinned digest in seconds.
