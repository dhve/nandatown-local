import pytest

from nandatown.board import render_board, scan_bundles
from nandatown.cli import main
from nandatown.new import ScaffoldError, scaffold
from nandatown.sim.runner import run_lab
from nandatown.sim.scenario import load_scenario_file
from nandatown.skills import validate_skill


def test_new_scenario_loads_and_runs(tmp_path):
    path = scaffold("scenario", "my-town", None, str(tmp_path))
    spec = load_scenario_file(path)
    assert spec.name == "my-town"
    assert {a.role for a in spec.agents} == {"buyer", "seller"}
    bundle_dir, result = run_lab(path, str(tmp_path / "runs"))
    verdicts = {s.name: s.status for s in result.stages}
    assert verdicts["ledger_conserved"] == "passed"
    assert verdicts["validator"] == "not_enough_evidence"
    assert result.verdict == "incomplete"


def test_new_plugin_registers_when_loaded(tmp_path):
    path = scaffold("plugin", "trust", "mytrust.v1", str(tmp_path))
    import importlib.util

    spec = importlib.util.spec_from_file_location("user_plugin", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from nandatown.layers import resolve
    assert resolve("trust", "mytrust.v1").plugin_id == "mytrust.v1"


def test_new_skill_validates(tmp_path):
    path = scaffold("skill", "my.skill", None, str(tmp_path))
    with open(path) as f:
        assert validate_skill(f.read()) == []


def test_new_agent_compiles(tmp_path):
    path = scaffold("agent", "my-agent", None, str(tmp_path))
    with open(path) as f:
        compile(f.read(), path, "exec")


def test_scaffold_refuses_overwrite_and_bad_layer(tmp_path):
    scaffold("skill", "twice", None, str(tmp_path))
    with pytest.raises(ScaffoldError):
        scaffold("skill", "twice", None, str(tmp_path))
    with pytest.raises(ScaffoldError):
        scaffold("plugin", "telepathy", "x.v1", str(tmp_path))
    with pytest.raises(ScaffoldError):
        scaffold("plugin", "trust", None, str(tmp_path))


def test_board_groups_and_ranks(tmp_path):
    run_lab("voting", str(tmp_path), seed=1)
    run_lab("voting", str(tmp_path), seed=2)
    run_lab("capability_spoofing_weak_auth", str(tmp_path))
    rows = scan_bundles(str(tmp_path))
    assert len(rows) == 3
    board = render_board(str(tmp_path))
    assert "voting" in board
    assert "2/2 passed" in board
    assert "0/1 passed" in board
    lines = board.splitlines()
    voting_line = next(i for i, l in enumerate(lines) if "voting" in l)
    weak_line = next(i for i, l in enumerate(lines)
                     if "weak_auth" in l)
    assert voting_line < weak_line


def test_cli_new_and_board(tmp_path, capsys):
    assert main(["new", "scenario", "demo", "--dir", str(tmp_path)]) == 0
    assert main(["board", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "no evidence bundles" in out
