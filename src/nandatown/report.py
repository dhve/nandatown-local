"""The System Fitness Report: a readable view generated from the bundle.

The report is not a record. It restates the evidence in plain language,
stage by stage, and never claims more than the bundle holds.
"""

from __future__ import annotations

import time
from typing import Any

STATUS_LABEL = {
    "passed": "Passed",
    "failed": "Failed",
    "not_enough_evidence": "Not enough evidence",
    "not_tested": "Not tested",
}

STAGE_MEANING = {
    "accepted": "the town committed the request before reporting success",
    "claimed": "a seller claimed the work under a lease",
    "received": "the seller acknowledged receipt through a valid fence",
    "processed": "the seller applied the task exactly once",
    "response": "the response was accepted and reached the buyer",
    "correct": "the buyer checked the total itself",
    "recovered_after_restart": "accepted work survived the crash and was"
                               " redelivered",
    "stale_fence_rejected": "the old attempt could not act after its lease",
    "duplicate_recognized": "the participant recognized work it already"
                            " handled",
    "wakeup_loss_tolerated": "a lost wake-up hint did not lose inbox work",
    "ack_retry_survived": "a lost acknowledgement was retried and recorded",
    "portable_identity": "portable identity is a later experiment",
}

SCOPE_SENTENCE = ("This result applies only to the named agents, releases,"
                  " scenario, failure, evaluator, and time window.")


def render_report(bundle: dict[str, Any]) -> str:
    profile = bundle["profile"]
    run = bundle["run"]
    result = bundle["result"]
    task = profile.task

    lines: list[str] = []
    add = lines.append
    add("NANDA Town System Fitness Report")
    add("=" * 40)
    add(f"Run:       {run.run_id}")
    add(f"Profile:   {profile.name} (fault: {profile.fault})")
    add(f"Task:      quote {task.quantity} x {task.sku} at"
        f" {task.unit_price_cents} cents, expecting"
        f" {task.expected_total_cents} cents")
    add(f"Releases:  " + ", ".join(f"{k} {v}"
                                   for k, v in sorted(run.releases.items())))
    created = time.strftime("%Y-%m-%d %H:%M:%S UTC",
                            time.gmtime(run.created_at))
    add(f"Started:   {created}")
    add(f"Verdict:   {result.verdict.upper()}")
    add("")
    add("The journey: bring, connect, attempt, disrupt, inspect, improve.")
    add("")
    add("Stages (each one a separate claim with its own failure boundary):")
    name_width = max(len(s.name) for s in result.stages)
    for s in result.stages:
        label = STATUS_LABEL[s.status]
        meaning = STAGE_MEANING.get(s.name, "")
        evidence = f" [{', '.join(s.evidence)}]" if s.evidence else ""
        add(f"  {s.name.ljust(name_width)}  {label:<20} {meaning}{evidence}")
        if s.note:
            add(f"  {' ' * name_width}  note: {s.note}")
    add("")
    add(f"Events recorded: {len(bundle['events'])}."
        f" Intents recorded: {len(bundle['intents'])}.")
    add(SCOPE_SENTENCE)
    add("One run is one scoped observation, not a certificate.")
    add("Improve: fix what failed and rerun the same profile.")
    return "\n".join(lines) + "\n"
