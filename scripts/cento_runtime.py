#!/usr/bin/env python3
"""Inspect Cento local worker runtime profiles."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cento_build  # noqa: E402


def profile_summary(name: str, profile: dict[str, Any]) -> dict[str, Any]:
    validation = cento_build.validate_runtime_profile(name, profile)
    runtime_type = str(profile.get("type") or "")
    executable = None
    executable_available = None
    if runtime_type == "command":
        argv = profile.get("argv")
        if isinstance(argv, list) and argv:
            executable = str(argv[0])
            executable_available = shutil.which(executable) is not None
    return {
        "name": name,
        "type": runtime_type or None,
        "status": validation["status"],
        "timeout_seconds": profile.get("timeout_seconds"),
        "max_changed_files": profile.get("max_changed_files"),
        "max_patch_lines": profile.get("max_patch_lines"),
        "executable": executable,
        "executable_available": executable_available,
        "errors": validation["errors"],
        "warnings": validation["warnings"],
    }


def command_list(args: argparse.Namespace) -> int:
    try:
        profiles = cento_build.load_runtime_profiles()
    except cento_build.BuildError as exc:
        print(f"cento runtime list: {exc}", file=sys.stderr)
        return 1
    payload = {"profiles": [profile_summary(name, profiles[name]) for name in sorted(profiles)]}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        if not payload["profiles"]:
            print("No runtime profiles configured.")
            return 0
        for item in payload["profiles"]:
            executable = ""
            if item["executable"]:
                availability = "available" if item["executable_available"] else "missing"
                executable = f" executable={item['executable']}({availability})"
            print(f"{item['name']:<18} {item['type']:<8} {item['status']}{executable}")
    return 0


def command_check(args: argparse.Namespace) -> int:
    try:
        profiles = cento_build.load_runtime_profiles()
    except cento_build.BuildError as exc:
        print(f"cento runtime check: {exc}", file=sys.stderr)
        return 1
    if args.name not in profiles:
        print(f"cento runtime check: runtime profile not found: {args.name}", file=sys.stderr)
        return 1
    summary = profile_summary(args.name, profiles[args.name])
    errors = [str(item) for item in summary["errors"]]
    warnings = [str(item) for item in summary["warnings"]]
    if args.require_executable and summary["executable"] and not summary["executable_available"]:
        errors.append(f"runtime executable not found on PATH: {summary['executable']}")
    if summary["executable"] and not summary["executable_available"]:
        warnings.append(f"runtime executable not found on PATH: {summary['executable']}")
    status = "passed" if not errors else "failed"
    payload = {**summary, "status": status, "errors": errors, "warnings": warnings, "profile_path": cento_build.rel(cento_build.RUNTIMES_PATH)}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"runtime check {args.name}: {status}")
        if payload["executable"]:
            availability = "available" if payload["executable_available"] else "missing"
            print(f"executable: {payload['executable']} ({availability})")
        for warning in warnings:
            print(f"warning: {warning}", file=sys.stderr)
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
    return 0 if status == "passed" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cento runtime", description="Inspect local builder runtime profiles.")
    sub = parser.add_subparsers(dest="command", required=True)

    list_cmd = sub.add_parser("list", help="List runtime profiles from .cento/runtimes.yaml.")
    list_cmd.add_argument("--json", action="store_true", help="Print JSON result.")
    list_cmd.set_defaults(func=command_list)

    check = sub.add_parser("check", help="Validate one runtime profile.")
    check.add_argument("name", help="Runtime profile name.")
    check.add_argument("--json", action="store_true", help="Print JSON result.")
    check.add_argument("--require-executable", action="store_true", help="Fail when a command runtime executable is missing.")
    check.set_defaults(func=command_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
