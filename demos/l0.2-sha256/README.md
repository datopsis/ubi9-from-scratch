# L0.2 — the same floor, doing real work

**Part three of the L0 tutorial.** Part two is
[L0.1](../l0.1-describe/README.md); part four is
[L0.3](../l0.3-authority/README.md).

> [!NOTE]
> **Verified in CI** on `ubuntu-latest` with Podman 5.x. Every command and
> output on this page was executed, not predicted.
>
> **939,069 bytes. One file. 4.0% of the official `ubi9-micro`.**

## What this shows

L0.1 proved what an empty image contains. This rung proves the same image can
do something useful: **it computes the SHA-256 of standard input.**

That function is chosen deliberately. Every rung of the ladder computes the
same digests by a different route — self-contained here, through OpenSSL at L2,
through the FIPS provider at L3 — so the rungs produce identical output and
their sizes compare directly. **The cost of a requirement is then a difference
in bytes, not a difference in what the program does.**

SHA-256 is implemented in the demo rather than linked, because L0's claim is
that the image holds nothing but the binary. Linking a crypto library would
make that claim untestable.

### What it does not show

- **glibc is not gone**, it is linked into the binary. The image has no libc
  file; the program has all the libc it needs.
- **`getaddrinfo`, NSS and `dlopen` are unreliable in a static glibc build.**
  This program does none of those, which is why it can be static.
- **This is not how you should do production crypto.** A hand-written SHA-256
  is correct here because it is verified against the NIST vectors *and* an
  independent implementation, and because the rung's whole point is having no
  dependencies. For real work, use a reviewed library — which is what L2 and L3
  are about.
