# L0.0 — what a container image actually is

**Part one of the L0 tutorial.** Next is
[L0.1 — describe](../l0.1-describe/README.md).

> [!NOTE]
> **Verified in CI** on `ubuntu-latest` with Podman 5.x. Every command and
> output on this page was executed, not predicted.
>
> **798,905 bytes. One file.** 3.4% of the official `ubi9-micro`.

## What this shows

Before building anything interesting, it is worth knowing what an image *is*.
Not conceptually — literally. A container image is a tar file containing some
JSON and some more tar files, and you can take it apart with tools you already
have.

This rung builds the simplest possible image — one statically linked C binary,
nothing else — and then pulls it apart by hand, file by file, so that
everything later in the ladder rests on a concrete picture rather than a
metaphor.

It also settles a confusion that catches people out in production: **an image
and a running container do not contain the same things.**

### What it does not show

- The program is deliberately trivial. This rung is about the format.
- This is not an OCI specification tutorial. It shows the parts you will
  actually meet; the specification has more.
- Nothing here needs a registry. Everything happens on local files.

## Prerequisites

| Requirement | Why | Exercised against |
| --- | --- | --- |
| Podman ≥ 4.0 (or Docker ≥ 20.10) | build and `save` | Podman 5.x |
| `tar`, `sha256sum` | taking the archive apart | GNU coreutils |
| `python3` or `jq` | reading the JSON | Python 3.12 |
| Network access to `registry.access.redhat.com` | pulls the UBI 9 builder | verified |

## Build

```sh
podman build \
  --squash-all \
  --file demos/l0.0-anatomy/Containerfile \
  --tag l0.0-anatomy:9.8 \
  demos/l0.0-anatomy
```

The program is C, not C++, and prints four lines. It compiles to **794,952
bytes** — because a static link pulls in glibc whether you use much of it or
not. The equivalent C++ program at [L0.1](../l0.1-describe/README.md) is
931,144 bytes; the extra ~136 KB is libstdc++ and the unwinder.

**That is worth sitting with.** Nearly 800 KB to print four lines. Your code is
a rounding error; the C library is the image. L1 is where that changes, because
a dynamically linked binary leaves glibc on the base image instead of carrying
its own copy.

## Run

```sh
podman run --rm \
  --cap-drop=ALL \
  --security-opt=no-new-privileges \
  --read-only \
  --network=none \
  l0.0-anatomy:9.8
```

```
L0.0 — anatomy
--------------
I am the only file in this image.

Take the image apart with:
  podman save --format docker-archive -o l0.0.tar l0.0-anatomy:9.8
  tar -tvf l0.0.tar

Everything else you can see at runtime was added by the container
runtime, not by the image. That distinction is the lesson.
```

## Take it apart: the docker-archive

```sh
podman save --format docker-archive -o l0.0.tar l0.0-anatomy:9.8
tar -tf l0.0.tar
```

```
68bfec523925145c02b76fee921c15e9a78315c47e8be89b9f818372feb1d7bd.tar
4909e37357c9697f0d6d39feabef0b35fe26ea27fa526f3f6867d60ac0d3e96d.json
0505fd6da2e60476efc6a55946b94cb29a774768d2fd96a33daa0707aa47ae2a/layer.tar
0505fd6da2e60476efc6a55946b94cb29a774768d2fd96a33daa0707aa47ae2a/VERSION
0505fd6da2e60476efc6a55946b94cb29a774768d2fd96a33daa0707aa47ae2a/json
manifest.json
repositories
```

Extract it and take each part in turn:

```sh
mkdir -p unpacked && tar -xf l0.0.tar -C unpacked && cd unpacked
```

### `manifest.json` — the table of contents

```sh
python3 -m json.tool manifest.json
```

It names three things: which file is the **config**, which files are the
**layers**, and what **tags** this image was saved under. That is all a
manifest does — it is an index, not content.

### `<sha>.json` — the config

```sh
python3 -m json.tool 4909e373*.json | head -40
```

This is the image's *behaviour*: `Env`, `Cmd`, `Entrypoint`, `User`,
`WorkingDir`, the labels, the architecture, and `rootfs.diff_ids` — the digests
of the layers' **uncompressed** contents.

Two things worth noticing:

- **The config is not the filesystem.** Nothing in here is a file your program
  can open. It is instructions for the runtime.
- **The digest of this file is the image ID.** When `podman images` shows an ID,
  it is the sha256 of this JSON. An image's identity is the hash of its
  configuration, which in turn references its layers by hash.

### `layer.tar` — the actual filesystem

```sh
tar -tvf 0505fd6d*/layer.tar
```

```
-rwxr-xr-x 0/0          794952 2026-09-10 11:34 app
```

**One entry.** That is the entire filesystem of this image: a single executable,
owned by root, mode 0755. No `/`, no `/etc`, no directories at all — a layer is
just a tar, and this one has one member.

You can extract and run it directly, because it is an ordinary Linux binary:

```sh
tar -xf 0505fd6d*/layer.tar -O app > /tmp/app && chmod +x /tmp/app && /tmp/app
```

It runs on your host, with your authority. [L0.3](../l0.3-authority/README.md)
is about why that difference matters.

### `VERSION` and `repositories`

Legacy fields from the Docker v1 image format, kept for compatibility.
`VERSION` contains `1.0`. You can ignore both — which is a useful thing to know
rather than to wonder about.

