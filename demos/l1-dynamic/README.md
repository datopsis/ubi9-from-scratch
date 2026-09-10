# L1 — leaving `scratch`

**The first rung above the floor.** Previous is
[L0.3 — authority](../l0.3-authority/README.md).

> [!NOTE]
> **Verified in CI** on `ubuntu-latest` with Podman 5.x. Every command and
> output on this page was executed, not predicted.
>
> **The binary got 4.9× smaller. The image got 25× larger.**

## What this shows

Every L0 rung carried its own copy of glibc inside the binary. This rung links
against the C library on the base image instead — which is how essentially all
software is normally built and shipped.

The point is to **measure what that costs**, and the answer is not what people
expect:

| | L0.2 static | L1 dynamic | Change |
| --- | ---: | ---: | --- |
| The binary | 939,069 B | **192,632 B** | 4.9× smaller |
| The image | 939,069 B | **23,788,574 B** | **25× larger** |
| Entries in the image | 1 | 878 | +877 |
| Components an SBOM finds | 0 | 22 | now visible |
| Vulnerabilities reported | 0 | 23 | now visible |

Dynamic linking moves code out of your binary and onto the base image. It does
not make the code disappear — **you now have to carry the base**, and the base
is a whole distribution's worth of files that your program mostly does not use.

It is the same program computing the same digests as
[L0.2](../l0.2-sha256/README.md), so nothing above is explained by the program
changing.

### What it does not show

- **This is not an argument against dynamic linking.** It is how most software
  ships, for good reasons: shared libraries are patched once and every consumer
  benefits, which is exactly what the 23 visible CVEs make possible.
- The base here is stock `ubi9-micro`, not a tailored one. Trimming it to what
  the program actually needs is a later rung.
- Still no shell, still no package manager — `ubi9-micro` has neither.

## Prerequisites

| Requirement | Why | Exercised against |
| --- | --- | --- |
| Podman ≥ 4.0 (or Docker ≥ 20.10) | multi-stage build, `--squash-all` | Podman 5.x |
| Network access to `registry.access.redhat.com` | builder image and base image | verified |
| `syft` and `grype` | SBOM and vulnerability scan (optional) | syft 1.51.1, grype 0.118.0 |

## Build

```sh
podman build \
  --squash-all \
  --file demos/l1-dynamic/Containerfile \
  --tag l1-dynamic:9.8 \
  demos/l1-dynamic
```

The build prints its own linkage:

```
--- linkage ---
	libm.so.6 => /lib64/libm.so.6 (0x00007f77f7902000)
	libc.so.6 => /lib64/libc.so.6 (0x00007f77f76f8000)
--- size ---
192632 bytes
```

### The trap this rung had to work around

A plain `g++ -o app main.cpp` would compile cleanly and then fail at startup:

```
error while loading shared libraries: libstdc++.so.6: cannot open shared object file
```

**`ubi9-micro` ships glibc but not libstdc++.** The dissection found exactly 20
packages in it, and `libstdc++` is not among them — see
[`docs/COMPONENTS.md`](../../docs/COMPONENTS.md). The base has a C library, not
a C++ one.

Three ways out, and the choice matters:

| Option | Cost | Verdict |
| --- | --- | --- |
| Add `libstdc++` to the base | A bigger base and a package to track | Reasonable, but changes two things at once |
| Link everything statically | Back to L0 | Defeats the purpose of the rung |
| **`-static-libstdc++ -static-libgcc`** | ~150 KB in the binary | **Used here** |

The third links the C++ runtime into the binary while leaving glibc dynamic.
That is why `ldd` above shows only `libm` and `libc`: libstdc++ is inside the
executable. It is a genuinely useful technique for targeting minimal bases, and
it keeps this rung to changing exactly one thing.

Note the build stage needs `libstdc++-static` for the `.a` archive.
`libstdc++-devel` is not enough — it ships the shared library and headers, not
the archive. The failure is `cannot find -lstdc++` at link time.

## Run

```sh
printf 'abc' | podman run --rm -i \
  --cap-drop=ALL \
  --security-opt=no-new-privileges \
  --read-only \
  --network=none \
  l1-dynamic:9.8
```

```
ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad
```

**Byte-identical to L0.2's output.** That is the ladder working: the rungs
differ in what they contain, not in what they do.

```sh
podman run --rm --cap-drop=ALL --network=none l1-dynamic:9.8 --report
```

```
L1 — dynamic C++ on ubi9-micro
------------------------------
function             : SHA-256 of stdin (self-contained)
NIST self-test       : passed (3 vectors)
sha256("abc")        : ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad
exceptions           : working
shared libraries     : 3 — loaded from the base image

This image is a base image plus one binary — see what that cost.
```

