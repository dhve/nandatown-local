# Architecture

One package, two testing modes, one evidence pipeline.

## Module map

```
src/nandatown/
  records.py       shared record types: TestProfile, RunRecord, Intent,
                   TownEvent, AgentMessage, ReleaseRef, EvidenceRecord,
                   StageResult, EvidenceResult, canonical fingerprinting
  schemas.py       exports the shared concepts as JSON Schemas

  layers/          the twelve protocol layers, one module each, plus the
                   plugin registry (register, resolve, plugins)

  sim/             the Lab
    engine.py      seeded discrete event queue, logical clock, layer wiring
    api.py         TownAPI: the only door between an agent and the world
    agents.py      reference role state machines
    scenario.py    ScenarioSpec, YAML loading, bundled scenarios
    scenarios/     six bundled YAML scenarios
    validators.py  per-scenario stage checks computed from events alone
    runner.py      run_lab: engine, redaction, evaluation, bundle

  db.py            the Track's durable truth: SQLite mailbox with leases,
                   fencing tokens, idempotent accept, event log
  coordinator.py   FastAPI app over db.py plus coordinator-side faults
  client.py        participant HTTP client with safe 503 retries
  participants/    stock buyer and seller subprocess agents with journals
  profiles.py      the five Track profiles (the boring quote)
  runner.py        run_town: coordinator subprocess, participants,
                   crash restart, evaluation, bundle
  evaluator.py     the Track stage evaluator

  bundle.py        write, load, verify evidence bundles (both modes)
  report.py        the System Fitness Report renderer
  replay.py        step-through event replay
  visualizer.py    single-file HTML replay with the town map
  campaign.py      precommitted multi-trial campaigns with distributions
  skills/          SkillMD parsing, validation, bundled skills
  cli.py           the one command
```

## The evidence pipeline

Both modes end the same way: a bundle directory holding the five
records (profile, run, intents, events, result) plus a manifest of
hashes and a rendered report. The evaluator or validator judges from
the exported events alone, so `verify` can recompute every hash and
replay the judgment. In the Lab, privacy redaction runs before
evaluation, so the recorded result is reproducible from public records
by construction.

## Determinism rules (Lab)

No wall clock and no unseeded randomness inside a run. Time is logical.
The event queue orders by (time, insertion sequence). Iteration is over
lists and sorted views, never bare sets or unsorted dicts, wherever
order reaches the trace. The only nondeterministic value in a Lab
bundle is the run id.

## Trust boundaries (Track)

The coordinator owns coordination facts and never holds participant
credentials. Participants own their own state directories and journals.
Runner observations (crash, restart, exit codes) are posted as events
attributed to the runner. Model-facing tools are join, discover,
notify, claim, send, ack, inspect; run creation and fault plans are
admin-only.

## Extending the town

- New layer plugin: `@register("payments", "yourledger.v1")` on a class
  taking the engine, then name it in a scenario under `layers:`.
- New scenario: a YAML file with agents, roles, faults, seed; run it by
  path, and add a validator under `sim/validators.py` with
  `@validator("your-name")` for stage verdicts.
- New role: `@role("your-role")` on a SimAgent subclass in
  `sim/agents.py`.
- Your own agent on the Track: speak the coordinator HTTP contract
  (`nandatown coordinator`); the schemas under `schemas/` define every
  shared record.
