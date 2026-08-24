"""Tier two: a model-driven participant on the Track.

The split is deliberate. The HARNESS is infrastructure and always
trustworthy: it owns the town client, the durable journal, the current
claim's fence, and the small tool surface. The BRAIN only emits tool
calls: the deterministic MockBrain by default (no inference, CI-safe),
or any OpenAI-compatible endpoint (Ollama included) via TOWN_MODEL.

The first agent-native fault lives here: context_truncation drops the
middle of the conversation past a message budget, exactly the failure a
real agent meets when its context compacts mid-task. The system prompt
survives; everything else must be recoverable through the protocol
(idempotent resend, redeliverable claims, the journal). The agent
reports its truncation count in its ack notes, which makes the fault's
survival an attributed assertion in the evidence.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import Any

import httpx

from ..client import StaleFenceError, TownClient
from ..skills import skill_source
from .base import Journal

MESSAGE_BUDGET = 6
KEEP_TAIL = 4
MAX_TURNS = 80
IDLE_LIMIT = 20

TOOLS = [
    {"type": "function", "function": {
        "name": "list_participants",
        "description": "List run participants with roles and capabilities.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "claim_work",
        "description": "Wait briefly for a hint, then claim one piece of"
                       " inbox work under a lease.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "send_work",
        "description": "Send work to a participant. Idempotent by"
                       " message_id: retrying identical content is safe.",
        "parameters": {"type": "object", "properties": {
            "message_id": {"type": "string"},
            "to": {"type": "string"},
            "kind": {"type": "string"},
            "body": {"type": "object"}},
            "required": ["message_id", "to", "kind", "body"]}}},
    {"type": "function", "function": {
        "name": "ack_work",
        "description": "Acknowledge the currently claimed work.",
        "parameters": {"type": "object", "properties": {
            "status": {"type": "string",
                       "enum": ["received", "processed", "rejected",
                                "retryable", "failed"]},
            "note": {"type": "object"}},
            "required": ["status"]}}},
    {"type": "function", "function": {
        "name": "finish",
        "description": "End this participant's run.",
        "parameters": {"type": "object", "properties": {
            "exit_code": {"type": "integer"},
            "note": {"type": "string"}},
            "required": ["exit_code"]}}},
]


class MockBrain:
    """A deterministic brain that speaks only through tool calls.

    It exists so the tier-two harness (tool loop, journal, fences,
    truncation) is exercised without inference. It rereads whatever
    survives in the conversation, so context truncation forces it to
    rediscover and safely resend, which is the point.
    """

    def __init__(self, role: str):
        self.role = role
        self._call_seq = 0

    def _call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        self._call_seq += 1
        return {"content": None, "tool_calls": [{
            "id": f"call-{self._call_seq}",
            "function": {"name": name, "arguments": json.dumps(args)}}]}

    @staticmethod
    def _history(messages: list[dict[str, Any]]):
        pending = {}
        history = []
        for m in messages:
            if m["role"] == "assistant" and m.get("tool_calls"):
                for tc in m["tool_calls"]:
                    pending[tc["id"]] = (tc["function"]["name"],
                                         tc["function"]["arguments"])
            elif m["role"] == "tool":
                name, args = pending.get(m.get("tool_call_id"),
                                         ("?", "{}"))
                history.append((name, args, m.get("content") or ""))
        return history

    @staticmethod
    def _task(messages: list[dict[str, Any]]) -> dict[str, Any]:
        system = messages[0]["content"]
        match = re.search(r"TASK=(\{.*?\})\n", system, re.S)
        return json.loads(match.group(1)) if match else {}

    def chat(self, messages: list[dict[str, Any]],
             tools: list[dict[str, Any]]) -> dict[str, Any]:
        history = self._history(messages)
        task = self._task(messages)
        idle = sum(1 for name, _, result in history
                   if name == "claim_work" and "no work" in result)
        if self.role == "seller":
            return self._seller(history, idle)
        return self._buyer(history, task, idle)

    def _seller(self, history, idle):
        last_claim = None
        after: list = []
        for name, args, result in history:
            if name == "claim_work" and "no work" not in result:
                last_claim, after = json.loads(result), []
            elif last_claim is not None:
                after.append((name, result))
        if last_claim is not None:
            acked = any(n == "ack_work" and "recorded" in r
                        for n, r in after)
            if not acked:
                if last_claim.get("already_processed"):
                    return self._call("ack_work",
                                      {"status": "processed",
                                       "note": {"duplicate": True}})
                sent = any(n == "send_work" and "accepted" in r
                           for n, r in after)
                body = last_claim["body"]
                total = body["quantity"] * body["unit_price_cents"]
                if not sent:
                    rid = "r-" + last_claim["message_id"].removeprefix("q-")
                    return self._call("send_work", {
                        "message_id": rid, "to": last_claim["from"],
                        "kind": "quote_response",
                        "body": {"request_id": last_claim["message_id"],
                                 "total_cents": total}})
                return self._call("ack_work",
                                  {"status": "processed",
                                   "note": {"applied": True,
                                            "total_cents": total}})
        if idle >= IDLE_LIMIT - 5:
            return self._call("finish", {"exit_code": 0,
                                         "note": "inbox stayed quiet"})
        return self._call("claim_work", {})

    def _buyer(self, history, task, idle):
        for name, args, result in reversed(history):
            if name == "claim_work" and "no work" not in result:
                claim = json.loads(result)
                if claim.get("kind") != "quote_response":
                    return self._call("ack_work",
                                      {"status": "rejected",
                                       "note": {"reason": "unknown kind"}})
                total = claim["body"]["total_cents"]
                correct = total == task.get("expected_total_cents")
                acked = False
                idx = history.index((name, args, result))
                for n, _, r in history[idx + 1:]:
                    if n == "ack_work" and "recorded" in r:
                        acked = True
                if not acked:
                    return self._call("ack_work", {
                        "status": "processed",
                        "note": {"correct": correct, "total_cents": total,
                                 "expected_total_cents":
                                     task.get("expected_total_cents")}})
                return self._call("finish",
                                  {"exit_code": 0 if correct else 4,
                                   "note": "validated"})
        seller = None
        for name, _, result in history:
            if name == "list_participants":
                for p in json.loads(result):
                    if "quote.read" in p.get("capabilities", []):
                        seller = p["name"]
        if seller is None:
            return self._call("list_participants", {})
        sent = any(name == "send_work" and "accepted" in result
                   for name, _, result in history)
        if not sent:
            return self._call("send_work", {
                "message_id": "q-1", "to": seller, "kind": "quote_request",
                "body": {"sku": task["sku"], "quantity": task["quantity"],
                         "unit_price_cents": task["unit_price_cents"]}})
        if idle >= IDLE_LIMIT:
            return self._call("finish", {"exit_code": 5,
                                         "note": "no response arrived"})
        return self._call("claim_work", {})


class ModelClient:
    """OpenAI-compatible chat completions, or the mock brain."""

    def __init__(self, model: str, role: str,
                 base_url: str | None = None, api_key: str | None = None,
                 http: httpx.Client | None = None):
        self.model = model
        self.mock = MockBrain(role) if model.startswith("mock:") else None
        if self.mock is None:
            self.base_url = (base_url
                             or os.environ.get("TOWN_MODEL_URL")
                             or "http://localhost:11434/v1")
            headers = {}
            key = api_key or os.environ.get("TOWN_MODEL_KEY")
            if key:
                headers["Authorization"] = f"Bearer {key}"
            self.http = http or httpx.Client(base_url=self.base_url,
                                             headers=headers, timeout=120.0)

    def chat(self, messages, tools) -> dict[str, Any]:
        if self.mock is not None:
            return self.mock.chat(messages, tools)
        r = self.http.post("/chat/completions",
                           json={"model": self.model, "messages": messages,
                                 "tools": tools, "tool_choice": "auto"})
        r.raise_for_status()
        message = r.json()["choices"][0]["message"]
        return {"content": message.get("content"),
                "tool_calls": message.get("tool_calls") or []}


class LLMParticipant:
    def __init__(self, client: TownClient, name: str, role: str,
                 state_dir: str, model: str, fault: str = "none"):
        self.client = client
        self.name = name
        self.role = role
        self.model = ModelClient(model, role)
        self.journal = Journal(os.path.join(state_dir, "journal.db"))
        self.fault = fault
        self.truncations = 0
        self.current_claim: dict[str, Any] | None = None
        self.exit_code: int | None = None
        self.messages: list[dict[str, Any]] = []

    def _system_prompt(self, token_note: str) -> str:
        role_skill = ("quote.read" if self.role == "seller"
                      else "quote.request")
        task = self.client.run_context.get("task", {})
        return (
            f"You are {self.name}, the {self.role} in a NANDA Town run."
            f" Use only your tools; every fact you assert goes into the"
            f" run's evidence.\nTASK={json.dumps(task)}\n{token_note}\n\n"
            + skill_source("town-protocol")
            + "\n\n" + skill_source(role_skill))

    # -- tool implementations ------------------------------------------

    def _tool_list_participants(self, args: dict[str, Any]) -> str:
        return json.dumps(self.client.participants())

    def _tool_claim_work(self, args: dict[str, Any]) -> str:
        self.client.notify(wait=0.4)
        claim = self.client.claim()
        if claim is None:
            return "no work right now"
        claim["already_processed"] = self.journal.seen(claim["message_id"])
        self.current_claim = claim
        return json.dumps(claim)

    def _tool_send_work(self, args: dict[str, Any]) -> str:
        out = self.client.send(args["message_id"], args["to"],
                               args["kind"], args["body"])
        return json.dumps({"accepted": True, **out})

    def _tool_ack_work(self, args: dict[str, Any]) -> str:
        if self.current_claim is None:
            return "error: no claimed work to acknowledge"
        note = dict(args.get("note") or {})
        note["context_truncations"] = self.truncations
        try:
            self.client.ack(self.current_claim["message_id"],
                            self.current_claim["fence"],
                            args["status"], note)
        except StaleFenceError:
            self.current_claim = None
            return "error: stale fence; the work will be redelivered"
        if args["status"] == "processed":
            self.journal.record(self.current_claim["message_id"],
                                {"note": note})
        self.current_claim = None
        return "recorded"

    def _tool_finish(self, args: dict[str, Any]) -> str:
        self.exit_code = int(args["exit_code"])
        return "finished"

    def _execute(self, name: str, args: dict[str, Any]) -> str:
        handler = getattr(self, f"_tool_{name}", None)
        if handler is None:
            return f"error: unknown tool {name}"
        try:
            return handler(args)
        except Exception as exc:
            return f"error: {type(exc).__name__}: {exc}"

    # -- the loop -------------------------------------------------------

    def _maybe_truncate(self) -> None:
        if self.fault != "context_truncation":
            return
        if len(self.messages) <= MESSAGE_BUDGET:
            return
        tail = self.messages[-KEEP_TAIL:]
        while tail and tail[0]["role"] == "tool":
            tail = tail[1:]
        self.messages = [self.messages[0]] + tail
        self.truncations += 1

    def run(self, deadline_seconds: float = 60.0) -> int:
        token_note = ("Your context may be truncated mid-run; anything"
                      " not in this system prompt can vanish. Recover"
                      " through the protocol: rediscover, resend the"
                      " same message identity, reclaim."
                      if self.fault == "context_truncation" else "")
        self.messages = [
            {"role": "system", "content": self._system_prompt(token_note)},
            {"role": "user", "content": "Begin. Work until your part of"
                                        " the task is done, then finish."},
        ]
        deadline = time.time() + deadline_seconds
        for _ in range(MAX_TURNS):
            if time.time() > deadline:
                return 6
            self._maybe_truncate()
            reply = self.model.chat(self.messages, TOOLS)
            calls = reply.get("tool_calls") or []
            self.messages.append({"role": "assistant",
                                  "content": reply.get("content"),
                                  "tool_calls": calls})
            if not calls:
                self.messages.append(
                    {"role": "user",
                     "content": "Use a tool, or finish."})
                continue
            for tc in calls:
                try:
                    args = json.loads(tc["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = self._execute(tc["function"]["name"], args)
                self.messages.append({"role": "tool",
                                      "tool_call_id": tc["id"],
                                      "content": result})
                if self.exit_code is not None:
                    return self.exit_code
            self._maybe_truncate()
        return 8


def main() -> None:
    env = os.environ
    client = TownClient(env["TOWN_URL"], env["RUN_ID"])
    client.join(env["NAME"], env["TOKEN"])
    participant = LLMParticipant(
        client, env["NAME"], env["ROLE"], env["STATE_DIR"],
        model=env.get("TOWN_MODEL", "mock:v1"),
        fault=env.get("FAULT", "none"),
    )
    sys.exit(participant.run(
        deadline_seconds=float(env.get("DEADLINE", "60"))))


if __name__ == "__main__":
    main()
