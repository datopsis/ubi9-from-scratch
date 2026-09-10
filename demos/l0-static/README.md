# L0 — static C++ on scratch

> [!NOTE]
> **Verified** in CI on `ubuntu-latest` with Podman 5.x. Run 34439485922.
>
> **Result: 934,974 bytes. One file. 4.0% of the official `ubi9-micro`.**

## What this shows

The floor of the WP9 ladder: a C++ application in an image that contains
nothing but the application. No libc file, no shell, no `/etc`, no package
manager, no directories — a single binary at `/app`.

**It does real work: it computes the SHA-256 of standard input.** That function
is deliberate. Every rung of the ladder computes the same digests by a
different route — self-contained here, through OpenSSL at L2, through the FIPS
provider at L3 — so the rungs produce identical output and their sizes are
directly comparable. The cost of each requirement is then a difference in
bytes, not a difference in what the program does.

SHA-256 is implemented in the demo rather than linked, because L0's claim is
that the image holds nothing but the binary. Linking a crypto library would
make that claim untestable.

It exists to establish the lower bound every other rung is measured against,
and to make one point concretely: **when a program is statically linked, the
base image contributes nothing, so the base image can be empty.** At this rung
a UBI-derived toolchain produces an image smaller than Alpine's base, because
the comparison is no longer glibc against musl — it is one binary against a
whole distribution.

### What it does not show

This rung is not generally applicable, and the ladder exists because of that:

- **glibc is still glibc.** It is linked *into* the binary, not absent. The
  image has no libc file; the program has all the libc it needs.
- **`getaddrinfo`, NSS and `dlopen` do not work reliably in a static glibc
  build.** Anything resolving hostnames or users through NSS, or loading a
  module by name, needs the dynamic linker. This demo does none of those, which
  is precisely why it can be static.
- **FIPS is impossible here.** OpenSSL's validated boundary is a provider
  module loaded at runtime via `dlopen`. A fully static binary cannot load it.
  L3 addresses FIPS and pays the size cost of doing so.
- No shell means no debugging inside the container, and no `/etc/passwd` means
  the process runs as a numeric uid with no name behind it.

## Prerequisites

| Requirement | Why | Exercised against |
| --- | --- | --- |
| Podman ≥ 4.0 or Docker ≥ 20.10 | multi-stage build, `--squash-all` | Podman 5.x |
| Network access to `registry.access.redhat.com` | pulls the UBI 9 builder image | verified |
| ~1 GB free disk | builder image plus toolchain | verified |

No Red Hat subscription is needed. `glibc-static` and `libstdc++-static` come
from CodeReady Builder, which the UBI repository definition enables by default.

## Build

From the repository root:

```sh
podman build \
  --squash-all \
  --file demos/l0-static/Containerfile \
  --tag l0-static:9.8 \
  demos/l0-static
```

The build prints its own linkage check. `ldd` on a fully static binary reports
`not a dynamic executable`, which is the outcome to expect.

## Run

Hash something:

```sh
printf 'abc' | podman run --rm -i l0-static:9.8
```

Observed output:

```
ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad
```

That is the FIPS 180-4 test vector for `"abc"`, and it matches `sha256sum`.

Ask it to describe its runtime instead:

```sh
podman run --rm l0-static:9.8 --report
```

```
L0 — static C++ on scratch
--------------------------
function             : SHA-256 of stdin (self-contained)
NIST self-test       : passed (3 vectors)
sha256("abc")        : ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad
exceptions           : working
shared libraries     : 0 — nothing loaded from the image

This image contains one file: the binary you are reading this from.
```

The program runs the NIST vectors on every invocation and exits `1` if they
fail, so it will not print a digest it cannot vouch for. `--report` also exits
`2` if it finds shared libraries mapped.

## Verify

**Function.** The demo owns its verification, which CI runs on every push:

```sh
demos/l0-static/verify.sh l0-static:9.8
```

Observed:

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
digest is verified against an independent implementation rather than only
against vectors compiled into the binary.

**Contents.** Export the filesystem and inspect it. A shell-based check cannot
be used here, because there is no shell.

```sh
podman create --name check l0-static:9.8
podman export check -o rootfs.tar
podman rm check
python scripts/verify_image.py rootfs.tar --expect-entries 1
```

Observed:

```
entries        : 1
  files        : 1
apparent bytes : 931,144
setuid         : 0
setgid         : 0
non-root owned : 0
package mgrs   : 0

all checks passed
```

**Size.**

```sh
podman image inspect l0-static:9.8 --format '{{.Size}}'
```

Observed: `934974`.

**Static linkage**, independently of what the program claims about itself:

```sh
podman create --name check l0-static:9.8 && podman export check -o rootfs.tar && podman rm check
tar -xOf rootfs.tar app | head -c 20 | od -c | head -2
```

A static binary has no `PT_INTERP` segment. `scripts/closure.py` reports
`static: true` for such a file, and finds no `DT_NEEDED` entries.

## Where this sits on the ladder

| Rung | Image bytes | Entries | vs `ubi9-micro` |
| --- | ---: | ---: | ---: |
| **L0 static** | **934,974** | **1** | **4.0%** |
| Official `ubi9-micro` | 23,591,424 | 877 | 100% |
| WP6 reconstruction | 23,613,441 | 874 | 100.1% |

L1 through L4 are not built yet. Each will appear here with its own measured
cost as it lands.

## Clean up

```sh
podman rmi l0-static:9.8
rm -f rootfs.tar
```
