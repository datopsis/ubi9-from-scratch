# The ladder

A sequence of containers where each rung adds exactly one requirement and
reports what that requirement costs. Every rung computes the same SHA-256
digests by a different route, so the rungs produce identical output and their
sizes compare directly.

Work through them in order. Each tutorial has the same sections, so once you
have done one you can navigate any of them.

## L0 — the floor: `scratch`, one static binary

| Part | Tutorial | Question it answers |
| --- | --- | --- |
| L0.0 | [describe](l0.1-describe/README.md) | What does an image with nothing in it actually contain? |
| L0.1 | [sha256](l0.2-sha256/README.md) | Can something that small do real work? |
| L0.2 | [authority](l0.3-authority/README.md) | If it's just a binary, why containerise it at all? |

**L0.2 is the one to read if you are sceptical of the whole idea.** It measures
what the kernel permits a process, contained versus not, and shows the same
process from the host with its capability set empty.

## Planned

| Rung | Adds | Status |
| --- | --- | --- |
| L1 | dynamic linkage against the reconstructed base | v0.2.0 |
| L2 | TLS via OpenSSL | v0.3.0 |
| L3 | FIPS-mode crypto | v0.4.0 |
| L4 | structured logging | v0.5.0 |

Beyond the ladder, `docs/ROADMAP.md` plans a minimal Java JRE container, a
FIPS-enabled Java container with a working PKCS#12 keystore, and several
images people commonly need — a static Go binary, a Python application, a
single-binary web service, and a debug sidecar.

## Conventions every tutorial follows

**Rootless, and no capabilities.** Every `podman run` uses
`--cap-drop=ALL --security-opt=no-new-privileges`, plus `--read-only` and
`--network=none` where the workload allows. Every image declares a non-root
`USER`. A tutorial needing a capability names it, justifies it, and shows what
fails without it.

**Everything shown was executed.** Outputs are copied from real runs, verified
in CI. Anything not yet run is marked `UNVERIFIED` until it has been.

**Security evidence in every rung.** Each tutorial generates an SBOM and runs a
vulnerability scan with `scripts/security_scan.sh` — the same script CI runs —
and explains how to do it by hand.

**Measured, not asserted.** Each rung reports image bytes, entry count,
component count and vulnerability count against the rung below.

## Results so far

| Rung | Image bytes | Entries | Components | Vulns |
| --- | ---: | ---: | ---: | ---: |
| L0.0 describe | 934,974 | 1 | 0 | 0 |
| L0.1 SHA-256 | 939,069 | 1 | 0 | 0 |
| L0.2 authority | ~939,000 | 1 | 0 | 0 |
| WP6 `micro` reconstruction | 23,585,791 | 871 | 22 | 23 |
| Official `ubi9-micro` | 23,591,424 | 877 | — | — |

Zero components at L0 is an absence of *visibility*, not an absence of risk.
Every L0 tutorial explains why, because it is the single most misleading number
in container security.
