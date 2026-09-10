#!/usr/bin/env bash
# Functional verification for L0.
#
# Proves the container does its job, not merely that it starts. Every rung of
# the ladder computes the same SHA-256 digests, so this script is the shared
# contract: an image that passes it produces correct output regardless of how
# it computes it.
#
# Usage: demos/l0-static/verify.sh <image>

set -euo pipefail

IMAGE="${1:?usage: verify.sh <image>}"
failures=0

# FIPS 180-4 test vectors: input, expected digest.
check() {
    local label="$1" input="$2" expected="$3" actual
    actual=$(printf '%s' "$input" | podman run --rm -i "$IMAGE")
    if [ "$actual" = "$expected" ]; then
        printf '  PASS  %-28s %s\n' "$label" "$actual"
    else
        printf '  FAIL  %-28s\n        expected %s\n        actual   %s\n' \
            "$label" "$expected" "$actual"
        failures=$((failures + 1))
    fi
}

echo "Functional test: SHA-256 of stdin"

check 'empty input' \
    '' \
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'

check '"abc"' \
    'abc' \
    'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'

check '448-bit message' \
    'abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq' \
    '248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1'

# A message larger than one 64-byte block, exercising the buffering path that
# the short vectors above do not reach.
echo
echo "Functional test: multi-block input"
long_input=$(head -c 100000 /dev/zero | tr '\0' 'a')
expected_long=$(printf '%s' "$long_input" | sha256sum | cut -d' ' -f1)
actual_long=$(printf '%s' "$long_input" | podman run --rm -i "$IMAGE")
if [ "$actual_long" = "$expected_long" ]; then
    printf '  PASS  %-28s %s\n' "100,000 bytes" "$actual_long"
else
    printf '  FAIL  %-28s\n        expected %s\n        actual   %s\n' \
        "100,000 bytes" "$expected_long" "$actual_long"
    failures=$((failures + 1))
fi

# The report mode must also succeed, and must confirm nothing was loaded from
# the image.
echo
echo "Runtime report"
report=$(podman run --rm "$IMAGE" --report)
echo "$report" | sed 's/^/  /'
if ! echo "$report" | grep -q 'shared libraries     : 0'; then
    echo "  FAIL  expected zero shared libraries mapped"
    failures=$((failures + 1))
fi

echo
if [ "$failures" -ne 0 ]; then
    echo "$failures check(s) failed"
    exit 1
fi
echo "all functional checks passed"
