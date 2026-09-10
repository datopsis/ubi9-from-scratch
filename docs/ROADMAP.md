# Roadmap

What this repository must contain before it is finished, in the order it gets
built. Each release is a self-contained tutorial that stands on its own.

## Status

| Release | Contents | State |
| --- | --- | --- |
| — | Phase 1: dissect and reproduce `ubi9-micro` | **done** |
| v0.1.0 | L0.0 describe · L0.1 SHA-256 | **this release** |
| v0.2.0 | L1 dynamic linkage | next |
| v0.3.0 | L2 OpenSSL TLS | planned |
| v0.4.0 | L3 FIPS-mode crypto | planned |
| v0.5.0 | L4 structured logging | planned |
| v0.6.0 | Java: a minimal JRE container | planned |
| v0.7.0 | Java: FIPS with a working keystore | planned |
| v0.8.0 | Other images people actually want | planned |
| v0.9.0 | Comparison against Alpine and distroless | planned |
| v1.0.0 | The write-up | planned |

## Principles that apply to every tutorial

These are not optional and not per-release decisions.

**Rootless.** Every container runs rootless, and every image that can declares
a non-root `USER`. The official `ubi9-micro` sets no `USER` and therefore runs
as uid 0 — a property this project documents rather than copies. Where an image
cannot yet run rootless, the tutorial says so and explains what blocks it.

**All capabilities dropped.** Every `podman run` in every tutorial uses
`--cap-drop=ALL --security-opt=no-new-privileges`, and where the workload
allows, `--read-only` with explicit `tmpfs` mounts. A tutorial needing a
capability must name it, justify it, and show what fails without it.

**Security evidence in every step.** Every tutorial generates an SBOM and runs
a vulnerability scan with `scripts/security_scan.sh` — the same script CI runs,
so the pipeline and the tutorial cannot drift. Every tutorial also shows how to
do it by hand, because a reader who only runs the script has learned nothing.

**Consistent structure.** Every tutorial has the same sections in the same
order: what it shows and does not show; prerequisites; build; run; exec and
inspect; review the contents; security; where it sits on the ladder; clean up.
A reader who has finished one can navigate any of them.

**Everything is measured.** Each rung reports image bytes, entry count,
component count and vulnerability count against the rung below. The cost of a
requirement is the difference.

## Phase 1 — Understand and reproduce — done

WP1 acquire and pin · WP2 image structure · WP3 file inventory · WP4 package
attribution · WP5 image metadata · WP6 reconstruction · WP7 comparison.

The reconstruction reproduces the official image with zero unexplained
differences — see `docs/COMPARISON.md`. WP8, the consolidated write-up, lands
with v1.0.0.

## Phase 2 — The ladder

Each rung adds one requirement and reports what it costs. Every rung computes
the same SHA-256 digests by a different route, so the rungs produce identical
output and their sizes compare directly.

### v0.1.0 — L0.0 and L0.1 — done

**L0.0 describe** — a statically linked C++ binary alone on `scratch`,
reporting the environment it runs in. Teaches what an empty image really means,
and that `podman exec` works only for binaries the image contains.

**L0.1 SHA-256** — the same floor doing real work, verified against the FIPS
180-4 vectors and cross-checked against an independent `sha256sum`.

Measured: 939,069 bytes, 1 file, 0 components, 0 vulnerabilities — and the
tutorial explains why zero vulnerabilities is not a clean bill of health.

### v0.2.0 — L1 dynamic linkage

The same program linked dynamically against the reconstructed `micro` base.
Teaches what leaving `scratch` costs, why `getaddrinfo` and NSS need the
dynamic loader, and how `scripts/closure.py` finds what a binary requires.

Adds a non-root `USER` — this is the first rung with an `/etc/passwd` to put
one in.

### v0.3.0 — L2 OpenSSL TLS

The program verifies a TLS connection. Teaches what transport security costs,
and introduces the first things a static closure cannot see: the CA trust
bundle, and the NSS modules behind hostname resolution.

### v0.4.0 — L3 FIPS-mode crypto

The same digest computed through OpenSSL's FIPS provider. Teaches the
distinction this project will not blur: an image can be **FIPS-capable**; only
a host-plus-image combination can be **FIPS-operating**, because FIPS mode
depends on a kernel booted `fips=1` and on crypto-policies the container
inherits rather than sets.

Also teaches why L0's approach cannot reach here: the validated boundary is a
provider module loaded by `dlopen`, which a fully static binary cannot load.

### v0.5.0 — L4 structured logging

What observability costs a minimal image, and what belongs to the runtime and
orchestrator rather than the image.

## Phase 3 — Images people actually want

