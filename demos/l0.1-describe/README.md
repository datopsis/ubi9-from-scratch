# L0.1 — a container that describes itself

**Part two of the L0 tutorial.** Part one is
[L0.0 — anatomy](../l0.0-anatomy/README.md); part three is
[L0.2](../l0.2-sha256/README.md), which does real work.

> [!NOTE]
> **Verified in CI** on `ubuntu-latest` with Podman 5.x. Every command and
> every output on this page was executed, not predicted.

## What this shows

An image containing exactly one file. No shell, no C library on disk, no
`/etc`, no package manager, no directories — a single statically linked binary
at `/app`.

The program's job is to **describe the environment it is running in**. That is
the whole point of this rung: before doing anything useful with a minimal
container, you should be able to see what "minimal" actually means. A container
that prints `hello` proves only that it started. This one proves what it
started *inside*.

It also exercises the parts of C++ that quietly need runtime support —
`std::string` and `std::vector` need libstdc++, and a thrown exception needs
the unwinder from libgcc. If those work in a static binary on an empty image,
the link really is self-contained.

### What it does not show

- **glibc is not gone.** It is linked *into* the binary. The image has no libc
  file; the program has all the libc it needs.
- **`getaddrinfo`, NSS and `dlopen` are unreliable in a static glibc build.**
  Anything resolving hostnames or users, or loading a module by name, needs the
  dynamic loader. This program does none of those, which is why it can be
  static.
- **FIPS is impossible at this rung.** OpenSSL's validated boundary is a
  provider module loaded at runtime via `dlopen`. A fully static binary cannot
  load one. L3 addresses FIPS and pays the size for it.
- **No shell means no poking around inside.** The "Exec and inspect" section
  below is about what you do instead.

## Prerequisites

| Requirement | Why | Exercised against |
| --- | --- | --- |
| Podman ≥ 4.0 (or Docker ≥ 20.10) | multi-stage build, `--squash-all` | Podman 5.x |
| Network access to `registry.access.redhat.com` | pulls the UBI 9 builder image | verified |
| ~1 GB free disk | builder image plus toolchain | verified |
| `syft` and `grype` | SBOM and vulnerability scan (optional) | syft 1.51.1, grype 0.118.0 |

No Red Hat subscription is needed. `glibc-static` and `libstdc++-static` come
from CodeReady Builder, which the UBI repo definition enables by default.

Install the security tools if you want to follow that section:

```sh
curl -sSfL https://get.anchore.io/syft  | sh -s -- -b /usr/local/bin
curl -sSfL https://get.anchore.io/grype | sh -s -- -b /usr/local/bin
```

## Build

From the repository root:

```sh
podman build \
  --squash-all \
  --file demos/l0.1-describe/Containerfile \
  --tag l0.1-describe:9.8 \
  demos/l0.1-describe
```

The build runs `ldd` on the result. A fully static binary reports
`not a dynamic executable` — that is the outcome you want.

`--squash-all` matters: the official `ubi9-micro` is a single layer, and every
image in this project matches that so comparisons stay meaningful.

## Run

Every run in this project is rootless with all capabilities dropped. That is
not decoration — this container needs none of them, and proving that is part of
the exercise.

```sh
podman run --rm \
  --cap-drop=ALL \
  --security-opt=no-new-privileges \
  --read-only \
  l0.1-describe:9.8
```

Observed output:

```
L0.3 — static C++ on scratch
----------------------------
purpose              : describe the environment it runs in
linked in statically : libstdc++, libgcc unwinder, glibc
exceptions           : working
shared libraries     : 0 — nothing loaded from the image

What this container has:
  /app                       this binary          present
  /bin/sh                    a shell              absent
  /etc/passwd                user database        absent
  /etc/resolv.conf           DNS configuration    absent
  /usr/lib64/libc.so.6       a C library on disk  absent
  /var/lib/rpm/rpmdb.sqlite  package database     absent

This image contains one file: the binary printing this.
```

Note `/etc/resolv.conf` reports **absent**. The container runtime normally
injects that file, but it cannot: injection needs an `/etc` directory to put it
in, and this image has none. That is a concrete consequence of an empty
filesystem, not a bug.

The program exits `1` if exception handling is broken and `2` if it finds
shared libraries mapped, so a zero exit means its claims held.

### Why it runs as a non-root user

The image declares `USER 1000:1000`. There is no `/etc/passwd`, so that uid has
no name behind it — which is fine. The point is that the container does not
default to uid 0 even where the runtime would permit it.

The official `ubi9-micro` sets no `USER` at all and therefore runs as root.
This project documents that rather than copying it.

## Exec and inspect

**Yes, you can exec into this container — with one large caveat.** `podman exec`
runs a binary *from inside the container's filesystem*. This image contains
exactly one binary, so exactly one thing can be exec'd.

Start it in a mode that stays alive:

```sh
podman run -d -i --name l00 \
  --cap-drop=ALL --security-opt=no-new-privileges --read-only \
  l0.1-describe:9.8 --wait
```

