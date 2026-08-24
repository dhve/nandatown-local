# nandatown

The open proving ground for the Internet of AI agents, running on your laptop.

Bring an agent. Give it a task. Break something on purpose. Leave with evidence of what actually happened.

This is a local-first developer sandbox and test harness. Two isolated participants complete one small task through a durable town coordinator while the town injects one named failure. The run produces a System Fitness Report that separately shows what passed, what failed, and what was not tested, plus a portable evidence bundle you can verify and replay.

## Install

```
pip install -e .
```

Python 3.11 or newer. No model, no wallet, no network beyond localhost. A full run takes a few seconds and costs nothing.

## The one command

```
nandatown run
```

This runs the default profile: the boring quote. A buyer asks a seller for 2 widgets at 1995 cents. The seller crashes after claiming the work. The town fences the dead attempt, redelivers, and the restarted seller answers. The buyer checks the total is 3990 cents. The task is not the demo. Custody, recovery, stale-attempt rejection, correlation, and correctness are the demo.

## The profiles

Every profile runs the same quote task under a different condition. Exactly one failure per run, chosen on purpose.

```
nandatown profiles
```

| Profile | What breaks | What must hold |
|---|---|---|
| quote-clean | nothing | the calibration baseline |
| quote-crash-restart | the seller stops after claiming | the stale attempt cannot act; the town redelivers; the task is applied once |
| quote-drop-wakeup | the wake-up hint is lost | the durable inbox still delivers; a hint is never the only copy of the work |
| quote-duplicate-delivery | the same work is offered twice | the seller recognizes work it already handled |
| quote-lost-ack | the first acknowledgement is lost | the retry is safe; nothing is applied twice |

## A sample report

```
NANDA Town System Fitness Report
========================================
Run:       run-c1e318ea3bcf
Profile:   quote-crash-restart (fault: crash_after_claim)
Task:      quote 2 x widget at 1995 cents, expecting 3990 cents
Verdict:   PASSED

Stages (each one a separate claim with its own failure boundary):
  accepted                 Passed   the town committed the request before reporting success
  claimed                  Passed   a seller claimed the work under a lease
  received                 Passed   the seller acknowledged receipt through a valid fence
  processed                Passed   the seller applied the task exactly once
  response                 Passed   the response was accepted and reached the buyer
  correct                  Passed   the buyer checked the total itself
  recovered_after_restart  Passed   accepted work survived the crash and was redelivered
  stale_fence_rejected     Passed   the old attempt could not act after its lease
  portable_identity        Not tested

This result applies only to the named agents, releases, scenario, failure, evaluator, and time window.
One run is one scoped observation, not a certificate.
```

An HTTP success response never becomes proof that the agent understood or completed the task. Acceptance, claiming, receipt, processing, response, and correctness are always judged separately, and missing evidence stays missing.

## The evidence bundle

Every run writes one directory under `runs/`. Five records keep the evidence understandable:

| File | Record | What it holds |
|---|---|---|
| `profile.json` | the test profile | the recipe: roles, task, condition, evaluator |
| `run.json` | the run | the attempt: participants, versions, configuration |
| `intents.jsonl` | the intents | the requested actions: send, claim, acknowledge |
| `events.jsonl` | the events | the attributed facts: who observed what, when |
| `result.json` | the result | the evaluator's stage verdicts |

`manifest.json` fingerprints every record. `report.md` is a readable view generated from the bundle, not a sixth record. `state/` keeps the run's operational state (the town database and each participant's journal) for inspection.

```
nandatown report runs/<run-id>
nandatown verify runs/<run-id>
```

`verify` recomputes every hash and replays the pinned evaluator over the recorded events. If someone edited the result, or the events no longer support it, verify says so.

## How delivery works

The coordinator's database is the source of operational truth.

- Accepted work and the intent to notify the recipient are recorded in one transaction.
- Delivery is at least once. Work is claimed under a lease with a fencing token. When a lease ends, the fence dies with it: an old attempt can never acknowledge work it no longer owns.
- Duplicate delivery is possible by design. Each participant keeps a durable journal of work already processed, so an effect is applied once on its own side.
- Retrying the same request identity with identical content returns the original acceptance. The same identity with different content is rejected.
- Live notifications are wake-up hints, never the only copy of the work.

## Bring your own agent

The stock buyer and seller are just clients of a small HTTP contract. Anything that speaks it can take their place.

```
nandatown coordinator --port 8477
```

| Method and path | Who | What it does |
|---|---|---|
| `POST /runs` | admin | create a run from a profile; returns join tokens |
| `POST /runs/{run}/join` | agent | enter the run; returns a session and the task |
| `GET /runs/{run}/participants` | agent | find peers and their capabilities |
| `POST /runs/{run}/messages` | agent | send work; idempotent by message identity |
| `GET /runs/{run}/inbox/notify` | agent | long-poll for a wake-up hint |
| `POST /runs/{run}/inbox/claim` | agent | claim one piece of work under a lease |
| `POST /runs/{run}/inbox/ack` | agent | acknowledge: received, processed, rejected, retryable, or failed |
| `GET /runs/{run}/events` | admin | export the attributed event log |
| `GET /runs/{run}/intents` | admin | export the requested actions |
| `POST /runs/{run}/finish` | admin | close the run |

Agent routes take an `X-Town-Session` header from join. Admin routes take `X-Town-Admin`. Run creation and fault plans are never agent tools.

## What a run does not prove

One run is one scoped observation. It does not prove general reliability, provider endorsement, exactly-once external side effects, independent judgment, or any universal score. Reliability claims need repeated, predeclared runs and independent observers. Later conclusions can reference this evidence; they never rewrite it.

## Lab now, Track later

What you have here is the Lab tier: scripted, deterministic participants, fast runs, controlled disruptions, no model tokens. The Track, real agent runtimes with real latency, context, and restart failures, is proposed and not part of this build. The two share the same records, the same stages, and the same coordinator contract, so a live run can be compared against a scripted one of the same scenario.

## Development

```
pip install -e ".[dev]"
pytest
```

Apache 2.0. Part of the NANDA Town effort under Project NANDA.
