# Comparison

The reconstruction measured against the official image.

> [!NOTE]
> Not started. Depends on `docs/RECONSTRUCTION.md`.

The comparison covers the dimensions the dissection recorded: file inventory,
permissions and ownership, package attribution, image configuration and
labels, and layer structure.

Every difference gets one of three dispositions, and the count of each is
reported:

- **Resolved** — the reconstruction was changed to match, and the change is
  explained.
- **Accepted** — the difference is inherent to rebuilding outside Red Hat's
  build system, such as build timestamps, and the reason is explained.
- **Open** — not yet understood.

A comparison that reports no open differences is only credible if it also
shows what it compared. Report the dimensions covered, not merely the verdict.
