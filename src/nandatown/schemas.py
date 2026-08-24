"""Export the shared concepts as language-neutral JSON Schemas.

The five shared concepts (the run plan, the agent message, the town
event, the exact release reference, and the evidence record) let
independent implementations check their messages without sharing any
code. Python is only the first implementation; it is not the protocol.
"""

from __future__ import annotations

import json
import os

from .records import (
    AgentMessage,
    EvidenceRecord,
    EvidenceResult,
    ReleaseRef,
    TestProfile,
    TownEvent,
)

SHARED_CONCEPTS = {
    "run_plan": TestProfile,
    "agent_message": AgentMessage,
    "town_event": TownEvent,
    "release_ref": ReleaseRef,
    "evidence_record": EvidenceRecord,
}

EXTRA_CONCEPTS = {
    "evidence_result": EvidenceResult,
}


def export_schemas(out_dir: str) -> list[str]:
    from .sim.scenario import ScenarioSpec

    os.makedirs(out_dir, exist_ok=True)
    written = []
    everything = dict(SHARED_CONCEPTS)
    everything.update(EXTRA_CONCEPTS)
    everything["scenario"] = ScenarioSpec
    for name, model in everything.items():
        schema = model.model_json_schema()
        schema["$id"] = f"https://nandatown.local/schemas/{name}.schema.json"
        path = os.path.join(out_dir, f"{name}.schema.json")
        with open(path, "w") as f:
            json.dump(schema, f, indent=2, sort_keys=True)
            f.write("\n")
        written.append(path)
    return written
