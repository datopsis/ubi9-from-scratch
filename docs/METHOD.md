# Method

How the dissection is performed. Every finding in `docs/FINDINGS.md` must be
reproducible from a command recorded here.

> [!NOTE]
> This document is a plan. Commands are added as they are run and confirmed,
> not in advance of running them.

## Pinning the subject

All recorded work refers to one digest-pinned image reference, so that results
stay meaningful after Red Hat publishes a new build. Resolve the tag once,
record the digest, and use the digest everywhere afterwards.

## Planned stages

1. **Acquire.** Copy the pinned image to a local OCI layout, without a
   container runtime in the path.
2. **Structure.** Record the manifest, config, layer count, layer digests,
   history entries, labels, and environment carried by the image.
3. **Inventory.** Extract the root filesystem and record every path with its
   mode, ownership, size, link target, and extended attributes.
4. **Attribution.** Map the inventory to the RPMs that own each file, and
   isolate the files no RPM claims.
5. **Metadata.** Examine the accounts, groups, release files, licences, and
   content manifests present in the image.
6. **Reconstruct.** Install the attributed package set into an
   `--installroot` from a build container, and assemble an image from the
   result.
7. **Compare.** Diff the reconstruction against the official image across the
   same dimensions, and account for every difference.

## Reproducibility notes

Record the tool versions used for each stage alongside its output. Extraction
and comparison results depend on the tool as much as on the image, and a
result without its tool version cannot be re-checked later.
