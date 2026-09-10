# Reference — ubi9/ubi-micro, itemized

Every layer, label, package, permission and byte of the official image, and
the ledger that reconciles what its packages declare against what it ships.

Subject: `registry.access.redhat.com/ubi9/ubi-micro`, pinned at
`sha256:f332c99eb8f798a8486821c91937f10ad64ee83d7e739303be2df051040918f6`,
resolved from `:latest` on 2026-09-09. RHEL 9.8 (Plow), built 2026-08-26.

Regenerate every figure here with `scripts/fetch_image.py`,
`scripts/inventory.py`, `scripts/rpmdb.py`, `scripts/attribute.py`,
`scripts/transaction.py` and `scripts/closure.py`.

## 1. Identity

| Object | Digest | Size | Media type |
| --- | --- | ---: | --- |
| Manifest list | `sha256:f332c99eb8f798a8486821c91937f10ad64ee83d7e739303be2df051040918f6` | 970 | `manifest.list.v2+json` |
| Manifest (amd64) | `sha256:a8296f84d6218b865e829dc5150cd82e903d7027ab7d50da283a8ec98a02a336` | 428 | `manifest.v2+json` |
| Config | `sha256:9a25cf5f233eab241d2488a39f4e815a7981155fa4367f71ff0e1b81caaa9e62` | 4,879 | `container.image.v1+json` |
| Layer (gzip) | `sha256:44bb90d0dc2d3c7487076e80e560778499b9e86c5c8709287bce0be56c5fb385` | 7,253,582 | `rootfs.diff.tar.gzip` |
| Layer (diff_id) | `sha256:49d88c5f8e857b7f1f820fe9d675e242502575a82be998cf9e18f6ef83f00e0d` | 23,591,424 | uncompressed tar |

Every digest verified by recomputing SHA-256 over the retrieved bytes; the
registry's `Docker-Content-Digest` was cross-checked but not trusted alone.

| Platform | Manifest digest |
| --- | --- |
| `linux/amd64` | `sha256:a8296f84d6218b865e829dc5150cd82e903d7027ab7d50da283a8ec98a02a336` |
| `linux/arm64/v8` | `sha256:56c0fe27030d858e76617f531a443b15a938d45fef6c22973016bcf73e12059b` |
| `linux/s390x` | `sha256:276937eca210dadf0c2d043544bda6edc8ac0632ce038348e15f01340ef8472d` |
| `linux/ppc64le` | `sha256:130ab100e4e6ec0428c0775c9cdd6c9fe75fc5d565b548285559d797c29bfe12` |

## 2. Runtime configuration

The entire runtime contract is four values.

| Key | Value | Note |
| --- | --- | --- |
| `Cmd` | `["/bin/sh","-c","/bin/sh"]` | resolves through `/bin`→`usr/bin`, `sh`→`bash` |
| `Env` | `PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin` | the only variable |
| `WorkingDir` | `/` | |
| `User` | *(unset)* | **runs as uid 0** |
| `Entrypoint` | *(unset)* | |
| `ExposedPorts`, `Volumes`, `HealthCheck` | *(unset)* | |
| `architecture` / `os` | `amd64` / `linux` | |
| `created` | `2026-08-26T21:14:05.021777547Z` | |

There is no `User`, so every deployment must set one itself.

## 3. Labels

All 22, verbatim from `/root/buildinfo/labels.json`.

| Label | Value |
| --- | --- |
| `name` | `ubi9/ubi-micro` |
| `version` | `9.8` |
| `release` | `1787778798` |
| `architecture` | `x86_64` |
| `com.redhat.component` | `ubi9-micro-container` |
| `cpe` | `cpe:/a:redhat:enterprise_linux:9::appstream` |
| `build-date` | `2026-08-26T21:13:51Z` |
| `org.opencontainers.image.created` | `2026-08-26T21:13:51Z` |
| `vcs-type` | `git` |
| `vcs-ref` | `f4a035c7f61947bd47d6abfc6b65c983adc04b2a` |
| `org.opencontainers.image.revision` | `f4a035c7f61947bd47d6abfc6b65c983adc04b2a` |
| `io.buildah.version` | `1.44.0` |
| `maintainer` | `Red Hat, Inc.` |
| `vendor` | `Red Hat, Inc.` |
| `distribution-scope` | `public` |
| `summary` | `ubi9 micro image` |
| `description` | `Very small image which doesn't install the package manager.` |
| `io.k8s.description` | `Very small image which doesn't install the package manager.` |
| `io.k8s.display-name` | `Red Hat Universal Base Image 9 Micro` |
| `io.openshift.expose-services` | *(empty)* |
| `url` | `https://catalog.redhat.com/en/search?searchType=containers` |
| `com.redhat.license_terms` | `https://www.redhat.com/en/about/red-hat-end-user-license-agreements#UBI` |

