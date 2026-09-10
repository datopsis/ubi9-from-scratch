# T3 — Skopeo

**Part 3 of the toolkit.** Previous: [T2](../t2-podman/README.md).
Next: [T4 — Buildah](../t4-buildah/README.md).

> [!NOTE]
> Verified against skopeo 1.13.3 in CI. Every output below was executed.

## What this shows

Skopeo answers questions about images **without pulling them and without a
container engine**. It is the right tool for asking a registry something, and
for moving images between registries and archive formats.

### What it does not show

- Running containers. Skopeo cannot; that is Podman's job.
- Building images. That is [buildah](../t4-buildah/README.md).

## Install

```sh
sudo apt-get install -y skopeo     # WSL2 Ubuntu / Debian
sudo dnf install -y skopeo         # RHEL / Fedora / CentOS Stream
```

## Ask a registry a question

The most useful thing skopeo does. **No layers are downloaded.**

```sh
skopeo inspect docker://registry.access.redhat.com/ubi9/ubi-micro:latest | jq '{Digest, Created, Architecture, Os}'
```

```json
{
  "Digest": "sha256:f332c99eb8f798a8486821c91937f10ad64ee83d7e739303be2df051040918f6",
  "Created": "2026-08-26T21:14:05.021777547Z",
  "Architecture": "amd64",
  "Os": "linux"
}
```

**That digest is the subject of this entire project.** Phase 1 obtained it by
speaking the registry API directly in Python; skopeo gets the same answer in
one command, which is a useful independent confirmation.

### Resolve a tag to a digest

The operation everything in this repository depends on:

```sh
skopeo inspect --format '{{.Digest}}' \
  docker://registry.access.redhat.com/ubi9/ubi-micro:latest
```

```
sha256:f332c99eb8f798a8486821c91937f10ad64ee83d7e739303be2df051040918f6
```

A tag is a **mutable pointer**; a digest is the content itself. Red Hat rebuilds
UBI images regularly, so `:latest` means something different next month. Pin
the digest and your build is reproducible:

```sh
podman run registry.access.redhat.com/ubi9/ubi-micro@sha256:f332c99e...
```

That is exactly what [L1's Containerfile](../../demos/l1-dynamic/Containerfile)
does.

### See the raw manifest

```sh
skopeo inspect --raw docker://registry.access.redhat.com/ubi9/ubi-micro:latest | jq .
```

```json
{
  "schemaVersion": 2,
  "mediaType": "application/vnd.docker.distribution.manifest.list.v2+json",
  "manifests": [
    { "digest": "sha256:a8296f84...", "platform": {"architecture": "amd64", "os": "linux"} },
    { "digest": "sha256:56c0fe27...", "platform": {"architecture": "arm64", "os": "linux", "variant": "v8"} },
    ...
  ]
}
```

This is a **manifest list** — one name covering four architectures. `--raw`
gives you the bytes the registry stores; without it, skopeo resolves to your
platform and shows you a friendlier summary. When you need to know what a
multi-arch image really contains, `--raw` is the flag.

## Move an image

```sh
podman save --format oci-archive -o image.tar l0.2-sha256:9.8
skopeo copy oci-archive:image.tar oci:./oci-layout:demo
```

```
Copying blob sha256:1d6fc11366b9...
Copying config sha256:6aaaefaeab91...
Writing manifest to image destination
```

```
./blobs/sha256/1d6fc11366b976296ccde4ffcd1c36e7857813da150aea1ead1ce551ca3bf4bc
./blobs/sha256/20f694357673f90aa4a8d2970e57c56641eb878b3534f936c9bcbb32ade64eaa
./blobs/sha256/6aaaefaeab91b9dc8eae968dc03720e6a2a2763670140c27567db945abf2abe7
./index.json
./oci-layout
```

That layout is what [L0.0](../../demos/l0.0-anatomy/README.md) took apart by
hand, and what [umoci](../t5-umoci/README.md) opens next.

### Transports

The `thing:` prefix is a **transport** — where skopeo should look:

| Transport | Means |
| --- | --- |
| `docker://` | a registry, over the network |
| `containers-storage:` | your local Podman/buildah storage |
| `oci:path:tag` | an OCI layout directory |
| `oci-archive:file.tar` | an OCI layout in a tar |
| `docker-archive:file.tar` | the older Docker save format |
| `dir:path` | blobs in a plain directory |

Copying between any two is one command, which is what makes skopeo the glue
between registries, CI and air-gapped environments.

### A trap worth knowing

Reading `containers-storage:` directly fails rootless without a user namespace:

```sh
skopeo copy containers-storage:l0.2-sha256:9.8 oci:./out:demo
```

```
Error during unshare(...): Operation not permitted
```

Two fixes: run it inside `podman unshare`, or export to an archive first as
above. The archive route works everywhere and needs no privileges, which is why
this project uses it. [T4](../t4-buildah/README.md) explains what `unshare`
means.

## Why this matters here

Skopeo is how you would do Phase 1's acquisition step in one line rather than
in Python. This project implemented it manually so the mechanics were visible —
verify a digest by recomputing it, follow the manifest list yourself — but for
day-to-day work, skopeo is the tool.

It is also the right answer for:

- checking whether a base image has been rebuilt, without pulling gigabytes;
- copying images into an air-gapped environment via a tar file;
- mirroring between registries in CI without a container engine installed.

## Security

Skopeo verifies digests as it copies — a corrupted or tampered blob fails
rather than being written. It can also check signatures
(`--policy`, `/etc/containers/policy.json`), which is how a registry's content
trust is enforced.

The habit worth forming: **always pin by digest in anything automated.**
`:latest` in a Containerfile means your build is not reproducible and a
compromised tag silently changes what you ship.

## Clean up

```sh
rm -rf oci-layout image.tar
```

---

**Next:** [T4 — Buildah](../t4-buildah/README.md)
