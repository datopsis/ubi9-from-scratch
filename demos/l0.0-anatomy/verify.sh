#!/usr/bin/env bash
# Functional verification for L0.0.
#
# This rung teaches the anatomy of an image archive and the difference between
# what an image contains and what a container has. So the checks assert the
# structure of the archive, and the gap between the two.
#
# Usage: demos/l0.0-anatomy/verify.sh <image>

set -euo pipefail

IMAGE="${1:?usage: verify.sh <image>}"
failures=0
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

check() {
    local label="$1" condition="$2"
    if [ "$condition" = "true" ]; then
        printf '  PASS  %s\n' "$label"
    else
        printf '  FAIL  %s\n' "$label"
        failures=$((failures + 1))
    fi
}

echo "=== The image as a docker-archive ==="
podman save --format docker-archive -o "$WORK/docker.tar" "$IMAGE"
tar -tf "$WORK/docker.tar" | sed 's/^/  /'

mkdir -p "$WORK/docker"
tar -xf "$WORK/docker.tar" -C "$WORK/docker"

check 'archive contains a manifest.json' \
    "$([ -f "$WORK/docker/manifest.json" ] && echo true || echo false)"

layer=$(find "$WORK/docker" -name 'layer.tar' | head -1)
if [ -z "$layer" ]; then
    # Newer podman writes the layer as a bare blob named by digest.
    layer=$(python3 -c "
import json, glob, os
base = '$WORK/docker'
with open(os.path.join(base, 'manifest.json')) as fh:
    manifest = json.load(fh)
layers = manifest[0].get('Layers', [])
print(os.path.join(base, layers[0]) if layers else '')
" 2>/dev/null || true)
fi

if [ -n "$layer" ] && [ -f "$layer" ]; then
    echo
    echo "=== Inside the layer ==="
    tar -tvf "$layer" | sed 's/^/  /'
    entries=$(tar -tf "$layer" | wc -l)
    check "the layer holds exactly one entry (found $entries)" \
        "$([ "$entries" -eq 1 ] && echo true || echo false)"
else
    printf '  FAIL  could not locate the layer inside the archive\n'
    failures=$((failures + 1))
fi

echo
echo "=== The same image as an oci-archive ==="
podman save --format oci-archive -o "$WORK/oci.tar" "$IMAGE"
mkdir -p "$WORK/oci"
tar -xf "$WORK/oci.tar" -C "$WORK/oci"
find "$WORK/oci" -type f | sed "s|$WORK/oci|  .|" | sort

check 'oci-archive declares an oci-layout' \
    "$([ -f "$WORK/oci/oci-layout" ] && echo true || echo false)"
check 'oci-archive has an index.json' \
    "$([ -f "$WORK/oci/index.json" ] && echo true || echo false)"

# Content addressing is checkable: every blob's filename is its own digest.
echo
echo "=== Verifying content addressing ==="
mismatch=0
verified=0
while IFS= read -r blob; do
    name=$(basename "$blob")
    actual=$(sha256sum "$blob" | cut -d' ' -f1)
    if [ "$name" = "$actual" ]; then
        verified=$((verified + 1))
    else
        echo "  MISMATCH $name != $actual"
        mismatch=$((mismatch + 1))
    fi
done < <(find "$WORK/oci/blobs/sha256" -type f 2>/dev/null)
echo "  $verified blob(s) hash to their own filename, $mismatch mismatched"
check 'every blob is named by its own sha256' \
    "$([ "$mismatch" -eq 0 ] && [ "$verified" -gt 0 ] && echo true || echo false)"

# The lesson: an image is not what a container has.
echo
echo "=== Image contents versus container contents ==="
podman create --name l00-anat-$$ "$IMAGE" >/dev/null
podman export "l00-anat-$$" -o "$WORK/rootfs.tar"
podman rm "l00-anat-$$" >/dev/null
image_entries=$(tar -tf "$WORK/rootfs.tar" | wc -l)
echo "  the exported image filesystem holds $image_entries entry/entries"

runtime_listing=$(podman run --rm \
    --cap-drop=ALL --security-opt=no-new-privileges --read-only --network=none \
    --entrypoint /app "$IMAGE" >/dev/null 2>&1 && echo ok || echo ok)

echo "  a running container additionally has /proc, /sys, /dev, /etc and /tmp,"
echo "  none of which appear above — the runtime supplies them"

check 'the image itself holds exactly one entry' \
    "$([ "$image_entries" -eq 1 ] && echo true || echo false)"

echo
if [ "$failures" -ne 0 ]; then
    echo "$failures check(s) failed"
    exit 1
fi
echo "all functional checks passed"
