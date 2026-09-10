#!/usr/bin/env python3
"""Acquire a digest-pinned image from a registry and verify every blob.

WP1. Talks the OCI distribution API directly rather than going through a
container runtime, so the recorded result describes the image as published
rather than one runtime's view of it. Every blob is verified by recomputing
its SHA-256 before it is used; a mismatch is fatal.

Requires only the standard library.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import urllib.request
from pathlib import Path

REGISTRY = "registry.access.redhat.com"
REPOSITORY = "ubi9/ubi-micro"

# The pinned subject of this study. Resolved from :latest on 2026-09-09.
# Findings are recorded against this digest, never against a floating tag.
PINNED_INDEX = "sha256:f332c99eb8f798a8486821c91937f10ad64ee83d7e739303be2df051040918f6"

MANIFEST_ACCEPT = ",".join(
    [
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    ]
)


def _get(url: str, accept: str | None = None) -> tuple[bytes, dict[str, str]]:
    request = urllib.request.Request(url)
    request.add_header("User-Agent", "ubi9-micro-from-scratch/wp1")
    if accept:
        request.add_header("Accept", accept)
    with urllib.request.urlopen(request) as response:
        return response.read(), {k.lower(): v for k, v in response.headers.items()}


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def verified_fetch(url: str, expected: str, accept: str | None = None) -> bytes:
    """Fetch a content-addressed blob and refuse to return unverified bytes."""
    body, headers = _get(url, accept)
    actual = _digest(body)
    if actual != expected:
        raise SystemExit(f"digest mismatch for {url}\n  expected {expected}\n  actual   {actual}")
    advertised = headers.get("docker-content-digest")
    if advertised and advertised != expected:
        raise SystemExit(f"registry advertised {advertised}, expected {expected}")
    return body


def resolve_tag(registry: str, repository: str, tag: str) -> tuple[str, bytes]:
    """Resolve a floating tag to the digest of the manifest it points at."""
    url = f"https://{registry}/v2/{repository}/manifests/{tag}"
    body, headers = _get(url, MANIFEST_ACCEPT)
    computed = _digest(body)
    advertised = headers.get("docker-content-digest")
    if advertised and advertised != computed:
        raise SystemExit(f"tag {tag}: registry said {advertised}, body hashes to {computed}")
    return computed, body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", default=REGISTRY)
    parser.add_argument("--repository", default=REPOSITORY)
    parser.add_argument(
        "--ref",
        default=PINNED_INDEX,
        help="digest to acquire; pass a tag only to discover a new digest",
    )
    parser.add_argument("--arch", default="amd64")
    parser.add_argument("--out", type=Path, default=Path("work"))
    parser.add_argument(
        "--resolve-only",
        action="store_true",
        help="print the digest a tag resolves to and stop",
    )
    args = parser.parse_args()

    base = f"https://{args.registry}/v2/{args.repository}"

    if not args.ref.startswith("sha256:"):
        digest, _ = resolve_tag(args.registry, args.repository, args.ref)
        print(f"{args.registry}/{args.repository}:{args.ref}")
        print(f"  resolves to {digest}")
        if args.resolve_only:
            return 0
        if digest != PINNED_INDEX:
            print(f"  NOTE: differs from the pinned subject {PINNED_INDEX}", file=sys.stderr)
        args.ref = digest

    out = args.out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    index_bytes = verified_fetch(f"{base}/manifests/{args.ref}", args.ref, MANIFEST_ACCEPT)
    (out / "index.json").write_bytes(index_bytes)
    index = json.loads(index_bytes)
    print(f"index    {args.ref}  ({len(index_bytes)} B)  VERIFIED")

    if "manifests" not in index:
        raise SystemExit("expected a manifest list; single manifests are not handled yet")

    platforms = {
        (m["platform"]["architecture"], m["platform"].get("variant", "")): m
        for m in index["manifests"]
    }
    print("  platforms: " + ", ".join(sorted(a + (("/" + v) if v else "") for a, v in platforms)))

    chosen = next((m for (a, _), m in platforms.items() if a == args.arch), None)
    if chosen is None:
        raise SystemExit(f"architecture {args.arch} not present in the index")

    manifest_digest = chosen["digest"]
    manifest_bytes = verified_fetch(
        f"{base}/manifests/{manifest_digest}", manifest_digest, MANIFEST_ACCEPT
    )
    (out / "manifest.json").write_bytes(manifest_bytes)
    manifest = json.loads(manifest_bytes)
    print(f"manifest {manifest_digest}  ({len(manifest_bytes)} B)  VERIFIED  [{args.arch}]")

    config_digest = manifest["config"]["digest"]
    config_bytes = verified_fetch(f"{base}/blobs/{config_digest}", config_digest)
    (out / "config.json").write_bytes(config_bytes)
    print(f"config   {config_digest}  ({len(config_bytes)} B)  VERIFIED")

    layers = manifest["layers"]
    print(f"layers   {len(layers)}")
    for n, layer in enumerate(layers):
        layer_digest = layer["digest"]
        layer_bytes = verified_fetch(f"{base}/blobs/{layer_digest}", layer_digest)
        path = out / f"layer-{n}.tar.gz"
        path.write_bytes(layer_bytes)
        print(f"  [{n}] {layer_digest}  ({len(layer_bytes)} B)  VERIFIED")

    (out / "subject.json").write_text(
        json.dumps(
            {
                "registry": args.registry,
                "repository": args.repository,
                "index_digest": args.ref,
                "architecture": args.arch,
                "manifest_digest": manifest_digest,
                "config_digest": config_digest,
                "layer_digests": [layer["digest"] for layer in layers],
            },
            indent=2,
        )
        + "\n"
    )
    print(f"\nwrote {out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