## 4. Build history

Nineteen entries, one layer — the image is squashed. History survives
squashing, so the original instruction sequence is still readable, and it
contains **no `RUN` instruction at all**.

| # | Instruction | Effect | Layer |
| --- | --- | --- | --- |
| 1–14 | `LABEL` × 14 | maintainer, vendor, url, component, name, version, cpe, scope, licence, summary, descriptions, display-name, expose-services | empty |
| 15 | `COPY dir:21269f5d… in /` | the entire root filesystem, pre-built elsewhere | empty |
| 16 | `COPY file:1376702515d5… in /etc/yum.repos.d/` | the public UBI repo definition | empty |
| 17 | `CMD /bin/sh` | sets the runtime command | empty |
| 18 | `COPY dir:95f81fb2… in /usr/share/buildinfo/` | content-sets.json, labels.json | empty |
| 19 | `COPY dir:95f81fb2… in /root/buildinfo/` | the same directory hash, duplicated | empty |
| 20 | `LABEL build-date, vcs-ref, release` | build identity stamped last | **layer** |

## 5. The byte ledger

| Step | Bytes |
| --- | ---: |
| Declared by 20 packages (RPM `SIZE`, hardlink groups counted once) | 23,046,779 |
| Trimmed after install (docs, locales, zoneinfo) | −8,498,676 |
| **Package content actually shipped** | **14,548,103** |
| Added, owned by no package (rpmdb, dnf state, buildinfo, repo files) | +8,449,842 |
| **Expected apparent file bytes** | **22,997,945** |
| Measured from tar headers (residual 1,037 B: symlink/hardlink accounting) | 22,998,982 |
| **Uncompressed tar, incl. headers and block padding** | **23,591,424** |
| Compressed layer as published (gzip, 3.25× ratio) | 7,253,582 |

Installing the recorded package set reproduces the 23,046,779 declared bytes,
not the 14,548,103 Red Hat shipped. Most of the difference comes free —
naming `glibc-minimal-langpack` excludes locale catalogues through RPM's
install-language filter — leaving only zoneinfo and the caches to delete.

## 6. Composition

Apparent file bytes by top-level directory, across 877 entries.

| Path | Bytes | Share | Contents |
| --- | ---: | ---: | --- |
| `/usr` | 13,791,479 | 60.0% | glibc, bash, coreutils, terminfo |
| `/var` | 8,443,600 | 36.7% | almost entirely the rpm and dnf databases |
| `/etc` | 762,166 | 3.3% | 692,252 of it is `/etc/services` |
| everything else | 1,737 | <0.1% | `/root`, `/dev`, empty mount points |

| Entry type | Count | Modes observed |
| --- | ---: | --- |
| Directories | 317 | `0755`×296, `0555`×17, `1777`×2, `0550`×1, `0775`×1 |
| Regular files | 432 | `0644`×238, `0555`×105, `0755`×87, `0000`×2 |
| Symlinks | 107 | — |
| Hardlinks | 21 | — |
| **Total** | **877** | |

### Ten largest files

| Path | Bytes | Share | Owner |
| --- | ---: | ---: | --- |
| `/var/lib/rpm/rpmdb.sqlite` | 7,405,568 | 32.20% | no package |
| `/usr/lib64/libc.so.6` | 2,549,360 | 11.08% | glibc |
| `/usr/bin/bash` | 1,389,072 | 6.04% | bash |
| `/usr/bin/coreutils` | 1,347,000 | 5.86% | coreutils-single |
| `/usr/sbin/ldconfig` | 1,176,464 | 5.12% | glibc |
| `/usr/lib64/ld-linux-x86-64.so.2` | 938,792 | 4.08% | glibc |
| `/usr/lib64/libm.so.6` | 912,968 | 3.97% | glibc |
| `/var/lib/dnf/history.sqlite-wal` | 852,872 | 3.71% | no package |
| `/usr/lib64/libsepol.so.2` | 802,664 | 3.49% | libsepol |
| `/etc/services` | 692,252 | 3.01% | setup |

## 7. Packages

Declared = files in the package manifest. Shipped = present in the image.
Cut = the remainder, excluding `%ghost` entries never installed.
Per-package roles are in [COMPONENTS.md](COMPONENTS.md).

