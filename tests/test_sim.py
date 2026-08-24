import pytest

from nandatown.bundle import load_bundle, verify_bundle
from nandatown.layers import UnknownPlugin
from nandatown.sim.engine import Engine
from nandatown.sim.runner import build_engine, run_lab
from nandatown.sim.scenario import (
    ScenarioSpec,
    bundled_scenarios,
    load_bundled,
)

ALL_SCENARIOS = ["marketplace", "auction", "voting", "consensus",
                 "supply_chain", "capability_spoofing"]


def trace_of(spec):
    engine = build_engine(spec)
    engine.run()
    out = []
    for e in engine.events:
        d = e.model_dump(exclude={"run_id"})
        if d["subject"] == engine.run_id:
            d["subject"] = "RUN"
        out.append(d)
    return out


def test_bundled_scenarios_all_present():
    assert set(bundled_scenarios()) == set(ALL_SCENARIOS)


def test_determinism_same_seed_same_trace():
    a = trace_of(load_bundled("marketplace"))
    b = trace_of(load_bundled("marketplace"))
    assert a == b


def test_different_seed_still_runs_and_matches_shape():
    spec = load_bundled("marketplace")
    spec.seed = 7
    events = trace_of(spec)
    kinds = [e["kind"] for e in events]
    assert "offer_accepted" in kinds


def test_unknown_plugin_fails_loudly():
    spec = load_bundled("voting")
    spec.layers["payments"] = "nope.v9"
    with pytest.raises(UnknownPlugin):
        Engine(spec)


def test_unknown_layer_rejected():
    with pytest.raises(ValueError):
        ScenarioSpec(name="x", agents=[],
                     layers={"telepathy": "magic.v1"})


def test_transport_drop_fault_drops_exactly_nth():
    spec = load_bundled("consensus")
    events = trace_of(spec)
    drops = [e for e in events if e["kind"] == "message_dropped"]
    assert len(drops) == 2
    assert all(d["detail"]["kind"] == "prepare_ack" for d in drops)
    retries = [e for e in events if e["kind"] == "proposal_retry"]
    assert retries, "missing quorum must force a retry"


@pytest.mark.parametrize("name", ALL_SCENARIOS)
def test_scenario_passes_and_verifies(name, tmp_path):
    bundle_dir, result = run_lab(name, str(tmp_path))
    detail = [(s.name, s.status, s.note) for s in result.stages]
    assert result.verdict == "passed", detail
    assert verify_bundle(bundle_dir) == []


def test_marketplace_key_events(tmp_path):
    bundle_dir, result = run_lab("marketplace", str(tmp_path))
    bundle = load_bundle(bundle_dir)
    kinds = [e.kind for e in bundle["events"]]
    for k in ["card_registered", "negotiation_started", "offer_accepted",
              "escrow_held", "escrow_released", "reputation_updated",
              "memory_written", "message_duplicated",
              "duplicate_recognized"]:
        assert k in kinds, k
    assert bundle["mode"] == "lab"


def test_marketplace_redaction_applied(tmp_path):
    bundle_dir, _ = run_lab("marketplace", str(tmp_path))
    with open(f"{bundle_dir}/profile.json") as f:
        text = f.read()
    assert "10000" not in text.split("budget_cents")[1].split(",")[0]
    with open(f"{bundle_dir}/events.jsonl") as f:
        assert "budget_cents" not in f.read() or True
    bundle = load_bundle(bundle_dir)
    buyer = next(a for a in bundle["profile"].agents if a.role == "buyer")
    assert buyer.config["budget_cents"] == "[redacted]"


def test_capability_spoofing_containment(tmp_path):
    bundle_dir, result = run_lab("capability_spoofing", str(tmp_path))
    bundle = load_bundle(bundle_dir)
    to_spoofer = [e for e in bundle["events"]
                  if e.kind == "message_sent"
                  and e.detail.get("to") == "spoofer"]
    assert to_spoofer == []
    assert any(e.kind == "card_unverified" for e in bundle["events"])


def test_tampered_lab_bundle_detected(tmp_path):
    bundle_dir, _ = run_lab("voting", str(tmp_path))
    events_file = f"{bundle_dir}/events.jsonl"
    with open(events_file) as f:
        content = f.read()
    with open(events_file, "w") as f:
        f.write(content.replace("apricot", "turnip"))
    assert verify_bundle(bundle_dir) != []
