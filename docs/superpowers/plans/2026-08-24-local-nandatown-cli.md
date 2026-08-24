# Local NANDA Town Sandbox + CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Alpha 0.2 "modular monolith" from the NANDA Town: Everything doc: one pip-installable CLI, one durable coordinator (HTTP contract, mailbox and leases, event log) on SQLite, two isolated buyer/seller participants, fault injection, a pinned evaluator, and a portable evidence bundle with a verify step.

**Architecture:** A FastAPI coordinator owns the durable truth in SQLite (runs, participants, messages, claims with fencing tokens, acks, notifications, events). Buyer and seller are scripted state-machine participants that run as separate subprocesses with their own state directories and idempotency journals, talking to the coordinator only over HTTP. A runner orchestrates one full run (start coordinator, spawn participants, inject one named fault, restart on crash, evaluate, write bundle). The CLI wraps the runner plus report and verify commands.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, pydantic v2, httpx, SQLite (stdlib sqlite3, WAL mode), pytest. CLI via argparse (stdlib).

## Global Constraints

- Package name and CLI command: `nandatown`. Project root: `/Users/admin/nandatown-local`.
- Laptop-first: a full lab run completes in under 15 seconds with no model, wallet, RPC, or network dependency beyond localhost.
- Delivery promise (doc 11.2, verbatim requirements): accepted work + intent to notify recorded in one database transaction; at-least-once delivery; duplicate delivery possible and participants must recognize work already handled; retrying the same request returns the original acceptance; reusing the same request identity with different content is rejected; live notifications are wake-up hints, never the only copy of the work; an HTTP success response never becomes proof the agent understood or completed the task.
- Stages are separate claims with separate failure boundaries: accepted, claimed, received, processed, response, correct. Missing evidence stays "Not enough evidence", never inferred.
- Every event names its observer. Participant assertions are attributed to the participant; the town cannot synthesize them.
- Five records only: test profile, run, intents, events, evidence bundle. The human report is a rendered view of the bundle, not a sixth record.
- Model-facing/participant tool surface is limited to: join run, find participants, wait for notify, claim inbox work, send work, acknowledge work, inspect run. Run creation and fault plans are CLI/admin only.
- No em dashes or en dashes anywhere in shipped files. No "Generated with Claude Code" or Co-Authored-By footers in commits. Plain, direct sentences in all docs.
- One run is evidence, not a diploma: report language must say the result applies only to the named agents, releases, scenario, failure, evaluator, and time.

## File Structure

```
nandatown-local/
  pyproject.toml
  README.md
  src/nandatown/
    __init__.py            version
    records.py             five record types (pydantic) + canonical JSON fingerprinting
    db.py                  SQLite store and transactional mailbox semantics
    coordinator.py         FastAPI app: HTTP contract + fault injection + event log
    client.py              TownClient, participant-side HTTP client (httpx)
    participants/
      __init__.py
      base.py              poll loop + durable idempotency journal
      buyer.py             sends quote request, validates 39.90
      seller.py            claims, applies once, responds; scripted crash fault
    evaluator.py           stage checks over the event log -> result record
    bundle.py              evidence bundle write/load/verify (manifest + sha256)
    report.py              System Fitness Report renderer (terminal + markdown)
    runner.py              full-run orchestration incl. seller restart
    profiles.py            five built-in test profiles
    cli.py                 argparse entry point
  tests/
    test_records.py
    test_db.py
    test_coordinator.py
    test_participants.py
    test_evaluator.py
    test_bundle.py
    test_e2e.py
```

## The HTTP contract (locked here, used by every task)

All participant routes require header `X-Town-Session: <session token>`. Admin routes require `X-Town-Admin: <admin token>` (runner-generated secret).

- `POST /runs` (admin) body `{profile: TestProfile}` -> `{run_id, join_tokens: {name: token}}`
- `POST /runs/{run_id}/join` body `{name, token}` -> `{session, participant_id, run: {run_id, task, roles}}`
- `GET /runs/{run_id}/participants` -> `[{name, role, capabilities}]`
- `POST /runs/{run_id}/messages` body `{message_id, to, kind, body}` -> `202 {message_id, accepted_at, replay: bool}`; same message_id + same content returns the original acceptance with `replay: true`; same message_id + different content -> `409 {error: "identity_reuse"}`
- `GET /runs/{run_id}/inbox/notify?wait=<seconds>` -> `{hint: bool}` long-poll wake-up hint
- `POST /runs/{run_id}/inbox/claim` -> `204` when no work, else `{message_id, kind, body, from, attempt, fence, lease_expires_at, duplicate: bool}`
- `POST /runs/{run_id}/inbox/ack` body `{message_id, fence, status, note}` with status in `received|processed|rejected|retryable|failed` -> `200`, or `409 {error: "stale_fence"}` when the fence is not the current claim, or `503` once when the lost_ack fault fires
- `GET /runs/{run_id}/events` (admin) -> `{events: [TownEvent]}`
- `GET /runs/{run_id}/intents` (admin) -> `{intents: [Intent]}`
- `POST /runs/{run_id}/finish` (admin) -> `200`

