"""Registry layer: the town's internal index.

Agents inside the sandbox do not belong on the main NANDA Index; the
town keeps its own separate index. Cards are published with a signature,
verification is checked at publish time, and lookups return verified
cards ranked by trust.
"""

from __future__ import annotations

from typing import Any

from . import register


@register("registry", "index.v1")
class TownIndex:
    """Publish signed agent cards, look peers up by capability."""

    def __init__(self, engine):
        self.engine = engine
        self.cards: dict[str, dict[str, Any]] = {}

    def publish(self, publisher: str, card: dict[str, Any],
                signature: str) -> bool:
        auth = self.engine.layers["auth"]
        verified = auth.verify(card["name"], card, signature,
                               subject=card["name"])
        entry = {"card": card, "verified": verified, "publisher": publisher}
        self.cards[card["name"]] = entry
        if verified:
            self.engine.emit("town", "card_registered", card["name"],
                             {"capabilities": card["capabilities"],
                              "verified": True})
        else:
            self.engine.emit("town", "card_unverified", card["name"],
                             {"capabilities": card["capabilities"],
                              "publisher": publisher})
        return verified

    def lookup(self, capability: str,
               include_unverified: bool = False) -> list[dict[str, Any]]:
        trust = self.engine.layers["trust"]
        hits = []
        for entry in self.cards.values():
            if capability not in entry["card"]["capabilities"]:
                continue
            if not entry["verified"] and not include_unverified:
                continue
            hits.append(entry["card"])
        return sorted(hits, key=lambda c: (-trust.score(c["name"]), c["name"]))

    def names_with(self, capability: str) -> list[str]:
        return [c["name"] for c in self.lookup(capability)]
