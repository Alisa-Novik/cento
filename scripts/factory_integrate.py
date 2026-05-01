#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys

import factory_integrator_core as core


def command_plan(args: argparse.Namespace) -> int:
    payload = core.create_apply_plan(core.resolve_run_dir(args.run_dir))
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else core.rel(core.resolve_run_dir(args.run_dir) / "integration" / "apply-plan.json"))
    return 0


def command_prepare(args: argparse.Namespace) -> int:
    payload = core.prepare_branch(
        core.resolve_run_dir(args.run_dir),
        branch=args.branch,
        worktree=args.worktree or None,
        dry_run=args.dry_run,
    )
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else core.rel(core.resolve_run_dir(args.run_dir) / "integration" / "integration-branch.json"))
    return 0 if payload["status"] != "failed" else 1


def command_apply(args: argparse.Namespace) -> int:
    payload = core.apply_patches(
        core.resolve_run_dir(args.run_dir),
        worktree=args.worktree or None,
        branch=args.branch,
        limit=args.limit,
        validate_each=args.validate_each,
    )
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else core.rel(core.resolve_run_dir(args.run_dir) / "integration" / "integration-state.json"))
    return 0 if not payload.get("rejected") else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare and apply Factory integration patches.")
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("run_dir")
    plan.add_argument("--json", action="store_true")
    plan.set_defaults(func=command_plan)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("run_dir")
    prepare.add_argument("--branch", default="")
    prepare.add_argument("--worktree", default="")
    prepare.add_argument("--dry-run", action="store_true")
    prepare.add_argument("--json", action="store_true")
    prepare.set_defaults(func=command_prepare)
    apply = sub.add_parser("apply")
    apply.add_argument("run_dir")
    apply.add_argument("--branch", default="")
    apply.add_argument("--worktree", default="")
    apply.add_argument("--limit", type=int, default=0)
    apply.add_argument("--validate-each", action="store_true")
    apply.add_argument("--json", action="store_true")
    apply.set_defaults(func=command_apply)
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except core.FactoryIntegratorError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
