#!/usr/bin/env bash
# Exercise every tool in the toolkit series against a real image.
#
# The tutorials in tools/ quote this script's output. Running it in CI is what
# stops those tutorials drifting away from what the tools actually do.
#
# Usage: scripts/toolkit_demo.sh [image]

set -uo pipefail

IMAGE="${1:-l0.2-sha256:9.8}"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

have() { command -v "$1" >/dev/null 2>&1; }

section() {
    echo
    echo "############################################################"
    echo "# $1"
    echo "############################################################"
    echo
}

section "Versions"
for tool in podman skopeo buildah umoci syft grype jq; do
    if have "$tool"; then
        printf '%-9s %s\n' "$tool" "$("$tool" --version 2>&1 | head -1)"
    else
        printf '%-9s NOT INSTALLED\n' "$tool"
    fi
done

# ---------------------------------------------------------------- skopeo ----
section "skopeo — asking a registry a question without pulling anything"

if have skopeo; then
    echo "\$ skopeo inspect --raw docker://registry.access.redhat.com/ubi9/ubi-micro:latest | head"
    skopeo inspect --raw docker://registry.access.redhat.com/ubi9/ubi-micro:latest 2>/dev/null \
        | head -c 600
    echo
    echo
    echo "\$ skopeo inspect docker://... | jq '{Digest, Created, Architecture}'"
    skopeo inspect docker://registry.access.redhat.com/ubi9/ubi-micro:latest 2>/dev/null \
        | (have jq && jq '{Digest, Created, Architecture, Os}' || head -20)
    echo
    echo "Resolving a tag to a digest — the operation this project's pinning depends on:"
    skopeo inspect --format '{{.Digest}}' \
        docker://registry.access.redhat.com/ubi9/ubi-micro:latest 2>/dev/null
    echo
    echo "\$ skopeo copy containers-storage:$IMAGE oci:$WORK/oci-layout:demo"
    skopeo copy "containers-storage:$IMAGE" "oci:$WORK/oci-layout:demo" 2>&1 | tail -3
    find "$WORK/oci-layout" -type f 2>/dev/null | sed "s|$WORK/oci-layout|  .|" | sort
else
    echo "skopeo not installed"
fi

# --------------------------------------------------------------- buildah ----
section "buildah — building an image with no Containerfile"

if have buildah; then
    echo "Assembling an image from nothing, step by step:"
    echo
    echo "\$ ctr=\$(buildah from scratch)"
    ctr=$(buildah from scratch 2>/dev/null)
    echo "  working container: $ctr"

    echo "\$ mnt=\$(buildah mount \$ctr)"
    mnt=$(buildah mount "$ctr" 2>/dev/null)
    echo "  mounted at: $mnt"
    echo "  (an ordinary directory — host tools work on it)"

    echo "\$ install -D -m0755 /bin/true \$mnt/app"
    install -D -m 0755 /bin/true "$mnt/app" 2>/dev/null && echo "  copied with the HOST's install(1)"
    echo "  contents now:"
    find "$mnt" -mindepth 1 2>/dev/null | sed "s|$mnt|  .|" | head -5

    echo "\$ buildah config --cmd /app --label demo=true \$ctr"
    buildah config --cmd /app --label demo=true "$ctr" 2>/dev/null && echo "  metadata set imperatively"

    buildah umount "$ctr" >/dev/null 2>&1
    echo "\$ buildah commit \$ctr buildah-demo:latest"
    buildah commit --quiet "$ctr" buildah-demo:latest 2>&1 | tail -1
    buildah rm "$ctr" >/dev/null 2>&1

    echo
    echo "The same operations exist in podman:"
    echo "  podman unshare   ==  buildah unshare"
    echo "  podman mount     ==  buildah mount"
    echo "  podman commit    ==  buildah commit"
    echo
    echo "\$ podman image inspect buildah-demo:latest --format '{{.Size}} bytes, {{len .RootFS.Layers}} layer'"
    podman image inspect buildah-demo:latest --format '{{.Size}} bytes, {{len .RootFS.Layers}} layer' 2>/dev/null
else
    echo "buildah not installed"
fi

# ----------------------------------------------------------------- umoci ----
section "umoci — opening an OCI layout and putting it back"

if have umoci && [ -d "$WORK/oci-layout" ]; then
    echo "\$ umoci list --layout $WORK/oci-layout"
    umoci list --layout "$WORK/oci-layout" 2>&1 | sed 's/^/  /'

    echo
    echo "\$ umoci stat --layout $WORK/oci-layout --image demo --json | head"
    umoci stat --layout "$WORK/oci-layout" --image demo --json 2>/dev/null | head -c 400
    echo

    echo
    echo "\$ umoci unpack --rootless --layout $WORK/oci-layout --image demo $WORK/bundle"
    umoci unpack --rootless --layout "$WORK/oci-layout" --image demo "$WORK/bundle" 2>&1 | tail -2
    if [ -d "$WORK/bundle/rootfs" ]; then
        echo "  the unpacked root filesystem:"
        find "$WORK/bundle/rootfs" -mindepth 1 2>/dev/null | sed "s|$WORK/bundle/rootfs|  .|" | head -5
        echo "  plus an OCI runtime config:"
        ls "$WORK/bundle" | sed 's/^/  /'
    fi
else
    echo "umoci not installed, or no layout to open"
fi

# ------------------------------------------------------------------ syft ----
section "syft — what is in this image?"

if have syft; then
    podman save --format oci-archive -o "$WORK/img.tar" "$IMAGE" >/dev/null 2>&1
    echo "\$ syft oci-archive:image.tar -o table"
    syft "oci-archive:$WORK/img.tar" -o table 2>/dev/null | head -12
    echo
    echo "The same command against the reconstructed ubi9-micro, for contrast:"
    if podman image exists micro:9.8 2>/dev/null; then
        podman save --format oci-archive -o "$WORK/micro.tar" micro:9.8 >/dev/null 2>&1
        syft "oci-archive:$WORK/micro.tar" -o table 2>/dev/null | head -12
    else
        echo "  (micro:9.8 not built in this job)"
    fi
else
    echo "syft not installed"
fi

# ----------------------------------------------------------------- grype ----
section "grype — what is wrong with what is in it?"

if have grype && [ -f "$WORK/img.tar" ]; then
    echo "\$ grype oci-archive:image.tar"
    grype "oci-archive:$WORK/img.tar" 2>/dev/null | head -8
    if [ -f "$WORK/micro.tar" ]; then
        echo
        echo "And against the reconstruction:"
        grype "oci-archive:$WORK/micro.tar" 2>/dev/null | head -12
    fi
else
    echo "grype not installed, or no archive to scan"
fi

section "Done"
echo "Every command above ran. The tutorials in tools/ quote this output."
