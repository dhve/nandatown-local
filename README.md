# nandatown

The open proving ground for the Internet of AI agents, running on your laptop.

Bring an agent. Give it a task. Break something on purpose. Leave with evidence of what actually happened. Agent, task, failure, evidence.

This is a local-first developer sandbox and test harness for NANDA protocols, services, and agent-to-agent workflows. It gives you two ways to test, twelve replaceable protocol layers, six ready scenarios, five fault profiles, campaigns for statistical evidence, portable evidence bundles anyone can verify, a step-by-step replay, and an HTML visualizer. No model, no wallet, no gas, no network beyond localhost. A full run takes seconds and costs nothing.

## Install

```
pip install -e .
```

Python 3.11 or newer.

## One command

```
nandatown run
```

That runs the default Track profile: the boring quote. A buyer asks a seller for 2 widgets at 1995 cents. The seller crashes after claiming the work. The town fences the dead attempt, redelivers, the restarted seller answers, and the buyer checks the total is 3990 cents. The task is not the demo. Custody, recovery, stale-attempt rejection, correlation, and correctness are the demo.

```
nandatown run marketplace
```

That runs a Lab scenario instead: two sellers and a buyer discover each other through the town index, haggle to a price, settle through escrow, survive a duplicated delivery, build reputation from signed receipts, and reuse a remembered counterparty in round two. Deterministic, seeded, replayable.

## The two ways to test

**The Lab** is repeatable: scripted, mechanical participants in a seeded discrete event simulation. Same scenario and seed, same trace, every time. Faults are declared in the scenario and injected by the transport layer. Fast enough for CI and for campaigns of many trials.

**The Track** is realistic: isolated participant subprocesses talking to a durable coordinator over real HTTP, with leases, fencing tokens, at-least-once delivery, and real process crashes and restarts. It is where a bring-your-own agent plugs in.

Both produce the same evidence bundle, so report, verify, replay, visualize, and campaign work identically on either.

## The twelve layers

Everything in the town runs on twelve replaceable protocol layers. Each has a working default plugin, and a scenario can swap any of them.

| Layer | Default | What it does |
|---|---|---|
| transport | memory.v1 | delivers envelopes, injects drop, duplicate, and delay faults |
| communication | envelope.v1 | message envelopes, conversation ids, correlation |
| identity | keys.v1 | per-agent keys and agent cards |
| registry | index.v1 | the town's internal index: publish cards, look up capabilities |
| auth | hmac.v1 | signs and verifies messages and cards; forged senders fail |
| trust | reputation.v1 | receipt-driven reputation with a public formula |
| payments | ledger.v1 | balances, transfers, escrow; money is conserved |
| coordination | contractnet.v1 | announce, bid, award, with late bids rejected |
| negotiation | haggle.v1 | alternating offers to an auditable agreed price |
| memory | kv.v1 | durable per-agent memory |
| privacy | redact.v1 | declared fields never leave the run |
| data_facts | evidence.v1 | signed one-observer, one-subject, one-time records |

```
nandatown layers
```

Register your own plugin with `@register("payments", "yourledger.v1")` and name it in a scenario under `layers:`.

## Lab scenarios

```
nandatown scenarios
nandatown run auction --seed 7
```

| Scenario | What it proves |
|---|---|
| marketplace | discovery, negotiation, escrow settlement, duplicate recognition, reputation, memory reuse |
| auction | sealed signed bids, highest bid wins, late bid rejected, exactly one payment |
| voting | one agent one vote, double ballot rejected, tally matches, result broadcast |
| consensus | quorum commit under dropped acknowledgements, retries recover the missing acceptors |
| supply_chain | contract-net bidding, milestone escrow per part, assembly ordering, delayed delivery survived |
| capability_spoofing | a forged capability card is unverified, contained, and gets no business |

Every scenario also gets two standing checks: the ledger conserved money across every movement, and no redacted field leaked into the exported records.

A scenario is a short YAML file: agents and roles, the plugin per layer, the faults, the seed. Point `nandatown run path/to/your.yaml` at your own.

