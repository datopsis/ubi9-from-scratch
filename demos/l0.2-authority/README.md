# L0.2 — why bother with a container at all?

**Part three of the L0 tutorial.** Part one is
[L0.0](../l0.0-describe/README.md), part two is
[L0.1](../l0.1-sha256/README.md).

> [!NOTE]
> **Verified in CI** on `ubuntu-latest` with Podman 5.x. Every command and
> output on this page was executed, not predicted.

## What this shows

By now there is a fair objection to the whole exercise. L0.1 is a single
931 KB static binary with no dependencies. You could `scp` it to a server and
run it. **So what is the container actually for?**

The answer is not packaging, and it is not portability — the static binary
already has both.

> **A static binary is a unit of code. A container is a unit of *authority*.**

A process inherits the ambient authority of whoever launched it: every file
that user can read, every network the host can reach, every process in the same
namespace. Nothing in the program asks for that authority, and nothing in the
program can reliably give it up — a compromised process runs with whatever the
kernel already granted it.

A container changes what the kernel grants. Same binary, same bytes, same
digest, different authority.

This rung does not assert that. **It measures it.** The program attempts six
ordinary actions and reports which the kernel permitted.

### What it does not show

- This is not a sandbox-escape exercise. Every probe is benign: it reads, or
  writes to a temporary path, or opens a socket it closes immediately.
- Containers are not a security boundary equivalent to a VM. They share a
  kernel. What they do give you is a *much* smaller grant of authority, and
  that is measurable, which is the point here.
- A confined run does **not** allow nothing — see the surprise below.

## Prerequisites

| Requirement | Why | Exercised against |
| --- | --- | --- |
| Podman ≥ 4.0 (or Docker ≥ 20.10) | multi-stage build, `--squash-all` | Podman 5.x |
| Network access to `registry.access.redhat.com` | pulls the UBI 9 builder image | verified |
| `ps` on the host | to see the container as a process | procps |
| `syft` and `grype` | SBOM and scan (optional) | syft 1.51.1, grype 0.118.0 |

## Build

```sh
podman build \
  --squash-all \
  --file demos/l0.2-authority/Containerfile \
  --tag l0.2-authority:9.8 \
  demos/l0.2-authority
```

## Run

Fully confined — every restriction this project applies by default:

```sh
podman run --rm \
  --cap-drop=ALL \
  --security-opt=no-new-privileges \
  --read-only \
  --network=none \
  l0.2-authority:9.8
```

Observed:

```
L0.2 — what the kernel lets this process do
-------------------------------------------
uid 1000, gid 1000, pid 1 (as this process sees it)

  effective capabilities    : 0000000000000000  (none — every capability dropped)

Probes:
  read /etc/passwd             ALLOWED   read 1 user accounts
  list /                       ALLOWED   10 entries visible at /
  reach 1.1.1.1:53             denied    Network is unreachable
  write to /tmp                ALLOWED   created and removed a file
  spawn a shell                denied    no shell exists in this filesystem
  enumerate processes          denied    only this process is visible — separate PID namespace

3 allowed, 3 denied
```

Now relax exactly one flag — drop `--network=none`, change nothing else:

```
  reach 1.1.1.1:53             ALLOWED   outbound connection succeeded

4 allowed, 2 denied
```

**The binary did not change. The digest did not change.** One launch flag moved
the boundary. That is the entire thesis of this rung, and it is why the
container is not redundant with the static binary: the binary is the code, the
launch is the authority.

### The surprise: a `scratch` image is not empty at runtime

Three probes succeeded under *full* confinement, and the reasons are worth
knowing because they contradict the obvious assumption:

- **`/etc/passwd` exists.** The image contains no `/etc` at all, but the
  Containerfile declares `USER 1000:1000`, and Podman injects a passwd entry so
  the uid resolves. One account, not the host's.
- **`/tmp` is writable despite `--read-only`.** Podman's `--read-only-tmpfs`
  defaults to on, mounting a tmpfs at `/tmp` and `/run`. The root filesystem is
  genuinely read-only; `/tmp` is a separate, empty, in-memory filesystem.
- **`/` has 10 entries.** The runtime creates mountpoints — `/proc`, `/sys`,
  `/dev`, `/etc`, `/tmp`, `/run` — even in an image that ships none of them.

None of this is a flaw. It is the difference between what an *image* contains
and what a *container* has, and confusing the two is how people end up
surprised in production. L0.0 reports these paths as absent because it is
inspecting a different launch configuration; both reports are correct.

If you want `/tmp` gone too: `--read-only-tmpfs=false`.

## Exec and inspect: the container from the host

This is where the concept lands. Start a held container:

