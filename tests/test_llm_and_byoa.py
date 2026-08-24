import json
import os
import sys

import httpx

from nandatown.bundle import load_bundle, verify_bundle
from nandatown.participants.llm import (
    MESSAGE_BUDGET,
    TOOLS,
    LLMParticipant,
    ModelClient,
)
from nandatown.runner import run_town

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def stage(result, name):
    return next(s for s in result.stages if s.name == name)


def test_model_client_parses_openai_shape():
    def responder(request):
        payload = json.loads(request.content)
        assert payload["model"] == "qwen-test"
        assert any(t["function"]["name"] == "claim_work"
                   for t in payload["tools"])
        return httpx.Response(200, json={"choices": [{"message": {
            "content": "thinking",
            "tool_calls": [{"id": "c1", "function": {
                "name": "claim_work", "arguments": "{}"}}]}}]})

    client = ModelClient("qwen-test", "seller",
                         http=httpx.Client(
                             transport=httpx.MockTransport(responder),
                             base_url="http://model"))
    out = client.chat([{"role": "system", "content": "s"}], TOOLS)
    assert out["tool_calls"][0]["function"]["name"] == "claim_work"


def test_truncation_keeps_system_and_counts(tmp_path):
    p = LLMParticipant.__new__(LLMParticipant)
    p.fault = "context_truncation"
    p.truncations = 0
    p.messages = [{"role": "system", "content": "SYSTEM"}] + [
        {"role": "assistant", "content": f"m{i}", "tool_calls": []}
        for i in range(MESSAGE_BUDGET + 4)]
    p._maybe_truncate()
    assert p.truncations == 1
    assert p.messages[0]["content"] == "SYSTEM"
    assert len(p.messages) <= 5


def test_llm_profile_end_to_end_with_mock_brain(tmp_path):
    bundle_dir, result = run_town("quote-llm", str(tmp_path))
    detail = [(s.name, s.status, s.note) for s in result.stages]
    assert result.verdict == "passed", detail
    assert verify_bundle(bundle_dir) == []
    bundle = load_bundle(bundle_dir)
    assert bundle["run"].config["model"] == "mock:v1"
    assert bundle["run"].config["runtimes"] == {"buyer": "llm",
                                                "seller": "llm"}
    names = {r["name"] for r in bundle["run"].config["skill_releases"]}
    assert "town-protocol" in names


def test_llm_truncation_profile_end_to_end(tmp_path):
    bundle_dir, result = run_town("quote-llm-truncation", str(tmp_path))
    detail = [(s.name, s.status, s.note) for s in result.stages]
    assert stage(result, "truncation_survived").status == "passed", detail
    assert stage(result, "correct").status == "passed", detail
    assert result.verdict == "passed", detail
    assert verify_bundle(bundle_dir) == []


def test_byoa_external_seller_end_to_end(tmp_path):
    example = os.path.join(REPO_ROOT, "examples", "byoa_seller.py")
    bundle_dir, result = run_town(
        "quote-clean", str(tmp_path),
        external={"seller": [sys.executable, example]})
    detail = [(s.name, s.status, s.note) for s in result.stages]
    assert result.verdict == "passed", detail
    bundle = load_bundle(bundle_dir)
    seller_acks = [e for e in bundle["events"]
                   if e.kind == "ack_recorded" and e.observer == "seller"]
    assert seller_acks[0].detail["note"].get("runtime") == "byoa-stdlib"
