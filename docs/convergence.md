# Convergence with "Test the Path, Not Just the Protocol"

The proposal's question is the product: can this exact agent, service,
or protocol implementation complete this exact NANDA journey, and if
not, where did it break? This build answers it. The table maps the
proposal's components to shipped modules; every row is tested.

| Proposal component | Shipped as |
|---|---|
| Town CLI | `cli.py`: one command for local runs and CI, the same machine result rendered for humans |
| Profile loader | `path_profiles.py` (exact versioned, frozen, fingerprinted path profiles), `profiles.py` (Track), `sim/scenario.py` (Lab) |
| Orchestrator | `path_runner.py` (path runs), `runner.py` (Track: isolated subprocesses, restarts), `sim/engine.py` (Lab) |
| Resolvers | direct endpoints and pinned local index files with resolution hops recorded (`path_runner._resolve`); discovery never becomes trust |
| Protocol drivers | native A2A (`a2a_adapter.py`), MCP (`mcp_adapter.py`), HTTP mailbox (`client.py`); upstream conformance results stay theirs |
| Evaluator | `path_runner.evaluate_path`, `evaluator.py`, `sim/validators.py`: stage results from observations, never blaming the subject for a Town defect |
| Evidence writer | `bundle.py`: exact manifest, private artifacts under state/, attestation, offline verification |
| Reporters | `report.py` (terminal and markdown), `visualizer.py` (web view), JSON records throughout |

## Result semantics, as specified

PASS, FAIL, NOT TESTED, INCONCLUSIVE, and ERROR each mean one thing
(`records.StageStatus`, rendered in `report.py`). If resolution fails,
later checks are not tested. If Town emits an invalid request or its
driver breaks, the run is an ERROR, not an agent failure
(`test_town_driver_fault_is_an_error_not_a_failure`). Missing evidence
never becomes a pass. Every failing report names the first broken
stage and carries a rerun command.

## The first real-agent experience, as proposed

```
nandatown test-agent --url http://127.0.0.1:9999 --profile a2a-capability-fulfillment@0.1
```

The starter workflow is the proposal's: a synthetic two-widget order
with a run nonce, exactly one terminal fulfillment expected, and the
controlled condition delivering the same logical order twice. All five
starter cases are demonstrated against the reference A2A seller and
its planted defects (`a2a serve --defect wrong_total |
duplicate_fulfillment | card_drift`): healthy, missing card pointer,
card mismatch naming both digests, valid protocol with the wrong
result, and the duplicate-fulfillment idempotency defect.

## Evidence stays separate from decisions

The run envelope (run.json) carries the subject locator, release
basis, descriptor digests, resolution hops, and the rerun command.
Atomic observations (events.jsonl) are one observer, one subject, one
fact, one time window. Receipts (`receipt.py`) are sanitized signed
derivatives; nothing private leaves the bundle. Town Proof
(`nandatown proof`) renders the TOWN-TESTED sentence only from
conclusive, covered, fresh, verified evidence, and says exactly why
not otherwise. Optional public anchoring through ERC-8004 rides the
existing portable-identity resolvers and stays outside the standard
path.

## Boundaries kept explicit

- Listed or discoverable does not mean installed, authorized, running,
  safe, or endorsed.
- An AgentCard is a declaration; a Town result is an observation.
- Liveness (Town Pulse) does not prove capability fulfillment and
  never refreshes a semantic result.
- A favorable result grants no permission to spend funds, use secrets,
  or invoke tools.
- A score or badge is a policy view over evidence, not the evidence
  itself.

## The three proofs

- Proof 1, bring one real agent: shipped and tested
  (`tests/test_path.py`): stage-separated result, evidence bundle,
  report, rerun command, non-author reproducible.
- Proof 2, two real runtimes: shipped as the Track
  (`tests/test_e2e.py`, `tests/test_llm_and_byoa.py`): isolated
  runtimes across a durable local network boundary, restart, duplicate
  delivery, lost acknowledgement, compatible traces against the
  deterministic Lab.
- Proof 3, one pinned end-to-end NANDA path: shipped
  (`test_index_resolution_and_missing_pointer`,
  `test_card_mismatch_names_both_digests_and_halts`): pinned index and
  card versions, and missing pointers, descriptor mismatch, and wrong
  semantic results attributed as different stages.

What remains organizational rather than technical, exactly as the
proposal's immediate actions list says: naming a maintainer reviewer
and an external agent developer, choosing the first evidence consumer,
and treating a public Town Proof pilot as an explicit later opt-in.
