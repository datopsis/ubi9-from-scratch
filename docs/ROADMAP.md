# Roadmap

Ordered work packages. Each one lands with its documentation, and no package
records a finding it has not reproduced.

The project runs in two phases. **Phase 1 explains the official image.** Phase 2
uses that understanding to build something smaller for a real application.
Phase 2 does not begin until Phase 1 is complete, because an optimised image
built on an unverified understanding proves nothing.

## Phase 1 — Understand and reproduce

### WP1 — Acquire and pin — done

Resolve `ubi9-micro` to a digest, copy it locally, record the reference used by
all later work. Subject pinned at
`sha256:f332c99eb8f798a8486821c91937f10ad64ee83d7e739303be2df051040918f6`.

### WP2 — Image structure — done

Manifest, config, history, labels, environment, layer digests. Established that
the image is squashed to one layer and its Containerfile contains no `RUN`.

### WP3 — File inventory — done

877 entries with modes, ownership, sizes, link targets and extended attributes,
read from tar headers rather than by extraction.

### WP4 — Package attribution — done

Twenty packages recovered from the rpmdb the image carries. Every inventory
entry attributed to an owning package or identified as unowned build residue.
Established the 8,498,676 bytes Red Hat trims after installing.

### WP5 — Image metadata — done

Accounts, release files, licences, content manifests, repository definitions.

### WP6 — Reconstruction

Build the image from an `--installroot` package transaction over `scratch`,
reproducing the trims recorded in WP4. Needs a Linux container runtime.

Unblocked. F12 recovered both build command lines verbatim and F13 identified
the three named packages, so the transaction to reproduce is known exactly
rather than reconstructed. The remaining unknown is the post-install cleanup
in I4, which must be reproduced by inspection of what is absent rather than
from a recorded command.

### WP7 — Comparison

Diff reconstruction against official across every dimension WP2–WP5 recorded,
and disposition each difference as resolved, accepted or open.

### WP8 — Write-up

Consolidate into an explanation that stands on its own for a reader who does
not run the scripts.

## Phase 2 — An application-tailored image

The goal is a container holding only what the installed application needs to
function, demonstrating that a UBI-based image can be small enough to compete
with vendors such as Alpine — while supporting requirements Alpine cannot
straightforwardly meet.

This phase is explicitly allowed to fail. **If a competitive size cannot be
reached, the deliverable is the explanation of why**, supported by the same
standard of evidence as everything else here. A documented floor is a result.

### WP9 — Application requirement profiling

Establish what an application actually needs at runtime rather than what its
packages declare: the shared-library closure, the configuration and data files
opened, the users and directories required, and the writable paths used. The
method must distinguish a genuine runtime requirement from a convenience.

### WP10 — OpenSSL and FIPS

Determine what FIPS-mode operation requires inside a container: which OpenSSL
components and provider modules must be present, what must be configured, and
which parts of the requirement belong to the host and kernel rather than the
image. Record precisely which claims the evidence supports.

No FIPS claim is made without matching evidence. Carrying a certified module is
not the same as operating in a validated configuration, and the write-up must
not blur the two.

### WP11 — Logging

Establish what logging costs a minimal image — what a container must contain to
emit logs usefully to stdout/stderr and to a collector, and what can be left to
the runtime and orchestrator.

### WP12 — Build and demonstrate

Build the tailored image and demonstrate the application functioning in it,
including under the FIPS and logging requirements above. Demonstration means a
runnable example in this repository, not an assertion.

### WP13 — Comparison against other vendors

Compare size honestly against equivalent Alpine and distroless images. The
comparison must state what each image contains, not only what each weighs, and
must account for differences that are structural rather than incidental — glibc
against musl foremost among them.

Where a size gap cannot be closed, explain the cause and quantify it.
