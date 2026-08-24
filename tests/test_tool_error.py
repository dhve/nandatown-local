from nandatown.bundle import load_bundle, verify_bundle
from nandatown.campaign import run_campaign
from nandatown.runner import run_town


def stage(result, name):
    return next(s for s in result.stages if s.name == name)


def test_tool_error_profile_end_to_end(tmp_path):
    bundle_dir, result = run_town("quote-llm-tool-error", str(tmp_path))
    detail = [(s.name, s.status, s.note) for s in result.stages]
    assert stage(result, "tool_error_survived").status == "passed", detail
    assert stage(result, "correct").status == "passed", detail
    assert result.verdict == "passed", detail
    assert verify_bundle(bundle_dir) == []
    bundle = load_bundle(bundle_dir)
    errored = [e for e in bundle["events"]
               if e.kind == "ack_recorded"
               and e.detail.get("note", {}).get("tool_errors", 0) >= 1]
    assert errored, "the seller must report the recovered tool error"


def test_campaign_drift_canary_on_llm_profile(tmp_path):
    campaign_dir, aggregate = run_campaign("quote-llm", 2,
                                           str(tmp_path))
    assert aggregate["observed_models"] == ["mock:v1"]
    assert aggregate["model_drift_detected"] is False
    with open(f"{campaign_dir}/campaign-report.md") as f:
        text = f.read()
    assert "stable across trials" in text
    assert "canary" in text
