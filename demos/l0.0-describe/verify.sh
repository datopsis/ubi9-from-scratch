#!/usr/bin/env bash
# Functional verification for L0.0.
#
# L0.0's job is to describe its environment truthfully, so verification checks
# that its claims match what the image actually contains — not merely that the
# process started.
#
# Usage: demos/l0.0-describe/verify.sh <image>

set -euo pipefail

IMAGE="${1:?usage: verify.sh <image>}"
failures=0

expect() {
    local label="$1" pattern="$2" haystack="$3"
    if echo "$haystack" | grep -q "$pattern"; then
        printf '  PASS  %s\n' "$label"
    else
        printf '  FAIL  %s\n        expected to match: %s\n' "$label" "$pattern"
        failures=$((failures + 1))
    fi
}

echo "Report output"
report=$(podman run --rm "$IMAGE")
echo "$report" | sed 's/^/  /'

echo
echo "Claim checks"
expect 'exceptions work in a static link'   'exceptions           : working'      "$report"
expect 'no shared libraries mapped'         'shared libraries     : 0'           "$report"
expect 'the binary can see itself'          '/app .* present'                    "$report"
expect 'no shell in the image'              '/bin/sh .* absent'                  "$report"
expect 'no user database'                   '/etc/passwd .* absent'              "$report"
expect 'no C library on disk'               'libc.so.6 .* absent'                "$report"
expect 'no package database'                'rpmdb.sqlite .* absent'             "$report"

echo
echo "Exit status"
if podman run --rm "$IMAGE" >/dev/null; then
    printf '  PASS  exits zero when its claims hold\n'
else
    printf '  FAIL  non-zero exit: a claim did not hold\n'
    failures=$((failures + 1))
fi

# The container must stay up under --wait, or the exec tutorial cannot work.
echo
echo "Exec support"
name="l00-exec-check-$$"
podman run -d -i --name "$name" "$IMAGE" --wait >/dev/null
cleanup() { podman rm -f "$name" >/dev/null 2>&1 || true; }
trap cleanup EXIT

ready=0
for _ in $(seq 1 25); do
    if podman logs "$name" 2>/dev/null | grep -q 'Holding open for exec'; then
        ready=1
        break
    fi
done
if [ "$ready" -ne 1 ]; then
    printf '  FAIL  container did not reach the holding state\n'
    failures=$((failures + 1))
else
    printf '  PASS  container stays running under --wait\n'
    # exec must work for a binary that exists in the image...
    if podman exec "$name" /app >/dev/null 2>&1; then
        printf '  PASS  podman exec runs /app inside the running container\n'
    else
        printf '  FAIL  podman exec /app did not succeed\n'
        failures=$((failures + 1))
    fi
    # ...and must fail for one that does not, which is the teaching point.
    if podman exec "$name" /bin/sh -c 'echo hi' >/dev/null 2>&1; then
        printf '  FAIL  a shell was found; this image should not have one\n'
        failures=$((failures + 1))
    else
        printf '  PASS  podman exec /bin/sh fails — there is no shell to exec\n'
    fi
fi

echo
if [ "$failures" -ne 0 ]; then
    echo "$failures check(s) failed"
    exit 1
fi
echo "all functional checks passed"
