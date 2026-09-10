# T4 — Buildah, and what `unshare` and `mount` actually mean

**Part 4 of the toolkit.** Previous: [T3](../t3-skopeo/README.md).
Next: [T5 — Umoci](../t5-umoci/README.md).

> [!NOTE]
> Verified against buildah 1.33.7 in CI. Every output below was executed,
> including the failure.

## What this shows

How to build a container image **without a Containerfile**, by assembling its
filesystem directly with ordinary host tools.

This is not a curiosity. It is how `ubi9-micro` was built — the dissection
found `io.buildah.version: 1.44.0` in the official image's labels — and it is
the only way to build an image that contains no shell.

### Why a Containerfile cannot do this

```dockerfile
FROM scratch
RUN echo hello        # fails: there is no shell in scratch to run this
```

`RUN` executes a command **inside the image being built**. An empty image has
nothing to execute it with. So an image with no shell and no package manager
cannot be built by running commands in it — it has to be assembled from
outside.

## The two words

### `mount`

Makes a container's filesystem appear as an ordinary directory on the host.
Once it is a directory, `cp`, `tar`, `install`, `sed` and everything else work
on it normally. **Nothing runs inside the container.**

### `unshare`

Puts your shell inside the container's **user namespace**.

In a rootless setup your uid 1000 is mapped to a range of host uids — the
`subuid` allocation from [T1](../t1-dev-environment/README.md). A file the
image says is owned by `root` (uid 0) is really owned by a high host uid like
166535. Without entering that namespace you see confusing ownership and cannot
set it correctly.

`unshare` makes the mapping apply to your shell too, so **root looks like root**
and file ownership works the way the image will see it.

## Install

```sh
sudo apt-get install -y buildah     # WSL2 Ubuntu / Debian
sudo dnf install -y buildah         # RHEL / Fedora / CentOS Stream
```

## Why `unshare` is not optional

Try mounting without it:

```sh
ctr=$(buildah from scratch)
buildah mount $ctr
```

Observed:

```
-> no path returned. Rootless mounting needs the user namespace.
```

No error dialogue, no explanation — just nothing useful. This is the failure
most people hit, and it is why the two commands are almost always seen
together.

## Build an image from nothing

```sh
buildah unshare bash -c '
    ctr=$(buildah from scratch)
    mnt=$(buildah mount "$ctr")

    install -D -m 0755 /bin/true "$mnt/app"

    buildah config --cmd /app --label demo=true "$ctr"
    buildah umount "$ctr"
    buildah commit "$ctr" buildah-demo:latest
    buildah rm "$ctr"
'
```

Observed:

```
  working container: working-container
  mounted at: /home/runner/.local/share/containers/storage/overlay/2b25e0d7.../merged
  (an ordinary directory — the HOST's tools work on it)
  copied /bin/true in with install(1); contents now:
    ./app
  metadata set with buildah config, no Containerfile involved
c335c82de8a8f715bdc36cb2263f62e657cf0f8cd55defde0e2ff07ae3cf2333
```

```sh
podman image inspect buildah-demo:latest --format '{{.Size}} bytes, {{len .RootFS.Layers}} layer'
```

```
30019 bytes, 1 layer
```

Read that sequence again, because every line is doing something a Containerfile
cannot:

| Command | What it did |
| --- | --- |
| `buildah from scratch` | Created a **working container** with no base image at all |
| `buildah mount` | Gave you its filesystem as a host directory |
| `install -D -m0755` | Populated it with the **host's** `install(1)` — no shell in the target |
| `buildah config` | Set `Cmd` and a label imperatively, no `LABEL` instruction |
| `buildah commit` | Turned the working container into an image |

The result is a 30 KB image containing one file, and at no point did anything
execute inside it.

## Podman does this too

The operations are the same, and the two share storage — a container created by
one is visible to the other:

```sh
podman unshare      # same as buildah unshare
podman mount        # same as buildah mount
podman commit       # same as buildah commit
```

So what is buildah *for*?

| | Podman | Buildah |
| --- | --- | --- |
| Built for | running containers | building images |
| Starting from nothing | needs an image to create from | `buildah from scratch` |
| Setting metadata | `podman commit --change ...` | `buildah config`, directly |
| Granularity | image in, image out | a working container you edit step by step |
| `podman build` | *is buildah, used as a library* | — |

**The difference is ergonomics, not capability.** If you are scripting the
construction of an image — especially one starting from `scratch` — buildah's
model fits. If you are running containers and occasionally need to poke at one,
Podman already has what you need.

## When to reach for this

- **Building an image with no shell.** The case this project is about.
- **Copying in files with exact ownership and modes** that a `COPY` instruction
  would not preserve.
- **Editing an image you cannot rebuild** — mount it, change one file, commit.
- **Scripted assembly** where the logic is easier in shell than in Containerfile
  syntax.

For most application images a Containerfile is clearer and you should use one.
Reach for this when the image is *assembled* rather than *installed into*.

## Security

Two points worth internalising:

**Rootless by default.** Everything above ran as an unprivileged user. The
files written as "root" inside the image are owned by a mapped host uid that
owns nothing else. Compare this with the traditional approach of building
images as root.

**No daemon, no socket.** There is no privileged service to compromise and no
socket whose access is equivalent to root.

**The caveat:** mounting a container's filesystem and editing it bypasses
everything a Containerfile records. There is no build history, no cached layer
explaining what happened. If you use this technique, the build **script** is
your only record — commit it, and treat it as you would a Containerfile.

That is not hypothetical. It is exactly the situation this project's Phase 1
faced: `ubi9-micro`'s Containerfile contains no `RUN`, so the interesting work
left no trace in the image, and recovering it took the dnf history database.

## Clean up

```sh
podman rmi buildah-demo:latest
buildah rm --all
```

---

**Next:** [T5 — Umoci](../t5-umoci/README.md)
