"""The town coordinator: run lifecycle, directory, mailbox API, faults.

The coordinator owns coordination facts and records them as events. It
never holds participant runtime credentials. The participant tool
surface is deliberately small: join, find participants, wait for a
wake-up hint, claim work, send work, acknowledge work, inspect the run.
Run creation, fault plans, and event export are admin-only.

An HTTP success response is a coordination fact (the town accepted or
recorded something). It is never proof that an agent understood or
completed a task; that separation belongs to the evaluator.
"""

from __future__ import annotations

import asyncio
import os
import secrets
import time
import uuid
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from .db import IdentityReuse, StaleFence, TownDB
from .records import TestProfile, fingerprint

ACK_STATUSES = {"received", "processed", "rejected", "retryable", "failed"}
FAULT_TARGET_KIND = "quote_request"


class CreateRun(BaseModel):
    profile: TestProfile


class JoinBody(BaseModel):
    name: str
    token: str


class SendBody(BaseModel):
    message_id: str
    to: str
    kind: str
    body: dict[str, Any]


class AckBody(BaseModel):
    message_id: str
    fence: str
    status: str
    note: dict[str, Any] = {}


class EventBody(BaseModel):
    observer: str
    kind: str
    subject: str
    detail: dict[str, Any] = {}


def build_app(db_path: str, admin_token: str) -> FastAPI:
    app = FastAPI(title="nandatown coordinator", version="0.2.0")
    db = TownDB(db_path)
    # Fault bookkeeping per run: each fault fires at most once.
    faults: dict[str, dict[str, Any]] = {}

    def fault_state(run_id: str) -> dict[str, Any]:
        if run_id not in faults:
            profile = db.run_profile(run_id) or {}
            faults[run_id] = {"fault": profile.get("fault", "none"),
                              "fired": False,
                              "lease": profile.get("lease_seconds", 5.0)}
        return faults[run_id]

    def require_admin(x_town_admin: str = Header(default="")):
        if x_town_admin != admin_token:
            raise HTTPException(status_code=401, detail="admin token required")

    def participant(run_id: str, x_town_session: str = Header(default="")):
        name = db.session_owner(run_id, x_town_session)
        if name is None:
            raise HTTPException(status_code=401, detail="valid session required")
        return name

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.post("/runs", dependencies=[Depends(require_admin)])
    def create_run(body: CreateRun):
        now = time.time()
        profile = body.profile
        run_id = db.create_run(profile.model_dump_json(), now=now)
        join_tokens = {}
        for name, role in profile.roles.items():
            token = secrets.token_hex(16)
            db.add_participant(run_id, name, role,
                               profile.capabilities.get(name, []), token)
            join_tokens[name] = token
        db.record_event(run_id, observer="town", kind="run_created",
                        subject=run_id, at=now,
                        detail={"profile": profile.name,
                                "profile_fingerprint":
                                    fingerprint(profile.model_dump()),
                                "fault": profile.fault})
        return {"run_id": run_id, "join_tokens": join_tokens}

    @app.post("/runs/{run_id}/join")
    def join(run_id: str, body: JoinBody):
        now = time.time()
        profile = db.run_profile(run_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="unknown run")
        session = db.authenticate(run_id, body.name, body.token, now=now)
        if session is None:
            raise HTTPException(status_code=403, detail="join rejected")
        db.record_event(run_id, observer="town", kind="participant_joined",
                        subject=body.name, at=now)
        return {
            "session": session,
            "participant_id": body.name,
            "run": {"run_id": run_id, "task": profile["task"],
                    "roles": profile["roles"],
                    "lease_seconds": profile["lease_seconds"]},
        }

    @app.get("/runs/{run_id}/participants")
    def directory(run_id: str, name: str = Depends(participant)):
        return db.directory(run_id)

    @app.post("/runs/{run_id}/messages", status_code=202)
    def send(run_id: str, body: SendBody, name: str = Depends(participant)):
        now = time.time()
        db.record_intent(run_id, actor=name, action="send",
                         payload=body.model_dump(), at=now)
        state = fault_state(run_id)
        suppress = False
        if (state["fault"] == "drop_wakeup" and not state["fired"]
                and body.kind == FAULT_TARGET_KIND):
            suppress = True
            state["fired"] = True
        try:
            accepted_at, replay = db.accept_message(
                run_id, sender=name, message_id=body.message_id, to=body.to,
                kind=body.kind, body=body.body,
                content_fingerprint=fingerprint(body.body), now=now,
                suppress_notify=suppress,
            )
        except IdentityReuse:
            raise HTTPException(
                status_code=409,
                detail={"error": "identity_reuse", "message_id": body.message_id},
            )
        if suppress and not replay:
            db.record_event(run_id, observer="town", kind="notify_suppressed",
                            subject=body.message_id, at=now,
                            detail={"fault": "drop_wakeup"})
        return {"message_id": body.message_id, "accepted_at": accepted_at,
                "replay": replay}

    @app.get("/runs/{run_id}/inbox/notify")
    async def notify(run_id: str, wait: float = 0.0,
                     name: str = Depends(participant)):
        deadline = time.time() + max(0.0, min(wait, 30.0))
        while True:
            if db.pop_notify(run_id, name):
                return {"hint": True}
            if time.time() >= deadline:
                return {"hint": False}
            await asyncio.sleep(0.05)

    @app.post("/runs/{run_id}/inbox/claim")
    def claim(run_id: str, name: str = Depends(participant)):
        now = time.time()
        db.record_intent(run_id, actor=name, action="claim", payload={}, at=now)
        state = fault_state(run_id)
        result = db.claim_next(run_id, name, lease_seconds=state["lease"],
                               now=now)
        if result is None and state["fault"] == "duplicate_delivery" \
                and not state["fired"]:
            done = state.get("done_target")
            if done:
                result = db.reoffer(run_id, done, name,
                                    lease_seconds=state["lease"], now=now)
                if result is not None:
                    state["fired"] = True
                    db.record_event(run_id, observer="town",
                                    kind="duplicate_offered", subject=done,
                                    at=now, detail={"fault":
                                                    "duplicate_delivery"})
        if result is None:
            from fastapi import Response
            return Response(status_code=204)
        return result

    @app.post("/runs/{run_id}/inbox/ack")
    def ack(run_id: str, body: AckBody, name: str = Depends(participant)):
        now = time.time()
        db.record_intent(run_id, actor=name, action="ack",
                         payload=body.model_dump(), at=now)
        if body.status not in ACK_STATUSES:
            raise HTTPException(status_code=422, detail="unknown ack status")
        state = fault_state(run_id)
        if (state["fault"] == "lost_ack" and not state["fired"]
                and body.status == "processed"):
            state["fired"] = True
            db.record_event(run_id, observer="town", kind="ack_dropped",
                            subject=body.message_id, at=now,
                            detail={"fault": "lost_ack",
                                    "participant": name})
            raise HTTPException(status_code=503,
                                detail={"error": "ack_lost"})
        try:
            db.ack(run_id, name, body.message_id, body.fence, body.status,
                   body.note, now=now)
        except StaleFence:
            raise HTTPException(
                status_code=409,
                detail={"error": "stale_fence", "message_id": body.message_id},
            )
        if (body.status == "processed"
                and state["fault"] == "duplicate_delivery"
                and db.message_kind(run_id, body.message_id)
                == FAULT_TARGET_KIND):
            state.setdefault("done_target", body.message_id)
        return {"recorded": True}

    @app.get("/runs/{run_id}/events", dependencies=[Depends(require_admin)])
    def events(run_id: str):
        return {"events": db.events(run_id)}

    @app.get("/runs/{run_id}/intents", dependencies=[Depends(require_admin)])
    def intents(run_id: str):
        return {"intents": db.intents(run_id)}

    @app.post("/runs/{run_id}/events", dependencies=[Depends(require_admin)])
    def post_event(run_id: str, body: EventBody):
        event_id = db.record_event(run_id, observer=body.observer,
                                   kind=body.kind, subject=body.subject,
                                   at=time.time(), detail=body.detail)
        return {"event_id": event_id}

    @app.post("/runs/{run_id}/finish", dependencies=[Depends(require_admin)])
    def finish(run_id: str):
        db.set_run_status(run_id, "finished")
        db.record_event(run_id, observer="town", kind="run_finished",
                        subject=run_id, at=time.time())
        return {"finished": True}

    return app


def main() -> None:
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(prog="nandatown-coordinator")
    parser.add_argument("--db", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8477)
    args = parser.parse_args()
    admin_token = os.environ.get("TOWN_ADMIN_TOKEN") or secrets.token_hex(16)
    if "TOWN_ADMIN_TOKEN" not in os.environ:
        print(f"admin token: {admin_token}")
    app = build_app(args.db, admin_token=admin_token)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
