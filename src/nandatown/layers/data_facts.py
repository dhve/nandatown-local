"""Data facts layer: signed evidence records.

The evidence rule: one record holds one fact, from one observer, about
one subject, at one time. The observer signs the record, and a subject
can never write its own record about itself.
"""

from __future__ import annotations

from typing import Any

from . import register
from ..records import fingerprint


class EvidenceError(Exception):
    pass


@register("data_facts", "evidence.v1")
class EvidenceRecords:
    """Attributed, signed, single-fact receipts."""

    def __init__(self, engine):
        self.engine = engine
        self.records: list[dict[str, Any]] = []
        self._seq = 0

    def attest(self, observer: str, subject: str, claim: str,
               value: Any) -> str:
        if observer == subject:
            raise EvidenceError("a subject cannot write its own record")
        self._seq += 1
        record_id = f"fact-{self._seq}"
        payload = {"record_id": record_id, "observer": observer,
                   "subject": subject, "claim": claim, "value": value,
                   "at": self.engine.now}
        auth = self.engine.layers["auth"]
        signature = auth.sign_as(observer, payload)
        record = dict(payload, signature=signature,
                      content_fingerprint=fingerprint(payload))
        self.records.append(record)
        self.engine.emit(observer, "receipt_attested", subject,
                         {"record_id": record_id, "claim": claim,
                          "value": value})
        return record_id

    def about(self, subject: str) -> list[dict[str, Any]]:
        return [r for r in self.records if r["subject"] == subject]
