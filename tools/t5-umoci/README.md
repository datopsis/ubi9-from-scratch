# T5 — Umoci

**Part 5 of the toolkit.** Previous: [T4](../t4-buildah/README.md).
Next: [T6 — Syft](../t6-syft/README.md).

> [!NOTE]
> Verified against umoci 0.4.7 in CI. Every output below was executed,
> including the flag mistake.

## What this shows

Umoci opens an **OCI image layout** — unpacking it to a root filesystem you can
inspect or modify, and packing it back up. Where skopeo *moves* images, umoci
*opens* them.

### What it does not show

- Building images from scratch. That is [buildah](../t4-buildah/README.md).
- Running containers. Umoci produces an OCI *bundle*, which a low-level runtime
  like `runc` or `crun` can run — but that is a layer below Podman.

## Install

Not packaged by Ubuntu or RHEL. Use the release binary and pin the version:

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

## Get a layout to work on

Umoci operates on an OCI layout directory, not on a registry or on Podman's
storage. Produce one as [T3](../t3-skopeo/README.md) showed:

```sh
podman save --format oci-archive -o image.tar l0.2-sha256:9.8
skopeo copy oci-archive:image.tar oci:./oci-layout:demo
```

## What is in the layout?

```sh
umoci list --layout ./oci-layout
```

```
demo
```

One tag. A layout can hold several images; `list` shows their tags.

### The flag trap

This is worth showing because it catches everyone once:

```sh
umoci stat --layout ./oci-layout --image demo --json
```

```
Incorrect Usage: flag provided but not defined: -layout
```

**Only `list` takes `--layout`.** Every other subcommand takes `--image` with
the layout path and tag joined by a colon:

```sh
umoci stat --image ./oci-layout:demo --json
```

```json
{"history":[
  {"created":"2026-09-10T13:02:00.949351763Z",
   "created_by":"/bin/sh -c #(nop) COPY file:90fc8a40... in /app ",
   "empty_layer":true},
  {"created":"2026-09-10T13:02:00.949380106Z",
   "created_by":"/bin/sh -c #(nop) USER 1000:1000",
   "empty_layer":true},
  ...
]}
```

That is the same build history [L0.0](../../demos/l0.0-anatomy/README.md)
read out of the config blob by hand — and the same structure Phase 1 used to
discover that `ubi9-micro`'s Containerfile contains no `RUN` instruction.

## Unpack it

```sh
umoci unpack --rootless --image ./oci-layout:demo ./bundle
```

```
./bundle/
  config.json
  rootfs/
  sha256_bd9b0970....mtree
  umoci.json
```

```sh
find ./bundle/rootfs -mindepth 1
```

```
./app
```

One file — the L0.2 binary. What umoci produced is an **OCI runtime bundle**:

| File | What it is |
| --- | --- |
| `rootfs/` | The unpacked filesystem, as the container will see it |
| `config.json` | The OCI *runtime* spec — namespaces, mounts, capabilities. Different from the image config. |
| `*.mtree` | A manifest of every file's metadata, so `repack` knows what changed |
| `umoci.json` | Umoci's own bookkeeping |

`--rootless` matters: without it umoci tries to restore ownership it cannot set
as an unprivileged user.

### Modify and repack

The reason to unpack at all:

```sh
echo "a new file" > ./bundle/rootfs/extra.txt
umoci repack --image ./oci-layout:modified ./bundle
umoci list --layout ./oci-layout
```

The `.mtree` file is how repack knows only `extra.txt` was added, so it
produces a new layer with just that change rather than rewriting everything.

## When to reach for this

- **Inspecting an image's runtime config** without running it.
- **Modifying an image you cannot rebuild** — a vendor image needing one file
  changed.
- **Producing a bundle for a low-level runtime**, if you are working below
  Podman.
- **Reproducibility work.** The `.mtree` manifest records every file's metadata,
  which makes "what actually changed between these two images" answerable.

For everyday work you will reach for skopeo and podman far more often. Umoci is
the tool for when you need to be *inside* the layout.

## Umoci and skopeo together

They are complementary, and the pairing is worth remembering:

```
registry ──skopeo──▶ OCI layout ──umoci──▶ rootfs you can edit
                          ▲                       │
                          └────────umoci──────────┘
                                  repack
```

Skopeo speaks to registries and converts between formats. Umoci opens what
skopeo produces. Neither needs a daemon or root.

## Security

Umoci's `--rootless` mode is the important flag: unpacking an untrusted image
as root is a genuine risk, because a malicious layer can contain device nodes,
setuid binaries or paths that escape the target directory. Rootless unpacking
cannot create those.

The `.mtree` manifest also has a security use: it is a detailed record of every
file's metadata, so comparing two of them detects changes a size or digest
comparison would miss. That is the same class of evidence this project's
[`scripts/compare.py`](../../scripts/compare.py) produces when checking a
rebuild against the original.

## Clean up

```sh
rm -rf oci-layout bundle image.tar
```

---

**Next:** [T6 — Syft](../t6-syft/README.md)
