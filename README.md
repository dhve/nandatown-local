# nandatown

The open proving ground for the Internet of AI agents, running on your laptop.

Bring an agent. Give it a task. Break something on purpose. Leave with evidence of what actually happened. Agent, task, failure, evidence.

This is a local-first developer sandbox and test harness for NANDA protocols, services, and agent-to-agent workflows. It gives you two ways to test, twelve replaceable protocol layers, six ready scenarios, five fault profiles, campaigns for statistical evidence, portable evidence bundles anyone can verify, a step-by-step replay, and an HTML visualizer. No model, no wallet, no gas, no network beyond localhost. A full run takes seconds and costs nothing.

## Install

From the repository root, in a virtual environment:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Python 3.11 or newer. The venv step matters on macOS and modern
Linux: Homebrew and distro Pythons are externally managed (PEP 668)
and refuse bare pip installs. `pipx install .` works too if you prefer
pipx-managed CLIs.

## The front door

```
nandatown
```

Bare `nandatown` opens the interactive town: a full-screen terminal
GUI with six tabs. Town (the journey and one-click proofs, including
breaking the auth layer on purpose), Run (pick any scenario or
profile, connect a harness per role, watch the stage table fill),
Agents (test your own agent and read the N-of-M stages line),
Protocols (import a PR from the upstream repo), Services (onboard an
OpenAPI document), and Evidence (browse, report, verify, visualize
every bundle). Everything the GUI does is also a plain command, so
anything you click is scriptable.

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
| capability_spoofing_weak_auth | the same scenario with auth swapped for plain.v1: the run FAILS on purpose, showing what the auth layer is for |

Every scenario also gets two standing checks: the ledger conserved money across every movement, and no redacted field leaked into the exported records.

A scenario is a short YAML file: agents and roles, the plugin per layer, the faults, the seed. Point `nandatown run path/to/your.yaml` at your own; `plugin_files:` in the YAML loads your own plugin and validator modules first.

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
| quote-llm | nothing (tier two baseline) | model-driven participants complete the task through the tool loop |
| quote-llm-truncation | the agents' context is truncated mid-run | the protocol carries the recovery: rediscover, resend the same identity, reclaim |

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

## Tier two: real model participants

The scripted participants are tier one. Tier two runs the same task
through a model tool loop:

```
nandatown run quote-llm
nandatown run quote-llm-truncation
nandatown run quote-llm --model qwen2.5
```

The harness is always infrastructure: it owns the town client, the
durable journal, the claim fence, and a small tool surface (find peers,
claim, send, acknowledge, finish). The brain only emits tool calls. By
default the brain is `mock:v1`, a deterministic policy that needs no
inference, so tier two runs free and in CI. Pass `--model` to use any
OpenAI-compatible endpoint; the default endpoint is a local Ollama
(`TOWN_MODEL_URL` overrides it, `TOWN_MODEL_KEY` adds a bearer token).
A hosted model is recorded in the run as an observed mutable
dependency, because it can change underneath a pinned release.

`quote-llm-truncation` is the first agent-native fault: past a message
budget the harness drops the middle of the conversation, exactly what a
real agent meets when its context compacts mid-task. The system prompt
survives; everything else must be recoverable through the protocol.
The agents report their truncation count in their acknowledgement
notes, so surviving the fault is an attributed assertion in the
evidence.

## Connect any harness

Every Track role runs behind a harness connector, so any agent runtime
plugs into a run:

```
nandatown run quote-clean --agent seller=cmd:"python my_agent.py"
nandatown run quote-clean --agent seller=llm:qwen2.5 --agent buyer=scripted
nandatown run quote-clean --agent buyer=external
```

`scripted` is the stock reference agent, `llm` and `llm:MODEL` the
model tool loop, `cmd:COMMAND` your own process in any language, and
`external` hands out join credentials so an agent anywhere can connect.

## Test protocols from the upstream repo

```
nandatown import-pr 220
nandatown protocols
nandatown run marketplace --plugin protocols/<dir>/plugin.py --layer trust=their.v2
```

`import-pr` pulls a contribution from projnanda/nandatown (or any
`--repo`): the changed files at the exact head commit, fingerprinted,
classified (plugin with its detected layer, scenario, skill, test),
checked (including the secret scan), and cataloged as
imported-untrusted. Importing never runs the code. When you choose to,
`--plugin` loads the contributed module and `--layer` swaps it into a
scenario, so the contribution runs against the town's reference agents
and comes back with a stage report.

## Test your own agent

```
nandatown test-agent --role seller --cmd "python examples/byoa_seller.py"
nandatown test-agent --role seller --wait
```

Your agent plays one role; the town supplies the counterpart, the
fault, the evaluator, and the report, ending with the line that
matters: how many town stages your agent passed. `--cmd` starts your
agent as a subprocess with TOWN_URL, RUN_ID, NAME, TOKEN in its
environment; `--wait` prints those credentials and waits while you
start it anywhere else. `examples/byoa_seller.py` is a complete
reference agent in plain standard-library Python: no nandatown import,
no dependency, just the HTTP contract.

## Onboard a service

```
nandatown onramp path/to/openapi.json
nandatown services
nandatown services paylite
```

The On-Ramp turns a provider's LOCAL OpenAPI document into a
reviewable candidate: a generated SKILL.md with every operation and its
declared side effect, the open questions a reviewer must resolve, an
exact release fingerprint over the snapshot, and structural checks
recorded as evidence (parsed, operations found, https-only servers,
auth declared, embedded-secret scan). Nothing is fetched from the
network and nothing in the document is ever executed. The candidate is
published to a pinned catalog as community-generated, unclaimed, and
not provider-endorsed: the SKILL.md is a claim, not a fact, and town
tests plus provider authorization stay separate evidence.

## Watch services over time

```
nandatown pulse --target paylite=https://api.example.com/health --count 10 --interval 60
nandatown pulse --report --db pulse.db
nandatown pulse --records --db pulse.db
```

A sandbox test at onboarding is one moment and cannot show next week.
Pulse probes each target on a schedule, keeps the full history in
SQLite, reports availability per service, and exports every probe as an
operational-history evidence record.

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

## Contribute a piece

```
nandatown new scenario my-town
nandatown new plugin trust mytrust.v1
nandatown new skill my.skill
nandatown new agent my-agent
nandatown board runs
```

A contribution usually carries a protocol (the rules), a plugin (the
code that runs those rules inside one layer), and a test that proves it
holds up. `new` starts each piece from a working template; `board` is
the local leaderboard over your evidence bundles, ranked by pass rate,
every line backed by a verifiable bundle.

## The raw HTTP contract

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

Built here already: the Lab, the Track with scripted and model-driven tiers, the first agent-native fault (context truncation), bring-your-own-agent testing, the OpenAPI On-Ramp with a pinned catalog, Town Pulse operational history, campaigns, and the evidence pipeline under all of it. Still proposed, labeled proposed until they exist here: A2A and MCP conformance testing against the upstream kits, portable agent identity through ERC-8004 with short-lived run grants, EFS subject to the Walk-Away Test, further agent-native fault profiles (tool-choice errors, hallucinated capabilities, model version drift canaries), and a continuously operated shared testnet.

## Development

```
pip install -e ".[dev]"
pytest
```

See `docs/architecture.md` for the module map. Apache 2.0. Part of the NANDA Town effort under Project NANDA.
