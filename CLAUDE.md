# CLAUDE.md

This file provides guidance to coding agents working in this repository.

## Project overview

This repository dissects Red Hat's official `ubi9-micro` image and rebuilds an
equivalent image from scratch. It is an investigation, not a product. Its
output is an explanation supported by reproducible evidence.

Preserve these non-negotiable properties:

- every finding is reproduced by a command recorded in `docs/METHOD.md` before
  it is written down as a finding;
- the official image is referenced by digest, never by a floating tag, in any
  command whose result is recorded;
- the reconstruction contains no package manager, matching the property that
  defines UBI Micro;
- differences between the reconstruction and the official image are explained,
  never hidden, normalised away, or excluded from comparison to make a result
  look cleaner;
- Red Hat content is downloaded from Red Hat, not vendored into this
  repository;
- documentation does not claim equivalence, supportability, or security
  parity with the official image without matching evidence.

## Development and verification

Use Podman for the primary workflow. Prefer `skopeo` and OCI layout tools over
runtime-specific inspection, so that results describe the image rather than
one runtime's view of it.

Dissection work must distinguish three kinds of statement, and the docs must
keep them distinct:

- what was observed directly in the image;
- what was inferred from RPM metadata or Red Hat's published build inputs;
- what remains unexplained.

An unexplained difference is a legitimate result. Record it as one rather than
speculating in the findings.

Working output — extracted root filesystems, layer tarballs, image manifests,
and scan results — is regenerable and must not be committed. Commit the
scripts that produce it and the analysis that interprets it.

## Documentation conventions

Findings carry their evidence: the image digest, the tool and version, the
command, and the relevant output. A finding without a reproducer is a note,
and belongs in the roadmap rather than in `docs/FINDINGS.md`.

Keep the dissection and the reconstruction separately reviewable. A change to
the reconstruction must not silently change what the dissection reported.

## Git conventions

Keep changes small and reviewable. Start work from current `main`, and do not
force-push.

Use concise Conventional Commit subjects such as `feat:`, `fix:`, `docs:`,
`test:`, `ci:`, `build:`, `refactor:`, and `chore:`.

Do not add `Co-Authored-By`, AI, assistant, or tool-attribution trailers to
commit messages. Commits are the human-reviewed record of intent; tool
attribution belongs in tool logs.
