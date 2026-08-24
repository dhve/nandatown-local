# Completion Plan (Phase 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining doc-scoped gaps: tier-two LLM participants with an agent-native fault, bring-your-own-agent conformance testing, the Town On-Ramp with a pinned services catalog, Town Pulse operational history, a demonstrated layer swap that fails on purpose, contributor scaffolding, and a local leaderboard.

**Architecture:** The LLM runtime is a harness (tool loop, journal, fence handling, context truncation) with a pluggable brain: a deterministic mock brain by default so CI needs no inference, and any OpenAI-compatible endpoint (Ollama included) for real models. BYOA reuses the Track runner with a command override per role. On-Ramp and Pulse emit evidence records in the shared shape and never execute submitted code.

## Tasks

### Task 16: Weak-auth plugin and the failing scenario
`layers/auth.py` gains `plain.v1` (trusts any claimed sender). New scenario `capability_spoofing_weak_auth.yaml` overriding `layers: {auth: plain.v1}`; with signatures gone the spoofer's card verifies, the buyer contacts it, and the run FAILS: that failing report is the point (swap a layer, watch the town break). Validator reuses capability_spoofing. Tests assert the weak run's verdict is failed with containment failed, while the strong run still passes.

### Task 17: Tier two, the LLM participant runtime
`participants/llm.py`: ModelClient speaking OpenAI-compatible chat completions (env TOWN_MODEL, TOWN_MODEL_URL, TOWN_MODEL_KEY; `mock:` prefix selects the deterministic MockBrain). Harness owns the journal, the current claim fence, and the tool surface (list_participants, claim_work with already_processed flag, send_work, ack_work, wait, finish); the brain only emits tool calls. Fault `context_truncation`: past a message budget the harness drops the middle of the conversation (system prompt survives), counts truncations, and the agent reports the count in its ack notes (its attributed assertion). `records.py` Fault literal gains context_truncation; TestProfile gains `runtimes: dict[str, str] = {}`. `profiles.py` adds quote-llm and quote-llm-truncation (both roles llm). `runner.py` selects module per runtime and passes fault plus model env to both participants; run.config records the model as an observed mutable dependency and the skill fingerprints as release references. `evaluator.py` adds stage truncation_survived for the new fault. Tests: mock-brained buyer and seller complete the clean run and the truncation run with truncations at least 1 and correct passed; e2e via run_town.

### Task 18: Bring your own agent
`runner.py` run_town gains `external: dict[str, list[str]]` command overrides per role. `examples/byoa_seller.py`: a standalone stdlib-only seller speaking the HTTP contract. CLI `nandatown test-agent --role seller --profile quote-clean --cmd "..."` (or `--wait` to print credentials and wait for a manual join), printing the N of M town stages line. E2E test runs the example as the external seller and expects verdict passed.

### Task 19: Town On-Ramp and the services catalog
`onramp.py`: load a LOCAL OpenAPI document (json or yaml; never fetched, never executed), analyze operations (method, path, declared side effect: read or write), auth schemes, servers; structural checks as evidence records (parsed, operations found, https-only servers, auth declared, embedded-secret scan); generate a candidate SKILL.md (status: candidate, community-generated, unclaimed, not provider-endorsed) that passes validate_skill; pin an exact release fingerprint over the snapshot; write candidate dir and update `catalog.json`. CLI `nandatown onramp <spec> --name <n> --out services` and `nandatown services [name] [--dir]`. Fixture: a small self-written paylite OpenAPI with one deliberately embedded fake secret to prove the scan. Tests cover generation, fingerprint stability, secret detection, catalog listing.

### Task 20: Town Pulse
`pulse.py`: probe(url) over HTTP; SQLite history of every probe; availability report per service; export of operational-history evidence records. CLI `nandatown pulse --target name=url --count N --interval S --db` and `--report` / `--records`. Test uses a local ephemeral HTTP server that goes down mid-campaign and asserts the availability percentage and down records.

### Task 21: Scaffolding, leaderboard, docs, ship
`new.py` templates: `nandatown new scenario|plugin|skill|agent <name> [--dir]`. `board.py`: scan a runs directory, group bundles by profile, show pass rates and latest run (`nandatown board [dir]`). README and architecture updates covering everything new; full suite; push; CI green.
