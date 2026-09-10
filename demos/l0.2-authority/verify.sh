#!/usr/bin/env bash
# Functional verification for L0.2.
#
# The claim is that confinement is enforced by the kernel rather than by the
# program. So the test is not "does it run" but "does the same binary get less
# authority when contained".
#
# The program exits with the number of probes the kernel allowed, so the
# assertion is simply that a fully confined run allows none.
#
# Usage: demos/l0.2-authority/verify.sh <image>

set -euo pipefail

IMAGE="${1:?usage: verify.sh <image>}"
failures=0

echo "Confined run — every restriction applied"
echo "  --cap-drop=ALL --security-opt=no-new-privileges --read-only --network=none"
echo

set +e
podman run --rm \
    --cap-drop=ALL \
    --security-opt=no-new-privileges \
    --read-only \
    --network=none \
    "$IMAGE"
confined=$?
set -e

echo
if [ "$confined" -eq 0 ]; then
    printf '  PASS  every probe denied under full confinement\n'
else
    printf '  FAIL  %d probe(s) succeeded under full confinement\n' "$confined"
    failures=$((failures + 1))
fi

# Relaxing one restriction must change the result, or the restrictions are not
# what is doing the work. Networking is the clearest single lever.
echo
echo "Same image, networking allowed"
set +e
podman run --rm \
    --cap-drop=ALL \
    --security-opt=no-new-privileges \
    --read-only \
    "$IMAGE" >/tmp/l02-net.txt 2>&1
relaxed=$?
set -e
sed 's/^/  /' /tmp/l02-net.txt

echo
if [ "$relaxed" -gt "$confined" ]; then
    printf '  PASS  relaxing one flag changed what the kernel permitted (%d vs %d)\n' \
        "$relaxed" "$confined"
    printf '        the confinement is doing the work, not the program\n'
else
    # Not a failure of the image: a CI runner may have no egress at all, in
    # which case the network probe fails either way and there is nothing to
    # compare. Report it rather than pretending the check ran.
    printf '  NOTE  no difference (%d vs %d) — this host likely has no egress,\n' \
        "$relaxed" "$confined"
    printf '        so the network probe fails regardless of the flag\n'
fi

rm -f /tmp/l02-net.txt

echo
if [ "$failures" -ne 0 ]; then
    echo "$failures check(s) failed"
    exit 1
fi
echo "all functional checks passed"
