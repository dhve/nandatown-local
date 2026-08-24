"""Built-in test profiles: the boring quote task under five conditions.

The task is not the demo. Custody, recovery, stale-attempt rejection,
correlation, and correctness are the demo.
"""

from __future__ import annotations

from .records import TestProfile

_TASK = {
    "kind": "quote",
    "sku": "widget",
    "quantity": 2,
    "unit_price_cents": 1995,
    "expected_total_cents": 3990,
}

_ROLES = {"buyer": "buyer", "seller": "seller"}
_CAPABILITIES = {"buyer": [], "seller": ["quote.read"]}


def _profile(name: str, fault: str, lease_seconds: float) -> TestProfile:
    return TestProfile(name=name, task=_TASK, roles=_ROLES,
                       capabilities=_CAPABILITIES, fault=fault,
                       lease_seconds=lease_seconds,
                       evaluator="stage-evaluator")


PROFILES: dict[str, TestProfile] = {
    "quote-clean": _profile("quote-clean", "none", 5.0),
    "quote-crash-restart": _profile("quote-crash-restart",
                                    "crash_after_claim", 1.5),
    "quote-drop-wakeup": _profile("quote-drop-wakeup", "drop_wakeup", 5.0),
    "quote-duplicate-delivery": _profile("quote-duplicate-delivery",
                                         "duplicate_delivery", 5.0),
    "quote-lost-ack": _profile("quote-lost-ack", "lost_ack", 5.0),
}

DEFAULT_PROFILE = "quote-crash-restart"

FAULT_DESCRIPTIONS = {
    "quote-clean": "no fault; the calibration baseline",
    "quote-crash-restart": "the seller stops after claiming the work, the"
                           " stale attempt is fenced, the town redelivers",
    "quote-drop-wakeup": "the wake-up hint is lost; the durable inbox must"
                         " still deliver",
    "quote-duplicate-delivery": "the same work is offered twice; the seller"
                                " must apply it once",
    "quote-lost-ack": "the first acknowledgement is lost; the retry must be"
                      " safe",
}