| Package | Version | Declared B | Decl. | Shipped | Cut | Cut B |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `bash` | 5.1.8-9.el9 | 7,738,778 | 132 | 27 | 105 | 6,306,306 |
| `glibc` | 2.34-275.el9_8 | 6,451,649 | 113 | 110 | 1 | 0 |
| `tzdata` | 2026c-1.el9_8 | 1,917,852 | 1,872 | 2 | 1,870 | 1,917,600 |
| `coreutils-single` | 8.32-41.el9_8 | 1,402,857 | 113 | 113 | 0 | 0 |
| `glibc-common` | 2.34-275.el9_8 | 1,081,358 | 51 | 51 | 0 | 0 |
| `ncurses-libs` | 6.2-12.20210508.el9 | 994,415 | 44 | 44 | 0 | 0 |
| `libsepol` | 3.6-3.el9 | 829,131 | 6 | 6 | 0 | 0 |
| `setup` | 2.13.7-10.el9 | 725,932 | 41 | 38 | 2 | 7,343 |
| `pcre2` | 10.40-6.el9 | 652,298 | 9 | 9 | 0 | 0 |
| `ncurses-base` | 6.2-12.20210508.el9 | 307,293 | 175 | 173 | 2 | 10,293 |
| `pcre2-syntax` | 10.40-6.el9 | 234,324 | 16 | 3 | 13 | 230,750 |
| `libgcc` | 11.5.0-14.el9 | 207,028 | 11 | 11 | 0 | 0 |
| `libcap` | 2.48-10.el9_8.1 | 177,487 | 32 | 26 | 6 | 7,637 |
| `libselinux` | 3.6-3.el9 | 176,845 | 8 | 8 | 0 | 0 |
| `redhat-release` | 9.8-1.0.el9 | 75,915 | 33 | 31 | 2 | 18,747 |
| `libacl` | 2.4.0-1.el9_8 | 44,714 | 5 | 5 | 0 | 0 |
| `libattr` | 2.6.0-1.el9_8 | 28,797 | 6 | 6 | 0 | 0 |
| `filesystem` | 3.16-5.el9 | 106 | 17,268 | 191 | 1,368 | 0 |
| `basesystem` | 11-13.el9 | 0 | 0 | 0 | 0 | 0 |
| `glibc-minimal-langpack` | 2.34-275.el9_8 | 0 | 0 | 0 | 0 | 0 |
| **20 packages** | 17 source RPMs | **23,046,779** | 19,935 | 854 | 3,369 | **8,498,676** |

Two GPG keys are also imported: `gpg-pubkey-fd431d51-4ae0493b` and
`gpg-pubkey-5a6340b3-6229229e`.

### The build transaction

Recovered from `/var/lib/dnf/history.sqlite`. Arguments only — the program
name is not recorded, though I5 identifies it as `microdnf`.

```
install --installroot /mnt/rootfs redhat-release --releasever 9 \
  --setopt install_weak_deps=false --nodocs --nogpgcheck -y

install --installroot /mnt/rootfs --setopt=reposdir=/etc/yum.repos.d/ \
  coreutils-single glibc-minimal-langpack --releasever 9 \
  --setopt install_weak_deps=false --nodocs -y
```

Named: `redhat-release`, `coreutils-single`, `glibc-minimal-langpack`. The
other seventeen came from the resolver.

## 8. What was removed after installing

Seven packages lost content. Licence texts stay — all 30 of them.

| Package | Files cut | Bytes | What went |
| --- | ---: | ---: | --- |
| `bash` | 105 | 6,306,306 | `/usr/share/doc/bash/*`, `bash.info.gz`, ~90 `LC_MESSAGES/bash.mo` |
| `tzdata` | 1,870 | 1,917,600 | the whole of `/usr/share/zoneinfo`, plus docs |
| `pcre2-syntax` | 13 | 230,750 | manual pages |
| `redhat-release` | 2 | 18,747 | `/usr/share/doc/redhat-release/GPL` |
| `ncurses-base` | 2 | 10,293 | documentation |
| `libcap` | 6 | 7,637 | documentation |
| `setup` | 2 | 7,343 | documentation |
| **7 packages** | **2,000** | **8,498,676** | 36.9% of everything declared |

By mechanism: `%doc`-flagged files account for 2,223,129 B across 91 files.
The rest is `/usr/share/locale` (4,770,375 B, 1,405 files — the install-language
filter) and `/usr/share/zoneinfo` (1,505,172 B, 1,864 files — a deletion).

> **`tzdata` is a trap.** The rpmdb records it as installed, so a scanner
> reports it present, but `/usr/share/zoneinfo` is absent and there is no
> `/etc/localtime`. Only `tzselect` (15,352 B) and a licence survive. Anything
> needing a timezone gets UTC.

## 9. The 41 paths no package claims

