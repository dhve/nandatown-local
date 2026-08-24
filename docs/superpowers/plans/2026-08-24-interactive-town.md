# Interactive Town Plan (Phase 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the town a product surface: a full-screen interactive terminal GUI launched by bare `nandatown`, per-role harness connectors so any agent runtime plugs into a run, layer and plugin overrides on the run command, and protocol onboarding that imports a PR from the upstream nandatown repository, checks it, and lets it run against the reference agents.

**Architecture:** The TUI (Textual) is a thin shell over the existing functions; every action it offers is also a plain CLI command, and long work runs in Textual workers so the interface stays live. Harnesses are per-role connector specs (scripted, llm with a model, cmd, external) resolved by the Track runner. PR import mirrors the On-Ramp discipline: snapshot, fingerprint, classify, check, catalog as imported-untrusted; running imported code stays an explicit later choice.

## Tasks

### Task 22: Harness connectors
`runner.py`: `parse_harness(spec)` supporting `scripted`, `llm`, `llm:MODEL`, `cmd:COMMAND`, `external`; `run_town(..., harnesses={role: spec})` overriding the profile's runtimes per role, with per-role model env. CLI: repeatable `--agent role=spec` on `nandatown run` (Track targets). Tests: cmd harness runs the BYOA example, llm harness overrides a scripted profile, per-role model env lands.

### Task 23: Run overrides for the Lab
`sim/runner.py` run_lab gains `plugins` (extra plugin files to load) and `layer_overrides` ({layer: plugin_id}). CLI: repeatable `--plugin FILE` and `--layer LAYER=ID` on `nandatown run` (Lab targets; a clear error on Track targets). Test: `--layer auth=plain.v1` on capability_spoofing produces the failing verdict without the dedicated weak-auth scenario file; a scaffolded custom plugin file loads via `--plugin`.

### Task 24: Protocol onboarding from the upstream repo
`protocols.py`: fetch a public PR (metadata, changed files at the head sha, fork-aware) from GitHub's API with optional GITHUB_TOKEN, capped in file count and size; snapshot into `protocols/<n>-<slug>/` with a content fingerprint; classify files (plugin with detected layer, scenario, skill, test, other); structural checks reusing the secret scan; catalog entry `imported-untrusted` with a printed recipe for running it against the reference agents (`nandatown run <scenario> --plugin ... --layer ...`). CLI: `nandatown import-pr N [--repo projnanda/nandatown]` and `nandatown protocols [name]`. Tests entirely over a mock transport; one live smoke outside pytest.

### Task 25: The interactive GUI
`tui.py`: a Textual app with tabs Town (journey, counts, quick run), Run (pick scenario or profile, per-role harness, fault visible, live log, stage table), Agents (harness explainer, test-agent with command or wait credentials), Protocols (import form plus catalog), Services (onramp form plus catalog), Evidence (bundle table with report, verify, replay, visualize). Bare `nandatown` and `nandatown ui` launch it. Workers keep the UI responsive. Pilot tests: the app mounts with all tabs, a Lab run triggered from the Run tab completes and fills the stage table.

### Task 26: Ship
pyproject gains textual. README: the GUI is the front door, harness connectors, protocol onboarding. Full suite, dash check, push, CI green.
