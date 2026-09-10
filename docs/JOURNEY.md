# The journey: from the official image to a rebuild

This is the narrative version of the dissection. It follows the order the work
actually happened in, including the assumptions that turned out to be wrong,
because the wrong turns are where most of the useful information came from.

`docs/FINDINGS.md` holds the same results as numbered, evidence-backed
statements. This document explains how we reached them and what each one
changed about the plan.

## Stage 0 — The question

Red Hat describes UBI Micro as a "very small image which doesn't install the
package manager". That description raises an obvious problem: if the image has
no package manager, nothing inside it can install anything, so it cannot have
been built the way an ordinary application image is built. Something outside
must have assembled its root filesystem.

The goal was to find out exactly what, and then do the same thing ourselves.

## Stage 1 — Pin the subject before touching it

The first decision was to work from a digest rather than a tag. Red Hat
rebuilds UBI images regularly, and `ubi9/ubi-micro:latest` is a moving target.
Any note that says "latest" becomes unreproducible the moment Red Hat ships a
new build.

We also chose to talk to the registry's HTTP API directly rather than through a
container runtime. A runtime reports its own view of an image — normalised,
sometimes re-compressed, filtered through its storage driver. The registry API
returns the bytes as published.

That gave us the subject, with every digest verified by recomputing SHA-256
locally rather than trusting the `Docker-Content-Digest` header:

```
manifest list  sha256:f332c99e...  970 B     (4 architectures)
  amd64        sha256:a8296f84...  428 B
  config       sha256:9a25cf5f...  4,879 B
  layer        sha256:44bb90d0...  7,253,582 B gzip
  diff_id      sha256:49d88c5f...  23,591,424 B uncompressed
```

**The size to match is 23,591,424 bytes uncompressed — 22.50 MiB — from a
7,253,582-byte download.** The uncompressed figure is the one a rebuild has to
answer for; the compressed figure depends on gzip settings and will differ even
when the contents are identical.

## Stage 2 — Read the image's own account of itself

The config blob was 4,879 bytes, which is large for an image this small. That
turned out to be the most informative thing we read all day.

The history has nineteen entries. Eighteen are marked `empty_layer: true` and
the manifest lists exactly one layer, so **the image is squashed**. But history
survives squashing, and it records the original build steps:

```
14 x LABEL ...
COPY dir:21269f5d...  in /
COPY file:1376702515d5...  in /etc/yum.repos.d/
CMD /bin/sh
COPY dir:95f81fb2...  in /usr/share/buildinfo/
COPY dir:95f81fb2...  in /root/buildinfo/
LABEL build-date, vcs-ref, release
```

There is no `RUN` instruction anywhere. The Containerfile that produced this
image does nothing but copy directories in and set metadata. The entire root
filesystem arrives as `dir:21269f5d...`, already built, from somewhere the
image does not describe.

That confirmed the Stage 0 suspicion and reframed the project. The interesting
work is not in the Containerfile at all — it is in whatever produced that
directory. Everything after this point is an attempt to reconstruct a build
step that leaves no direct trace.

One immediate correction fell out here. `Cmd` is `["/bin/sh","-c","/bin/sh"]`,
and `/bin` is a symlink to `usr/bin` while `/usr/bin/sh` is a symlink to
`bash`, so **UBI Micro does ship a shell** — a real 1.39 MB bash binary. The
widely repeated "no shell" claim about UBI Micro is wrong. It is the *package
manager* that is absent.

## Stage 3 — Inventory the filesystem without extracting it

The obvious next step is to unpack the layer and walk the tree. We did not do
that, for a reason worth recording.

Extracting a container layer onto a filesystem tells you what that filesystem
was willing to preserve. Modes, ownership and extended attributes survive on
Linux and quietly vanish on Windows; extraction as a non-root user loses
ownership everywhere. The resulting inventory would describe the extraction,
not the image.

The tar headers, by contrast, are the image's own record. Reading them directly
is both more faithful and portable to any host. 877 entries came back:

| Entry type | Count |
| --- | ---: |
| Directories | 317 |
| Files | 432 |
| Symlinks | 107 |
| Hardlinks | 21 |
| Apparent file bytes | 22,998,982 |

And three numbers that are all zero: **no setuid entries, no setgid entries, no
file capabilities.** For a base image that is a genuinely strong starting
posture, and it is a property the reconstruction must not accidentally break —
a careless `microdnf` invocation pulling a different package set can
reintroduce setuid binaries without anyone noticing.

Exactly one entry is not owned by `root:root`: `/var/spool/mail`, mode 0775,
owner `root:mail`. That is a `setup` package artifact rather than a decision
anyone made about this image.

## Stage 4 — The database that should not have been there

