#!/usr/bin/env python3
"""Write the Parallel Delivery release-candidate fixture inputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import parallel_delivery_release_candidate as rc  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create deterministic safe-apply release-candidate fixture inputs.")
    parser.add_argument("--out", required=True)
    parser.add_argument("--base-commit", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    payload = rc.build_release_candidate_fixture(Path(args.out), base_commit=rc.resolve_expected_base_commit(args.base_commit) or args.base_commit)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(payload["run_dir"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
