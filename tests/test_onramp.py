import json
import os

import pytest

from nandatown.cli import main
from nandatown.onramp import (
    OnrampError,
    analyze,
    catalog_entries,
    load_openapi,
    onramp,
    slugify,
)
from nandatown.skills import parse_skill, validate_skill

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures",
                       "paylite.json")


def test_analyze_classifies_effects():
    spec, _ = load_openapi(FIXTURE)
    analysis = analyze(spec)
    assert analysis["title"] == "PayLite"
    effects = {op["operation_id"]: op["effect"]
               for op in analysis["operations"]}
    assert effects["getQuote"] == "read"
    assert effects["createPayment"] == "write"
    assert any("createPayment" in u or "/payments" in u
               for u in analysis["unknowns"])
    assert analysis["auth_schemes"] == {"apiKey": "apiKey"}


def test_onramp_generates_valid_candidate(tmp_path):
    candidate = onramp(FIXTURE, out_dir=str(tmp_path))
    assert candidate.endswith("paylite")
    with open(os.path.join(candidate, "SKILL.md")) as f:
        skill_text = f.read()
    assert validate_skill(skill_text) == []
    skill = parse_skill(skill_text)
    assert skill.role == "service"
    assert "a claim, not a fact" in skill.body
    assert "POST /payments" in skill.body
    checks = [json.loads(line) for line in
              open(os.path.join(candidate, "checks.jsonl"))]
    by_test = {c["test"]: c["result"] for c in checks}
    assert by_test["spec-parsed"] == "passed"
    assert by_test["https-servers"] == "passed"
    assert by_test["auth-declared"] == "passed"
    assert by_test["secret-scan"] == "passed"
    assert all(c["observer"] == "onramp.v1" for c in checks)


def test_fingerprint_stability_and_catalog(tmp_path):
    onramp(FIXTURE, out_dir=str(tmp_path))
    first = catalog_entries(str(tmp_path))[0]["fingerprint"]
    onramp(FIXTURE, out_dir=str(tmp_path))
    entries = catalog_entries(str(tmp_path))
    assert len(entries) == 1
    assert entries[0]["fingerprint"] == first
    assert entries[0]["status"] == "candidate-unclaimed"


def test_embedded_secret_is_caught(tmp_path):
    with open(FIXTURE) as f:
        spec = json.load(f)
    spec["info"]["description"] = \
        "Use key sk_live_AAAABBBBCCCCDDDD for testing"
    tainted = tmp_path / "tainted.json"
    tainted.write_text(json.dumps(spec))
    candidate = onramp(str(tainted), name="tainted",
                       out_dir=str(tmp_path / "services"))
    checks = [json.loads(line) for line in
              open(os.path.join(candidate, "checks.jsonl"))]
    scan = next(c for c in checks if c["test"] == "secret-scan")
    assert scan["result"] == "failed"
    assert "sk_live_AAAA" not in json.dumps(scan["evidence"])


def test_rejects_non_openapi(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"hello": "world"}')
    with pytest.raises(OnrampError):
        onramp(str(bad), out_dir=str(tmp_path))


def test_slugify():
    assert slugify("PayLite") == "paylite"
    assert slugify("Stripe Payments API") == "stripe-payments-api"
    assert slugify("42 Things") == "svc-42-things"


def test_cli_onramp_and_services(tmp_path, capsys):
    out = str(tmp_path / "services")
    assert main(["onramp", FIXTURE, "--out", out]) == 0
    assert main(["services", "--dir", out]) == 0
    assert main(["services", "paylite", "--dir", out]) == 0
    text = capsys.readouterr().out
    assert "candidate-unclaimed" in text
    assert "PayLite (candidate integration)" in text
