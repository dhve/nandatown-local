"""Participant-side town client.

Wraps the coordinator HTTP contract. Retries one 503 on send and ack,
because a lost acknowledgement is an expected failure mode, and safe:
send is idempotent by message identity and ack is fenced.
"""

from __future__ import annotations

import time
from typing import Any

import httpx


class StaleFenceError(Exception):
    pass


class TownClient:
    def __init__(self, base_url: str, run_id: str,
                 http: httpx.Client | None = None):
        self.run_id = run_id
        self.http = http or httpx.Client(base_url=base_url, timeout=35.0)
        self.session: str | None = None
        self.name: str | None = None
        self.run_context: dict[str, Any] = {}

    def _headers(self) -> dict[str, str]:
        return {"X-Town-Session": self.session or ""}

    def _post_with_retry(self, path: str, json: dict) -> httpx.Response:
        r = self.http.post(path, json=json, headers=self._headers())
        if r.status_code == 503:
            time.sleep(0.2)
            r = self.http.post(path, json=json, headers=self._headers())
        return r

    def join(self, name: str, token: str) -> dict[str, Any]:
        r = self.http.post(f"/runs/{self.run_id}/join",
                           json={"name": name, "token": token})
        r.raise_for_status()
        data = r.json()
        self.session = data["session"]
        self.name = name
        self.run_context = data["run"]
        return data

    def participants(self) -> list[dict[str, Any]]:
        r = self.http.get(f"/runs/{self.run_id}/participants",
                          headers=self._headers())
        r.raise_for_status()
        return r.json()

    def send(self, message_id: str, to: str, kind: str,
             body: dict[str, Any]) -> dict[str, Any]:
        r = self._post_with_retry(
            f"/runs/{self.run_id}/messages",
            {"message_id": message_id, "to": to, "kind": kind, "body": body},
        )
        r.raise_for_status()
        return r.json()

    def notify(self, wait: float = 0.5) -> bool:
        r = self.http.get(f"/runs/{self.run_id}/inbox/notify",
                          params={"wait": wait}, headers=self._headers())
        r.raise_for_status()
        return r.json()["hint"]

    def claim(self) -> dict[str, Any] | None:
        r = self.http.post(f"/runs/{self.run_id}/inbox/claim",
                           headers=self._headers())
        if r.status_code == 204:
            return None
        r.raise_for_status()
        return r.json()

    def ack(self, message_id: str, fence: str, status: str,
            note: dict[str, Any] | None = None) -> dict[str, Any]:
        r = self._post_with_retry(
            f"/runs/{self.run_id}/inbox/ack",
            {"message_id": message_id, "fence": fence, "status": status,
             "note": note or {}},
        )
        if r.status_code == 409 and r.json().get("detail", {}).get("error") \
                == "stale_fence":
            raise StaleFenceError(fence)
        r.raise_for_status()
        return r.json()
