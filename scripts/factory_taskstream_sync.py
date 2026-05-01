#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys

import factory_integrator_core as core


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preview Factory Taskstream status sync.")
    parser.add_argument("run_dir")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = core.taskstream_sync_preview(core.resolve_run_dir(args.run_dir))
    except core.FactoryIntegratorError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else core.rel(core.resolve_run_dir(args.run_dir) / "integration" / "taskstream-sync-preview.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