Faults (exactly one per profile, chosen from): `none`, `drop_wakeup` (suppress the notify hint for the first quote_request; durable inbox still serves it), `duplicate_delivery` (offer the first processed quote_request one extra time on a later claim with `duplicate: true`), `lost_ack` (return 503 for the first processed-ack of the quote_request, once), `crash_after_claim` (participant-side: seller stalls past its lease after its first claim, tries the stale-fence ack, exits nonzero, runner restarts it).

Town events (observer `town` unless noted): `run_created`, `participant_joined`, `message_accepted`, `replay_returned`, `identity_reuse_rejected`, `notify_suppressed`, `message_claimed`, `claim_expired`, `duplicate_offered`, `stale_fence_rejected`, `ack_dropped`, `ack_recorded` (observer: the acking participant, with its note payload), `run_finished`, plus runner-observed `participant_crashed` and `participant_restarted`.

---

### Task 1: Project skeleton, records, fingerprinting

**Files:**
- Create: `pyproject.toml`, `src/nandatown/__init__.py`, `src/nandatown/records.py`
- Test: `tests/test_records.py`

**Interfaces:**
- Produces: pydantic models `TestProfile` (name, task: dict with kind/sku/quantity/unit_price_cents/expected_total_cents, roles: dict name->role, capabilities: dict name->list, fault, lease_seconds, evaluator: str), `RunRecord`, `Intent`, `TownEvent` (event_id, run_id, at, observer, kind, subject, detail: dict), `EvidenceResult` (stage results + verdict), and `fingerprint(obj) -> "sha256:<hex>"` over canonical JSON (sorted keys, compact separators).

- [ ] Steps: write `tests/test_records.py` covering: fingerprint is stable across key order, changes when content changes; `TestProfile` round-trips through JSON; a `TownEvent` requires observer and kind. Run to fail, implement `records.py`, run to pass, `git commit -m "feat: record types and canonical fingerprinting"`.

### Task 2: SQLite store with transactional mailbox semantics

