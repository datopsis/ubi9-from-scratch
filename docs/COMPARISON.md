# Comparison

The reconstruction measured against the official image.

**Result: zero open differences.** Every difference between the two is
accounted for by a finding, and the only content the reconstruction lacks is
the 3,346 bytes of Red Hat build metadata it deliberately does not reproduce.

Reproducer: `.github/workflows/ci.yml`, run 34439810973. Locally:

```sh
python scripts/fetch_image.py && python scripts/inventory.py
podman create --name check micro:9.8
podman export check -o rootfs.tar
podman rm check
python scripts/compare.py rootfs.tar
```

## Headline

| Measure | Official | Reconstruction | Delta |
| --- | ---: | ---: | ---: |
| Image size (uncompressed) | 23,591,424 | 23,585,792 | **−5,632** |
| Apparent file bytes | 22,998,824 | 22,995,478 | **−3,346** |
| Entries compared | 876 | 870 | −6 |
| **Open differences** | — | — | **0** |

Entry counts exclude the paths a container runtime injects into an exported
filesystem (`/etc/hosts`, `/etc/hostname`, `/etc/resolv.conf`), which belong to
neither image.

The reconstruction is now *smaller* than the official image, by exactly the
metadata it declines to copy.

## Dispositions

All six differences are **accepted**. None is open.

| Paths | Disposition | Reason |
| --- | --- | --- |
| `/root/buildinfo`, `/usr/share/buildinfo` and their four files | accepted | F11: Red Hat build metadata. Reproducing `labels.json` — which carries `maintainer`, `vendor`, `build-date` and Red Hat's git revision — would misrepresent the origin of a rebuild. 3,346 B. |
| `/var/lib/rpm/*` | accepted | F7: the rpm database records *this* transaction. Byte content differs; size does not, which is why the totals stay this close. |
| `/var/lib/dnf/*` | accepted | F7: the dnf history likewise records this build rather than Red Hat's. |
| `/var/log/hawkey.log` | accepted | The build log of this transaction. |
| `/var/lib/rhsm/*` | accepted | Subscription state written by the transaction. |
| `/var/log/dnf*.log` | accepted, and removed | I5: `dnf` writes three logs that `microdnf` does not. The reconstruction deletes them to match the official end state. |

No mode differences, no ownership differences, and no size differences on any
path present in both images.

## How the delta was closed

The first comparison reported five open differences and a +22,237 byte delta.
Those numbers reconciled exactly:

```
+25,583   /var/log/dnf.log, dnf.librepo.log, dnf.rpm.log   (extra)
 −3,346   buildinfo at two paths                           (deliberately absent)
────────
+22,237   measured delta
```

Removing the three dnf logs left −3,346, which is the buildinfo alone.

That reconciliation produced a finding rather than just a fix. The official
image carries `/var/log/hawkey.log` but none of dnf's own three logs.
`microdnf` writes the first and not the others; `dnf` writes all four. So
**microdnf ran the original transaction** — something F12 could not establish,
because the dnf history stores arguments without a program name (I5).

## What this does and does not establish

**Established.** The recovered transaction is correct. Running it reproduces
the official image's file inventory exactly, with identical package versions,
permissions and ownership throughout.

Two things previously assumed are now observed: the public UBI mirrors carry
the same RPM builds as the internal content set (F17), and the RPM
install-language filter does apply to an installroot transaction, so naming
`glibc-minimal-langpack` is sufficient and no locale deletion is needed (I3).

**Not established.** This is not a byte-identical rebuild and cannot be one.
The rpm database differs in content — sqlite page layout, install transaction
IDs and internal timestamps are per-run — even though it does not differ
meaningfully in size. Any claim of byte-identity would require concealing
that.

U3 also remains: the cleanup step in I4 was reproduced from what is absent
rather than from a recorded command. The comparison now shows no residue from
it, which is evidence the reproduction is complete but not proof that Red
Hat's own cleanup did nothing else.
