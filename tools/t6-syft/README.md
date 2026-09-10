# T6 — Syft

**Part 6 of the toolkit.** Previous: [T5](../t5-umoci/README.md).
Next: [T7 — Grype](../t7-grype/README.md).

> [!NOTE]
> Verified against syft 1.51.1 in CI. Every output below was executed.

## What this shows

Syft answers "what is in this image?" and writes the answer as an **SBOM** — a
Software Bill of Materials, a machine-readable inventory of components.

It also demonstrates the limit of that question, which is the more valuable
lesson.

### What it does not show

- Whether anything is *wrong* with what it finds. That is
  [grype](../t7-grype/README.md).
- What the image can *do* when running. No SBOM tool addresses that.

## Install

```sh
curl -sSfL https://get.anchore.io/syft | sudo sh -s -- -b /usr/local/bin
syft version | head -2
```

```
Application:   syft
Version:       1.51.1
```

Available for RHEL and Ubuntu the same way — it is a single static binary with
no daemon.

## Catalogue an image

Scan an exported archive rather than asking syft to talk to Podman. It needs no
socket and works identically anywhere:

```sh
podman save --format oci-archive -o image.tar \
  registry.access.redhat.com/ubi9/ubi-micro:latest
syft oci-archive:image.tar -o table
```

```
NAME                    VERSION              TYPE
basesystem              11-13.el9            rpm
bash                    5.1.8-9.el9          rpm
coreutils-single        8.32-41.el9_8        rpm
filesystem              3.16-5.el9           rpm
glibc                   2.34-275.el9_8       rpm
glibc-common            2.34-275.el9_8       rpm
glibc-minimal-langpack  2.34-275.el9_8       rpm
gpg-pubkey              5a6340b3-6229229e    rpm
gpg-pubkey              fd431d51-4ae0493b    rpm
libacl                  2.4.0-1.el9_8        rpm
libattr                 2.6.0-1.el9_8        rpm
libcap                  2.48-10.el9_8.1      rpm
libgcc                  11.5.0-14.el9        rpm
...
```

**Those are exactly the 20 packages and 2 GPG keys Phase 1 recovered by
decoding the rpm database by hand** — see
[`docs/COMPONENTS.md`](../../docs/COMPONENTS.md). Syft is reading the same
database. Knowing that is what makes the next section obvious rather than
surprising.

## Where the answer comes from

Syft does not analyse binaries. It looks for **package metadata** that a
package manager left behind:

| Ecosystem | What syft reads |
| --- | --- |
| RPM (RHEL, UBI) | `/var/lib/rpm/rpmdb.sqlite` |
| Debian | `/var/lib/dpkg/status` |
| Alpine | `/lib/apk/db/installed` |
| Python | `*.dist-info`, `*.egg-info` |
| Node | `package-lock.json`, `node_modules` |
| Go | build metadata embedded in the binary |

Everything syft reports comes from one of those. **If a file is not described
by any of them, syft cannot see it.**

## The limit, demonstrated

Now scan an [L0](../../demos/l0.2-sha256/README.md) image — 939 KB, one file, a
statically linked binary:

```sh
podman save --format oci-archive -o l0.tar l0.2-sha256:9.8
syft oci-archive:l0.tar -o table
```

```
No packages discovered
```

**This is the single most misleading result in container security.**

The image contains a C++ program with glibc, libstdc++ and the libgcc unwinder
compiled into it. All of that code is present. None of it is *described*,
because there is no package database — the binary was linked, not installed.

| Image | Bytes | Components syft finds |
| --- | ---: | ---: |
| L0.2 static | 939,069 | **0** |
| Official `ubi9-micro` | 23,591,424 | 22 |

The 23 MB image is not worse. It is **legible**. 31.4% of `ubi9-micro` is its
rpm database, and that is precisely what buys the visibility.

**An empty SBOM is not a clean bill of health. It is a refusal to answer.**

## Output formats

```sh
syft oci-archive:image.tar \
  -o spdx-json=sbom.spdx.json \
  -o cyclonedx-json=sbom.cdx.json \
  -o json=sbom.syft.json
```

| Format | Use it when |
| --- | --- |
| **SPDX** | A compliance process asks for an SBOM. The ISO-standardised format. |
| **CycloneDX** | Feeding a scanner or a vulnerability platform. |
| **syft JSON** | You want syft's own richer detail, including file digests. |

Producing all three costs about a second, which is why
[`scripts/security_scan.sh`](../../scripts/security_scan.sh) does.

### Counting components correctly

A trap this project fell into: an SPDX document contains a package describing
**the image itself**, so counting `packages` reports 1 for an image containing
none. Count syft's own `artifacts` instead:

```sh
jq '.artifacts | length' sbom.syft.json
```

## Doing better for static binaries

If syft cannot describe a statically linked artefact, what can?

**Generate the SBOM at build time, from the build inputs.** The build stage
knows exactly which compiler and which library versions it linked against; the
resulting image does not. Capture it there and attach it to the image as an
attestation rather than deriving it from the image afterwards.

That is why this project records build inputs per rung rather than relying on a
scan — see [`docs/METHODOLOGY.md`](../../docs/METHODOLOGY.md).

## Security

The habit worth forming: **read an SBOM's emptiness as a question, not an
answer.** When a scan reports nothing, establish whether that is because the
image contains nothing or because the image describes nothing. Those are very
different situations and they produce identical reports.

## Clean up

```sh
rm -f image.tar l0.tar sbom.*.json
```

---

**Next:** [T7 — Grype](../t7-grype/README.md)
