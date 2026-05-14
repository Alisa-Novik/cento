#!/usr/bin/env python3
"""Write deterministic Patch Swarm patch bundle fixture inputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import parallel_delivery_patch_bundles as patch_bundles  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write Patch Swarm patch bundle fixture inputs.")
    parser.add_argument("--out", required=True, help="Fixture run directory.")
    parser.add_argument("--base-commit", required=True, help="Base commit to record in fixture manifests.")
    parser.add_argument("--run-id", default="patch-bundle-fixture")
    args = parser.parse_args(argv)

    payload = patch_bundles.build_fixture_inputs(Path(args.out), base_commit=args.base_commit, run_id=args.run_id)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
