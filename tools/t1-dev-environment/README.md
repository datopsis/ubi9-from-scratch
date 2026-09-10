# T1 — Your development environment

**Part 1 of the toolkit.** Next is [T2 — Podman](../t2-podman/README.md).

> [!NOTE]
> The `apt` commands are verified on `ubuntu-latest` in CI. The `dnf` commands
> are verified by running them inside a `ubi9` container. Neither set is
> transcribed from documentation.

## What this shows

Getting from a clean machine to one that can build, run and inspect containers
— rootless, with nothing running as a daemon.

### What it does not show

- Kubernetes, or any orchestrator. Everything here is a single machine.
- Docker. This project is Podman-first; the differences are noted where they
  matter, but teaching both doubles the surface area without doubling what you
  learn.

## Where to work

**On Windows: use WSL2.** The Python analysis scripts in this repository run
natively on Windows, but every container operation needs a Linux kernel —
namespaces, cgroups and capabilities are kernel features, and there is no
portable substitute.

```powershell
wsl --install -d Ubuntu
wsl -d Ubuntu
```

If WSL2 is already installed, check you are on version 2:

```powershell
wsl -l -v
```

`VERSION` must be `2`. WSL1 does not have the kernel features containers need.

**On macOS:** Podman runs a Linux VM for you (`podman machine init`). The
commands below then work inside it.

## Install

### WSL2 Ubuntu / Debian

```sh
sudo apt-get update
sudo apt-get install -y podman skopeo buildah jq
```

Verified output:

```
podman version 4.9.3
skopeo version 1.13.3
buildah version 1.33.7 (image-spec 1.1.0-rc.5, runtime-spec 1.1.0)
jq-1.7
```

### Red Hat Enterprise Linux / Fedora / CentOS Stream

```sh
sudo dnf install -y podman skopeo buildah jq
```

On RHEL these are in the standard AppStream repository — no subscription beyond
the base one, and no third-party repo.

### umoci — no distribution package

Not packaged by Ubuntu or RHEL. Install the release binary:

```sh
UMOCI_VERSION=v0.4.7
curl -sSfL -o /tmp/umoci \
  "https://github.com/opencontainers/umoci/releases/download/${UMOCI_VERSION}/umoci.amd64"
sudo install -m0755 /tmp/umoci /usr/local/bin/umoci
umoci --version
```

```
umoci version 0.4.7
```

Pin the version rather than fetching `latest` — the same reason this project
pins images by digest.

### syft and grype

```sh
curl -sSfL https://get.anchore.io/syft  | sudo sh -s -- -b /usr/local/bin
curl -sSfL https://get.anchore.io/grype | sudo sh -s -- -b /usr/local/bin
```

> [!WARNING]
> That pattern pipes a script from the internet into a shell. It is what the
> vendor documents, and it is what CI does here, but you should know what you
> are accepting. To inspect first:
> ```sh
> curl -sSfL https://get.anchore.io/syft -o syft-install.sh
> less syft-install.sh
> sudo sh syft-install.sh -b /usr/local/bin
> ```
> Both tools also publish signed release archives if you prefer those.

## Verify rootless works

This is the step people skip and then debug for an hour.

```sh
podman info --format '{{.Host.Security.Rootless}}'
```

Expect `true`. If it says `false` you are running as root, which works but is
not what this project's tutorials assume.

### The uid mapping

Rootless containers need a range of subordinate uids and gids allocated to you:

```sh
grep "^$USER:" /etc/subuid /etc/subgid
```

Expect something like:

```
/etc/subuid:youruser:100000:65536
/etc/subgid:youruser:100000:65536
```

**If those lines are missing, rootless containers will fail** with errors about
`newuidmap` or "no subuid ranges found". Fix it:

```sh
sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 "$USER"
podman system migrate
```

This is what makes a container's `root` map to an unprivileged host uid. When
[L0.3](../../demos/l0.3-authority/README.md) shows a container process owned by
host uid `166535`, this allocation is why.

### On WSL2 specifically

Two things commonly bite:

- **systemd.** Older WSL2 setups run without it. Podman mostly works anyway,
  but socket activation does not. Enable it in `/etc/wsl.conf`:
  ```ini
  [boot]
  systemd=true
  ```
  Then `wsl --shutdown` from PowerShell and restart the distribution.
- **Filesystem performance.** Working under `/mnt/c` is slow and loses Linux
  permissions. Clone this repository into the WSL2 filesystem (`~/`), not into
  a Windows drive.

## Smoke test

```sh
podman run --rm registry.access.redhat.com/ubi9/ubi-micro:latest /bin/sh -c 'echo it works'
```

```
it works
```

That command pulls a real image, starts a container, runs a shell in it, and
cleans up. If it works, everything in this repository will.

Now try it the way this project does — rootless, no capabilities, read-only
root, no network:

```sh
podman run --rm \
  --cap-drop=ALL \
  --security-opt=no-new-privileges \
  --read-only \
  --network=none \
  registry.access.redhat.com/ubi9/ubi-micro:latest /bin/sh -c 'echo still works'
```

If that also works, your setup is not just functional but correctly confined.
[T2](../t2-podman/README.md) explains what each of those flags does.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `newuidmap: write to uid_map failed` | No subuid range | The `usermod` command above |
| `Error: OCI runtime error` on WSL2 | cgroups v2 not available | Update WSL (`wsl --update`) |
| Very slow builds | Working under `/mnt/c` | Move the repo into the WSL2 filesystem |
| `short-name did not resolve` | Podman refuses ambiguous image names | Use the fully qualified name, as every command here does |
| Permission denied on a bind mount | uid mapping | Add `--userns=keep-id` |

## Clean up

Nothing to undo — this tutorial only installed tools. To reclaim space later:

```sh
podman system prune -a
```

---

**Next:** [T2 — Podman](../t2-podman/README.md)