**Files:**
- Create: `src/nandatown/db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces: class `TownDB(path)` with methods `create_run(profile_json) -> run_id`, `add_participant(run_id, name, role, capabilities, join_token)`, `authenticate(run_id, name, token) -> session`, `session_owner(session)`, `directory(run_id)`, `accept_message(run_id, sender, message_id, to, kind, body_json, fingerprint) -> (accepted_at, replay)` raising `IdentityReuse`, `pop_notify(run_id, participant) -> bool`, `claim_next(run_id, participant, lease_seconds, now) -> claim dict or None` (expires stale leases first, increments attempt, issues new fence token), `ack(run_id, participant, message_id, fence, status, note, now)` raising `StaleFence`, `record_event(...)`, `events(run_id)`, `intents(run_id)`, `record_intent(...)`.
- `accept_message` inserts the message row and the notification row in ONE transaction. Message states: accepted -> claimed -> done(processed|rejected|failed); retryable ack returns it to accepted.

- [ ] Steps: failing tests for: accept then claim returns work with fence 1 attempt 1; expired lease makes work claimable again with attempt 2 and a new fence, and the old fence's ack raises `StaleFence`; identical resend returns replay acceptance, different-content resend raises `IdentityReuse`; ack with current fence transitions state and a second claim returns None; notification row exists after accept (query it directly). Implement `db.py` (WAL, foreign keys, monotonic fence via claims rowid). Run, pass, `git commit -m "feat: durable mailbox with leases, fencing, idempotent accept"`.

### Task 3: Coordinator HTTP app with fault injection

**Files:**
- Create: `src/nandatown/coordinator.py`
- Test: `tests/test_coordinator.py` (fastapi TestClient)

**Interfaces:**
- Consumes: `TownDB`, records.
- Produces: `build_app(db_path, admin_token) -> FastAPI` implementing the locked contract above, recording an Intent for every send/claim/ack request and a TownEvent for every fact, and applying the run profile's fault (`drop_wakeup`, `duplicate_delivery`, `lost_ack` are coordinator-side; each fires at most once and always records its event).

- [ ] Steps: failing tests for: full happy path over HTTP (create run, both join, directory shows seller capability quote.read, send, notify hint true, claim, ack processed, events contain message_accepted and ack_recorded with observer seller); identity reuse -> 409; stale fence -> 409 with stale_fence_rejected event; drop_wakeup -> notify returns no hint but claim still returns work and notify_suppressed event exists; duplicate_delivery -> after processed ack one extra claim returns the same message with duplicate true and duplicate_offered event; lost_ack -> first processed ack gets 503 with ack_dropped event, retry gets 200. Implement, run, pass, `git commit -m "feat: coordinator HTTP contract with fault injection"`.

### Task 4: Participant client and base loop

**Files:**
- Create: `src/nandatown/client.py`, `src/nandatown/participants/__init__.py`, `src/nandatown/participants/base.py`
- Test: `tests/test_participants.py` (client half)

**Interfaces:**
- Produces: `TownClient(base_url, run_id)` with `join(name, token)`, `participants()`, `send(message_id, to, kind, body) -> dict` (retries 503 once), `notify(wait)`, `claim()`, `ack(message_id, fence, status, note)`; `Journal(path)` with `seen(message_id)`, `record(message_id, result_json)`, `get(message_id)` backed by its own SQLite file (the participant's durable processed-work record); `run_loop(client, journal, handler, until, poll_interval)` that waits on notify with a short timeout, then claims regardless (hint is never the only copy), dispatches to `handler(claim) -> (status, note, replies)` and sends replies before acking.

- [ ] Steps: failing tests for Journal durability across reopen and for send retry-on-503 using a stub transport; implement; pass; `git commit -m "feat: town client, durable journal, participant loop"`.

### Task 5: Buyer and seller

**Files:**
- Create: `src/nandatown/participants/buyer.py`, `src/nandatown/participants/seller.py`
- Test: extend `tests/test_participants.py` (in-process against TestClient-served app)

**Interfaces:**
- Produces: `python -m nandatown.participants.seller` and `...buyer` runnable with env `TOWN_URL, RUN_ID, NAME, TOKEN, STATE_DIR, FAULT`. Seller: joins, loops; on quote_request q-<n>: if journal seen -> resend original response (idempotent send) and ack processed with note `{duplicate: true}`; else compute `total_cents = quantity * unit_price_cents`, journal it, send quote_response `r-<same n>` to buyer with `{request_id, total_cents}`, ack processed. With `FAULT=crash_after_claim` and no journal marker `crashed-once`: after first claim, write marker, sleep past lease, attempt ack with the now-stale fence (expect 409), exit code 3. Buyer: joins, discovers the participant whose capabilities include `quote.read`, sends q-1 `{sku, quantity, unit_price_cents}` from the profile task, then loops waiting for quote_response; on it, checks `total_cents == expected_total_cents`, acks processed with note `{correct: bool, total_cents}`, exits 0 on correct, 4 on incorrect.

- [ ] Steps: failing test running buyer and seller logic in threads against an in-process app for the clean profile asserting the buyer's ack note says correct with total 3990; implement both modules; pass; `git commit -m "feat: scripted buyer and seller participants"`.

### Task 6: Evaluator

**Files:**
- Create: `src/nandatown/evaluator.py`
- Test: `tests/test_evaluator.py`

**Interfaces:**
- Consumes: events list, profile.
- Produces: `evaluate(profile, run, events) -> EvidenceResult` with `EVALUATOR_VERSION = "0.2.0"`. Stages, each Passed/Failed/Not enough evidence with the exact evidence event ids: `accepted` (message_accepted for the quote request), `claimed`, `received` (ack_recorded by seller with valid fence), `processed` (exactly one non-duplicate processed ack by seller; more than one applied -> Failed), `response` (quote_response accepted and claimed by buyer), `correct` (buyer ack note correct true). Fault checks only when the profile names the fault: `recovered_after_restart` (claim_expired then later message_claimed), `stale_fence_rejected`, `duplicate_recognized` (duplicate_offered then seller processed-with-duplicate-note and only one apply), `wakeup_loss_tolerated` (notify_suppressed then message_claimed), `ack_retry_survived` (ack_dropped then ack_recorded). Always includes `portable_identity: Not tested (short-lived run sessions)`. Verdict passed only if every applicable stage passed.

- [ ] Steps: failing tests with hand-built event lists: clean pass; missing buyer ack -> correct is Not enough evidence, verdict not passed; two applied processed acks -> processed Failed; crash profile event list -> recovered_after_restart and stale_fence_rejected Passed. Implement; pass; `git commit -m "feat: pinned stage evaluator"`.

### Task 7: Evidence bundle and report

**Files:**
- Create: `src/nandatown/bundle.py`, `src/nandatown/report.py`
- Test: `tests/test_bundle.py`

**Interfaces:**
- Produces: `write_bundle(dir, profile, run, intents, events, result) -> manifest` writing `profile.json, run.json, intents.jsonl, events.jsonl, result.json, manifest.json` (sha256 per file plus bundle fingerprint) and `report.md`; `load_bundle(dir)`; `verify_bundle(dir) -> list[str]` returning problems: hash mismatches, or evaluator re-run (same EVALUATOR_VERSION) whose stage verdicts differ from result.json. `render_report(bundle) -> str` showing: header (run id, profile, fault, releases, time), the journey line (bring, connect, attempt, disrupt, inspect, improve), a stage table with evidence ids, fault checks, Not tested items, and the scope sentence: "This result applies only to the named agents, releases, scenario, failure, evaluator, and time window. One run is one scoped observation, not a certificate."

- [ ] Steps: failing tests: write then verify -> no problems; tamper with events.jsonl -> hash problem reported; edit result.json verdict -> evaluator mismatch reported; report contains the scope sentence and one row per stage. Implement; pass; `git commit -m "feat: portable evidence bundle with verify and report"`.

### Task 8: Profiles, runner, CLI

**Files:**
- Create: `src/nandatown/profiles.py`, `src/nandatown/runner.py`, `src/nandatown/cli.py`; Modify: `pyproject.toml` (console script `nandatown = nandatown.cli:main`)
- Test: `tests/test_e2e.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `PROFILES` dict with `quote-clean`, `quote-crash-restart` (default), `quote-drop-wakeup`, `quote-duplicate-delivery`, `quote-lost-ack`, all on the boring quote task (2 widgets at 1995 cents, expected 3990). `run_town(profile_name, out_dir, port=0) -> (bundle_dir, result)`: starts uvicorn coordinator subprocess on a free port with a temp SQLite path, creates the run, spawns buyer and seller subprocesses with env, on seller exit code 3 records participant_crashed and restarts it once recording participant_restarted, waits for buyer exit (timeout 30s), finishes run, pulls events and intents, evaluates, writes bundle under `out_dir/<run_id>/`, always tears down subprocesses. CLI: `nandatown run [--profile P] [--out DIR]` prints the report and exits 0 only on verdict passed; `nandatown profiles`; `nandatown report <bundle_dir>`; `nandatown verify <bundle_dir>`; `nandatown coordinator [--port N] [--db PATH]` for bring-your-own-agent use.

