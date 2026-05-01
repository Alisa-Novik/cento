#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import factory_dispatch_core as core


def command_validate(args: argparse.Namespace) -> int:
    path = Path(args.queue_json)
    if not path.is_absolute():
        path = core.ROOT / path
    payload = core.read_json(path)
    run_dir = path.parents[1] if path.parent.name == "queue" else None
    errors = core.validate_queue_payload(payload, run_dir)
    result = {
        "schema_version": "factory-queue-validation/v1",
        "queue": core.rel(path),
        "valid": not errors,
        "errors": errors,
    }
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else ("valid" if not errors else "\n".join(errors)))
    return 0 if not errors else 1


def command_generate(args: argparse.Namespace) -> int:
    run_dir = core.resolve_run_dir(args.run_dir)
    payload = core.generate_queue(run_dir)
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else core.rel(run_dir / "queue" / "queue.json"))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate or generate Factory queue artifacts.")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="Validate queue.json.")
    validate.add_argument("queue_json")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=command_validate)
    generate = sub.add_parser("generate", help="Generate queue artifacts for a Factory run.")
    generate.add_argument("run_dir")
    generate.add_argument("--json", action="store_true")
    generate.set_defaults(func=command_generate)
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except core.FactoryDispatchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