8,449,842 bytes, 36.7% of the image. None would be recreated by installing
packages.

| Group | Bytes | Paths | Origin |
| --- | ---: | --- | --- |
| RPM database | 7,438,336 | `rpmdb.sqlite`, `-shm`, `-wal`, `.rpm.lock` | install transaction |
| DNF history | 1,004,424 | `history.sqlite`, `-wal` (852,872 B), `-shm` | install transaction |
| Repo definitions | 2,832 | `ubi.repo`, `redhat.repo` | `COPY` step 16 |
| Buildinfo ×2 | 3,346 | `labels.json`, `content-sets.json` at two paths | `COPY` steps 18–19 |
| Subscription state | 360 | `/var/lib/rhsm/productid.js`, `repo_server_val/redhat.repo` | install transaction |
| Build log | 480 | `/var/log/hawkey.log` | install transaction |
| Device node | 64 | `/dev/null` | build scaffolding |
| Empty directories | 0 | `/etc/dnf/*`, `/etc/pki/{entitlement,product,swid}`, `/usr/lib/{rpm,swidtag,sysctl.d,systemd/*,tmpfiles.d}`, `/usr/lib64/security`, `/var/lib/rhsm` | install transaction |

## 10. Security posture

Measured across all 877 entries from tar headers.

| Property | Count | Detail |
| --- | ---: | --- |
| setuid entries | 0 | no privilege-escalating binaries |
| setgid entries | 0 | |
| File capabilities | 0 | no `security.capability` xattr anywhere |
| Non-root owned | 1 | `/var/spool/mail`, mode 0775, owner `0:12` (`root:mail`) |
| World-writable | 2 | `/tmp`, `/var/tmp`, mode 1777 with sticky bit |
| Package manager binaries | 0 | no `rpm`, `dnf`, `microdnf`, `yum` |
| Shell | 1 | `/usr/bin/bash`, 1,389,072 B, reachable as `/bin/sh` |
| Default user | — | **root** — the config sets no `User` |

## 11. Provenance

| Role | Repositories | Access |
| --- | --- | --- |
| Built from (`content-sets.json`) | `rhel-9-for-{x86_64,aarch64,ppc64le,s390x}-baseos-rpms` and their source variants | internal, subscription |
| Ships a repo file for (`ubi.repo`) | `ubi-9-baseos-rpms`, `ubi-9-appstream-rpms`, `ubi-9-codeready-builder-rpms`, plus disabled debug and source variants | public, `cdn-ubi.redhat.com` |

Both enabled repos are GPG-verified against
`file:///etc/pki/rpm-gpg/RPM-GPG-KEY-redhat-release` with `gpgcheck = 1`.

The gap between build and shipped repositories was expected to be the largest
obstacle to reconstruction. It was not: a rebuild from the public mirrors
resolved to the identical package versions (F17).

## 12. Rebuild specification

| Requirement | Target | Source |
| --- | --- | --- |
| Install package set into `--installroot` | 3 named, 17 resolved | §7 |
| Exclude documentation | `--nodocs`, keep 30 licence dirs | §8 |
| Exclude locale catalogues | name `glibc-minimal-langpack` | §8 |
| Remove zoneinfo after install | `/usr/share/zoneinfo`, 1,917,600 B | §8 |
| Base the image on `scratch` | no package manager in result | §10 |
| Copy rootfs, then repo file | `/etc/yum.repos.d/ubi.repo`, 2,474 B | §4 |
| Set `Cmd` and `PATH` only | `["/bin/sh","-c","/bin/sh"]` | §2 |
| Squash | 1 layer | §4 |
| Preserve security posture | 0 setuid, 0 setgid, 0 caps | §10 |
| Match file inventory | 877 entries, 22,998,982 B | §6 |

**Verified.** See [COMPARISON.md](COMPARISON.md): the rebuild reproduces the
inventory with zero unexplained differences, at 23,585,792 B against
23,591,424 B.

### Structural differences a rebuild cannot eliminate

| Difference | Magnitude | Why |
| --- | ---: | --- |
| rpmdb content | ~7,400,000 B of non-identical bytes | sqlite page layout, install transaction IDs and timestamps differ per run. Affects byte-identity, not size — `VACUUM` reclaims only 65,536 B, so the database is genuinely dense. |
| Source repositories | — | Internal RHEL content sets are unreachable outside Red Hat; the public mirrors are the substitute. |
| Build identity | — | `build-date`, `vcs-ref f4a035c7…`, `release 1787778798` name Red Hat's build system. |

A byte-identical rebuild is not achievable, and claiming one would mean
concealing the rpmdb difference.
