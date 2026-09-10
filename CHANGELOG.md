# Changelog

All notable changes to this project are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

Releases are tutorials. Each one is a self-contained lesson that builds, runs,
verifies and scans a real container, with every command and output executed
rather than predicted.

## [Unreleased]

Next: **v0.2.0 — L1**, leaving `scratch` and linking dynamically against the
reconstructed base, and measuring what that costs. See
[docs/ROADMAP.md](docs/ROADMAP.md).

## [0.1.0] — 2026-09-10

First release. Establishes the method, reproduces Red Hat's `ubi9-micro`
exactly, and opens the tutorial ladder with three lessons at its floor.

### Phase 1 — dissecting and reproducing `ubi9-micro`

- Pinned the subject at
  `sha256:f332c99eb8f798a8486821c91937f10ad64ee83d7e739303be2df051040918f6`
  and verified every blob by recomputing SHA-256 rather than trusting the
  registry's advertised digest.
- Recovered the complete file inventory — 877 entries — by reading tar headers
  rather than extracting, so the record describes the image rather than what a
  filesystem preserved.
- Recovered the installed package set from the rpm database the image ships
  despite having no package manager able to read it: 20 packages, 2 GPG keys,
  17 source RPMs.
- **Recovered the literal build commands** from the dnf history database the
  image carries. Only three packages were ever named; the other seventeen came
  from the dependency resolver.
- Attributed every file to an owning package, resolving declared paths through
  the image's own `/usr`-merge symlinks, and established the 8,498,676 bytes
  Red Hat trims after installing.
- **Rebuilt the image and verified it**: 23,585,791 bytes against the official
  23,591,424, with **zero unexplained differences**. The only content absent is
  3,346 bytes of Red Hat build metadata the rebuild deliberately declines to
  copy.

### Phase 2 — the tutorial ladder, L0

- **L0.0 describe** — a statically linked C++ binary alone on `scratch` that
  reports the environment it runs in. Teaches what an empty image means, and
  that `podman exec` works only for binaries the image contains.
- **L0.1 SHA-256** — the same floor doing real work, verified against the
  FIPS 180-4 vectors and cross-checked against an independent `sha256sum`.
  939,069 bytes in one file, 4.0% of the official image.
- **L0.2 authority** — answers the objection to the whole exercise: if it is
  just a static binary, why containerise it? Measures what the kernel permits
  the same binary contained and uncontained, and shows the process from the
  host with an empty capability bounding set.

### Tooling

- `scripts/fetch_image.py` — acquire and verify an image over the OCI
  distribution API, with no container runtime and no Linux required.
- `scripts/inventory.py` — full file inventory from tar headers.
- `scripts/rpmdb.py` — decode the RPM database the image carries.
- `scripts/attribute.py` — map every file to its owning package.
- `scripts/transaction.py` — recover the build commands.
- `scripts/closure.py` — compute what a binary actually needs, by reading ELF
  headers. Running `bash` needs 4 files and 5,072,312 bytes, 22% of the image.
- `scripts/compare.py` — diff a rebuild against the official image and
  disposition every difference.
- `scripts/verify_image.py` — assert image properties by inspecting an exported
  filesystem, so it works on images with no shell.
- `scripts/security_scan.sh` — SBOM and vulnerability scan, run identically in
  CI and on a workstation.

### Documentation

- `docs/JOURNEY.md` — the narrative, including the wrong turns.
- `docs/REFERENCE.md` — every layer, label, package and byte, in tables.
- `docs/COMPONENTS.md` — what each of the 20 packages is, why it is there,
  runtime linkage versus RPM dependency, and what it costs.
- `docs/FINDINGS.md` — numbered findings, each with a reproducer.
- `docs/COMPARISON.md` — the rebuild measured against the original.
- `docs/METHOD.md`, `docs/ROADMAP.md`, `docs/BADGING.md`.

### Continuous integration

- Every image builds, runs, is functionally verified, has its filesystem
  inspected, and is scanned for vulnerabilities on every push.
- The reconstruction is compared against the official image path by path, and
  the build fails if a difference appears that no finding explains.

### Findings worth knowing

- **UBI Micro ships a shell.** `Cmd` resolves through `/bin/sh` to a real
  1.39 MB `bash`. The common "no shell" claim is wrong; it is the package
  manager that is absent.
- **31.4% of the image is its rpm database**, which nothing in the image can
  read — but vulnerability scanners can, which is why it is kept.
- **`tzdata` is registered but its data is gone.** Scanners report it present;
  `/usr/share/zoneinfo` is absent and there is no `/etc/localtime`.
- **`--nodocs` explains only a quarter of what Red Hat removes.** Locale
  catalogues go via the RPM install-language filter, and zoneinfo via a
  cleanup no recorded command explains.
- **A `scratch` image is not empty at runtime.** The container runtime injects
  `/etc/passwd` for a declared `USER` and mounts a tmpfs on `/tmp`.
- **Zero vulnerabilities is not a clean bill of health.** An image with no
  package database gives a package-based scanner nothing to read.

[Unreleased]: https://github.com/datopsis/ubi9-from-scratch/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/datopsis/ubi9-from-scratch/releases/tag/v0.1.0
