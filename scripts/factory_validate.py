#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys

import factory_dispatch_core as core


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aggregate Factory dispatch validation evidence.")
    parser.add_argument("run_dir")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = core.validation_summary(core.resolve_run_dir(args.run_dir))
    except core.FactoryDispatchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else core.rel(core.resolve_run_dir(args.run_dir) / "evidence" / "validation-summary.json"))
    return 0 if payload["decision"] == "approve" else 1


if __name__ == "__main__":
    raise SystemExit(main())
