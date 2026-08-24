"""Privacy layer: redaction of declared fields from exported records.

The run still uses real values in memory; what leaves the run (the
bundle's profile and events) has the declared fields replaced. Public
reports exclude secrets by construction, not by promise.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from . import register

REDACTED = "[redacted]"


@register("privacy", "redact.v1")
class FieldRedaction:
    """Replaces declared field names with a marker in any nested record."""

    def __init__(self, engine):
        self.engine = engine
        self.fields: set[str] = set()

    def configure(self, fields: list[str]) -> None:
        self.fields = set(fields)

    def _scrub(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: (REDACTED if k in self.fields else self._scrub(v))
                    for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._scrub(v) for v in obj]
        return obj

    def redact(self, record: Any) -> Any:
        if not self.fields:
            return record
        return self._scrub(deepcopy(record))
