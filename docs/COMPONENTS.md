# Components

Every package in the official `ubi9-micro` image, what it is, why it is there,
and what it costs. Twenty packages ship 14,549,140 bytes between them; the
remaining 8,449,842 bytes belong to no package and are covered in
[Unowned content](#unowned-content).

Three packages were named on the command line. The other seventeen were pulled
in by the dependency resolver (F13). That distinction is in the **Why** column,
because it decides what a reconstruction should ask for.

## How "why present" was established

Two different kinds of evidence, kept separate because they answer different
questions:

- **Runtime linkage** — observed by reading `DT_NEEDED` out of the ELF headers
  with `python scripts/closure.py`. This is what a program actually loads.
- **RPM dependency** — the package was pulled in to satisfy an RPM `Requires`,
  which is not the same thing. A package can be installed without any binary in
  the image ever loading it.

Where those two disagree, the package is a **trim candidate**: present because
packaging required it, not because anything runs it. Confirming a trim is safe
needs a runtime trace, not this analysis alone.

## The runtime dependency graph

Observed from the image, not from documentation:

```
/usr/bin/bash          -> libtinfo.so.6   (ncurses-libs)
                       -> libc.so.6       (glibc)

/usr/bin/coreutils     -> libselinux.so.1 (libselinux)
                       -> libacl.so.1     (libacl)
                       -> libattr.so.1    (libattr)
                       -> libcap.so.2     (libcap)
                       -> libc.so.6       (glibc)

libselinux.so.1        -> libpcre2-8.so.0 (pcre2)
                       -> libc.so.6

libc.so.6              -> ld-linux-x86-64.so.2
```

Running `bash` alone needs **4 files, 5,072,312 B**. Running `bash` and
`coreutils` needs **10 files, 7,340,792 B** — 31.9% of the image.

## The twenty packages

| Package | Shipped | Files | Why present | What it does |
| --- | ---: | ---: | --- | --- |
| `glibc` | 6,454,520 | 109 | dependency | The C library. `libc.so.6` and the dynamic loader `ld-linux-x86-64.so.2`. Everything in the image links it; nothing runs without it. Also carries `ldconfig` (1,176,464 B), a build-time tool the runtime does not need. |
| `bash` | 1,432,434 | 27 | dependency | The shell. Reached as `/bin/sh` and the image's `Cmd`. Present because something required `/bin/sh`, not because UBI Micro set out to ship a shell. |
| `coreutils-single` | 1,402,768 | 112 | **named** | `ls`, `cat`, `cp`, `mkdir` and the rest, built as one multi-call binary rather than ~110 separate ones. The 112 files are mostly symlinks into that single binary. |
| `glibc-common` | 1,081,072 | 49 | dependency | Architecture-independent glibc data — `/etc/rpc`, character maps, and the `C.utf8` locale under `/usr/lib/locale`. |
| `ncurses-libs` | 993,808 | 39 | dependency | `libtinfo`, the terminal-handling library `bash` links against. Not needed by a program that never touches a terminal. |
| `libsepol` | 829,096 | 5 | dependency | SELinux **policy** manipulation. **Trim candidate** — it appears in no runtime closure in this image. It is an RPM dependency of the SELinux stack rather than something `libselinux` loads at run time. |
| `setup` | 718,589 | 38 | dependency | The base system files: `/etc/passwd`, `/etc/group`, `/etc/hosts`, `/etc/shells`, and `/etc/services` — the last of which is 692,252 B on its own, 95% of this package. Also the one non-root-owned path in the image, `/var/spool/mail`. |
| `pcre2` | 652,168 | 7 | dependency | Perl-compatible regular expressions. Present because `libselinux` links it, not because anything in the image uses regexes directly. |
| `ncurses-base` | 297,000 | 173 | dependency | The terminfo database — 165 terminal definitions. A container that is not attached to a terminal needs none of them. |
| `libgcc` | 206,960 | 10 | dependency | `libgcc_s.so.1`, the GCC runtime support library used for stack unwinding during exception handling. **Trim candidate** for C programs — it appears in no runtime closure here, though a C++ program throwing exceptions does need it. |
| `libselinux` | 176,808 | 7 | dependency | The SELinux userspace API. `coreutils` links it so that file operations can preserve security contexts. |
| `libcap` | 169,600 | 24 | dependency | POSIX capabilities. Linked by `coreutils`. Note the image itself sets no file capabilities at all (F5). |
| `redhat-release` | 57,098 | 31 | **named** | Identity and trust: `/etc/redhat-release`, `/etc/os-release`, and the RPM GPG keys under `/etc/pki/rpm-gpg`. Installed first, with GPG checking disabled, because it carries the key everything after it is verified against (F14). |
| `libacl` | 44,656 | 4 | dependency | POSIX access control lists. Linked by `coreutils`. |
| `libattr` | 28,737 | 5 | dependency | Extended attributes. Linked by `coreutils` and by `libacl`. |
| `pcre2-syntax` | 3,574 | 3 | dependency | Documentation for PCRE2 syntax. 230,750 B of its content was trimmed; what remains is 3,574 B of licence text. |
| `tzdata` | 252 | 2 | dependency | Timezone data — **except the data is gone**. 1,917,600 B of `/usr/share/zoneinfo` was removed after installation (I4). What ships is `tzselect` and a licence file. Anything needing a timezone gets UTC. |
| `filesystem` | 0 | 191 | dependency | Owns the directory hierarchy — `/usr`, `/etc`, `/var` and the rest. Contributes 191 directories and zero bytes of file content. Declares 17,268 paths, of which 15,723 are `%ghost` entries such as `/proc` and `/sys` that are never written. |
| `basesystem` | 0 | 0 | dependency | A metapackage. Declares no files at all; exists to establish install ordering for a base system. |
| `glibc-minimal-langpack` | 0 | 0 | **named** | Declares no files either. It is a *policy* selection: naming it restricts the locales glibc installs to the minimum, which is why `/usr/lib/locale` holds only `C.utf8` and no `.mo` catalogues survive (I3). |

Two of the three named packages install nothing. `glibc-minimal-langpack`
selects a policy and `redhat-release` bootstraps trust — only
`coreutils-single` was chosen for its contents.

## Unowned content

8,449,842 bytes, 36.7% of the image, belong to no package. None of it would be
recreated by installing packages, and it breaks into four groups:

| Group | Bytes | What it is |
| --- | ---: | --- |
| RPM database | 7,438,336 | `/var/lib/rpm/rpmdb.sqlite` and its journal. Written by the install transaction. Nothing in the image can read it — there is no `rpm` binary — but vulnerability scanners can, which is why it is kept. |
| DNF history | 1,004,424 | `/var/lib/dnf/history.sqlite` plus an 852,872 B write-ahead log that was never checkpointed. Pure build residue; it also happens to be what recorded the build commands (F12). |
| Buildinfo and repo files | 6,178 | `labels.json` and `content-sets.json` at two paths, plus `ubi.repo` and `redhat.repo`. Added by `COPY`, not installed. |
| Subscription state, logs, `/dev/null` | 904 | `/var/lib/rhsm`, `/var/log/hawkey.log`, and a device node. |

## What this means for a tailored image

Ranked by what the evidence supports, not by how much it saves:

1. **Safe now.** DNF history (1,004,424 B) is build residue with no runtime
   role. `/var/log/hawkey.log` likewise.
2. **Safe if you accept losing scanner visibility.** The rpm database
   (7,438,336 B). Removing it halves the image and blinds Trivy, Grype and
   Clair, which read exactly that file to enumerate packages.
3. **Trim candidates, need a runtime trace to confirm.** `libsepol` (829,096 B)
   and `libgcc` (206,960 B) appear in no runtime closure. `libgcc` must stay for
   any C++ program that throws.
4. **Workload-dependent.** `ncurses-base` + `ncurses-libs` (1,290,808 B) matter
   only if something attaches to a terminal. `/etc/services` (692,252 B) matters
   only if something resolves service names.
5. **Never.** Licence texts (277,510 B) — a redistribution obligation, not a
   size decision.

A static closure is a lower bound. It cannot see `dlopen` targets — which
includes the OpenSSL FIPS provider — NSS modules behind `getaddrinfo`,
certificate bundles, or configuration files. Confirming any trim in group 3 or
4 requires the runtime tracing in WP9, not this analysis.
