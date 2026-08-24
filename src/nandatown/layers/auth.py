"""Auth layer: message and card signing plus verification."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from . import register
from ..records import canonical_json


@register("auth", "hmac.v1")
class HmacAuth:
    """Signs payloads with the sender's identity key; forged senders fail."""

    def __init__(self, engine):
        self.engine = engine

    def _identity(self):
        return self.engine.layers["identity"]

    def sign_as(self, name: str, payload: Any) -> str:
        key = self._identity().key(name)
        if key is None:
            raise KeyError(f"no identity for {name}")
        return hmac.new(key.encode(), canonical_json(payload).encode(),
                        hashlib.sha256).hexdigest()

    def verify(self, claimed_name: str, payload: Any, signature: str,
               subject: str = "") -> bool:
        key = self._identity().key(claimed_name)
        ok = key is not None and hmac.compare_digest(
            hmac.new(key.encode(), canonical_json(payload).encode(),
                     hashlib.sha256).hexdigest(),
            signature,
        )
        if not ok:
            self.engine.emit("town", "signature_invalid",
                             subject or claimed_name,
                             {"claimed": claimed_name})
        return ok