- [ ] Steps: failing e2e test invoking `run_town("quote-clean", tmp)` asserting verdict passed and bundle verify clean, plus `run_town("quote-crash-restart", tmp)` asserting recovered_after_restart and stale_fence_rejected Passed with verdict passed; implement profiles, runner, cli; `pip install -e .`; run full pytest; run `nandatown run` for every profile by hand and confirm exit 0; `git commit -m "feat: profiles, runner, one-command CLI"`.

### Task 9: README

**Files:**
- Create: `README.md`

- [ ] Steps: write README with: the one-line product framing (bring an agent, give it a task, break something on purpose, leave with evidence); install (`pip install -e .`); the one command (`nandatown run`); what each profile breaks; a sample report; the five records and where they live in a bundle; the HTTP contract table for bring-your-own-agent against `nandatown coordinator`; what a run does not prove (general reliability, provider endorsement, exactly-once external side effects, a universal score); Lab now, Track later wording with the Track labeled proposed. Plain sentences, no em dashes. `git commit -m "docs: README"`.

## Self-Review Notes

- Spec coverage: Alpha 0.2 monolith pieces all present (CLI, coordinator on SQLite, two isolated participants, evidence bundle, verify step). Run Zero semantics in Tasks 2/3/5. Boring-quote stages in Task 6. Journey and scope language in Task 7. BYOA seam via `nandatown coordinator` in Task 8. Out of scope, deliberately: A2A, Ethereum/ERC-8004, EFS, onboarding On-Ramp, campaigns (README mentions them as the growth path only).
- Type consistency: fence is an opaque string issued per claim; message ids are caller-chosen logical identities; all money is integer cents.
