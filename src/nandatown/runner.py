"""Full-run orchestration: one command, one run, one evidence bundle.

The runner starts a coordinator subprocess, spawns the buyer and seller
as isolated subprocesses with their own state directories, restarts the
seller once if it crashes, finishes the run, evaluates the event log,
and writes the portable bundle. Runner observations (crash, restart,
exit) are posted as attributed events; the runner never synthesizes
participant assertions.
"""

from __future__ import annotations

import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
from typing import Any

import httpx

from . import __version__
from .bundle import write_bundle
from .evaluator import EVALUATOR_VERSION, evaluate
from .records import RunRecord, TestProfile, TownEvent, fingerprint
from .profiles import PROFILES

SELLER_CRASH_EXIT = 3


class RunnerError(Exception):
    pass


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_health(http: httpx.Client, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if http.get("/health").status_code == 200:
                return
        except httpx.TransportError:
            pass
        time.sleep(0.1)
    raise RunnerError("coordinator did not become healthy")


def _spawn_participant(module: str, url: str, run_id: str, name: str,
                       token: str, state_dir: str, fault: str,
                       deadline: str) -> subprocess.Popen:
    os.makedirs(state_dir, exist_ok=True)
    env = dict(os.environ)
    env.update({"TOWN_URL": url, "RUN_ID": run_id, "NAME": name,
                "TOKEN": token, "STATE_DIR": state_dir, "FAULT": fault,
                "DEADLINE": deadline})
    return subprocess.Popen([sys.executable, "-m", module], env=env,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)


def _quiescent(profile: TestProfile, events: list[dict[str, Any]]) -> bool:
    """Has the seller side finished everything this profile expects?"""
    seller_acks = [e for e in events
                   if e["kind"] == "ack_recorded"
                   and e["observer"] == "seller"
                   and e["detail"].get("status") == "processed"]
    applied = [e for e in seller_acks if e["detail"]["note"].get("applied")]
    if profile.fault == "duplicate_delivery":
        duplicates = [e for e in seller_acks
                      if e["detail"]["note"].get("duplicate")]
        return bool(applied) and bool(duplicates)
    return bool(applied)


def run_town(profile_name: str, out_dir: str,
             port: int = 0) -> tuple[str, Any]:
    if profile_name not in PROFILES:
        raise RunnerError(f"unknown profile {profile_name!r};"
                          f" choose from {sorted(PROFILES)}")
    profile = PROFILES[profile_name]
    admin_token = secrets.token_hex(16)
    port = port or _free_port()
    url = f"http://127.0.0.1:{port}"

    os.makedirs(out_dir, exist_ok=True)
    scratch = os.path.join(out_dir, f".scratch-{secrets.token_hex(4)}")
    os.makedirs(scratch, exist_ok=True)
    db_path = os.path.join(scratch, "town.db")

    env = dict(os.environ)
    env["TOWN_ADMIN_TOKEN"] = admin_token
    coordinator = subprocess.Popen(
        [sys.executable, "-m", "nandatown.coordinator", "--db", db_path,
         "--port", str(port)],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    procs: list[subprocess.Popen] = [coordinator]
    admin = httpx.Client(base_url=url, timeout=10.0,
                         headers={"X-Town-Admin": admin_token})
    bundle_dir: str | None = None
    try:
        _wait_health(admin)
        created = admin.post("/runs",
                             json={"profile": profile.model_dump()})
        created.raise_for_status()
        run_id = created.json()["run_id"]
        tokens = created.json()["join_tokens"]

        def post_event(observer: str, kind: str, subject: str,
                       detail: dict | None = None) -> None:
            admin.post(f"/runs/{run_id}/events",
                       json={"observer": observer, "kind": kind,
                             "subject": subject, "detail": detail or {}})

        def get_events() -> list[dict[str, Any]]:
            return admin.get(f"/runs/{run_id}/events").json()["events"]

        seller_fault = ("crash_after_claim"
                        if profile.fault == "crash_after_claim" else "none")
        seller_state = os.path.join(scratch, "seller")
        buyer_state = os.path.join(scratch, "buyer")

        def spawn_seller() -> subprocess.Popen:
            p = _spawn_participant("nandatown.participants.seller", url,
                                   run_id, "seller", tokens["seller"],
                                   seller_state, seller_fault, "40")
            procs.append(p)
            return p

        seller = spawn_seller()
        buyer = _spawn_participant("nandatown.participants.buyer", url,
                                   run_id, "buyer", tokens["buyer"],
                                   buyer_state, "none", "30")
        procs.append(buyer)

        restarted = False
        deadline = time.time() + 45.0
        while time.time() < deadline:
            if buyer.poll() is not None:
                break
            rc = seller.poll()
            if rc is not None:
                if rc == SELLER_CRASH_EXIT and not restarted:
                    post_event("runner", "participant_crashed", "seller",
                               {"exit_code": rc})
                    seller = spawn_seller()
                    post_event("runner", "participant_restarted", "seller")
                    restarted = True
                else:
                    post_event("runner", "participant_exited", "seller",
                               {"exit_code": rc})
                    break
            time.sleep(0.1)
        if buyer.poll() is None:
            buyer.terminate()
        post_event("runner", "participant_exited", "buyer",
                   {"exit_code": buyer.poll()})

        quiet_deadline = time.time() + 8.0
        while time.time() < quiet_deadline:
            if _quiescent(profile, get_events()):
                break
            time.sleep(0.2)

        if seller.poll() is None:
            seller.terminate()
        admin.post(f"/runs/{run_id}/finish")

        raw_events = get_events()
        events = [TownEvent.model_validate(e) for e in raw_events]
        intents = admin.get(f"/runs/{run_id}/intents").json()["intents"]
        directory = [
            {"name": p["name"], "role": p["role"],
             "capabilities": p["capabilities"],
             "release": f"nandatown.participants.{p['role']} {__version__}"}
            for p in [
                {"name": "buyer", "role": "buyer", "capabilities": []},
                {"name": "seller", "role": "seller",
                 "capabilities": ["quote.read"]},
            ]
        ]
        created_at = next((e.at for e in events if e.kind == "run_created"),
                          time.time())
        run_record = RunRecord(
            run_id=run_id,
            profile_name=profile.name,
            profile_fingerprint=fingerprint(profile.model_dump()),
            created_at=created_at,
            participants=directory,
            releases={
                "nandatown": __version__,
                "evaluator": EVALUATOR_VERSION,
                "python": sys.version.split()[0],
            },
            config={"port": port, "restarted_seller": restarted},
        )
        result = evaluate(profile, run_id, events)
        bundle_dir = os.path.join(out_dir, run_id)
        write_bundle(bundle_dir, profile, run_record, intents, events, result)
        return bundle_dir, result
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        admin.close()
        # Keep the operational state (town.db, journals) inspectable
        # inside the bundle once the processes that owned it are gone.
        if bundle_dir and os.path.isdir(bundle_dir):
            shutil.move(scratch, os.path.join(bundle_dir, "state"))