The ladder proves a principle. This phase applies it to workloads a reader
would really ship, which is where the interesting failures live.

### v0.6.0 — A minimal Java JRE container

A working Java application in the smallest UBI-derived image that can run it.

- Use `jlink` to build a custom runtime containing only the modules the
  application resolves, rather than shipping a whole JRE.
- Establish what the JVM needs beyond the runtime itself: `libz`, `libjli`,
  fontconfig for anything graphical, `/etc/passwd` for `user.name`, and
  timezone data — which the dissection showed `ubi9-micro` does not have.
- Run rootless, all capabilities dropped, read-only root filesystem with an
  explicit writable path for the JVM's temporary files.
- Working example: an application doing real work with a verifiable result,
  not `System.out.println("hello")`.
- Compare against `registry.access.redhat.com/ubi9/openjdk-21-runtime`.

**Known unknowns to resolve here.** Whether a jlink runtime can run on a
`scratch`-based image at all or needs the `micro` base; and what the JVM does
when `/etc/localtime` and the zoneinfo database are absent, given the tzdata
finding.

### v0.7.0 — Java with FIPS and a working keystore

The v0.6.0 container upgraded to FIPS-mode crypto, demonstrating the capability
rather than asserting it.

- Configure the JVM to use the system's FIPS-validated crypto through
  `java.security`, rather than a bundled provider.
- Build a **PKCS#12 keystore** and demonstrate loading it — FIPS mode rejects
  the legacy JKS format, which is the failure most people meet first.
- Working example: a TLS handshake succeeding with a key from that keystore,
  and the same handshake failing when a non-approved algorithm is requested —
  demonstrating FIPS is in force rather than merely configured.
- Record what the host must provide, and state plainly which claims the
  evidence supports.

### v0.8.0 — Other images people actually want

The same method applied to containers a reader is likely to need next. Each is
a full tutorial in the standard structure, with its own measurements and
security evidence.

- **A static Go binary** — the comparison case for L0, since Go makes static
  linking the default rather than a fight.
- **A Python application** — the hard case: an interpreter cannot be statically
  linked away, so this measures what a language runtime really costs.
- **A single-binary web service** — TLS, health endpoint, read-only root, no
  shell. The realistic shape of a production container.
- **A debug sidecar** — the answer to "there is no shell in my container": a
  separate image sharing the namespace, so the runtime image stays minimal.

## Phase 4 — Conclusions

### v0.9.0 — Comparison against other vendors

Compare against Alpine and distroless **at equal capability**, not equal name.
An image without a validated crypto module is not a smaller version of a
FIPS-capable image; it is a different image that cannot serve the same
workload. State what each image contains, not only what each weighs, and
account for differences that are structural — glibc against musl foremost.

Where a size gap cannot be closed, explain the cause and quantify it.

### v1.0.0 — The write-up

WP8: consolidate everything into an explanation that stands on its own for a
reader who runs none of it.

## Capabilities: a teaching thread, not a checkbox

The principle above says drop all capabilities. Several planned tutorials will
genuinely need one, and those are the most instructive moments in the project —
a reader learns more from *why this needs `NET_BIND_SERVICE`* than from a list
of flags. Where it is expected to come up:

| Where | Capability | The lesson |
| --- | --- | --- |
| v0.8.0 web service | `NET_BIND_SERVICE` | Only needed to bind below port 1024. The tutorial binds 8443 instead and drops it entirely — the capability is usually an avoidable design choice. |
| v0.6.0 Java | none, but `--read-only` bites | The JVM wants a writable temp directory. Shows `--tmpfs /tmp` rather than granting write access to the root filesystem. |
| v0.8.0 debug sidecar | `SYS_PTRACE` | Needed to inspect another process. Shows why it belongs on a sidecar used briefly, never on a runtime image. |
| Any rootless image | `--userns=keep-id` | Not a capability, but the same class of confusion: uid mapping is what usually breaks a rootless volume mount. |

Each tutorial that grants a capability must show the failure without it, the
narrowest grant that fixes it, and the design change that removes the need
where one exists.

## Cross-cutting work

Not tied to a single release.

- **Multi-architecture.** Everything so far is amd64. The official image ships
  four architectures; the reconstruction should be verified on at least arm64.
- **Release automation.** CI builds and verifies every image; publishing them
  with signatures and attestations is not done.
- **U2 — mtimes.** 80 distinct mtimes in the official image; the rule deciding
  which files keep original RPM timestamps is not established.
- **U3 — the cleanup.** Red Hat's post-install cleanup was reproduced from what
  is absent rather than from any recorded command. Its full extent is unknown.
