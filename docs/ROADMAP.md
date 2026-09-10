# Roadmap

Ordered work packages. Each one lands with its documentation, and no package
records a finding it has not reproduced.

## WP1 — Acquire and pin

Resolve `ubi9-micro` to a digest, copy it to a local OCI layout, and record
the reference used by all later work.

## WP2 — Image structure

Record manifest, config, history, labels, environment, and layer digests.

## WP3 — File inventory

Extract the root filesystem and produce a complete, sorted inventory with
modes, ownership, sizes, link targets, and extended attributes.

## WP4 — Package attribution

Map the inventory to owning RPMs. Isolate and characterise the unattributed
files.

## WP5 — Image metadata

Accounts, groups, release files, licences, and content manifests.

## WP6 — Reconstruction

Build the image from an `--installroot` package transaction over `scratch`.

## WP7 — Comparison

Diff reconstruction against official across every dimension WP2–WP5 recorded,
and disposition each difference.

## WP8 — Write-up

Consolidate the findings into an explanation that stands on its own for a
reader who does not run the scripts.
