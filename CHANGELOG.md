# Changelog

All notable changes to this project are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

Releases are tutorials. Each one is a self-contained lesson that builds, runs,
verifies and scans a real container, with every command and output executed
rather than predicted.

## [Unreleased]

Next: **v0.4.0 — L2 (OpenSSL TLS)** and **M1**, the tutorial on how containers
are normally built, measured so every later number has a baseline. See
[docs/ROADMAP.md](docs/ROADMAP.md).

## [0.3.0] — 2026-09-10

**Part 0 — the toolkit.** Seven tutorials introducing every tool the series
uses, so the earlier assumption that a reader already had Podman and knew what
it was doing is now paid for rather than made.

### Added

- **[T1 — Your development environment](tools/t1-dev-environment/README.md)** —
  clean machine to working setup. Covers the `subuid`/`subgid` allocation that
  is what usually breaks a rootless install, and the two things that bite on
  WSL2 specifically.
- **[T2 — Podman](tools/t2-podman/README.md)** — daemonless and rootless
  explained, and what every flag in this project's `podman run` lines is for.
- **[T3 — Skopeo](tools/t3-skopeo/README.md)** — asking a registry a question
  without pulling anything, and resolving a tag to a digest. Independently
  confirms the digest Phase 1 pinned.
- **[T4 — Buildah](tools/t4-buildah/README.md)** — building an image with no
  Containerfile. **Explains what `unshare` and `mount` mean** rather than
  assuming them, shows `mount` returning nothing outside a user namespace, and
  builds a 30 KB image from `scratch` using only host tools.
- **[T5 — Umoci](tools/t5-umoci/README.md)** — opening an OCI layout, the
  runtime bundle it produces, and the `--layout` versus `--image` flag trap.
- **[T6 — Syft](tools/t6-syft/README.md)** — what an SBOM is, where the answer
  comes from, and why a `scratch` image yields `No packages discovered`.
- **[T7 — Grype](tools/t7-grype/README.md)** — reading a scan honestly:
  severity is not risk, row counts overstate, and two scanners will disagree.
- CI verifies every install command. The `apt` commands run on the runner; the
  `dnf` commands run inside a `ubi9` container, so neither set is transcribed
  from documentation.
- `scripts/toolkit_demo.sh` — exercises every tool against a real image on
  every push, so the tutorials cannot drift from what the tools actually do.

### Corrected

- An earlier claim implied buildah was uniquely able to mount a container's
  filesystem. `podman unshare` and `podman mount` do the same job; the
  difference is ergonomics, not capability, and T4 says so with a comparison.

## [0.2.0] — 2026-09-10

Adds the anatomy lesson the series was missing, the first rung above the floor,
and the method track that ties the whole series together.

### Added

- **L0.0 anatomy** — takes a container image apart by hand. The docker-archive
  layout, the OCI layout, and content addressing verified rather than believed:
  every blob is named by its own sha256, and the tutorial checks it. Its
  payload is C rather than C++ so the archive holds exactly one file and the
  visible cost is glibc rather than the program. 798,905 bytes.
- **L1 dynamic** — the same SHA-256 program linked against the base image's
  glibc instead of carrying a copy. **The binary gets 4.9× smaller (939,069 →
  192,632 bytes) and the image gets 25× larger (939,069 → 23,788,574).**
- `docs/METHODOLOGY.md` — the destination the tutorials build toward: a flow
  diagram and checklist for assembling a container from scratch, what static
  analysis cannot see, the functional and security differences between the two
  ways people build containers, and an honest account of the disadvantages.
- `docs/ROADMAP.md` expanded with a toolkit series (podman, skopeo, buildah,
  umoci, syft, grype), replication of `ubi9-minimal` and `ubi9`, a method track,
  and a shortlist of further tooling with the reason each earns a place.

### Changed

- The L0 rungs are renumbered to make room for the anatomy lesson: describe is
  now L0.1, SHA-256 is L0.2, authority is L0.3.
- Both L0 images declare `USER 1000:1000` rather than defaulting to uid 0.

### Findings

- **A `scratch` image is not empty at runtime.** Under full confinement three
  probes still succeeded: the runtime injects `/etc/passwd` for a declared
  `USER` and mounts a tmpfs on `/tmp`, so `--read-only` gives a process *more*
  reachable filesystem, not less. An image and a container are different
  things.
- **`ubi9-micro` ships glibc but not libstdc++.** A plain dynamic C++ build
  compiles and then fails at startup. `-static-libstdc++ -static-libgcc`
  targets a minimal base without adding a package to it.
- **Going dynamic did not introduce 23 vulnerabilities — it made them
  visible.** The same glibc flaws were compiled into the static binary where no
  scanner could report them.

### Corrected

- `podman unshare` and `podman mount` do the same job as their buildah
  equivalents. An earlier claim implied buildah was uniquely capable of
  mounting a container's filesystem; the difference is ergonomics, not
  capability, and both terms are now explained rather than assumed.

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

[Unreleased]: https://github.com/datopsis/ubi9-from-scratch/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/datopsis/ubi9-from-scratch/releases/tag/v0.3.0
[0.2.0]: https://github.com/datopsis/ubi9-from-scratch/releases/tag/v0.2.0
[0.1.0]: https://github.com/datopsis/ubi9-from-scratch/releases/tag/v0.1.0
