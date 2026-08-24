import json

import pytest
from pydantic import ValidationError

from nandatown.records import (
    EvidenceResult,
    StageResult,
    TestProfile,
    TownEvent,
    canonical_json,
    fingerprint,
)


def sample_profile() -> TestProfile:
    return TestProfile(
        name="quote-clean",
        task={
            "kind": "quote",
            "sku": "widget",
            "quantity": 2,
            "unit_price_cents": 1995,
            "expected_total_cents": 3990,
        },
        roles={"buyer": "buyer", "seller": "seller"},
        capabilities={"buyer": [], "seller": ["quote.read"]},
        fault="none",
        lease_seconds=5.0,
        evaluator="stage-evaluator",
    )


def test_fingerprint_stable_across_key_order():
    a = {"b": 1, "a": [1, 2, {"z": True, "y": None}]}
    b = {"a": [1, 2, {"y": None, "z": True}], "b": 1}
    assert fingerprint(a) == fingerprint(b)
    assert fingerprint(a).startswith("sha256:")


def test_fingerprint_changes_with_content():
    assert fingerprint({"total_cents": 3990}) != fingerprint({"total_cents": 3991})


def test_canonical_json_is_compact_and_sorted():
    s = canonical_json({"b": 1, "a": 2})
    assert s == '{"a":2,"b":1}'


def test_profile_round_trips_through_json():
    p = sample_profile()
    p2 = TestProfile.model_validate(json.loads(p.model_dump_json()))
    assert p2 == p
    assert fingerprint(p.model_dump()) == fingerprint(p2.model_dump())


def test_event_requires_observer_and_kind():
    with pytest.raises(ValidationError):
        TownEvent(event_id="ev-1", run_id="r", at=1.0, subject="q-1", detail={})


def test_evidence_result_verdict_fields():
    r = EvidenceResult(
        run_id="run-1",
        evaluator_version="0.2.0",
        stages=[StageResult(name="accepted", status="passed", evidence=["ev-1"])],
        verdict="passed",
        evaluated_at=1.0,
    )
    assert r.stages[0].status == "passed"
    with pytest.raises(ValidationError):
        StageResult(name="accepted", status="maybe")