- **FIPS is impossible at this rung**, for the reason in
  [L0.1](../l0.1-describe/README.md#what-it-does-not-show).

## Prerequisites

| Requirement | Why | Exercised against |
| --- | --- | --- |
| Podman ≥ 4.0 (or Docker ≥ 20.10) | multi-stage build, `--squash-all` | Podman 5.x |
| Network access to `registry.access.redhat.com` | pulls the UBI 9 builder image | verified |
| ~1 GB free disk | builder image plus toolchain | verified |
| `syft` and `grype` | SBOM and vulnerability scan (optional) | syft 1.51.1, grype 0.118.0 |

```sh
curl -sSfL https://get.anchore.io/syft  | sh -s -- -b /usr/local/bin
curl -sSfL https://get.anchore.io/grype | sh -s -- -b /usr/local/bin
```

## Build

```sh
podman build \
  --squash-all \
  --file demos/l0.2-sha256/Containerfile \
  --tag l0.2-sha256:9.8 \
  demos/l0.2-sha256
```

## Run

```sh
printf 'abc' | podman run --rm -i \
  --cap-drop=ALL \
  --security-opt=no-new-privileges \
  --read-only \
  --network=none \
  l0.2-sha256:9.8
```

Observed:

```
ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad
```

That is the FIPS 180-4 vector for `"abc"`, and it matches `sha256sum`. Note
`--network=none`: a hashing tool has no business reaching the network, and
saying so at launch costs nothing.

Hash a file:

```sh
podman run --rm -i --cap-drop=ALL --network=none l0.2-sha256:9.8 < myfile
```

Ask it to describe itself instead:

```sh
podman run --rm --cap-drop=ALL --network=none l0.2-sha256:9.8 --report
```

```
L0.3 — static C++ on scratch
----------------------------
function             : SHA-256 of stdin (self-contained)
NIST self-test       : passed (3 vectors)
sha256("abc")        : ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad
exceptions           : working
shared libraries     : 0 — nothing loaded from the image

This image contains one file: the binary printing this.
```

The program runs the NIST vectors on **every** invocation and exits `1` if they
fail, so it will never print a digest it cannot vouch for.

## Exec and inspect

The mechanics are the same as [L0.1](../l0.1-describe/README.md#exec-and-inspect):
`podman exec` works only for binaries the image contains, and this image
contains one. There is no shell.

What is worth adding here is the practical payoff.

### Make the container feel like a native command

Because the entrypoint is an ordinary binary reading stdin and writing stdout,
the container composes with everything else in a shell pipeline:

```sh
alias sha256c='podman run --rm -i --cap-drop=ALL --security-opt=no-new-privileges --read-only --network=none l0.2-sha256:9.8'

sha256c < myfile
cat a b c | sha256c
tar cf - ./dir | sha256c
```

`sha256c` now reads exactly like a native tool, but the implementation is
pinned to an image digest, carries no dependencies, cannot touch your
filesystem, and cannot reach the network. Uninstalling it is `podman rmi`.

This is how minimal containers become practical to *use* rather than only to
deploy: **the image is the unit of distribution, the alias is the interface,
and the launch flags are the sandbox.** For a tool you run against untrusted
input — which is exactly what a hashing tool does — that is a real improvement
over a binary on your `PATH`.

### A health check with no extra bytes

The binary validates itself and exits non-zero on failure, so:

```dockerfile
HEALTHCHECK --interval=30s CMD ["/app", "--report"]
```

No shell, no `curl`, nothing added to the image.

## Review the contents

```sh
podman create --name check l0.2-sha256:9.8
podman export check -o rootfs.tar
podman rm check
python scripts/verify_image.py rootfs.tar --expect-entries 1
```

```
entries        : 1
  files        : 1
apparent bytes : 935,288
setuid         : 0
setgid         : 0
non-root owned : 0
package mgrs   : 0

all checks passed
```

```sh
podman image inspect l0.2-sha256:9.8 --format '{{.Size}}'
```

Observed: `939069`. The SHA-256 implementation accounts for 4,095 of those
bytes — L0.1, which only describes itself, is 934,974.

### Verify the function, not just the container

```sh
demos/l0.2-sha256/verify.sh l0.2-sha256:9.8
```

```
Functional test: SHA-256 of stdin
  PASS  empty input                  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
  PASS  "abc"                        ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad
  PASS  448-bit message              248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1

Functional test: multi-block input
  PASS  100,000 bytes                6d1cf22d7cc09b085dfc25ee1a1f3ae0265804c607bc2074ad253bcc82fd81ee

all functional checks passed
```

The 100,000-byte case is cross-checked against the host's `sha256sum`, so the
result is verified against an **independent implementation** rather than only
against constants compiled into the binary. That distinction matters: a wrong
implementation with matching wrong test vectors passes its own suite.

## Security

```sh
scripts/security_scan.sh l0.2-sha256:9.8
```

```
components catalogued: 0
vulnerabilities found : 0

  Zero packages found. For an image built on scratch this is expected and is
  NOT a clean bill of health: there is no package database, so a package-based
  scanner has nothing to inspect. The dependencies were linked into the binary
  and remain there.
```

### Do it by hand

```sh
podman save --format oci-archive -o image.tar l0.2-sha256:9.8
syft oci-archive:image.tar -o table
grype oci-archive:image.tar -o table
```

Scanning an exported archive avoids needing a container-engine socket and works
identically anywhere.

### The lesson, and it is the important one

Compare against the reconstructed `ubi9-micro`, scanned by the same script:

| Image | Bytes | Components | Vulnerabilities |
| --- | ---: | ---: | --- |
| L0.2 | 939,069 | 0 | 0 — *nothing is visible* |
| `micro` | 23,585,791 | 22 | 23 (17 Medium, 6 Low) — real and actionable |

**The larger image looks worse and is more honest.** 31.4% of `ubi9-micro` is
its rpm database, and that database is what buys the visibility. Removing it
makes the image smaller *and* the report emptier, and only one of those is an
improvement.

A vulnerable libc compiled into a static binary produces exactly the same clean
report as a safe one. To reason about a static binary's exposure you need its
**build inputs** — the toolchain and library versions it was compiled against —
which the image does not carry. That is why this project records build inputs
per rung rather than relying on a scan.

This is the trade the whole ladder measures, and it is why "smallest image
wins" is the wrong objective.

## Where this sits on the ladder

| Rung | Image bytes | Entries | Components | Vulns |
| --- | ---: | ---: | ---: | ---: |
| L0.1 describe | 934,974 | 1 | 0 | 0 |
| **L0.2 SHA-256** | **939,069** | **1** | **0** | **0** |
| L0.3 authority | ~939,000 | 1 | 0 | 0 |
| WP6 `micro` reconstruction | 23,585,791 | 871 | 22 | 23 |
| Official `ubi9-micro` | 23,591,424 | 877 | — | — |

## Clean up

```sh
podman rmi l0.2-sha256:9.8
rm -f rootfs.tar image.tar
rm -rf security-results
unalias sha256c 2>/dev/null
```

---

**Next:** [L0.3 — why use a container at all?](../l0.3-authority/README.md)
