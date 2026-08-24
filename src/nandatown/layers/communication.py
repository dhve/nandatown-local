"""Communication layer: envelopes, conversation ids, correlation."""

from __future__ import annotations

from typing import Any

from . import register


@register("communication", "envelope.v1")
class EnvelopeComms:
    """Wraps every message in a correlated envelope with stable ids."""

    def __init__(self, engine):
        self.engine = engine
        self._message_seq = 0
        self._conversation_seq = 0

    def new_conversation(self) -> str:
        self._conversation_seq += 1
        return f"c-{self._conversation_seq}"

    def envelope(self, sender: str, to: str, kind: str, body: dict[str, Any],
                 conversation: str | None = None) -> dict[str, Any]:
        self._message_seq += 1
        return {
            "message_id": f"m-{self._message_seq}",
            "conversation": conversation or self.new_conversation(),
            "sender": sender,
            "to": to,
            "kind": kind,
            "body": body,
        }

    def reply(self, original: dict[str, Any], sender: str, kind: str,
              body: dict[str, Any]) -> dict[str, Any]:
        return self.envelope(sender, original["sender"], kind, body,
                             conversation=original["conversation"])
