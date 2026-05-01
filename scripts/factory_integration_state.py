#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import factory_integrator_core as core


def command_validate(args: argparse.Namespace) -> int:
    path = Path(args.integration_state)
    if not path.is_absolute():
        path = core.ROOT / path
    errors = core.validate_integration_state(path)
    payload = {
        "schema_version": "factory-integration-state-validation/v1",
        "integration_state": core.rel(path),
        "valid": not errors,
        "errors": errors,
    }
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else ("valid" if not errors else "\n".join(errors)))
    return 0 if not errors else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Factory integration-state.json.")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("integration_state")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=command_validate)
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except core.FactoryIntegratorError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
