# UBI 9 Micro from scratch

[![License](https://img.shields.io/github/license/datopsis/ubi9-from-scratch)](LICENSE)
[![Base: Red Hat UBI 9](https://img.shields.io/badge/base-Red%20Hat%20UBI%209-EE0000?logo=redhat&logoColor=white)](https://developers.redhat.com/products/rhel/ubi)
[![Subject: ubi9-micro](https://img.shields.io/badge/subject-ubi9--micro-EE0000?logo=redhat&logoColor=white)](docs/METHOD.md)
[![Status: investigation](https://img.shields.io/badge/status-investigation-F2994A)](docs/ROADMAP.md)
[![Badge policy](https://img.shields.io/badge/badges-policy-2F80ED)](docs/BADGING.md)

`ubi9-from-scratch` takes Red Hat's official `ubi9-micro` image apart
and rebuilds an equivalent image from first principles. The goal is a
documented, reproducible answer to a question the published Containerfile
does not fully explain: what is actually inside UBI Micro, how did it get
there, and what does a from-scratch reconstruction have to do to match it.

> [!IMPORTANT]
> This repository is at the investigation stage. The dissection through package
> attribution is complete and reproducible; no reconstruction has been built
> yet, and no claim of equivalence with the official image has been tested.

Start with **[the journey](docs/JOURNEY.md)** for the narrative walkthrough, or
**[findings](docs/FINDINGS.md)** for the evidence-backed results.

## What the dissection found so far

The subject is pinned at `sha256:f332c99e…` (RHEL 9.8, built 2026-08-26):
**23,591,424 bytes uncompressed** from a 7,253,582-byte download, in a single
squashed layer of 877 entries.

Its Containerfile contains no `RUN` instruction at all — the entire root
filesystem arrives as a pre-built directory, so the build that matters happens
somewhere the image does not describe. The image ships **no setuid, setgid or
file-capability entries**, and it does ship a shell: `Cmd` resolves through
`/bin/sh` to a real `bash` binary, so the common "UBI Micro has no shell" claim
is wrong — it is the package manager that is absent.

It also ships its own rpm database, 31.4% of the uncompressed image, which
names the twenty packages the reconstruction has to install.

## Why UBI Micro is interesting

UBI Micro is not built the way an ordinary application image is built. It has
no package manager of its own, so it cannot install anything into itself. The
image is instead assembled from the outside: a separate build container
installs a minimal package set into a directory with `--installroot`, and that
directory becomes the filesystem of an image whose base is `scratch`.

That inversion is what makes the image worth dissecting. Every file in the
result was placed by a package transaction that happened somewhere else, which
means the image content can be traced back to specific RPMs, and a
reconstruction can be checked file by file rather than judged by whether it
happens to run.

## Scope

The investigation is organized in two halves.

Dissection asks what the official image is:

- the layer, config, and manifest structure of the published image;
- the complete file inventory of its root filesystem;
- the RPM set that accounts for that inventory, and the files it does not;
- the users, groups, permissions, capabilities, and metadata carried in the
  image;
- the release metadata, licences, and content manifests Red Hat ships inside
  it.

Reconstruction asks what it takes to produce the same thing:

- a build that installs the identified package set into an `--installroot`;
- an image assembled from that root filesystem with no package manager in the
  result;
- a documented comparison of the reconstruction against the official image;
- an explanation of each remaining difference, including the ones that cannot
  be removed.

## Non-goals

This project does not attempt to redistribute Red Hat content, to present its
output as a supported UBI image, or to claim that a reconstruction is a
drop-in replacement for the official one. It is a study, and its value is the
explanation rather than the artifact.

## Requirements

The workflow targets Podman on Linux, and expects `skopeo` and `umoci` or an
equivalent OCI layout tool for the dissection half. Exact versions will be
pinned in `docs/METHOD.md` as the commands land.

## Repository layout

| Path | Contents |
| --- | --- |
| `docs/JOURNEY.md` | Narrative walkthrough: official image to rebuild. |
| `docs/METHOD.md` | How the dissection is performed, command by command. |
| `docs/FINDINGS.md` | What the dissection showed, with evidence. |
| `docs/RECONSTRUCTION.md` | How the from-scratch build is assembled. |
| `docs/COMPARISON.md` | Reconstruction measured against the official image. |
| `docs/ROADMAP.md` | Ordered work packages. |
| `docs/BADGING.md` | Badge inventory and policy. |
| `scripts/` | Reproducible dissection and comparison tooling. |

## Licence

The tooling and documentation in this repository are licensed under
Apache-2.0; see [LICENSE](LICENSE). Red Hat UBI content referenced or
downloaded by these scripts remains subject to Red Hat's own terms, and none
of it is redistributed here. This project is not affiliated with or endorsed
by Red Hat.
