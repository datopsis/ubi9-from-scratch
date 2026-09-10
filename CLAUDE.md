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

## Demonstrations

Every demonstration in this repository ships complete build and run
instructions. Complete means a reader with none of this context can go from a
clean checkout to a running result without inferring a step. Each demo's
`README.md` states, in this order:

- what the demo shows, and what it deliberately does not;
- prerequisites, with the versions the instructions were exercised against;
- the exact build command, copy-pasteable, with no placeholder the reader must
  silently resolve;
- the exact run command;
- the expected output, quoted, so a reader knows whether it worked;
- how to verify the claim the demo makes — a size figure, a linkage check, a
  crypto self-test — rather than trusting that it ran;
- how to remove what the demo created.

Mark every command that has not actually been executed. An instruction written
from analysis but never run is labelled `UNVERIFIED` at the top of its README
and in the block itself, and the label is removed in the same change that
records the run and its real output. Do not document an untested command as
working, and do not paste expected output that was written rather than
observed.

When a demo reports a size, state which size: compressed layer, uncompressed
layer, or apparent file bytes. A number without its measure is not a result.

## Explaining what is in an image

Every image this repository builds ships an explanation of its contents, and
every application it carries ships an explanation of what it does. A reader
must be able to answer, for any component present, three questions: what is
this, why is it here, and what breaks without it.

For each component, record:

- what it is, in one sentence, without assuming the reader knows the package;
- why it is present — named deliberately, or pulled in to satisfy a dependency;
- what needs it, distinguishing **runtime linkage** observed in ELF headers
  from an **RPM dependency**, because a package can be installed without
  anything ever loading it;
- what it costs, in bytes actually shipped rather than bytes declared.

Where runtime linkage and RPM dependency disagree, say so and mark the
component a trim candidate. Do not remove it on that basis alone: static
analysis cannot see `dlopen` targets, NSS modules, certificates or
configuration, so a trim is confirmed by a runtime trace, never by a closure.

`docs/COMPONENTS.md` is the worked example of this standard.

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