## Track profiles

```
nandatown profiles
```

| Profile | What breaks | What must hold |
|---|---|---|
| quote-clean | nothing | the calibration baseline |
| quote-crash-restart | the seller stops after claiming | the stale attempt is fenced, the town redelivers, the task applies once |
| quote-drop-wakeup | the wake-up hint is lost | the durable inbox still delivers |
| quote-duplicate-delivery | the same work is offered twice | the seller recognizes work it already handled |
| quote-lost-ack | the first acknowledgement is lost | the retry is safe, nothing applies twice |

Delivery semantics, in one paragraph: the coordinator's database is the source of operational truth. Accepted work and the intent to notify are recorded in one transaction. Delivery is at least once, under leases with fencing tokens; an expired fence can never acknowledge. Duplicate delivery is possible by design, and each participant keeps a durable journal so effects apply once. Retrying the same message identity with identical content returns the original acceptance; the same identity with different content is rejected. Notifications are wake-up hints, never the only copy of the work.

## Evidence, not claims

Every run writes one bundle directory with five records: `profile.json` (the recipe), `run.json` (the attempt), `intents.jsonl` (the requested actions), `events.jsonl` (the attributed facts), `result.json` (the evaluator's stage verdicts), plus `manifest.json` with a hash of every record. `report.md` is a readable view, not a sixth record.

```
nandatown report runs/<id>
nandatown verify runs/<id>
nandatown replay runs/<id> --kind escrow_released
nandatown visualize runs/<id>
```

`verify` recomputes every hash and replays the pinned evaluator over the recorded events; edits to the result or the events are caught. `visualize` writes a single HTML file: agents on a town map, messages animating along the timeline, the event log, and the stage table.

Stages are separate claims with separate failure boundaries. An HTTP success is never proof an agent understood or completed a task. Missing evidence stays missing. Every event names its observer, and the town cannot synthesize a participant's assertions.

## Campaigns

One run resolving to one verdict certifies luck. A campaign precommits its plan before the first trial and reports the whole distribution:

```
nandatown campaign marketplace --trials 20
nandatown campaign quote-lost-ack --trials 5
```

Every pass, failure, incomplete, and error stays in the record. The unit of evidence is the distribution.

## Skills

```
nandatown skills
nandatown skills town-protocol
nandatown skills --validate my-skill.md
```

A SkillMD is a short Markdown file with YAML frontmatter that any agent can read and follow. The bundled skills document the shared town protocol and each reference role.

## Bring your own agent

The stock participants are just clients of a small HTTP contract. Anything that speaks it can take their place:

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
| `POST /runs/{run}/inbox/ack` | agent | acknowledge: received, processed, rejected, retryable, failed |
| `GET /runs/{run}/events` | admin | export the attributed event log |
| `GET /runs/{run}/intents` | admin | export the requested actions |
| `POST /runs/{run}/finish` | admin | close the run |

Agent routes take `X-Town-Session` from join; admin routes take `X-Town-Admin`. Run creation and fault plans are never agent tools. The shared concepts (run plan, agent message, town event, release reference, evidence record) ship as JSON Schemas under `schemas/`, regenerated with `nandatown schemas`. Python is the first implementation, not the protocol.

## What a run does not prove

One run is one scoped observation. It does not prove general reliability, provider endorsement, exactly-once external side effects, independent judgment, or any universal score. Reliability claims need precommitted campaigns and independent observers. Later conclusions can reference the evidence; they never rewrite it.

## Where this is heading

This build is the Lab plus the first Track. The proposed next steps from the design work, in order: real LLM-backed participants against the same coordinator contract, A2A and MCP onboarding through a Town On-Ramp, portable agent identity through ERC-8004 with short-lived run grants, and agent-native fault profiles (context truncation, tool-choice errors, hallucinated capabilities) alongside the transport faults. Each is labeled proposed until it exists here.

## Development

```
pip install -e ".[dev]"
pytest
```

See `docs/architecture.md` for the module map. Apache 2.0. Part of the NANDA Town effort under Project NANDA.
