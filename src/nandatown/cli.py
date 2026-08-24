"""The nandatown command: bring, connect, attempt, disrupt, inspect, improve.

One command for the user. Everything else in the package serves it.
"""

from __future__ import annotations

import argparse
import sys

from . import __version__


def cmd_run(args: argparse.Namespace) -> int:
    from .bundle import load_bundle
    from .report import render_report
    from .runner import run_town

    print(f"nandatown {__version__}: running profile {args.profile}")
    bundle_dir, result = run_town(args.profile, args.out)
    print(render_report(load_bundle(bundle_dir)))
    print(f"Evidence bundle: {bundle_dir}")
    return 0 if result.verdict == "passed" else 1


def cmd_profiles(_args: argparse.Namespace) -> int:
    from .profiles import DEFAULT_PROFILE, FAULT_DESCRIPTIONS, PROFILES

    width = max(len(n) for n in PROFILES)
    for name in PROFILES:
        marker = " (default)" if name == DEFAULT_PROFILE else ""
        print(f"{name.ljust(width)}  {FAULT_DESCRIPTIONS[name]}{marker}")
    return 0


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


def cmd_coordinator(args: argparse.Namespace) -> int:
    import os
    import secrets

    import uvicorn

    from .coordinator import build_app

    admin_token = os.environ.get("TOWN_ADMIN_TOKEN") or secrets.token_hex(16)
    print(f"coordinator on http://{args.host}:{args.port}")
    print(f"admin token: {admin_token}")
    print("bring your own agent: join tokens come from POST /runs;"
          " see the README for the HTTP contract")
    app = build_app(args.db, admin_token=admin_token)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


def main(argv: list[str] | None = None) -> int:
    from .profiles import DEFAULT_PROFILE, PROFILES

    parser = argparse.ArgumentParser(
        prog="nandatown",
        description="Local-first NANDA Town sandbox and test harness."
                    " Bring an agent, give it a task, break something on"
                    " purpose, leave with evidence.",
    )
    parser.add_argument("--version", action="version",
                        version=f"nandatown {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run one profile and print the report")
    p_run.add_argument("--profile", default=DEFAULT_PROFILE,
                       choices=sorted(PROFILES))
    p_run.add_argument("--out", default="runs",
                       help="directory for evidence bundles")
    p_run.set_defaults(func=cmd_run)

    p_profiles = sub.add_parser("profiles", help="list built-in profiles")
    p_profiles.set_defaults(func=cmd_profiles)

    p_report = sub.add_parser("report", help="render a bundle's report")
    p_report.add_argument("bundle_dir")
    p_report.set_defaults(func=cmd_report)

    p_verify = sub.add_parser("verify",
                              help="check a bundle's integrity and replay"
                                   " the evaluator")
    p_verify.add_argument("bundle_dir")
    p_verify.set_defaults(func=cmd_verify)

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