## The same image as an OCI archive

The docker-archive format is Docker's. The **OCI** format is the standard, and
it is what registries actually store.

```sh
cd .. && podman save --format oci-archive -o l0.0-oci.tar l0.0-anatomy:9.8
mkdir -p oci && tar -xf l0.0-oci.tar -C oci && find oci -type f | sort
```

```
oci/blobs/sha256/3d11383446cf083fc0c55c0d21375263d054858efc31607ff4b5c226b6d58959
oci/blobs/sha256/4909e37357c9697f0d6d39feabef0b35fe26ea27fa526f3f6867d60ac0d3e96d
oci/blobs/sha256/cddcbc9e5fc1d0235c507b196aa69aad0032e50e9413cb897a2e9ec8da285583
oci/index.json
oci/oci-layout
```

Different shape, same information:

| File | What it is |
| --- | --- |
| `oci-layout` | Declares the layout version. Two lines. |
| `index.json` | The entry point — points at a manifest blob by digest. |
| `blobs/sha256/…` | Everything else: the manifest, the config, the layer. All three, undifferentiated. |

Follow the chain yourself — `index.json` → manifest blob → config and layer
blobs:

```sh
python3 -m json.tool oci/index.json
```

Every blob is named by its own digest, so nothing needs a filename. **You can
verify that:**

```sh
for blob in oci/blobs/sha256/*; do
  echo "$(basename "$blob")  vs  $(sha256sum "$blob" | cut -d' ' -f1)"
done
```

CI does exactly this on every push:

```
3 blob(s) hash to their own filename, 0 mismatched
```

**This is content addressing, and it is the whole security model of container
distribution.** A digest is not a label someone attached — it is what the bytes
*are*. If a registry, a proxy, or a mirror alters one byte of a layer, its
digest changes and the reference no longer resolves. It is also why this
project pins images by digest rather than tag: a tag is a mutable pointer, a
digest is the content.

## The lesson: an image is not a container

Here is the part that catches people out. The image holds **one file**. Now
look at what the running container has:

```sh
podman run --rm --cap-drop=ALL --read-only l0.3-authority:9.8
```

```
  read /etc/passwd             ALLOWED   read 1 user accounts
  list /                       ALLOWED   10 entries visible at /
  write to /tmp                ALLOWED   created and removed a file
```

Ten entries at `/`, a readable `/etc/passwd`, and a writable `/tmp` — **none of
which are in the archive you just unpacked.** The runtime supplies them:

| What appears | Where it comes from |
| --- | --- |
| `/proc`, `/sys`, `/dev` | Mounted by the runtime; the kernel's interfaces, not files in your image. |
| `/etc/passwd`, `/etc/group` | Injected by Podman so a declared `USER` resolves to a name. One entry, not your host's. |
| `/etc/hosts`, `/etc/resolv.conf` | Injected for networking — absent under `--network=none`. |
| `/tmp`, `/run` | tmpfs, mounted because `--read-only-tmpfs` defaults on. Empty, in memory, gone at exit. |

So **"my image contains nothing" and "my container has a writable `/tmp` and a
`/etc/passwd`" are both true at once.** They describe different things.

This matters in practice. When you audit an image you are auditing the archive.
When you reason about what a process can reach, you must reason about the
launch as well. A scanner reads the first and knows nothing about the second.

Want the tmpfs gone too? `--read-only-tmpfs=false`.

## Review the contents

```sh
podman create --name check l0.0-anatomy:9.8
podman export check -o rootfs.tar
podman rm check
python scripts/verify_image.py rootfs.tar --expect-entries 1
```

Note `podman export` gives you the *container's* filesystem, flattened — which
for a created-but-never-started container is the image's filesystem. It is the
technique that scales to any image, and it is how CI verifies every rung.

```sh
demos/l0.0-anatomy/verify.sh l0.0-anatomy:9.8
```

Runs every check on this page: archive structure, one entry in the layer, OCI
layout, content addressing, and the image-versus-container gap.

## Security

```sh
scripts/security_scan.sh l0.0-anatomy:9.8
```

Zero components, zero vulnerabilities — and, as at every L0 rung, that is an
absence of *visibility* rather than of risk. [L0.2's security
section](../l0.2-sha256/README.md#security) explains it in full.

There is an anatomy-specific point. You now know an SBOM tool reads the layer
tar and looks for package metadata. This image's layer has one file and no
metadata, so there is nothing to find. The scanner is not failing; it is
correctly reporting that the image tells it nothing.

## Where this sits on the ladder

| Rung | Image bytes | Entries | Components | Vulns |
| --- | ---: | ---: | ---: | ---: |
| **L0.0 anatomy (C)** | **798,905** | **1** | **0** | **0** |
| L0.1 describe (C++) | 934,974 | 1 | 0 | 0 |
| L0.2 SHA-256 | 939,069 | 1 | 0 | 0 |
| L0.3 authority | ~939,000 | 1 | 0 | 0 |
| WP6 `micro` reconstruction | 23,585,791 | 871 | 22 | 23 |
| Official `ubi9-micro` | 23,591,424 | 877 | — | — |

## Clean up

```sh
podman rmi l0.0-anatomy:9.8
rm -rf unpacked oci l0.0.tar l0.0-oci.tar rootfs.tar /tmp/app
rm -rf security-results
```

---

**Next:** [L0.1 — a container that describes itself](../l0.1-describe/README.md)
