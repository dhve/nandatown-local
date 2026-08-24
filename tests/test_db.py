import pytest

from nandatown.db import IdentityReuse, StaleFence, TownDB
from nandatown.records import fingerprint


@pytest.fixture()
def db(tmp_path):
    return TownDB(str(tmp_path / "town.db"))


@pytest.fixture()
def run(db):
    run_id = db.create_run(profile_json='{"name":"quote-clean"}')
    db.add_participant(run_id, "buyer", "buyer", [], "tok-b")
    db.add_participant(run_id, "seller", "seller", ["quote.read"], "tok-s")
    return run_id


BODY = {"sku": "widget", "quantity": 2, "unit_price_cents": 1995}
FP = fingerprint(BODY)


def accept(db, run_id, now=100.0):
    return db.accept_message(
        run_id, sender="buyer", message_id="q-1", to="seller",
        kind="quote_request", body=BODY, content_fingerprint=FP, now=now,
    )


def test_accept_then_claim_returns_work_with_fence(db, run):
    accepted_at, replay = accept(db, run)
    assert accepted_at == 100.0 and replay is False
    claim = db.claim_next(run, "seller", lease_seconds=5.0, now=101.0)
    assert claim["message_id"] == "q-1"
    assert claim["attempt"] == 1
    assert claim["body"] == BODY
    assert claim["from"] == "buyer"
    assert claim["lease_expires_at"] == 106.0
    assert claim["fence"]


def test_idempotent_resend_and_identity_reuse(db, run):
    accept(db, run, now=100.0)
    accepted_at, replay = accept(db, run, now=200.0)
    assert accepted_at == 100.0 and replay is True
    with pytest.raises(IdentityReuse):
        db.accept_message(
            run, sender="buyer", message_id="q-1", to="seller",
            kind="quote_request", body={"quantity": 3},
            content_fingerprint=fingerprint({"quantity": 3}), now=201.0,
        )


def test_notification_written_in_same_transaction(db, run):
    accept(db, run)
    assert db.pop_notify(run, "seller") is True
    assert db.pop_notify(run, "seller") is False


def test_expired_lease_reclaim_and_stale_fence(db, run):
    accept(db, run)
    first = db.claim_next(run, "seller", lease_seconds=2.0, now=101.0)
    assert db.claim_next(run, "seller", lease_seconds=2.0, now=102.0) is None
    second = db.claim_next(run, "seller", lease_seconds=2.0, now=104.0)
    assert second["message_id"] == "q-1"
    assert second["attempt"] == 2
    assert second["fence"] != first["fence"]
    with pytest.raises(StaleFence):
        db.ack(run, "seller", "q-1", first["fence"], "processed", {}, now=104.5)
    kinds = [e["kind"] for e in db.events(run)]
    assert "claim_expired" in kinds
    assert "stale_fence_rejected" in kinds


def test_lease_expiry_inside_ack_is_stale(db, run):
    accept(db, run)
    first = db.claim_next(run, "seller", lease_seconds=2.0, now=101.0)
    with pytest.raises(StaleFence):
        db.ack(run, "seller", "q-1", first["fence"], "processed", {}, now=110.0)
    again = db.claim_next(run, "seller", lease_seconds=2.0, now=111.0)
    assert again["attempt"] == 2


def test_ack_completes_message(db, run):
    accept(db, run)
    claim = db.claim_next(run, "seller", lease_seconds=5.0, now=101.0)
    db.ack(run, "seller", "q-1", claim["fence"], "processed",
           {"applied": True}, now=102.0)
    assert db.claim_next(run, "seller", lease_seconds=5.0, now=103.0) is None
    events = db.events(run)
    ack_events = [e for e in events if e["kind"] == "ack_recorded"]
    assert len(ack_events) == 1
    assert ack_events[0]["observer"] == "seller"
    assert ack_events[0]["detail"]["note"] == {"applied": True}


def test_retryable_ack_returns_work_to_inbox(db, run):
    accept(db, run)
    claim = db.claim_next(run, "seller", lease_seconds=5.0, now=101.0)
    db.ack(run, "seller", "q-1", claim["fence"], "retryable", {}, now=102.0)
    again = db.claim_next(run, "seller", lease_seconds=5.0, now=103.0)
    assert again["attempt"] == 2


def test_sessions_and_directory(db, run):
    session = db.authenticate(run, "seller", "tok-s")
    assert db.session_owner(run, session) == "seller"
    assert db.session_owner(run, "bogus") is None
    assert db.authenticate(run, "seller", "wrong") is None
    directory = db.directory(run)
    assert {d["name"] for d in directory} == {"buyer", "seller"}
    seller = next(d for d in directory if d["name"] == "seller")
    assert seller["capabilities"] == ["quote.read"]


def test_events_and_intents_are_ordered(db, run):
    db.record_event(run, observer="town", kind="run_created", subject=run, at=1.0)
    db.record_event(run, observer="town", kind="participant_joined",
                    subject="buyer", at=2.0)
    db.record_intent(run, actor="buyer", action="send",
                     payload={"message_id": "q-1"}, at=2.5)
    events = db.events(run)
    assert [e["kind"] for e in events] == ["run_created", "participant_joined"]
    assert events[0]["event_id"] == "ev-1"
    intents = db.intents(run)
    assert intents[0]["action"] == "send"
    assert intents[0]["intent_id"] == "in-1"
