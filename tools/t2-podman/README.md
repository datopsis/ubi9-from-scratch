# T2 — Podman

**Part 2 of the toolkit.** Previous: [T1](../t1-dev-environment/README.md).
Next: [T3 — Skopeo](../t3-skopeo/README.md).

> [!NOTE]
> Verified against Podman 4.9.3 on Ubuntu 24.04 in CI.

## What this shows

Podman is the container engine used everywhere in this repository. This
tutorial covers what it actually does, why "daemonless" and "rootless" matter,
and what every flag in this project's `podman run` lines is for.

### What it does not show

- Pods, compose, or Kubernetes YAML generation. Podman does all three; none is
  needed here.
- A Docker comparison beyond the essentials.

## The two things that make Podman different

**Daemonless.** There is no background service. `podman run` forks a process
and that process *is* your container — you saw this in
[L0.3](../../demos/l0.3-authority/README.md), where the host process tree
showed:

```
   2829    2827 app
   2827       1 conmon
      1       0 systemd
```

Your container is a normal process under `conmon`, a small supervisor. Nothing
is proxying through a daemon, so a container's lifetime is tied to the process
that started it, and `podman` can run as an ordinary user.

**Rootless.** Containers run as you, not as root. Container uid 0 maps to an
unprivileged host uid from the range T1 allocated. A process that escapes its
namespace is nobody on the host.

Docker's default model is the opposite: a root daemon that clients talk to, so
anyone who can reach the socket can effectively become root.

## The command this project uses

Every `podman run` in this repository looks like this, and each flag earns its
place:

```sh
podman run --rm \
  --cap-drop=ALL \
  --security-opt=no-new-privileges \
  --read-only \
  --network=none \
  <image>
```

| Flag | What it does | Why |
| --- | --- | --- |
| `--rm` | Delete the container when it exits | Containers are disposable; keeping them is how disks fill up |
| `--cap-drop=ALL` | Empty the capability set | Most workloads need none. [L0.3](../../demos/l0.3-authority/README.md) proves the kernel then reports `CapEff: 0000000000000000` |
| `--security-opt=no-new-privileges` | Forbid privilege escalation via `setuid` | Even if a `setuid` binary existed, it could not elevate |
| `--read-only` | Root filesystem is not writable | An attacker cannot persist anything |
| `--network=none` | No network namespace at all | A hashing tool has no business making connections |

**Learn these as a default and relax them deliberately.** The usual habit is
the reverse — run with everything, restrict later — and "later" rarely arrives.

### A surprise worth knowing

`--read-only` does **not** mean nothing is writable. Podman still mounts a
tmpfs on `/tmp` and `/run` unless you say otherwise:

```sh
podman run --rm --read-only --read-only-tmpfs=false <image>
```

[L0.0](../../demos/l0.0-anatomy/README.md) covers why an image and a running
container do not contain the same things.

## Try it

```sh
podman run --rm registry.access.redhat.com/ubi9/ubi-micro:latest /bin/sh -c 'echo hello'
```

What happened, in order: Podman resolved the name, pulled the manifest and
layers if not already local, unpacked them into a container filesystem, created
namespaces, applied the security settings, and executed `/bin/sh` as pid 1
inside.

### Inspect without running

```sh
podman image inspect registry.access.redhat.com/ubi9/ubi-micro:latest \
  --format '{{.Size}} bytes, {{len .RootFS.Layers}} layer(s)'
```

```
23591424 bytes, 1 layer(s)
```

That is the image the whole of Phase 1 dissected.

### Get the filesystem out

The technique this project uses everywhere, because it works on images with no
shell:

```sh
podman create --name check registry.access.redhat.com/ubi9/ubi-micro:latest
podman export check -o rootfs.tar
podman rm check
tar -tf rootfs.tar | wc -l
```

```
877
```

`create` makes a container without starting it; `export` flattens its
filesystem to a tar. No shell is involved, so it works on
[L0](../../demos/l0.0-anatomy/README.md) images too.

### `podman unshare` and `podman mount`

Podman can do what most people associate with buildah:

```sh
podman unshare
# you are now in your user namespace; root looks like root
podman mount <container>
```

[T4](../t4-buildah/README.md) explains both terms properly and shows the
technique. The point here is only that Podman is not limited to running things.

## Podman versus Docker, briefly

| | Podman | Docker |
| --- | --- | --- |
| Daemon | none | `dockerd`, running as root |
| Rootless | default | possible, not default |
| Socket access = root | no | yes, effectively |
| CLI | near-identical | — |
| Building | `podman build`, buildah under the hood | BuildKit |

Most `docker` commands work if you `alias docker=podman`. Where this project's
commands differ, it is usually `--squash-all` (Podman) versus `--squash`
(Docker, needing experimental features).

## Security

A tool tutorial has no image to scan, but there is a security point specific to
Podman, and it is the most important one in this part:

**A vulnerability scan tells you about the image. It tells you nothing about
how the container was launched.** An image with zero CVEs run `--privileged` is
a worse outcome than one with twenty run `--cap-drop=ALL --read-only`. Only one
of those appears in a report.

That is why every tutorial in this repository shows the full `podman run` line
rather than an abbreviated one.

## Clean up

```sh
rm -f rootfs.tar
podman system prune -a     # removes unused images and containers
```

---

**Next:** [T3 — Skopeo](../t3-skopeo/README.md)
