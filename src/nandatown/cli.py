"""The nandatown command: bring, connect, attempt, disrupt, inspect, improve.

One command interface for the whole town: deterministic Lab scenarios,
real-agent Track profiles, campaigns, evidence bundles, reports,
verification, replay, visualization, skills, layers, and the standalone
coordinator for bringing your own agent.
"""

from __future__ import annotations

import argparse
import sys

from . import __version__


def _is_lab(name: str) -> bool:
    from .sim.scenario import bundled_scenarios
    return (name in bundled_scenarios()
            or name.endswith((".yaml", ".yml")))


def cmd_run(args: argparse.Namespace) -> int:
    from .bundle import load_bundle
    from .profiles import PROFILES
    from .report import render_report

    name = args.name
    if name in PROFILES:
        from .runner import run_town
        print(f"nandatown {__version__}: Track run of {name}"
              " (real subprocess agents)")
        bundle_dir, result = run_town(name, args.out)
    elif _is_lab(name):
        from .sim.runner import run_lab
        print(f"nandatown {__version__}: Lab run of {name}"
              " (deterministic, no model, no tokens)")
        bundle_dir, result = run_lab(name, args.out, seed=args.seed)
    else:
        from .sim.scenario import bundled_scenarios
        print(f"unknown target {name!r}")
        print(f"lab scenarios:  {', '.join(sorted(bundled_scenarios()))}")
        print(f"track profiles: {', '.join(sorted(PROFILES))}")
        return 2
    print(render_report(load_bundle(bundle_dir)))
    print(f"Evidence bundle: {bundle_dir}")
    return 0 if result.verdict == "passed" else 1


def cmd_scenarios(_args: argparse.Namespace) -> int:
    from .sim.scenario import bundled_scenarios

    entries = bundled_scenarios()
    width = max(len(n) for n in entries)
    print("Lab scenarios (deterministic, run with: nandatown run <name>):")
    for name, description in entries.items():
        print(f"  {name.ljust(width)}  {description}")
    return 0


def cmd_profiles(_args: argparse.Namespace) -> int:
    from .profiles import DEFAULT_PROFILE, FAULT_DESCRIPTIONS, PROFILES

    width = max(len(n) for n in PROFILES)
    print("Track profiles (real subprocess agents over HTTP):")
    for name in PROFILES:
        marker = " (default)" if name == DEFAULT_PROFILE else ""
        print(f"  {name.ljust(width)}  {FAULT_DESCRIPTIONS[name]}{marker}")
    return 0


def cmd_layers(_args: argparse.Namespace) -> int:
    from .layers import DEFAULT_PLUGINS, plugins

    print("The twelve protocol layers and their registered plugins:")
    for layer, entries in plugins().items():
        print(f"  {layer}")
        for entry in entries:
            default = (" (default)"
                       if entry["plugin_id"] == DEFAULT_PLUGINS[layer]
                       else "")
            print(f"    {entry['plugin_id']}{default}  {entry['summary']}")
    print()
    print("A scenario swaps any plugin under its layers: mapping;"
          " register your own with @register(layer, plugin_id).")
    return 0


def cmd_skills(args: argparse.Namespace) -> int:
    from .skills import builtin_skills, skill_source, validate_skill

    if args.validate:
        with open(args.validate) as f:
            problems = validate_skill(f.read())
        if not problems:
            print(f"{args.validate}: valid SkillMD")
            return 0
        for p in problems:
            print(f"problem: {p}")
        return 1
    if args.name:
        print(skill_source(args.name), end="")
        return 0
    skills = builtin_skills()
    width = max(len(n) for n in skills)
    print("Registered SkillMDs (show one with: nandatown skills <name>):")
    for name, skill in skills.items():
        print(f"  {name.ljust(width)}  v{skill.version}  {skill.summary}")
    return 0


def cmd_campaign(args: argparse.Namespace) -> int:
    from .campaign import run_campaign

    campaign_dir, aggregate = run_campaign(args.name, args.trials, args.out,
                                           seed_base=args.seed_base)
    with open(f"{campaign_dir}/campaign-report.md") as f:
        print(f.read())
    print(f"Campaign bundle: {campaign_dir}")
    failed = aggregate["verdicts"].get("failed", 0) \
        + aggregate["verdicts"].get("error", 0)
    return 0 if failed == 0 else 1


def cmd_report(args: argparse.Namespace) -> int:
    from .bundle import load_bundle
    from .report import render_report

    print(render_report(load_bundle(args.bundle_dir)))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    from .bundle import verify_bundle

    problems = verify_bundle(args.bundle_dir)
    if not problems:
        print("bundle verified: hashes match and the evaluator reproduces"
              " the recorded result")
        return 0
    for p in problems:
        print(f"problem: {p}")
    return 1


