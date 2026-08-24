# No Caveats Plan (Phase 5)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate every remaining caveat and every "proposed" label that can be honestly built on this machine: upstream scenario compatibility, a browser-served GUI, MCP and A2A edges, portable identity with run grants (flipping portable_identity to Passed), walk-away mirroring and recovery, the next agent-native fault, and operator mode.

## Tasks

### Task 27: Upstream scenario adapter
`upstream.py`: detect the projnanda/nandatown scenario format (agents as {count, brain, roles}), translate to ScenarioSpec: layer keys comms and datafacts mapped, upstream plugin ids substituted by local defaults with every substitution recorded as an adaptation, role maps per task type (voting, marketplace and its variants, auction, consensus, supply_chain, capability_fulfillment, spoofing variants, generic exchange fallback), counts expanded to named agents with deterministic per-index configs, tick durations to max_time, message_drop rates to the new seeded `drop_rate` transport fault. Adapted runs use the generic `adapted.v1` validator (participants active, messages flowed, ledger conserved, privacy) with the original task type and all adaptations in the report. Fixtures: the real upstream voting.yaml and PR 220's capability_fulfillment.yaml (Apache 2.0, SPDX retained). resolve_spec auto-detects, so `nandatown run <upstream.yaml>` and imported PR scenarios just run.

### Task 28: Browser GUI
textual-serve: `nandatown ui --web [--port]` serves the same TownApp in any browser; no terminal required.

### Task 29: Portable identity and run grants
`identity_portable.py` (cryptography Ed25519): controller keypairs in a keystore, a town identity registry (the local testnet registry; resolvers pluggable, including an eth_call resolver with configurable endpoint, contract, and selector), signed short-lived Run Grants authorizing one disposable session key for one run with named permissions. Coordinator: join by grant (registry-resolved controller key verifies the grant, grant verifies the session key, session bound to it); events portable_identity_verified. Track runner `--identity` provisions identities and grants for both roles; the evaluator's portable_identity stage becomes Passed with evidence when grants were used, Not tested otherwise. Controller keys never enter participant environments; only the per-run session key does. CLI: `nandatown identity new|list|grant`.

### Task 30: Walk-away mirrors
`mirror.py`: `nandatown mirror <bundle> <mirror-dir>` stores a content-addressed copy under its bundle fingerprint; `nandatown recover <fingerprint> --mirror dir [--mirror dir2] --out dir` restores from any surviving mirror and verifies. Test simulates loss: delete the original, recover from the second mirror, verify clean.

### Task 31: MCP adapter
`mcp_adapter.py`: a real MCP stdio server (JSON-RPC 2.0: initialize, tools/list, tools/call, protocol version 2025-06-18) exposing the participant tool surface (join, participants, notify, claim, send, ack) bound to one run, so any MCP host can literally play a role in the town. `nandatown mcp serve --url --run --name --token`; `nandatown mcp test --cmd "..."` probes an external MCP server (initialize handshake, tools listed, optional tool call) and reports conformance. Tests drive the server over pipes end to end inside a Track run: an MCP client completes the seller role.

### Task 32: A2A edge
`a2a_adapter.py`: serve a town seller as an A2A agent (agent card at /.well-known/agent-card.json, JSON-RPC message/send returning a completed task with the quote, tasks/get); `nandatown a2a test <url>` fetches and validates the card and runs a message/send round trip; harness `a2a:<url>` bridges a Track role to an external A2A agent (town claim -> A2A message -> reply -> ack). Test: serve the reference A2A seller locally, bridge the town's seller role to it, full Track run passes.

### Task 33: Next agent-native fault and drift canary
`tool_error` fault in the LLM harness (first claim tool result is corrupted into an error; the brain must retry; count reported in ack notes), profile quote-llm-tool-error, evaluator stage tool_error_survived. Campaigns record the model per trial and flag drift across trials in the aggregate.

### Task 34: Operator mode
docs/operators.md: running a shared coordinator (persistence, tokens, quotas, backup of the SQLite truth), with launchd and systemd unit files under deploy/. No claims beyond what ships.

### Task 35: Ship
README and architecture updates removing every proposed label that now exists, full suite, dash check, push, CI green, memory update.
