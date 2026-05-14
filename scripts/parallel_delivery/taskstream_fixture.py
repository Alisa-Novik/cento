#!/usr/bin/env python3
"""Write deterministic Patch Swarm Taskstream handoff fixture input."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import parallel_delivery_taskstream as taskstream  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a deterministic Patch Swarm taskstream handoff fixture split plan.")
    parser.add_argument("--out", required=True, help="Fixture run directory.")
    parser.add_argument("--base-commit", required=True, help="Base commit to record in split-plan.json.")
    parser.add_argument("--timestamp", default=taskstream.DEFAULT_TIMESTAMP)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out_dir = taskstream.resolve_root_path(args.out)
    split_plan = taskstream.build_fixture_split_plan(out_dir, base_commit=args.base_commit, timestamp=args.timestamp)
    print(f"split_plan: {taskstream.rel(split_plan)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
