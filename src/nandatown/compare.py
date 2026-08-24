"""Protocol comparison: same agents, same scenario, different rules.

The article's promise, executable: a researcher tests a new reputation
algorithm without rebuilding the marketplace, a startup compares
payment protocols using the same agents and scenarios, a standards
group compares competing protocols through repeatable experiments.
One command runs the identical scenario under each variant and puts
the stage verdicts side by side, each side backed by its own
verifiable bundle.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any


def run_comparison(target: str, swaps: dict[str, str], out_dir: str,
                   seed: int | None = None,
                   plugins: list[str] | None = None
                   ) -> tuple[str, dict[str, Any]]:
    from .sim.runner import run_lab

    compare_id = "cmp-" + uuid.uuid4().hex[:10]
    compare_dir = os.path.join(out_dir, compare_id)
    os.makedirs(compare_dir, exist_ok=True)

    variants = {
        "baseline": {},
        "swapped": swaps,
    }
    results: dict[str, dict[str, Any]] = {}
    for label, overrides in variants.items():
        bundle_dir, result = run_lab(target, compare_dir, seed=seed,
                                     plugins=plugins,
                                     layer_overrides=overrides or None)
        results[label] = {
            "run_id": result.run_id,
            "bundle": os.path.basename(bundle_dir),
            "verdict": result.verdict,
            "stages": {s.name: s.status for s in result.stages},
            "overrides": overrides,
        }

    baseline_stages = results["baseline"]["stages"]
    swapped_stages = results["swapped"]["stages"]
    differences = sorted(
        name for name in set(baseline_stages) | set(swapped_stages)
        if baseline_stages.get(name) != swapped_stages.get(name))
    comparison = {
        "compare_id": compare_id,
        "target": target,
        "swaps": swaps,
        "seed": seed,
        "variants": results,
        "differences": differences,
        "compared_at": time.time(),
    }
    with open(os.path.join(compare_dir, "comparison.json"), "w") as f:
        json.dump(comparison, f, indent=2)
    with open(os.path.join(compare_dir, "comparison.md"), "w") as f:
        f.write(render_comparison(comparison))
    return compare_dir, comparison


def render_comparison(comparison: dict[str, Any]) -> str:
    lines: list[str] = []
    add = lines.append
    add("NANDA Town Protocol Comparison")
    add("=" * 40)
    add(f"Scenario:  {comparison['target']}")
    swaps = ", ".join(f"{k}: {v}" for k, v in comparison["swaps"].items())
    add(f"Swapped:   {swaps}")
    add("Same agents, same scenario, same seed; only the rules differ.")
    add("")
    baseline = comparison["variants"]["baseline"]
    swapped = comparison["variants"]["swapped"]
    add(f"Verdict:   baseline {baseline['verdict'].upper()},"
        f" swapped {swapped['verdict'].upper()}")
    add("")
    names = sorted(set(baseline["stages"]) | set(swapped["stages"]))
    width = max(len(n) for n in names)
    add(f"  {'stage'.ljust(width)}  {'baseline':<22} swapped")
    for name in names:
        b = baseline["stages"].get(name, "absent")
        s = swapped["stages"].get(name, "absent")
        marker = "  <- differs" if b != s else ""
        add(f"  {name.ljust(width)}  {b:<22} {s}{marker}")
    add("")
    if comparison["differences"]:
        add("The swap changed: " + ", ".join(comparison["differences"])
            + ".")
    else:
        add("The swap changed no stage verdict under this scenario and"
            " seed.")
    add("Each column is backed by its own verifiable bundle in this"
        " directory.")
    return "\n".join(lines) + "\n"
