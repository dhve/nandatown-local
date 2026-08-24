"""Identity layer: agent identities, secret keys, agent cards."""

from __future__ import annotations

from typing import Any

from . import register


@register("identity", "keys.v1")
class KeyIdentity:
    """Per-agent secret keys and agent cards, seeded and deterministic."""

    def __init__(self, engine):
        self.engine = engine
        self.identities: dict[str, dict[str, Any]] = {}
        self._seq = 0

    def create(self, name: str) -> dict[str, Any]:
        if name in self.identities:
            return self.identities[name]
        self._seq += 1
        key = "".join(self.engine.rng.choices("0123456789abcdef", k=32))
        ident = {"name": name, "agent_id": f"aid-{self._seq}", "key": key}
        self.identities[name] = ident
        self.engine.emit("town", "identity_created", name,
                         {"agent_id": ident["agent_id"]})
        return ident

    def key(self, name: str) -> str | None:
        ident = self.identities.get(name)
        return ident["key"] if ident else None

    def card(self, name: str, capabilities: list[str],
             facts: dict[str, Any]) -> dict[str, Any]:
        ident = self.create(name)
        return {
            "name": name,
            "agent_id": ident["agent_id"],
            "capabilities": capabilities,
            "facts": facts,
        }