```sh
podman run -d -i --name l02 \
  --cap-drop=ALL --security-opt=no-new-privileges --read-only --network=none \
  l0.2-authority:9.8 --hold
```

Ask it what pid it thinks it is, then ask the host:

```sh
podman logs l02 | grep pid
podman inspect l02 --format '{{.State.Pid}}'
```

```
uid 1000, gid 1000, pid 1 (as this process sees it)
2829
```

**Both are true simultaneously.** Now look at it from the host:

```sh
ps -o pid,ppid,user,args -p 2829
```

```
    PID    PPID USER     COMMAND
   2829    2827 166535   /app --hold
```

And its parent chain:

```
   2829    2827 app
   2827       1 conmon
      1       0 systemd
```

**There is no "container" in that process tree.** There is an ordinary process
called `app`, whose parent is `conmon` (Podman's per-container supervisor),
whose parent is `systemd`. A container is not a thing the kernel has; it is a
process the kernel has been told to be restrictive about.

Note the user column: `166535`, not `1000`. That is the rootless uid mapping —
container uid 1000 maps to an unprivileged host uid that owns nothing. Even if
the process escaped its filesystem, it would be a nobody on the host.

Now the kernel's own record of what it granted:

```sh
grep -E '^(Name|Pid|NSpid|CapEff|CapBnd|NoNewPrivs|Seccomp):' /proc/2829/status
```

```
Name:	app
Pid:	2829
NSpid:	2829	1
CapEff:	0000000000000000
CapBnd:	0000000000000000
NoNewPrivs:	1
Seccomp:	2
```

Read that line by line, because every field is the argument for containers:

| Field | Value | What it means |
| --- | --- | --- |
| `NSpid` | `2829 1` | The kernel records **both** pids for one process — 2829 in the host namespace, 1 in its own. The namespace is not a fiction the runtime maintains; it is kernel state. |
| `CapEff` | all zeros | Effective capabilities: none. It cannot bind a low port, load a module, change ownership, or read another user's files. |
| `CapBnd` | all zeros | The *bounding* set is empty too, so it can never acquire a capability, even by exec'ing something setuid. This is the one that matters. |
| `NoNewPrivs` | `1` | A `setuid` binary could not elevate it. There isn't one in the image, but the kernel would refuse anyway. |
| `Seccomp` | `2` | Filter mode: a syscall allowlist is in force. Most of the kernel's API surface is simply unavailable. |

Run the same binary directly on the host and every one of those fields is
different: a full capability set for root, an empty seccomp filter, one pid,
and the entire filesystem in reach.

**That difference is the container, and it is enforced by the kernel rather
than by the program's good behaviour.** You cannot get it by shipping a binary,
because a binary cannot restrict the context it is launched into. That is the
technical reason.

Clean up:

```sh
podman rm -f l02
```

## Review the contents

```sh
podman create --name check l0.2-authority:9.8
podman export check -o rootfs.tar
podman rm check
python scripts/verify_image.py rootfs.tar --expect-entries 1
```

One file, no setuid, no setgid, no package managers — the same floor as L0.0
and L0.1.

## Security

```sh
scripts/security_scan.sh l0.2-authority:9.8
```

Zero components, zero vulnerabilities, and the same caveat as the other L0
rungs: that is an absence of *visibility*, not an absence of risk. See
[L0.1's security section](../l0.1-sha256/README.md#security) for the full
explanation.

There is a second lesson here specific to this rung. A scanner tells you what
is in an image. **It tells you nothing about what the container is permitted to
do.** An image with zero CVEs launched with `--privileged` is a worse security
outcome than an image with twenty CVEs launched with `--cap-drop=ALL`. Both
halves need evidence, and only one of them shows up in a scan report.

## Where this sits on the ladder

| Rung | Image bytes | Entries | Components | Vulns |
| --- | ---: | ---: | ---: | ---: |
| L0.0 describe | 934,974 | 1 | 0 | 0 |
| L0.1 SHA-256 | 939,069 | 1 | 0 | 0 |
| **L0.2 authority** | **~939,000** | **1** | **0** | **0** |
| WP6 `micro` reconstruction | 23,585,791 | 871 | 22 | 23 |
| Official `ubi9-micro` | 23,591,424 | 877 | — | — |

All three L0 rungs are the same floor. What changes between them is what the
program *does*, not what the image contains — which is exactly what makes the
comparison honest.

## Clean up

```sh
podman rm -f l02 2>/dev/null
podman rmi l0.2-authority:9.8
rm -f rootfs.tar
rm -rf security-results
```

---

**Next:** L1 — leaving `scratch` and linking dynamically, and what that costs.
