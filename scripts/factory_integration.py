#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys

import factory_dispatch_core as core


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Factory integration dry-run checks.")
    sub = parser.add_subparsers(dest="command", required=True)
    dry_run = sub.add_parser("dry-run", help="Create integration dry-run artifacts.")
    dry_run.add_argument("run_dir")
    dry_run.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = core.integration_dry_run(core.resolve_run_dir(args.run_dir))
    except core.FactoryDispatchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else core.rel(core.resolve_run_dir(args.run_dir) / "integration" / "integration-plan.json"))
    return 0 if payload["decision"] != "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
