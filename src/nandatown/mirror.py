"""Walk-away mirroring: evidence that survives its origin.

A bundle is content addressed by its fingerprint. Mirror it anywhere,
lose the original, lose all but one mirror, and the run can still be
recovered and verified byte for byte. Passing the walk-away test
proves one recovery path, not truth; the verify step still judges the
evidence itself.
"""

from __future__ import annotations

import json
import os
import shutil


class MirrorError(Exception):
    pass


def _fingerprint_of(bundle_dir: str) -> str:
    with open(os.path.join(bundle_dir, "manifest.json")) as f:
        return json.load(f)["bundle_fingerprint"]


def mirror_bundle(bundle_dir: str, mirror_dir: str) -> str:
    fingerprint = _fingerprint_of(bundle_dir)
    slug = fingerprint.removeprefix("sha256:")
    destination = os.path.join(mirror_dir, slug)
    if os.path.exists(destination):
        return destination
    os.makedirs(mirror_dir, exist_ok=True)
    shutil.copytree(bundle_dir, destination,
                    ignore=shutil.ignore_patterns("state"))
    return destination


def recover_bundle(fingerprint: str, mirrors: list[str],
                   out_dir: str) -> str:
    from .bundle import verify_bundle

    slug = fingerprint.removeprefix("sha256:")
    for mirror in mirrors:
        candidate = os.path.join(mirror, slug)
        if not os.path.isdir(candidate):
            continue
        destination = os.path.join(out_dir, f"recovered-{slug[:12]}")
        if os.path.exists(destination):
            shutil.rmtree(destination)
        shutil.copytree(candidate, destination)
        if _fingerprint_of(destination) != fingerprint:
            raise MirrorError(f"mirror {mirror} holds a bundle whose"
                              " manifest disagrees with its address")
        problems = verify_bundle(destination)
        if problems:
            raise MirrorError(f"recovered bundle fails verification:"
                              f" {problems}")
        return destination
    raise MirrorError(f"no surviving mirror holds {fingerprint}")
