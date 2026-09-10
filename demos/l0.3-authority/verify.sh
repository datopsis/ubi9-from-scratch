#!/usr/bin/env bash
# Functional verification for L0.2.
#
# The claim is that confinement is enforced by the kernel, not by the program.
# So the test is not "does it run" but "does the same binary get different
# authority depending on how it is launched".
#
# Note what this does NOT assert: that a confined run allows nothing. A scratch
# image is not empty at runtime — the container runtime injects /etc/passwd for
# the declared USER and mounts a tmpfs on /tmp. Asserting zero would be
# asserting something false. What is asserted is the confinement that actually
# holds, and that relaxing a flag changes the result.
#
# Usage: demos/l0.3-authority/verify.sh <image>

set -euo pipefail

IMAGE="${1:?usage: verify.sh <image>}"
failures=0

check() {
    local label="$1" pattern="$2" text="$3"
    if echo "$text" | grep -q "$pattern"; then
        printf '  PASS  %s\n' "$label"
    else
        printf '  FAIL  %s (expected to match: %s)\n' "$label" "$pattern"
        failures=$((failures + 1))
    fi
}

echo "=== Confined run ==="
echo "--cap-drop=ALL --security-opt=no-new-privileges --read-only --network=none"
echo
set +e
confined_out=$(podman run --rm \
    --cap-drop=ALL --security-opt=no-new-privileges --read-only --network=none \
    "$IMAGE" 2>&1)
confined=$?
set -e
echo "$confined_out" | sed 's/^/  /'

echo
check 'every capability dropped'      'effective capabilities    : 0000000000000000' "$confined_out"
check 'runs as a non-root uid'        'uid 1000'                                     "$confined_out"
check 'no shell can be spawned'       'spawn a shell.*denied'                        "$confined_out"
check 'cannot enumerate host processes' 'enumerate processes.*denied'                "$confined_out"
check 'no network reachable'          'reach 1.1.1.1:53.*denied'                     "$confined_out"

echo
echo "=== Same image, networking allowed ==="
set +e
relaxed_out=$(podman run --rm \
    --cap-drop=ALL --security-opt=no-new-privileges --read-only \
    "$IMAGE" 2>&1)
relaxed=$?
set -e
echo "$relaxed_out" | sed 's/^/  /'

echo
if [ "$relaxed" -gt "$confined" ]; then
    printf '  PASS  one flag changed what the kernel permitted (%d allowed vs %d)\n' \
        "$relaxed" "$confined"
    printf '        the confinement does the work, not the program\n'
else
    printf '  NOTE  no difference (%d vs %d) — this host likely has no egress,\n' \
        "$relaxed" "$confined"
    printf '        so the network probe fails either way\n'
fi

# The point that lands hardest: from the host, a container is just a process.
echo
echo "=== The same process, seen from the host ==="
name="l02-hold-$$"
podman run -d -i --name "$name" \
    --cap-drop=ALL --security-opt=no-new-privileges --read-only --network=none \
    "$IMAGE" --hold >/dev/null
cleanup() { podman rm -f "$name" >/dev/null 2>&1 || true; }
trap cleanup EXIT

ready=0
for _ in $(seq 1 40); do
    if podman logs "$name" 2>/dev/null | grep -q 'Holding'; then ready=1; break; fi
done

if [ "$ready" -ne 1 ]; then
    printf '  FAIL  container did not reach the holding state\n'
    failures=$((failures + 1))
else
    inside=$(podman logs "$name" 2>/dev/null | grep -o 'pid [0-9]*' | head -1 | awk '{print $2}')
    hostpid=$(podman inspect "$name" --format '{{.State.Pid}}')

    echo "  The container believes it is pid $inside."
    echo "  The host knows it as pid $hostpid. Both are true."
    echo
    echo "  Host process tree:"
    if command -v ps >/dev/null 2>&1; then
        ps -o pid,ppid,user,args -p "$hostpid" 2>/dev/null | sed 's/^/    /' || true
        echo
        echo "  Its parent chain on the host:"
        pid="$hostpid"
        for _ in 1 2 3 4; do
            line=$(ps -o pid=,ppid=,comm= -p "$pid" 2>/dev/null) || break
            echo "    $line"
            pid=$(echo "$line" | awk '{print $2}')
            [ -z "$pid" ] || [ "$pid" = "0" ] && break
        done
    fi

    echo
    echo "  The kernel's own view of what it granted that process:"
    if [ -r "/proc/$hostpid/status" ]; then
        grep -E '^(Name|Pid|NSpid|CapEff|CapBnd|NoNewPrivs|Seccomp):' \
            "/proc/$hostpid/status" 2>/dev/null | sed 's/^/    /' || true
    else
        echo "    /proc/$hostpid/status not readable from here"
    fi

    if [ "$inside" = "1" ] && [ "$hostpid" != "1" ]; then
        printf '\n  PASS  the process is pid 1 to itself and pid %s to the host\n' "$hostpid"
    else
        printf '\n  NOTE  pid inside=%s host=%s — expected 1 and something else\n' \
            "$inside" "$hostpid"
    fi
fi

echo
if [ "$failures" -ne 0 ]; then
    echo "$failures check(s) failed"
    exit 1
fi
echo "all functional checks passed"