Exec the binary that exists:

```sh
podman exec l00 /app
```

That works, and reprints the report from inside the already-running container.

Now try the thing everyone reaches for first:

```sh
podman exec l00 /bin/sh
```

```
Error: crun: executable file `/bin/sh` not found in $PATH: No such file or directory: OCI runtime attempt to invoke a command that was not found
```

Both results are verified in CI. **There is no shell to exec**, so the usual
`exec -it ... sh` debugging loop is simply unavailable.

### Why this is useful, not just trivia

**1. A container that behaves like a local command.** Because the entrypoint is
a normal binary, you can alias the whole container and forget it is one:

```sh
alias describe='podman run --rm --cap-drop=ALL --security-opt=no-new-privileges --read-only l0.1-describe:9.8'
describe
```

The alias is worth more at L0.2, where the container computes a digest —
`sha256c < myfile` reads exactly like a native tool while the implementation
stays isolated, pinned and disposable. This is how minimal containers become
practical to *use* rather than only to deploy: the container is the unit of
distribution, and the alias is the interface.

**2. `exec` is your only way into a running container without a shell.** When a
distroless container misbehaves in production, `exec sh` is not an option. What
you have instead is whatever binaries the image ships — so it is worth giving
your application a diagnostic mode, exactly as this one has `--report`:

```sh
podman exec l00 /app          # ask the running container about itself
```

That same property makes a health check possible without adding anything:

```dockerfile
HEALTHCHECK --interval=30s CMD ["/app"]
```

The binary already validates its own claims and exits non-zero when they fail,
so the health check needs no shell, no `curl`, and no extra bytes.

### Inspecting without exec

For anything `exec` cannot reach, work on the filesystem from outside:

```sh
podman create --name check l0.1-describe:9.8
podman export check -o rootfs.tar
podman rm check
tar -tvf rootfs.tar
```

```
-rwxr-xr-x 0/0          931144 2026-09-10 10:52 app
```

One file. This is also how the CI verification works, and it is the technique
that scales to any image regardless of what it contains.

Clean up the running container when you are done:

```sh
podman rm -f l00
```

## Review the contents

```sh
python scripts/verify_image.py rootfs.tar --expect-entries 1
```

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

Image size, which is the number the ladder tracks:

```sh
podman image inspect l0.1-describe:9.8 --format '{{.Size}}'
```

Observed: `934974`.

Confirm the linkage independently of what the program says about itself —
`scripts/closure.py` reports `static: true` and finds no `DT_NEEDED` entries
for a fully static binary.

## Security

Run the same script CI runs:

```sh
scripts/security_scan.sh l0.1-describe:9.8
```

Observed:

```
components catalogued: 0
vulnerabilities found : 0

  Zero packages found. For an image built on scratch this is expected and is
  NOT a clean bill of health: there is no package database, so a package-based
  scanner has nothing to inspect. The dependencies were linked into the binary
  and remain there.
```

### Do it by hand, so you understand the result

```sh
podman save --format oci-archive -o image.tar l0.1-describe:9.8
syft oci-archive:image.tar -o table
grype oci-archive:image.tar -o table
```

Scanning an exported archive rather than asking the tools to talk to Podman
avoids needing a socket, and works the same on any machine.

**This is the most important lesson here.** The scan is empty because
there is nothing for a package-based scanner to read — no rpmdb, no manifest,
no metadata. A vulnerable libc compiled into a static binary produces the
identical clean report as a safe one.

Compare with the reconstructed `ubi9-micro` from the same script:

| Image | Bytes | Components | Vulnerabilities |
| --- | ---: | ---: | --- |
| L0.1 | 934,974 | 0 | 0 — nothing is visible |
| `micro` | 23,585,791 | 22 | 23 (17 Medium, 6 Low) — real, and actionable |

The larger image looks worse and is more honest. 31.4% of `ubi9-micro` is its
rpm database, and that is what buys the visibility. Removing it makes the image
smaller *and* the report emptier, and only one of those is an improvement.

To reason about a static binary's exposure you need its **build inputs** — the
toolchain and library versions it was compiled against — which the image does
not carry. That is why this project records build inputs per rung rather than
relying on a scan.

## Where this sits on the ladder

| Rung | Image bytes | Entries | Components | Vulns |
| --- | ---: | ---: | ---: | ---: |
| **L0.1 describe** | **934,974** | **1** | **0** | **0** |
| L0.2 SHA-256 | 939,069 | 1 | 0 | 0 |
| WP6 `micro` reconstruction | 23,585,791 | 871 | 22 | 23 |
| Official `ubi9-micro` | 23,591,424 | 877 | — | — |

## Clean up

```sh
podman rm -f l00 2>/dev/null
podman rmi l0.1-describe:9.8
rm -f rootfs.tar image.tar
rm -rf security-results
```

---

**Next:** [L0.2 — the same floor, doing real work](../l0.2-sha256/README.md).
