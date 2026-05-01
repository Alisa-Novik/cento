#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys

import factory_integrator_core as core


def command_plan(args: argparse.Namespace) -> int:
    payload = core.rollback_plan(core.resolve_run_dir(args.run_dir))
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else core.rel(core.resolve_run_dir(args.run_dir) / "integration" / "rollback-plan.json"))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Factory integration rollback metadata.")
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("run_dir")
    plan.add_argument("--json", action="store_true")
    plan.set_defaults(func=command_plan)
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except core.FactoryIntegratorError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
