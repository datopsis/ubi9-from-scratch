# Findings

Results of the dissection. Every entry states how it was obtained and is
reproducible with the scripts in `scripts/`.

**Subject (WP1).** `registry.access.redhat.com/ubi9/ubi-micro`, resolved from
`:latest` on 2026-09-09 and pinned thereafter:

| Object | Digest | Size |
| --- | --- | ---: |
| Manifest list | `sha256:f332c99eb8f798a8486821c91937f10ad64ee83d7e739303be2df051040918f6` | 970 B |
| Manifest (amd64) | `sha256:a8296f84d6218b865e829dc5150cd82e903d7027ab7d50da283a8ec98a02a336` | 428 B |
| Config | `sha256:9a25cf5f233eab241d2488a39f4e815a7981155fa4367f71ff0e1b81caaa9e62` | 4,879 B |
| Layer (gzip) | `sha256:44bb90d0dc2d3c7487076e80e560778499b9e86c5c8709287bce0be56c5fb385` | 7,253,582 B |
| Layer (diff_id) | `sha256:49d88c5f8e857b7f1f820fe9d675e242502575a82be998cf9e18f6ef83f00e0d` | 23,591,424 B |

Also published for `arm64/v8`, `s390x`, and `ppc64le`. RHEL 9.8 (Plow),
release `1787778798`, built 2026-08-26T21:13:51Z from git `f4a035c7`.

Every digest above was verified by recomputing SHA-256 over the retrieved
bytes; the registry's `Docker-Content-Digest` was checked but not trusted on
its own.

## Observed

**F1 — The image is squashed to one layer.** The config carries nineteen
history entries; eighteen are `empty_layer: true` and one is not. Reproducer:
`jq '.history' work/config.json`.

**F2 — The Containerfile only copies and labels.** The history records
fourteen `LABEL` instructions, `COPY dir:… in /` for the whole root
filesystem, `COPY file:… in /etc/yum.repos.d/`, `CMD /bin/sh`, two `COPY`
instructions placing an identical directory hash at `/usr/share/buildinfo/`
and `/root/buildinfo/`, and a closing `LABEL`. No `RUN` instruction appears.
The root filesystem is therefore built outside this Containerfile.

**F3 — Built with Buildah 1.44.0.** `io.buildah.version` in
`/root/buildinfo/labels.json`.

**F4 — Layer contents.** 877 tar entries: 317 directories, 432 files, 107
symlinks, 21 hardlinks. Apparent file bytes 22,998,982. Reproducer:
`python scripts/inventory.py`.

**F5 — No setuid, setgid, or file-capability entries.** All three counts are
zero across 877 entries. Exactly one entry is not owned by `root:root`:
`/var/spool/mail`, mode `0775`, owner `0:12` (`root:mail`).

**F6 — A shell is present; the package manager is not.** `/bin` is a symlink
to `usr/bin`, and `/usr/bin/sh` is a symlink to `bash`, so the configured
`Cmd` of `["/bin/sh","-c","/bin/sh"]` resolves to `/usr/bin/bash`
(1,389,072 B). `rpm`, `dnf`, `microdnf`, and `yum` binaries are all absent.
The image description "doesn't install the package manager" refers to the
package manager, not the shell.

**F7 — The RPM database ships in the image.** `/var/lib/rpm/rpmdb.sqlite` is
present at 7,405,568 B — 31.4% of the uncompressed layer — despite no binary
being able to read it in-image. `/var/lib/dnf/history.sqlite` and its
write-ahead log add a further 1,004,424 B. Package metadata is therefore
about 36% of the image.

**F8 — The installed package set.** Twenty packages and two imported GPG
keys, from seventeen source RPMs. Reproducer: `python scripts/rpmdb.py`.

```
basesystem-11-13.el9.noarch                    glibc-minimal-langpack-2.34-275.el9_8.x86_64
bash-5.1.8-9.el9.x86_64                        libacl-2.4.0-1.el9_8.x86_64
coreutils-single-8.32-41.el9_8.x86_64          libattr-2.6.0-1.el9_8.x86_64
filesystem-3.16-5.el9.x86_64                   libcap-2.48-10.el9_8.1.x86_64
glibc-2.34-275.el9_8.x86_64                    libgcc-11.5.0-14.el9.x86_64
glibc-common-2.34-275.el9_8.x86_64             libselinux-3.6-3.el9.x86_64
libsepol-3.6-3.el9.x86_64                      pcre2-syntax-10.40-6.el9.noarch
ncurses-base-6.2-12.20210508.el9.noarch        redhat-release-9.8-1.0.el9.x86_64
ncurses-libs-6.2-12.20210508.el9.x86_64        setup-2.13.7-10.el9.noarch
pcre2-10.40-6.el9.x86_64                       tzdata-2026c-1.el9_8.noarch
```

**F9 — Documentation was excluded at install time.** `/usr/share/doc` and
`/usr/share/info` contain one entry each — the empty directory itself — while
`/usr/share/licenses` retains 30. `bash` declares 7,738,778 B unpacked but
contributes a 1,389,072 B binary. This is the signature of `--nodocs` (or
`tsflags=nodocs`), with licence files deliberately retained.

**F10 — The build repositories are not the shipped repositories.**
`/root/buildinfo/content-sets.json` names `rhel-9-for-x86_64-baseos-rpms`,
an internal subscription content set. The `/etc/yum.repos.d/ubi.repo` shipped
in the image points instead at the public `cdn-ubi.redhat.com` mirrors. A
reconstruction outside Red Hat necessarily draws from the public repository.

**F11 — Buildinfo is duplicated.** `content-sets.json` (589 B) and
`labels.json` (1,084 B) appear at both `/root/buildinfo/` and
`/usr/share/buildinfo/`, from the same source directory hash in the history.

## Inferred

**I1 — The root filesystem came from an `--installroot` transaction.** F2
shows no `RUN` in the Containerfile, F7 shows a populated rpmdb and dnf
history, and F9 shows install-time flags. Together these indicate a package
transaction performed in a separate build container against an installroot,
whose output directory was then copied in. This is consistent with Red Hat's
documented `ubi-micro` build approach but is not directly observable here.

**I2 — Declared and measured sizes agree only by coincidence.** The rpmdb
reports 23,046,779 B unpacked against 22,998,982 B measured, a 47,797 B gap.
That closeness is misleading: F9 removes several megabytes of documentation
that packages declare, while F7 adds 7.4 MB of rpmdb that no package owns.
The two errors happen to offset. Per-file attribution via the `Basenames`
table is needed before any per-package size claim is made.

## Unexplained

**U1 — The minimal explicit install set is not yet known.** Twenty packages
are installed, but which were named on the command line and which arrived as
dependencies has not been determined. Resolving this needs the `Requirename`
and `Providename` tables, and it matters: naming all twenty in a
reconstruction would pin versions that Red Hat allowed the resolver to
choose.

**U2 — Eighty distinct mtimes.** Most entries carry build-time stamps
(2026-08-26T21:14:01–04Z) but some retain original RPM mtimes as old as
2008-08-12. The rule deciding which is preserved is not established.
