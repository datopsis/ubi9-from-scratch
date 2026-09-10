# Reconstruction — WP6

> [!NOTE]
> **Verified.** Every command on this page has been executed in CI on
> `ubuntu-latest` with Podman 5.x. The outputs below are observed, not
> predicted. Run 34439224680 is the record.
>
> **Result: 23,613,441 bytes against the official 23,591,424 — a delta of
> 22,017 bytes, 0.09%.**

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
| A Linux container runtime | The build runs a package transaction; it cannot be done on Windows or macOS natively | ubuntu-latest (GitHub runner) |
| Podman ≥ 4.0 or Docker ≥ 20.10 | `--squash-all` / multi-stage build support | Podman 5.x |
| Network access to Red Hat CDNs | `registry.access.redhat.com`, `cdn-ubi.redhat.com` | verified |
| Python 3.9+ | Extracting the repo file from the official layer | 3.12.14 |
| ~2 GB free disk | Builder image plus the installroot | verified |

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

**Step 3 — build.**

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

```sh
podman run --rm ubi9-from-scratch:wp6 /bin/sh -c 'echo hello from the rebuild'
```

Output:

```
hello from the rebuild
```

The shell is present. F13 established that `bash` is a *dependency*, not a
named package, so this build never asks for it — the resolver supplies it,
exactly as it does for the official image.

## Verify

A build that runs is not a result. These checks are the actual deliverable.

**Size.** Compare uncompressed layer bytes, the figure the dissection recorded
(23,591,424 B for the official image).

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

## Result

| Measure | Bytes |
| --- | ---: |
| This reconstruction | 23,613,441 |
| Official `ubi9-micro` | 23,591,424 |
| **Delta** | **+22,017 (0.09%)** |

Verified in the same run: exactly one layer; no `rpm`, `dnf`, `microdnf` or
`yum`; no setuid or setgid entries anywhere in the filesystem.

The build resolved to the **same package versions as the official image** —
`glibc-2.34-275.el9_8`, `tzdata-2026c-1.el9_8`, `redhat-release-9.8-1.0.el9`
and the rest. That answers a question this page previously listed as assumed:
the public UBI mirrors do carry the same RPM builds as the internal content
set the official image was built from.

It also settles I3. Had the install-language filter not applied to an
installroot transaction, the `.mo` catalogues would have been installed and
this image would be roughly 4.7 MB heavier. It is not, so naming
`glibc-minimal-langpack` is sufficient and no locale deletion step is needed.

## Known differences

These cannot be eliminated and are not defects:

| Difference | Magnitude | Cause |
| --- | ---: | --- |
| rpmdb **content** | ~7,400,000 B of non-identical bytes | sqlite page layout and transaction IDs differ per run. Note this affects byte-identity, not size — both images carry an rpmdb of comparable size, which is why the totals land within 0.09%. |
| Build identity | — | `build-date`, `vcs-ref`, `release` name Red Hat's build system |
| Labels | — | Deliberately not copied. Reproducing `maintainer` and `vendor` on a rebuild would misrepresent its origin. |

## Known unknowns

One remains. **The cleanup step** (I4/U3): `rm -rf /usr/share/zoneinfo
/var/cache/*` reproduces what is absent from the official image, but the
actual cleanup Red Hat ran is recorded nowhere, so it may have removed more.
The 22,017-byte delta is small enough that any additional removal must also be
small — but "small" is not "none", and WP7 will locate it by diffing the file
inventories rather than the totals.

Locale exclusion (I3) was previously listed here and is now resolved — see
[Result](#result).

## Clean up

```sh
podman rmi ubi9-from-scratch:wp6
rm -f reconstruction/ubi.repo
rm -rf work/
```
