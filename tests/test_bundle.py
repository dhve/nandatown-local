import json

from nandatown.bundle import load_bundle, verify_bundle, write_bundle
from nandatown.report import render_report
from nandatown.evaluator import evaluate
from nandatown.records import RunRecord, TestProfile

from test_evaluator import clean_events, profile

SCOPE_SENTENCE = ("This result applies only to the named agents, releases,"
                  " scenario, failure, evaluator, and time window.")


def make_bundle(tmp_path):
    p = profile()
    events = clean_events()
    run = RunRecord(
        run_id="run-1", profile_name=p.name, profile_fingerprint="sha256:x",
        created_at=1.0,
        participants=[{"name": "buyer", "role": "buyer"},
                      {"name": "seller", "role": "seller"}],
        releases={"nandatown": "0.2.0", "evaluator": "0.2.0",
                  "python": "3.14"},
    )
    intents = [{"intent_id": "in-1", "run_id": "run-1", "at": 1.0,
                "actor": "buyer", "action": "send",
                "payload": {"message_id": "q-1"}}]
    result = evaluate(p, "run-1", events)
    out = tmp_path / "bundle"
    write_bundle(str(out), p, run, intents, events, result)
    return str(out), result


def test_write_then_verify_is_clean(tmp_path):
    path, _ = make_bundle(tmp_path)
    assert verify_bundle(path) == []
    bundle = load_bundle(path)
    assert bundle["profile"].name == "quote-none"
    assert bundle["result"].verdict == "passed"
    assert len(bundle["events"]) == 10


def test_tampered_events_are_detected(tmp_path):
    path, _ = make_bundle(tmp_path)
    events_file = tmp_path / "bundle" / "events.jsonl"
    lines = events_file.read_text().splitlines()
    first = json.loads(lines[0])
    first["observer"] = "attacker"
    lines[0] = json.dumps(first)
    events_file.write_text("\n".join(lines) + "\n")
    problems = verify_bundle(path)
    assert any("events.jsonl" in p for p in problems)


def test_edited_result_is_detected(tmp_path):
    path, _ = make_bundle(tmp_path)
    result_file = tmp_path / "bundle" / "result.json"
    data = json.loads(result_file.read_text())
    data["verdict"] = "failed"
    for s in data["stages"]:
        if s["name"] == "correct":
            s["status"] = "failed"
    result_file.write_text(json.dumps(data))
    problems = verify_bundle(path)
    assert any("result.json" in p for p in problems)


def test_evaluator_mismatch_is_detected_even_with_valid_hashes(tmp_path):
    path, _ = make_bundle(tmp_path)
    result_file = tmp_path / "bundle" / "result.json"
    data = json.loads(result_file.read_text())
    for s in data["stages"]:
        if s["name"] == "correct":
            s["status"] = "failed"
    data["verdict"] = "failed"
    result_file.write_text(json.dumps(data))
    manifest_file = tmp_path / "bundle" / "manifest.json"
    manifest = json.loads(manifest_file.read_text())
    import hashlib
    manifest["files"]["result.json"] = "sha256:" + hashlib.sha256(
        result_file.read_bytes()).hexdigest()
    manifest_file.write_text(json.dumps(manifest))
    problems = verify_bundle(path)
    assert any("evaluator" in p for p in problems)


def test_report_contains_scope_and_stages(tmp_path):
    path, _ = make_bundle(tmp_path)
    bundle = load_bundle(path)
    text = render_report(bundle)
    assert SCOPE_SENTENCE in text
    for name in ["accepted", "claimed", "received", "processed", "response",
                 "correct", "portable_identity"]:
        assert name in text
    assert "bring" in text and "disrupt" in text and "improve" in text
    report_md = (tmp_path / "bundle" / "report.md").read_text()
    assert SCOPE_SENTENCE in report_md
    assert "—" not in text and "–" not in text
