import os

from nandatown.bundle import load_bundle, verify_bundle
from nandatown.sim.runner import run_lab
from nandatown.sim.scenario import load_scenario_file
from nandatown.sim.upstream import adapt_upstream

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "upstream")


def fixture(name):
    return os.path.join(FIXTURES, name)


def stage(result, name):
    return next(s for s in result.stages if s.name == name)


def test_upstream_format_is_detected_and_adapted():
    spec = load_scenario_file(fixture("voting.yaml"))
    assert spec.name == "upstream-voting"
    assert spec.validator == "adapted"
    roles = [a.role for a in spec.agents]
    assert roles.count("ballot_box") == 1
    assert roles.count("voter") == 19
    assert any("coordinator adapted as ballot_box" in a
               for a in spec.adaptations)


def test_pr220_capability_fulfillment_runs_end_to_end(tmp_path):
    bundle_dir, result = run_lab(fixture("capability_fulfillment.yaml"),
                                 str(tmp_path))
    detail = [(s.name, s.status, s.note) for s in result.stages]
    assert result.verdict == "passed", detail
    for name in ["population_active", "discovery", "messages_flowed",
                 "task_completed"]:
        assert stage(result, name).status == "passed", detail
    assert verify_bundle(bundle_dir) == []
    bundle = load_bundle(bundle_dir)
    assert any("requester adapted as buyer" in a
               for a in bundle["profile"].adaptations)


def test_upstream_voting_runs_end_to_end(tmp_path):
    bundle_dir, result = run_lab(fixture("voting.yaml"), str(tmp_path))
    detail = [(s.name, s.status, s.note) for s in result.stages]
    assert result.verdict == "passed", detail
    assert verify_bundle(bundle_dir) == []


def test_upstream_marketplace_scales_population(tmp_path):
    spec = load_scenario_file(fixture("marketplace.yaml"))
    assert len(spec.agents) <= 32
    buyers = sum(1 for a in spec.agents if a.role == "buyer")
    sellers = sum(1 for a in spec.agents if a.role == "seller")
    assert buyers >= 10 and sellers >= 10
    assert any("scaled" in a for a in spec.adaptations)
    bundle_dir, result = run_lab(fixture("marketplace.yaml"),
                                 str(tmp_path))
    detail = [(s.name, s.status, s.note) for s in result.stages]
    assert result.verdict == "passed", detail


def test_drop_rate_failures_translate():
    spec = adapt_upstream({
        "name": "lossy", "seed": 1,
        "agents": {"roles": [{"name": "requester", "count": 1},
                             {"name": "provider", "count": 1}]},
        "task": {"type": "capability_fulfillment"},
        "failures": {"message_drop": 0.5, "byzantine_agents": 0.1},
        "duration": "ticks: 10000",
    })
    assert spec.faults[0].action == "drop_rate"
    assert spec.faults[0].rate == 0.2
    assert spec.max_time == 300.0
    assert any("byzantine" in a for a in spec.adaptations)


def test_unknown_task_falls_back_to_exchange():
    spec = adapt_upstream({
        "name": "mystery", "seed": 3,
        "agents": {"roles": [{"name": "alpha", "count": 1},
                             {"name": "beta", "count": 1}]},
        "task": {"type": "quantum_bartering"},
    })
    assert {a.role for a in spec.agents} == {"buyer", "seller"}
    assert any("alpha adapted as buyer" in a for a in spec.adaptations)
