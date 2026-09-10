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

### WP6 — Reconstruction — done

Build the image from an `--installroot` package transaction over `scratch`,
reproducing the trims recorded in WP4. Needs a Linux container runtime.

Built and verified in CI: 23,613,441 B against the official 23,591,424 B, a
delta of 22,017 B (0.09%), single layer, no package manager, no setuid or
setgid entries. See `reconstruction/README.md`.

The remaining unknown is the post-install cleanup in I4, which was reproduced
from what is absent rather than from a recorded command. WP7 locates any
residue by diffing inventories rather than totals.

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

### WP9 — The C++ demonstrator

A C++ application built in this repository, carried in an image containing only
what it needs to run. It is the vehicle for every measurement in this phase, so
it is built as a ladder rather than a single target: each rung adds one
requirement and reports what that requirement costs in bytes.

| Rung | Adds | Linkage | What it demonstrates |
| --- | --- | --- | --- |
| L0 | a static C++ binary, nothing else | fully static | the floor: an image with no libc at all |
| L1 | dynamic linkage against the base | glibc, libstdc++ | what leaving `scratch` costs |
| L2 | TLS via OpenSSL | + openssl-libs | what transport security costs |
| L3 | FIPS-mode crypto | + FIPS provider module | see WP10 |
| L4 | structured logging | see WP11 | what observability costs |

The ladder exists because the rungs are in tension. A fully static binary needs
no base image, but **FIPS cannot be satisfied by a fully static build** — the
validated boundary is a shared provider module that OpenSSL loads at runtime.
Requiring FIPS therefore forces dynamic linkage and reinstates the glibc floor.
Reporting one number for "the minimal image" would conceal that; reporting the
ladder makes the cost of each requirement explicit and lets a reader choose the
rung their workload actually needs.

Static linkage against glibc carries its own limits — `getaddrinfo`, NSS and
anything reached through `dlopen` do not work reliably in a fully static
build. L0 and L1 must state which of these the demonstrator exercises rather
than implying a static build is universally viable.

Profiling method, applied at every rung: establish what the application needs
at runtime rather than what its packages declare — the shared-library closure,
the configuration and data files opened, the users and directories required,
and the writable paths used. The method must distinguish a genuine runtime
requirement from a convenience.

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

### WP12 — Build, demonstrate and trim

Build the image at each rung of the WP9 ladder and demonstrate the application
functioning in it. Demonstration means a runnable example in this repository,
not an assertion.

Trim each rung to what WP9 profiling proved necessary, and record what was
removed and how the removal was verified not to break the application. A trim
that is not demonstrated to be safe is not a result.

Further use cases and code examples extend the ladder. Each new one states the
requirement it adds, its measured cost in bytes, and what it removes from the
set of workloads the rung below can serve.

### WP13 — Comparison against other vendors

Compare size honestly against equivalent Alpine and distroless images. The
comparison must state what each image contains, not only what each weighs, and
must account for differences that are structural rather than incidental — glibc
against musl foremost among them.

Compare at equal capability, not equal name. An Alpine image without a
validated crypto module is not a smaller version of a FIPS-capable image; it is
a different image that cannot serve the same workload. Where a comparison has
no equivalent on the other side, say so rather than reporting the size gap
alone.

Where a size gap cannot be closed, explain the cause and quantify it.
