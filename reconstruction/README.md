# Reconstruction — WP6

> [!WARNING]
> **UNVERIFIED.** Every command on this page was derived from the dissection
> and has **not been executed**. No build has been run, no size has been
> measured, and the expected outputs below are stated as predictions, not
> observations. This banner and every `UNVERIFIED` marker are removed in the
> same change that records a real run and its actual output.

## What this shows

Rebuilding `ubi9/ubi-micro` from first principles, using the package
transaction recovered from the official image itself rather than a guess at
what Red Hat did.

**What it does not show.** This is not a Red Hat product, is not supported, and
is not claimed to be equivalent to the official image. It reproduces the build
*process*; WP7 measures how close the *result* gets. A byte-identical rebuild
is known to be impossible — see [Known differences](#known-differences).

## Prerequisites

| Requirement | Why | Exercised against |
| --- | --- | --- |
| A Linux container runtime | The build runs a package transaction; it cannot be done on Windows or macOS natively | *not yet run* |
| Podman ≥ 4.0 or Docker ≥ 20.10 | `--squash` / multi-stage build support | *not yet run* |
| Network access to Red Hat CDNs | `registry.access.redhat.com`, `cdn-ubi.redhat.com` | *not yet run* |
| Python 3.9+ | Extracting the repo file from the official layer | 3.12.10 |
| ~2 GB free disk | Builder image plus the installroot | *not yet run* |

No Red Hat subscription is needed. The public UBI repositories are used.

## Build

All commands run from the repository root.

**Step 1 — fetch the official image.** The reconstruction needs one file from
it, and WP7 needs it for comparison.

```sh
python scripts/fetch_image.py
```

Expected: five `VERIFIED` lines and `wrote work/`.

**Step 2 — extract the repo definition.** `ubi.repo` is not installed by any
package, so it must come from the official image. It is deliberately not
committed to this repository.

```sh
python reconstruction/extract-repo-file.py
```

Expected:

```
wrote reconstruction/ubi.repo  (2474 B)
sha256:f59e1e4c2f20048ef3204f5c81d23b04aac53a7d789b1f4d055a937867109f13
```

That digest is from the pinned subject. A different one means the official
image changed and the study needs re-pinning.

**Step 3 — build.** `UNVERIFIED`

```sh
podman build \
  --squash-all \
  --file reconstruction/Containerfile \
  --tag ubi9-from-scratch:wp6 \
  reconstruction/
```

`--squash-all` is required: F1 established the official image is a single
layer, and a multi-layer rebuild is not comparable. Docker users substitute
`docker build --squash` (which needs experimental features enabled) or export
and re-import the filesystem.

## Run

`UNVERIFIED`

```sh
podman run --rm ubi9-from-scratch:wp6 /bin/sh -c 'echo hello from the rebuild'
```

Predicted output:

```
hello from the rebuild
```

This works only if the rebuild reproduced a shell. F13 established that `bash`
is a *dependency*, not a named package, so its presence is a consequence of
the resolver and not something this build requests. If the shell is absent,
that is a finding, not a bug in these instructions.

## Verify

A build that runs is not a result. These checks are the actual deliverable.

**Size.** `UNVERIFIED` — compare uncompressed layer bytes, which is the figure
the dissection recorded (23,591,424 B for the official image).

```sh
podman image inspect ubi9-from-scratch:wp6 --format '{{.Size}}'
```

**Layer count.** Must be 1.

```sh
podman image inspect ubi9-from-scratch:wp6 --format '{{len .RootFS.Layers}}'
```

**No package manager.** All four must be absent.

```sh
podman run --rm ubi9-from-scratch:wp6 /bin/sh -c \
  'for b in rpm dnf microdnf yum; do command -v $b && echo "FAIL: $b present"; done; echo checked'
```

**Full comparison.** WP7 is not implemented yet. When it is, it diffs the
rebuild against the official image across the dimensions of `docs/FINDINGS.md`
— inventory, permissions, package set, config — and dispositions every
difference.

## Known differences

These cannot be eliminated and are not defects:

| Difference | Magnitude | Cause |
| --- | ---: | --- |
| rpmdb bytes | ~7,400,000 | sqlite page layout and transaction IDs differ per run; VACUUM reclaims only 65,536 B, so the database is genuinely dense |
| Source repositories | — | The official build used `rhel-9-for-x86_64-baseos-rpms`, an internal content set. This build uses the public UBI mirrors. Whether they carry identical RPM builds is **assumed, not verified**. |
| Build identity | — | `build-date`, `vcs-ref`, `release` name Red Hat's build system |
| Labels | — | Deliberately not copied. Reproducing `maintainer` and `vendor` on a rebuild would misrepresent its origin. |

## Known unknowns

Two things in this build are reproductions of an observed end state rather than
recovered instructions, and WP7 will show whether they are right:

1. **The cleanup step** (I4/U3). `rm -rf /usr/share/zoneinfo /var/cache/*`
   reproduces what is absent from the official image. The actual cleanup Red
   Hat ran is not recorded anywhere in the image, so it may have removed more.
2. **Locale exclusion** (I3). The official image contains no `.mo` catalogues.
   This is believed to come from RPM's install-language filter rather than a
   deletion, and the builder image's own `%_install_langs` macro may or may not
   apply to a transaction targeting an installroot. If the rebuild comes out
   ~4.7 MB heavier than expected, this is the cause.

## Clean up

```sh
podman rmi ubi9-from-scratch:wp6
rm -f reconstruction/ubi.repo
rm -rf work/
```
