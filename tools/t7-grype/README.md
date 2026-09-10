# T7 — Grype

**Part 7 of the toolkit.** Previous: [T6](../t6-syft/README.md).
Back to [the toolkit index](../README.md).

> [!NOTE]
> Verified against grype 0.118.0 in CI. Every output below was executed.

## What this shows

Grype answers "what is known to be wrong with what is in this image?" — it
matches the components [syft](../t6-syft/README.md) catalogued against
vulnerability databases.

It also shows how to read that answer honestly, which is harder than running
the command.

### What it does not show

- Whether a vulnerability is *exploitable in your deployment*. It cannot know.
- Anything about how the container is launched. A scan describes the image.
- Anything it cannot see — which, after T6, you already know is the important
  caveat.

## Install

```sh
curl -sSfL https://get.anchore.io/grype | sudo sh -s -- -b /usr/local/bin
grype version | head -2
```

```
Application:         grype
Version:             0.118.0
```

## Scan an image

```sh
podman save --format oci-archive -o image.tar \
  registry.access.redhat.com/ubi9/ubi-micro:latest
grype oci-archive:image.tar
```

```
NAME                    INSTALLED            TYPE  VULNERABILITY   SEVERITY  EPSS         RISK
pcre2                   10.40-6.el9          rpm   CVE-2022-41409  Low       1.1% (64th)  0.5
pcre2-syntax            10.40-6.el9          rpm   CVE-2022-41409  Low       1.1% (64th)  0.5
ncurses-base            6.2-12.20210508.el9  rpm   CVE-2023-50495  Low       1.0% (59th)  0.5
ncurses-libs            6.2-12.20210508.el9  rpm   CVE-2023-50495  Low       1.0% (59th)  0.5
libgcc                  11.5.0-14.el9        rpm   CVE-2022-27943  Low       0.9% (57th)  0.4
libgcc                  11.5.0-14.el9        rpm   CVE-2021-46195  Low       0.8% (53rd)  0.2
glibc                   2.34-275.el9_8       rpm   CVE-2026-6791   Medium    0.2% (10th)  0.1
glibc-common            2.34-275.el9_8       rpm   CVE-2026-6791   Medium    0.2% (10th)  0.1
glibc-minimal-langpack  2.34-275.el9_8       rpm   CVE-2026-6791   Medium    0.2% (10th)  0.1
...
```

Twenty-three findings across twenty-two components: 17 Medium, 6 Low.

### Reading a row

| Column | What it means |
| --- | --- |
| `NAME` / `INSTALLED` | The package and version syft catalogued |
| `VULNERABILITY` | The CVE identifier |
| `SEVERITY` | CVSS band. **Not** a measure of your risk. |
| `EPSS` | Probability this is exploited in the wild in the next 30 days, and its percentile |
| `RISK` | Grype's combination of the two |

**`EPSS` is the column most people ignore and should not.** `CVE-2026-6791` is
Medium severity but sits in the 10th percentile for exploitation — the severity
band and the likelihood of anyone actually using it disagree sharply.

Notice also that one CVE appears three times: `glibc`, `glibc-common` and
`glibc-minimal-langpack` are built from the same source RPM. Three rows, one
underlying flaw. Counting rows overstates the problem.

## Scan an SBOM instead

Better practice, and what
[`scripts/security_scan.sh`](../../scripts/security_scan.sh) does:

```sh
syft oci-archive:image.tar -o spdx-json=sbom.spdx.json
grype sbom:sbom.spdx.json
```

The scan then describes **exactly** the component set the SBOM does, so the two
artefacts cannot disagree. It also means the SBOM can be produced once at build
time and re-scanned later as the vulnerability database changes — without
rebuilding or even keeping the image.

## The result that should change how you read a report

```sh
grype oci-archive:l0.tar     # the 939 KB L0 image
```

```
No vulnerabilities found
```

| Image | Bytes | Components | Vulnerabilities |
| --- | ---: | ---: | ---: |
| L0.2 static | 939,069 | 0 | **0** |
| Official `ubi9-micro` | 23,591,424 | 22 | **23** |

**The small image is not safer. It is unreadable.**

The same glibc, with the same flaws, is compiled into L0's binary. Grype has
nothing to match against because syft found nothing to catalogue. A genuinely
safe image and a badly outdated one produce the identical report.

This is the paradox at the centre of minimal containers, and it is why "fewer
CVEs" is a bad objective:

- **Minimising the image** shrinks the attack surface — no shell, no package
  manager, nothing to enumerate. Real, measurable security value.
- **The same minimisation** removes the metadata that makes the image auditable.
- Both effects are produced by the same change, and only one of them shows up
  in a report.

## What a scan cannot tell you

A vulnerability scan describes an image. It knows nothing about:

- **How the container is launched.** An image with zero CVEs run
  `--privileged` is worse than one with twenty run `--cap-drop=ALL --read-only`.
  [L0.3](../../demos/l0.3-authority/README.md) measures that difference; no
  scanner does.
- **Whether the vulnerable code path is reachable.** A flaw in a `bash` feature
  in an image whose program never invokes `bash` is not the same risk as one in
  its hot path.
- **What was linked rather than installed**, per the section above.

## Use a second scanner

Grype is not the only answer, and comparing is instructive:

```sh
trivy image --input image.tar
```

Trivy and grype use different databases and different matching rules, and
**they disagree** — different counts, sometimes different CVEs for the same
package. Neither is simply right. Seeing the disagreement is the fastest way to
stop treating a scan result as an objective fact about an image.

## Use it in CI, carefully

```sh
grype sbom:sbom.spdx.json --fail-on critical
```

Failing a build on findings is reasonable *if* you have decided what the
threshold means. Failing on `--fail-on low` against a base image you do not
control produces a permanently red pipeline that everyone learns to ignore,
which is worse than no gate at all.

This project deliberately does **not** fail its build on scan findings. It
records them as evidence, because the interesting fact is not the count — it is
that L0 reports zero while carrying the same code as an image reporting 23.

## Security

The whole tutorial is the security lesson, so to state it plainly:

1. A scan reports what the image *describes*, not what it *contains*.
2. Severity is not risk; check EPSS and reachability.
3. Row counts overstate — several packages often share one source flaw.
4. Two scanners will disagree; that is information, not a defect.
5. None of it says anything about how the container is run.

## Clean up

```sh
rm -f image.tar l0.tar sbom.spdx.json
```

---

**That is the toolkit.** Back to [the index](../README.md), or on to
[the ladder](../../demos/README.md), where these tools build progressively less
minimal containers and measure the cost of each step.
