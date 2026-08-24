"""The A2A bridge: an external Agent2Agent agent as a town participant.

The bridge owns the town side (join, claim under a lease, journal,
acknowledge); the external A2A agent owns the thinking. Each claimed
quote request becomes one message/send; the returned task's artifact
becomes the quote response. Town mailbox semantics stay canonical.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

from ..a2a_adapter import artifact_text, send_message
from ..client import TownClient
from .base import Journal, run_loop


def build_handler(a2a_url: str, journal: Journal):
    def handler(claim: dict[str, Any]):
        if claim["kind"] != "quote_request":
            return "rejected", {"reason": "unknown kind"}, []
        message_id = claim["message_id"]
        if journal.seen(message_id):
            reply = journal.get(message_id)["reply"]
            return "processed", {"duplicate": True}, [reply]
        body = dict(claim["body"], request_id=message_id)
        task = send_message(a2a_url, json.dumps(body))
        state = task.get("status", {}).get("state")
        if state != "completed":
            return "retryable", {"a2a_state": state}, []
        quote = json.loads(artifact_text(task))
        reply = {
            "message_id": "r-" + message_id.removeprefix("q-"),
            "to": claim["from"],
            "kind": "quote_response",
            "body": {"request_id": message_id,
                     "total_cents": quote["total_cents"]},
        }
        journal.record(message_id, {"reply": reply,
                                    "a2a_task": task["id"]})
        return "processed", {"applied": True,
                             "total_cents": quote["total_cents"],
                             "runtime": "a2a-bridge",
                             "a2a_task": task["id"]}, [reply]

    return handler


def run(client: TownClient, name: str, token: str, state_dir: str,
        a2a_url: str, deadline_seconds: float = 60.0,
        grant_json: str | None = None) -> int:
    client.join_auto(name, token, grant_json)
    journal = Journal(os.path.join(state_dir, "journal.db"))
    handler = build_handler(a2a_url, journal)
    deadline = time.time() + deadline_seconds
    run_loop(client, handler, until=lambda: time.time() > deadline)
    return 0


def main() -> None:
    env = os.environ
    client = TownClient(env["TOWN_URL"], env["RUN_ID"])
    code = run(client, env["NAME"], env["TOKEN"], env["STATE_DIR"],
               env["A2A_URL"],
               deadline_seconds=float(env.get("DEADLINE", "60")),
               grant_json=env.get("TOWN_GRANT"))
    sys.exit(code)


if __name__ == "__main__":
    main()
