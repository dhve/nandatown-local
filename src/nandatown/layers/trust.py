"""Trust layer: a simple default reputation score with a public formula.

The formula: the sum of receipt outcomes, +1 for good and -1 for bad,
each backed by an attributed data-facts receipt. Deliberately simple and
reproducible from the event log.
"""

from __future__ import annotations

from . import register


@register("trust", "reputation.v1")
class ReceiptReputation:
    """Receipt-driven reputation: sum of good minus bad outcomes."""

    def __init__(self, engine):
        self.engine = engine
        self.scores: dict[str, int] = {}

    def score(self, name: str) -> int:
        return self.scores.get(name, 0)

    def update(self, observer: str, subject: str, outcome: str,
               receipt_id: str) -> int:
        delta = 1 if outcome == "good" else -1
        self.scores[subject] = self.score(subject) + delta
        self.engine.emit(observer, "reputation_updated", subject,
                         {"outcome": outcome, "delta": delta,
                          "score": self.scores[subject],
                          "receipt": receipt_id})
        return self.scores[subject]
