import os
import shlex
import sys

import pytest

from nandatown.bundle import load_bundle
from nandatown.cli import main
from nandatown.runner import RunnerError, parse_harness, run_town
from nandatown.sim.runner import run_lab

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLE = os.path.join(REPO_ROOT, "examples", "byoa_seller.py")


def test_parse_harness_specs():
    assert parse_harness("scripted") == {"kind": "scripted"}
    assert parse_harness("llm") == {"kind": "llm", "model": None}
    assert parse_harness("llm:qwen2.5") == {"kind": "llm",
                                            "model": "qwen2.5"}
    assert parse_harness('cmd:python my_agent.py --fast') == {
        "kind": "cmd", "command": ["python", "my_agent.py", "--fast"]}
    assert parse_harness("external") == {"kind": "external"}
    with pytest.raises(RunnerError):
        parse_harness("telepathy")
    with pytest.raises(RunnerError):
        parse_harness("cmd:")


def test_cmd_harness_runs_external_agent(tmp_path):
    spec = "cmd:" + " ".join(shlex.quote(p)
                             for p in [sys.executable, EXAMPLE])
    bundle_dir, result = run_town("quote-clean", str(tmp_path),
                                  harnesses={"seller": spec})
    detail = [(s.name, s.status, s.note) for s in result.stages]
    assert result.verdict == "passed", detail
    bundle = load_bundle(bundle_dir)
    assert bundle["run"].config["harnesses"] == {"seller": spec}


def test_llm_harness_overrides_scripted_profile(tmp_path):
    bundle_dir, result = run_town("quote-clean", str(tmp_path),
                                  harnesses={"seller": "llm:mock:alt"})
    detail = [(s.name, s.status, s.note) for s in result.stages]
    assert result.verdict == "passed", detail
    bundle = load_bundle(bundle_dir)
    assert bundle["run"].config["model"] == "mock:v1"
    assert bundle["run"].config["harnesses"]["seller"] == "llm:mock:alt"


def test_layer_override_reproduces_weak_auth_failure(tmp_path):
    bundle_dir, result = run_lab("capability_spoofing", str(tmp_path),
                                 layer_overrides={"auth": "plain.v1"})
    stages = {s.name: s.status for s in result.stages}
    assert result.verdict == "failed", stages
    assert stages["containment"] == "failed"
    bundle = load_bundle(bundle_dir)
    assert bundle["profile"].layers["auth"] == "plain.v1"


def test_plugin_flag_loads_scaffolded_plugin(tmp_path):
    from nandatown.new import scaffold

    path = scaffold("plugin", "memory", "scratch.v1", str(tmp_path))
    run_lab("voting", str(tmp_path / "runs"), plugins=[path])
    from nandatown.layers import resolve
    assert resolve("memory", "scratch.v1").plugin_id == "scratch.v1"


def test_cli_flag_scoping(tmp_path, capsys):
    assert main(["run", "voting", "--agent", "seller=llm",
                 "--out", str(tmp_path)]) == 2
    assert "Track profiles" in capsys.readouterr().out
    assert main(["run", "quote-clean", "--layer", "auth=plain.v1",
                 "--out", str(tmp_path)]) == 2
    assert "Lab scenarios" in capsys.readouterr().out
    assert main(["run", "capability_spoofing", "--layer",
                 "auth=plain.v1", "--out", str(tmp_path)]) == 1
    assert "FAILED" in capsys.readouterr().out
