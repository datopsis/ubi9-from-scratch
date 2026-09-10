#!/usr/bin/env bash
# Generate an SBOM and scan an image for known vulnerabilities.
#
# The same script runs in CI and on a workstation, so what the pipeline claims
# is exactly what a reader can reproduce. Nothing here is specific to this
# project's images.
#
# Usage: scripts/security_scan.sh <image> [output-dir]
#
# Tools, both single static binaries with no daemon:
#   syft   https://github.com/anchore/syft    — builds the SBOM
#   grype  https://github.com/anchore/grype   — scans it for known CVEs
#
# The image is exported to an OCI archive first and the tools read that, so no
# container-engine socket is needed and the same commands work anywhere.
#
# Install (Linux/macOS):
#   curl -sSfL https://get.anchore.io/syft  | sh -s -- -b /usr/local/bin
#   curl -sSfL https://get.anchore.io/grype | sh -s -- -b /usr/local/bin
#
# READ THIS BEFORE TRUSTING A CLEAN RESULT
# ----------------------------------------
# An SBOM tool finds what a package database tells it about. An image built on
# `scratch` with a statically linked binary has no package database at all, so
# syft reports zero packages and grype therefore reports zero vulnerabilities.
#
# That is not the same as being free of vulnerabilities. The code is still
# there — it was linked into the binary, where no package-based scanner can
# see it. A vulnerable libc compiled into a static binary produces exactly the
# same clean report as a genuinely safe one.
#
# This is the trade the ladder is measuring. Package metadata costs bytes
# (31.4% of the official ubi9-micro is its rpm database) and buys scanner
# visibility. Removing it makes the image smaller and the scan report emptier,
# and only one of those is an improvement.

set -euo pipefail

IMAGE="${1:?usage: security_scan.sh <image> [output-dir]}"
OUTDIR="${2:-security-results}"
SAFE_NAME=$(echo "$IMAGE" | tr '/:' '__')

mkdir -p "$OUTDIR"

# Scan an exported OCI archive rather than asking the tools to talk to a
# container engine. syft's podman backend needs a socket that is often absent
# (rootless setups, CI runners), and an archive is what a reader can hand to
# any scanner, on any machine, without a daemon running.
ARCHIVE=$(mktemp -d)/image.tar
trap 'rm -rf "$(dirname "$ARCHIVE")"' EXIT
echo "=== Exporting $IMAGE to an OCI archive ==="
podman save --format oci-archive -o "$ARCHIVE" "$IMAGE"
echo "archive: $(stat -c '%s bytes' "$ARCHIVE")"
echo

have() { command -v "$1" >/dev/null 2>&1; }

if ! have syft || ! have grype; then
    echo "syft and grype are required. Install them with:"
    echo "  curl -sSfL https://get.anchore.io/syft  | sh -s -- -b /usr/local/bin"
    echo "  curl -sSfL https://get.anchore.io/grype | sh -s -- -b /usr/local/bin"
    exit 127
fi

echo "=== Tool versions ==="
syft version | head -2
grype version | head -2

echo
echo "=== SBOM: $IMAGE ==="
# SPDX is the format most compliance processes ask for; CycloneDX is what many
# scanners consume. Producing both costs one extra second.
syft "oci-archive:$ARCHIVE" -o spdx-json="$OUTDIR/${SAFE_NAME}.spdx.json" \
                     -o cyclonedx-json="$OUTDIR/${SAFE_NAME}.cdx.json" \
                     -o table

packages=$(python3 -c "
import json,sys
with open('$OUTDIR/${SAFE_NAME}.spdx.json') as fh:
    doc = json.load(fh)
print(len(doc.get('packages', [])))
" 2>/dev/null || echo "?")

echo
echo "=== Vulnerability scan ==="
# Scan the SBOM we just produced, so the scan and the SBOM describe exactly
# the same set of components.
grype "sbom:$OUTDIR/${SAFE_NAME}.spdx.json" -o table --file "$OUTDIR/${SAFE_NAME}.grype.txt" || true
grype "sbom:$OUTDIR/${SAFE_NAME}.spdx.json" -o json --file "$OUTDIR/${SAFE_NAME}.grype.json" >/dev/null 2>&1 || true
cat "$OUTDIR/${SAFE_NAME}.grype.txt"

echo
echo "=== Interpretation ==="
echo "packages catalogued: $packages"
if [ "$packages" = "0" ]; then
    cat <<'NOTE'

  Zero packages found. For an image built on scratch this is expected and is
  NOT a clean bill of health: there is no package database, so a package-based
  scanner has nothing to inspect. The dependencies were linked into the binary
  and remain there.

  To reason about a static binary's exposure you need the build-time
  dependency list — the toolchain and library versions the binary was compiled
  against — which the image itself does not carry. That is why WP9 records the
  build inputs alongside each rung rather than relying on a scan.
NOTE
else
    echo
    echo "  $packages packages catalogued from the image's own package database."
    echo "  A finding here is actionable: the package and its version are known."
fi

echo
echo "wrote $OUTDIR/"
ls -la "$OUTDIR" | tail -n +2