Three shared objects mapped, where every L0 rung reported zero: `libc`, `libm`,
and the dynamic loader itself. The program's assertion is inverted from L0's —
here, finding *no* shared libraries would mean the rung was not doing what it
claims.

## Exec and inspect

The mechanics are as described in
[L0.1](../l0.1-describe/README.md#exec-and-inspect), with one difference worth
noticing: this image has 878 entries, so there is much more to exec — and still
no shell, because `ubi9-micro` does not ship one in a form you can reach here.

### Find what the binary actually needs

This is the rung where dependency analysis starts to matter, so use the tool on
it:

```sh
podman create --name check l1-dynamic:9.8
podman export check -o rootfs.tar
podman rm check
python scripts/closure.py /app --layer rootfs.tar
```

The closure is small — the binary, `libc`, `libm`, and the loader. Against 878
entries in the image, **that is the gap a tailored base would close.** The
official `ubi9-micro` is carrying `bash`, `coreutils`, `ncurses`, `pcre2`,
`libselinux` and an rpm database that this program never touches.

Static analysis cannot see everything, and this program is deliberately easy:
no `dlopen`, no hostname resolution, no certificates, no timezones. Rungs that
need those meet the limits — see
[`docs/METHODOLOGY.md`](../../docs/METHODOLOGY.md).

## Review the contents

```sh
python scripts/verify_image.py rootfs.tar
```

```
entries        : 878
apparent bytes : 23,191,614
setuid         : 0
setgid         : 0
package mgrs   : 0
```

877 of those 878 entries came from the base image. One is `/app`.

```sh
podman image inspect l1-dynamic:9.8 --format '{{.Size}}'
```

Observed: `23788574`.

```sh
demos/l1-dynamic/verify.sh l1-dynamic:9.8
```

Runs the same SHA-256 vectors as L0.2 plus the 100,000-byte cross-check against
the host's `sha256sum`, and asserts that shared libraries *are* loaded.

## Security

```sh
scripts/security_scan.sh l1-dynamic:9.8
```

```
components catalogued: 22
vulnerabilities found : 23
  Medium       17
  Low          6
```

### The result that should change how you read a scan

| Image | Bytes | Components | Vulnerabilities |
| --- | ---: | ---: | ---: |
| L0.2 static | 939,069 | 0 | 0 |
| **L1 dynamic** | **23,788,574** | **22** | **23** |

Going dynamic did not introduce 23 vulnerabilities. **It made them visible.**

The same glibc, with the same flaws, was compiled into L0.2's binary. No
scanner reported it, because a static binary carries no package metadata for a
scanner to read. L1 carries an rpm database — 31.4% of the base image — and
that database is the only reason anything can be reported at all.

There is a real security argument on each side, and it is worth being clear
about both:

- **For dynamic:** the flaws are visible, attributable to a package and
  version, and fixable by rebuilding on a patched base. You can prove what you
  are exposed to.
- **For static:** the attack surface is genuinely smaller — one file, no
  shell, no package manager, nothing to enumerate — but you cannot demonstrate
  what is inside it, and neither can anyone auditing you.

"Fewer CVEs" is not the same as "safer", and this pair of images is the
cleanest demonstration of that difference this project has.

### Do it by hand

```sh
podman save --format oci-archive -o image.tar l1-dynamic:9.8
syft oci-archive:image.tar -o table
grype oci-archive:image.tar -o table
```

## Where this sits on the ladder

| Rung | Image bytes | Entries | Components | Vulns |
| --- | ---: | ---: | ---: | ---: |
| L0.0 anatomy (C) | 798,905 | 1 | 0 | 0 |
| L0.1 describe (C++) | 934,974 | 1 | 0 | 0 |
| L0.2 SHA-256 | 939,069 | 1 | 0 | 0 |
| L0.3 authority | ~939,000 | 1 | 0 | 0 |
| **L1 dynamic** | **23,788,574** | **878** | **22** | **23** |
| WP6 `micro` reconstruction | 23,585,791 | 871 | 22 | 23 |
| Official `ubi9-micro` | 23,591,424 | 877 | — | — |

L1 is the base image plus 202,783 bytes. Everything else it weighs, it
inherited.

## Clean up

```sh
podman rmi l1-dynamic:9.8
rm -f rootfs.tar image.tar
rm -rf security-results
```

---

**Next:** L2 — TLS via OpenSSL, and the first dependencies that no closure
analysis can find.
