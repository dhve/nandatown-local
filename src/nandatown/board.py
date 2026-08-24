"""The local leaderboard: what has been proven on this machine.

Scans a runs directory for evidence bundles and shows, per profile or
scenario, how many runs exist and how many passed. Rankings derive from
evidence bundles anyone can verify; the board is a view, never a
record.
"""

from __future__ import annotations

import json
import os
from typing import Any


def scan_bundles(directory: str) -> list[dict[str, Any]]:
    rows = []
    if not os.path.isdir(directory):
        return rows
    for entry in sorted(os.listdir(directory)):
        bundle_dir = os.path.join(directory, entry)
        manifest_path = os.path.join(bundle_dir, "manifest.json")
        run_path = os.path.join(bundle_dir, "run.json")
        result_path = os.path.join(bundle_dir, "result.json")
        if not (os.path.exists(manifest_path)
                and os.path.exists(run_path)
                and os.path.exists(result_path)):
            continue
        with open(manifest_path) as f:
            manifest = json.load(f)
        with open(run_path) as f:
            run = json.load(f)
        with open(result_path) as f:
            result = json.load(f)
        rows.append({
            "run_id": run["run_id"],
            "profile": run["profile_name"],
            "mode": manifest.get("mode", "track"),
            "verdict": result["verdict"],
            "at": manifest.get("created_at", 0.0),
        })
    return rows


def render_board(directory: str) -> str:
    rows = scan_bundles(directory)
    if not rows:
        return (f"no evidence bundles under {directory}; run one with:"
                " nandatown run\n")
    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        g = groups.setdefault(row["profile"],
                              {"mode": row["mode"], "runs": 0,
                               "passed": 0, "last_verdict": "",
                               "last_at": 0.0})
        g["runs"] += 1
        g["passed"] += row["verdict"] == "passed"
        if row["at"] >= g["last_at"]:
            g["last_at"] = row["at"]
            g["last_verdict"] = row["verdict"]
    width = max(len(name) for name in groups)
    lines = [f"Town board over {directory} ({len(rows)} bundles)",
             "=" * 40]
    ranked = sorted(groups.items(),
                    key=lambda kv: (-kv[1]["passed"] / kv[1]["runs"],
                                    kv[0]))
    for name, g in ranked:
        rate = 100.0 * g["passed"] / g["runs"]
        lines.append(f"{name.ljust(width)}  {g['mode']:<5}"
                     f" {g['passed']}/{g['runs']} passed"
                     f" ({rate:5.1f}%), last {g['last_verdict']}")
    lines.append("")
    lines.append("Every line is backed by a verifiable bundle:"
                 " nandatown verify <dir>. The board is a view, not a"
                 " record.")
    return "\n".join(lines) + "\n"
