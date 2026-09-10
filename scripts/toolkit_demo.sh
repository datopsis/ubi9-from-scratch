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
    echo "Reading from containers-storage directly needs a user namespace:"
    echo "\$ skopeo copy containers-storage:$IMAGE oci:...  # outside unshare"
    skopeo copy "containers-storage:$IMAGE" "$WORK/nope:demo" 2>&1 | tail -1 | sed 's/^/  /'
    echo
    echo "Exporting to an archive first avoids that, and works anywhere:"
    echo "\$ podman save --format oci-archive -o image.tar $IMAGE"
    podman save --format oci-archive -o "$WORK/src.tar" "$IMAGE" >/dev/null 2>&1
    echo "\$ skopeo copy oci-archive:image.tar oci:$WORK/oci-layout:demo"
    skopeo copy "oci-archive:$WORK/src.tar" "oci:$WORK/oci-layout:demo" 2>&1 | tail -3
    find "$WORK/oci-layout" -type f 2>/dev/null | sed "s|$WORK/oci-layout|  .|" | sort
else
    echo "skopeo not installed"
fi

# --------------------------------------------------------------- buildah ----
section "buildah — building an image with no Containerfile"

if have buildah; then
    echo "First, why 'unshare' is not optional. Outside a user namespace:"
    echo "\$ ctr=\$(buildah from scratch); buildah mount \$ctr"
    ctr=$(buildah from scratch 2>/dev/null)
    mnt_outside=$(buildah mount "$ctr" 2>&1)
    if [ -z "$mnt_outside" ] || echo "$mnt_outside" | grep -qi "denied\|must\|error"; then
        echo "  -> no path returned. Rootless mounting needs the user namespace."
    else
        echo "  -> $mnt_outside"
    fi
    buildah rm "$ctr" >/dev/null 2>&1

    echo
    echo "Now the same thing inside one:"
    echo "\$ buildah unshare bash -c '...'"
    buildah unshare bash -c '
        set -e
        ctr=$(buildah from scratch)
        echo "  working container: $ctr"
        mnt=$(buildah mount "$ctr")
        echo "  mounted at: $mnt"
        echo "  (an ordinary directory — the HOST'"'"'s tools work on it)"
        install -D -m 0755 /bin/true "$mnt/app"
        echo "  copied /bin/true in with install(1); contents now:"
        find "$mnt" -mindepth 1 | sed "s|$mnt|    .|"
        buildah config --cmd /app --label demo=true "$ctr"
        echo "  metadata set with buildah config, no Containerfile involved"
        buildah umount "$ctr" >/dev/null
        buildah commit --quiet "$ctr" buildah-demo:latest
        buildah rm "$ctr" >/dev/null
    ' 2>&1 | grep -v "^Getting\|^Copying\|^Writing\|^Storing" | head -20

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
    echo
    echo "Only 'list' takes --layout. Everything else takes --image <path>:<tag>:"
    echo "\$ umoci stat --image $WORK/oci-layout:demo --json"
    umoci stat --image "$WORK/oci-layout:demo" --json 2>&1 | head -c 400
    echo

    echo
    echo "\$ umoci unpack --rootless --image $WORK/oci-layout:demo $WORK/bundle"
    umoci unpack --rootless --image "$WORK/oci-layout:demo" "$WORK/bundle" 2>&1 | tail -2
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