The largest file in the image is not a library or a binary. It is
`/var/lib/rpm/rpmdb.sqlite`, at 7,405,568 bytes — **31.4% of the entire
uncompressed image**. Add `/var/lib/dnf/history.sqlite` and its write-ahead log
and package metadata accounts for roughly 36% of UBI Micro.

This is the project's luckiest break and its biggest open problem at once.

The lucky part: an image with no package manager still ships a complete record
of its own package transaction. We do not have to infer what was installed from
file layout and guesswork — we can read the answer. Parsing the header blobs
out of the sqlite database (the sqlite backend stores them without the 8-byte
lead magic, which cost us one wrong assumption) yields twenty packages and two
imported GPG keys, from seventeen source RPMs:

```
basesystem  bash  coreutils-single  filesystem  glibc  glibc-common
glibc-minimal-langpack  libacl  libattr  libcap  libgcc  libselinux
libsepol  ncurses-base  ncurses-libs  pcre2  pcre2-syntax
redhat-release  setup  tzdata
```

That is the shopping list, and it is the single most useful thing the
dissection produced.

The problem: 7.4 MB of sqlite is not byte-reproducible. Database page layout,
install transaction IDs and internal timestamps all differ between runs. So
even a rebuild that installs precisely these twenty packages from precisely
these RPMs will not produce a byte-identical layer, and the difference will be
measured in megabytes rather than bytes. Any comparison has to treat the rpmdb
as a separately accounted region rather than expecting it to match.

## Stage 5 — A size that agreed for the wrong reason

The rpmdb declares 23,046,779 unpacked bytes. We had measured 22,998,982 from
the tar headers. A gap of 47,797 bytes across 23 MB looked like confirmation
that the picture was consistent.

It was not. `bash` declares 7,738,778 bytes unpacked, but the bash binary in
the image is 1,389,072 bytes. Checking the documentation paths explained why:
`/usr/share/doc` and `/usr/share/info` each contain exactly one entry — the
empty directory itself — while `/usr/share/licenses` retains 30. Documentation
was stripped at install time (`--nodocs`), with licences deliberately kept.

So the packages declare several megabytes that are not present, and the image
carries 7.4 MB of rpmdb that no package declares. The two errors are of similar
size and cancel. The totals agreeing was a coincidence that would have hidden
both facts had we accepted it.

The lesson generalises: an aggregate that matches is not evidence that the
parts match. Per-package size claims need the `Basenames` table, which is still
outstanding.

## Stage 6 — What a reconstruction has to do

Putting the stages together, the build that produced this image was:

1. In a **build container that has `microdnf`**, install the package set into a
   directory with `--installroot`, excluding documentation and weak
   dependencies, against RHEL 9 BaseOS.
2. Take that directory and `COPY` it into an image whose base is `scratch`, so
   the result inherits nothing and contains no package manager.
3. Add `/etc/yum.repos.d/ubi.repo` pointing at the public UBI mirrors — added
   *after* the rootfs, and pointing somewhere other than where the build itself
   drew from.
4. Set `CMD ["/bin/sh"]` and the `PATH`-only environment.
5. Write the buildinfo pair to both `/usr/share/buildinfo/` and
   `/root/buildinfo/`.
6. Apply 22 labels and squash to a single layer.

Steps 2 through 6 are mechanical. Step 1 is the whole game, and one detail of
it is still open: **we know all twenty installed packages, but not which were
named explicitly and which the resolver pulled in.** That distinction matters.
Naming all twenty in a reconstruction would freeze versions Red Hat left to
dependency resolution, producing an image that looks identical today and
diverges at the next rebuild for reasons nobody will remember. Answering it
needs the `Requirename` and `Providename` tables.

## Stage 7 — What can never match, and why that is fine

Some differences are structural and should be documented rather than chased:

- **Source repositories differ.** The buildinfo names
  `rhel-9-for-x86_64-baseos-rpms`, an internal subscription content set. A
  rebuild outside Red Hat draws from the public `cdn-ubi.redhat.com` mirrors.
  The RPMs should be the same builds, but that is an assumption to verify
  rather than a given.
- **The rpmdb will differ**, for the reasons in Stage 4 — several megabytes of
  unavoidable difference.
- **Timestamps and build identity.** `build-date`, `vcs-ref` (`f4a035c7...`)
  and `release` (`1787778798`) refer to Red Hat's own build system and cannot
  be meaningfully reproduced.

A reconstruction that matches the file inventory, the package set, the
permissions and the security posture — while differing in the rpmdb bytes and
the build identity — is a success. Claiming a byte-identical rebuild would
require hiding the rpmdb difference, and that is exactly the kind of result
this repository exists not to produce.

## Where the journey stands

Stages 1 through 5 are done and reproducible from `scripts/`. The
reconstruction has not been attempted, because building it needs a Linux
container runtime and the resolver question from Stage 6 should be settled
first — it determines what the build command actually says.
