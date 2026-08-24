"""Memory layer: a durable per-agent key-value store.

Writes are events (key only, never the value, so exported traces do not
leak private state through the memory layer).
"""

from __future__ import annotations

from typing import Any

from . import register


@register("memory", "kv.v1")
class KeyValueMemory:
    """Per-agent key-value memory with attributed write events."""

    def __init__(self, engine):
        self.engine = engine
        self.stores: dict[str, dict[str, Any]] = {}

    def remember(self, agent: str, key: str, value: Any) -> None:
        self.stores.setdefault(agent, {})[key] = value
        self.engine.emit(agent, "memory_written", agent, {"key": key})

    def recall(self, agent: str, key: str) -> Any:
        return self.stores.get(agent, {}).get(key)
