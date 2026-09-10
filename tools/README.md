# Part 0 — the toolkit

The tutorials in [`demos/`](../demos/README.md) assume you have Podman and know
roughly what it is doing. This part pays for that assumption.

Seven short tutorials, each introducing one tool on its own terms: what it is,
what problem it solves, and what it is doing when this project uses it. Work
through them if you are new to containers, or dip into the ones you need.

| # | Tutorial | What it is for |
| --- | --- | --- |
| T1 | [Your development environment](t1-dev-environment/README.md) | Getting from a clean machine to one that can build and inspect containers |
| T2 | [Podman](t2-podman/README.md) | Running containers, rootless and daemonless |
| T3 | [Skopeo](t3-skopeo/README.md) | Asking a registry a question without pulling anything |
| T4 | [Buildah](t4-buildah/README.md) | Building images with no Containerfile — and what `unshare` and `mount` mean |
| T5 | [Umoci](t5-umoci/README.md) | Opening an OCI layout and putting it back |
| T6 | [Syft](t6-syft/README.md) | What is in this image? |
| T7 | [Grype](t7-grype/README.md) | What is wrong with what is in it? |

**Start with [T1](t1-dev-environment/README.md)** if you have nothing
installed. If you already run containers, [T4](t4-buildah/README.md) is the one
with the technique most people have not met.

## Which environment these target

Every command is given for both:

- **WSL2 Ubuntu** — `apt`. If you are on Windows, this is where you should be
  working; the analysis scripts run natively on Windows but every container
  operation needs Linux.
- **Red Hat Enterprise Linux / Fedora / CentOS Stream** — `dnf`. This project
  is about Red Hat's base images, so it is a natural home.

Both command sets are verified in CI on every push. The `apt` commands run on
the runner; the `dnf` commands run inside a `ubi9` container, so neither is
transcribed from documentation.

## Versions these were verified against

| Tool | Version | How it was installed |
| --- | --- | --- |
| podman | 4.9.3 | `apt install podman` (Ubuntu 24.04) |
| skopeo | 1.13.3 | `apt install skopeo` |
| buildah | 1.33.7 | `apt install buildah` |
| umoci | 0.4.7 | GitHub release binary — no distribution package |
| syft | 1.51.1 | `get.anchore.io/syft` installer |
| grype | 0.118.0 | `get.anchore.io/grype` installer |
| jq | 1.7 | `apt install jq` |

Your versions will differ. Where a command is version-sensitive, the tutorial
says so.

## The shape of this toolchain

Worth understanding before you start, because it explains why there are so many
separate tools rather than one:

```
      build              store               move              inspect
    ┌────────┐        ┌──────────┐        ┌────────┐        ┌──────────┐
    │buildah │───────▶│containers│◀──────▶│ skopeo │        │  syft    │
    │ podman │        │ /storage │        └────────┘        │  grype   │
    │  build │        └──────────┘             │            │  umoci   │
    └────────┘              │                  ▼            └──────────┘
                            │            registry, or             ▲
                            ▼            OCI archive ─────────────┘
                       podman run
```

These are not competitors. `podman`, `buildah` and `skopeo` share the same
storage and the same underlying libraries — `podman build` *is* buildah used as
a library. They are one toolchain with several front ends, each shaped for a
different job.

None of them needs a daemon, and none of them needs root.

## Next

After the toolkit, [the ladder](../demos/README.md) puts these tools to work
building progressively less minimal containers and measuring the cost of each
step.

[`docs/METHODOLOGY.md`](../docs/METHODOLOGY.md) is where the whole series lands.
