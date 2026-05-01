#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import factory_dispatch_core as core


def command_collect(args: argparse.Namespace) -> int:
    run_dir = core.resolve_run_dir(args.run_dir)
    payload = core.collect_patches(run_dir)
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else core.rel(run_dir / "patch-collection-summary.json"))
    return 0


def command_validate(args: argparse.Namespace) -> int:
    path = Path(args.patch_json)
    if not path.is_absolute():
        path = core.ROOT / path
    errors = core.validate_patch_json(path)
    result = {
        "schema_version": "factory-patch-validation/v1",
        "patch": core.rel(path),
        "valid": not errors,
        "errors": errors,
    }
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else ("valid" if not errors else "\n".join(errors)))
    return 0 if not errors else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect and validate Factory patch bundles.")
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("collect", help="Collect patch bundles for a Factory run.")
    collect.add_argument("run_dir")
    collect.add_argument("--json", action="store_true")
    collect.set_defaults(func=command_collect)
    validate = sub.add_parser("validate", help="Validate patch.json.")
    validate.add_argument("patch_json")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=command_validate)
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except core.FactoryDispatchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
