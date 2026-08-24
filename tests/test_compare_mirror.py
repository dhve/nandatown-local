import json
import os
import shutil

import pytest

from nandatown.cli import main
from nandatown.compare import run_comparison
from nandatown.mirror import MirrorError, mirror_bundle, recover_bundle
from nandatown.sim.runner import run_lab


def test_comparison_shows_what_the_swap_breaks(tmp_path):
    compare_dir, comparison = run_comparison(
        "capability_spoofing", {"auth": "plain.v1"}, str(tmp_path))
    assert comparison["variants"]["baseline"]["verdict"] == "passed"
    assert comparison["variants"]["swapped"]["verdict"] == "failed"
    assert "containment" in comparison["differences"]
    assert "spoof_detected" in comparison["differences"]
    with open(os.path.join(compare_dir, "comparison.md")) as f:
        text = f.read()
    assert "Same agents, same scenario, same seed" in text
    assert "<- differs" in text
    bundles = [d for d in os.listdir(compare_dir)
               if d.startswith("sim-")]
    assert len(bundles) == 2


def test_comparison_with_no_behavioral_change(tmp_path):
    _, comparison = run_comparison("voting", {"payments": "ledger.v1"},
                                   str(tmp_path))
    assert comparison["differences"] == []


def test_walk_away_recovery(tmp_path):
    bundle_dir, _ = run_lab("voting", str(tmp_path / "runs"))
    with open(os.path.join(bundle_dir, "manifest.json")) as f:
        fingerprint = json.load(f)["bundle_fingerprint"]

    mirror_a = str(tmp_path / "mirror-a")
    mirror_b = str(tmp_path / "mirror-b")
    mirror_bundle(bundle_dir, mirror_a)
    mirror_bundle(bundle_dir, mirror_b)

    # Walk away: the original database is gone, the original bundle is
    # gone, and the first mirror is gone too.
    shutil.rmtree(bundle_dir)
    shutil.rmtree(mirror_a)

    restored = recover_bundle(fingerprint, [mirror_a, mirror_b],
                              str(tmp_path / "fresh"))
    assert os.path.exists(os.path.join(restored, "events.jsonl"))

    shutil.rmtree(mirror_b)
    with pytest.raises(MirrorError):
        recover_bundle(fingerprint, [mirror_a, mirror_b],
                       str(tmp_path / "fresh2"))


def test_tampered_mirror_is_rejected(tmp_path):
    bundle_dir, _ = run_lab("voting", str(tmp_path / "runs"))
    with open(os.path.join(bundle_dir, "manifest.json")) as f:
        fingerprint = json.load(f)["bundle_fingerprint"]
    mirror = str(tmp_path / "mirror")
    stored = mirror_bundle(bundle_dir, mirror)
    events = os.path.join(stored, "events.jsonl")
    with open(events, "a") as f:
        f.write('{"forged": true}\n')
    with pytest.raises(MirrorError):
        recover_bundle(fingerprint, [mirror], str(tmp_path / "fresh"))


def test_cli_compare_and_mirror(tmp_path, capsys):
    out = str(tmp_path)
    assert main(["compare", "voting", "--swap", "trust=reputation.v1",
                 "--out", out]) == 0
    text = capsys.readouterr().out
    assert "Protocol Comparison" in text
    run_dirs = [d for d in os.listdir(out) if d.startswith("cmp-")]
    bundle = None
    for d in os.listdir(os.path.join(out, run_dirs[0])):
        if d.startswith("sim-"):
            bundle = os.path.join(out, run_dirs[0], d)
    assert main(["mirror", bundle, str(tmp_path / "m")]) == 0
    with open(os.path.join(bundle, "manifest.json")) as f:
        fingerprint = json.load(f)["bundle_fingerprint"]
    assert main(["recover", fingerprint, "--mirror",
                 str(tmp_path / "m"), "--out", out]) == 0
    assert "recovered and verified" in capsys.readouterr().out
