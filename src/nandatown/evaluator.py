"""The pinned stage evaluator.

Each stage is a separate claim with a separate failure boundary.
Acceptance, claiming, receipt, processing, response, and semantic
correctness are always judged separately; an HTTP success response never
becomes proof that the agent understood or completed the task. Missing
evidence stays missing: it is reported as Not enough evidence, never
inferred.
"""

from __future__ import annotations

import time

from .records import EvidenceResult, StageResult, TestProfile, TownEvent

EVALUATOR_VERSION = "0.2.0"

REQUEST_KIND = "quote_request"
RESPONSE_KIND = "quote_response"


def _passed(name: str, evidence: list[str], note: str = "") -> StageResult:
    return StageResult(name=name, status="passed", evidence=evidence, note=note)


def _failed(name: str, evidence: list[str], note: str) -> StageResult:
    return StageResult(name=name, status="failed", evidence=evidence, note=note)


def _missing(name: str, note: str) -> StageResult:
    return StageResult(name=name, status="not_enough_evidence", evidence=[],
                       note=note)


def evaluate(profile: TestProfile, run_id: str,
             events: list[TownEvent]) -> EvidenceResult:
    seller = next((n for n, r in profile.roles.items() if r == "seller"), "seller")
    buyer = next((n for n, r in profile.roles.items() if r == "buyer"), "buyer")

    def find(ekind: str, **conds) -> list[TownEvent]:
        out = []
        for e in events:
            if e.kind != ekind:
                continue
            if "observer" in conds and e.observer != conds["observer"]:
                continue
            if "subject" in conds and e.subject != conds["subject"]:
                continue
            ok = True
            for key, val in conds.items():
                if key in ("observer", "subject"):
                    continue
                if e.detail.get(key) != val:
                    ok = False
                    break
            if ok:
                out.append(e)
        return out

    accepted_req = find("message_accepted", kind=REQUEST_KIND)
    request_id = accepted_req[0].subject if accepted_req else None

    stages: list[StageResult] = []

    # accepted: the town committed the request before reporting success.
    if accepted_req:
        stages.append(_passed("accepted", [accepted_req[0].event_id]))
    else:
        stages.append(_missing("accepted", "no accepted quote request"))

    # claimed: a seller claimed the request under a lease.
    claims = find("message_claimed", subject=request_id) if request_id else []
    if claims:
        stages.append(_passed("claimed", [c.event_id for c in claims]))
    else:
        stages.append(_missing("claimed", "the request was never claimed"))

    # received: the seller acknowledged the request through a valid fence.
    seller_acks = (find("ack_recorded", observer=seller, subject=request_id)
                   if request_id else [])
    received = [a for a in seller_acks
                if a.detail.get("status") in ("received", "processed")]
    if received:
        stages.append(_passed("received", [received[0].event_id]))
    else:
        stages.append(_missing("received",
                               "no acknowledged receipt by the seller"))

    # processed: the seller applied the task exactly once on its own side.
    processed = [a for a in seller_acks if a.detail.get("status") == "processed"]
    applied = [a for a in processed if a.detail.get("note", {}).get("applied")]
    if not processed:
        stages.append(_missing("processed", "no processed acknowledgement"))
    elif len(applied) == 1:
        stages.append(_passed("processed", [applied[0].event_id]))
    elif len(applied) == 0:
        stages.append(_missing("processed",
                               "processed acknowledgements carry no"
                               " application record"))
    else:
        stages.append(_failed("processed", [a.event_id for a in applied],
                              f"applied {len(applied)} times, expected once"))

    # response: the quote response was accepted and reached the buyer.
    accepted_resp = find("message_accepted", kind=RESPONSE_KIND)
    response_id = accepted_resp[0].subject if accepted_resp else None
    buyer_claims = (find("message_claimed", subject=response_id,
                         claimant=buyer) if response_id else [])
    if accepted_resp and buyer_claims:
        stages.append(_passed("response", [accepted_resp[0].event_id,
                                           buyer_claims[0].event_id]))
    else:
        stages.append(_missing("response",
                               "no quote response accepted and claimed by"
                               " the buyer"))

    # correct: the buyer's own assertion about the total.
    buyer_acks = (find("ack_recorded", observer=buyer, subject=response_id)
                  if response_id else [])
    verdict_acks = [a for a in buyer_acks
                    if "correct" in a.detail.get("note", {})]
    if verdict_acks:
        note = verdict_acks[0].detail["note"]
        if note["correct"]:
            stages.append(_passed("correct", [verdict_acks[0].event_id]))
        else:
            stages.append(_failed(
                "correct", [verdict_acks[0].event_id],
                f"buyer observed total {note.get('total_cents')} against"
                f" expected {profile.task.expected_total_cents}"))
    else:
        stages.append(_missing("correct", "the buyer made no correctness"
                                          " assertion"))

    # Fault checks apply only when the profile names the fault.
    fault = profile.fault
    if fault == "crash_after_claim":
        ended_early = (find("claim_expired", subject=request_id)
                       + find("stale_fence_rejected", subject=request_id)
                       if request_id else [])
        reclaimed = [c for c in claims if c.detail.get("attempt", 1) >= 2]
        restarts = find("participant_restarted")
        if ended_early and reclaimed:
            evidence = ([e.event_id for e in ended_early]
                        + [reclaimed[0].event_id]
                        + [r.event_id for r in restarts])
            stages.append(_passed("recovered_after_restart", evidence))
        else:
            stages.append(_missing("recovered_after_restart",
                                   "no lease end followed by redelivery"))
        fences = (find("stale_fence_rejected", subject=request_id)
                  if request_id else [])
        if fences:
            stages.append(_passed("stale_fence_rejected",
                                  [f.event_id for f in fences]))
        else:
            stages.append(_missing("stale_fence_rejected",
                                   "no stale fence was rejected"))
    elif fault == "duplicate_delivery":
        offered = find("duplicate_offered")
        recognized = [a for a in seller_acks
                      if a.detail.get("note", {}).get("duplicate")]
        if offered and recognized and len(applied) == 1:
            stages.append(_passed("duplicate_recognized",
                                  [offered[0].event_id,
                                   recognized[0].event_id]))
        else:
            stages.append(_missing("duplicate_recognized",
                                   "no duplicate offer recognized exactly"
                                   " once"))
    elif fault == "drop_wakeup":
        suppressed = find("notify_suppressed")
        if suppressed and claims:
            stages.append(_passed("wakeup_loss_tolerated",
                                  [suppressed[0].event_id,
                                   claims[0].event_id]))
        else:
            stages.append(_missing("wakeup_loss_tolerated",
                                   "no suppressed wake-up followed by a"
                                   " claim"))
    elif fault == "lost_ack":
        dropped = find("ack_dropped")
        if dropped and processed:
            stages.append(_passed("ack_retry_survived",
                                  [dropped[0].event_id,
                                   processed[0].event_id]))
        else:
            stages.append(_missing("ack_retry_survived",
                                   "no dropped acknowledgement followed by"
                                   " a recorded retry"))

    stages.append(StageResult(
        name="portable_identity", status="not_tested",
        note="short-lived run sessions; portable identity is a later"
             " experiment"))

    applicable = [s for s in stages if s.status != "not_tested"]
    if any(s.status == "failed" for s in applicable):
        verdict = "failed"
    elif all(s.status == "passed" for s in applicable):
        verdict = "passed"
    else:
        verdict = "incomplete"

    return EvidenceResult(run_id=run_id, evaluator_version=EVALUATOR_VERSION,
                          stages=stages, verdict=verdict,
                          evaluated_at=time.time())