def cmd_replay(args: argparse.Namespace) -> int:
    from .bundle import load_bundle
    from .replay import render_replay

    print(render_replay(load_bundle(args.bundle_dir), start=args.start,
                        limit=args.limit, kind=args.kind))
    return 0


def cmd_visualize(args: argparse.Namespace) -> int:
    import os

    from .bundle import load_bundle
    from .visualizer import write_visualizer

    bundle = load_bundle(args.bundle_dir)
    out = args.output or os.path.join(args.bundle_dir, "town.html")
    write_visualizer(bundle, out)
    print(f"visualizer written to {out}")
    print("open it in a browser: agents on the map, messages on the"
          " timeline, the report alongside")
    return 0


def cmd_schemas(args: argparse.Namespace) -> int:
    from .schemas import export_schemas

    for path in export_schemas(args.out):
        print(f"wrote {path}")
    return 0


def cmd_coordinator(args: argparse.Namespace) -> int:
    import os
    import secrets

    import uvicorn

    from .coordinator import build_app

    admin_token = os.environ.get("TOWN_ADMIN_TOKEN") or secrets.token_hex(16)
    print(f"coordinator on http://{args.host}:{args.port}")
    print(f"admin token: {admin_token}")
    print("bring your own agent: create a run with POST /runs, join with"
          " the returned tokens; see README for the contract")
    app = build_app(args.db, admin_token=admin_token)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="nandatown",
        description="The open proving ground for the Internet of AI"
                    " agents. Bring an agent, give it a task, break"
                    " something on purpose, leave with evidence.",
    )
    parser.add_argument("--version", action="version",
                        version=f"nandatown {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run a Lab scenario or Track"
                                       " profile and print the report")
    p_run.add_argument("name", nargs="?", default="quote-crash-restart",
                       help="scenario name, profile name, or a scenario"
                            " YAML path")
    p_run.add_argument("--seed", type=int, default=None,
                       help="override the Lab scenario seed")
    p_run.add_argument("--out", default="runs",
                       help="directory for evidence bundles")
    p_run.set_defaults(func=cmd_run)

    sub.add_parser("scenarios",
                   help="list Lab scenarios").set_defaults(func=cmd_scenarios)
    sub.add_parser("profiles",
                   help="list Track profiles").set_defaults(func=cmd_profiles)
    sub.add_parser("layers",
                   help="list the twelve layers and their"
                        " plugins").set_defaults(func=cmd_layers)

    p_skills = sub.add_parser("skills", help="list, show, or validate"
                                             " SkillMDs")
    p_skills.add_argument("name", nargs="?", default=None)
    p_skills.add_argument("--validate", metavar="PATH", default=None)
    p_skills.set_defaults(func=cmd_skills)

    p_campaign = sub.add_parser(
        "campaign", help="run a precommitted campaign and report the"
                         " distribution")
    p_campaign.add_argument("name")
    p_campaign.add_argument("--trials", type=int, default=10)
    p_campaign.add_argument("--seed-base", type=int, default=1000)
    p_campaign.add_argument("--out", default="runs")
    p_campaign.set_defaults(func=cmd_campaign)

    p_report = sub.add_parser("report", help="render a bundle's report")
    p_report.add_argument("bundle_dir")
    p_report.set_defaults(func=cmd_report)

    p_verify = sub.add_parser("verify",
                              help="check a bundle's integrity and replay"
                                   " the evaluator")
    p_verify.add_argument("bundle_dir")
    p_verify.set_defaults(func=cmd_verify)

    p_replay = sub.add_parser("replay", help="step through a bundle's"
                                             " events")
    p_replay.add_argument("bundle_dir")
    p_replay.add_argument("--start", type=int, default=0)
    p_replay.add_argument("--limit", type=int, default=None)
    p_replay.add_argument("--kind", default=None)
    p_replay.set_defaults(func=cmd_replay)

    p_vis = sub.add_parser("visualize", help="write the HTML visualizer"
                                             " for a bundle")
    p_vis.add_argument("bundle_dir")
    p_vis.add_argument("-o", "--output", default=None)
    p_vis.set_defaults(func=cmd_visualize)

    p_schemas = sub.add_parser("schemas", help="export the shared JSON"
                                               " Schemas")
    p_schemas.add_argument("--out", default="schemas")
    p_schemas.set_defaults(func=cmd_schemas)

    p_coord = sub.add_parser("coordinator",
                             help="run a standalone coordinator for your"
                                  " own agent")
    p_coord.add_argument("--host", default="127.0.0.1")
    p_coord.add_argument("--port", type=int, default=8477)
    p_coord.add_argument("--db", default="town.db")
    p_coord.set_defaults(func=cmd_coordinator)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
