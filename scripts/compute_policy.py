#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_PATH = ROOT / ".cento" / "compute-policy.json"
DEFAULT_RUNTIME_REGISTRY_PATH = ROOT / "data" / "agent-runtimes.json"
SCHEMA_VERSION = "cento.compute_policy.v1"

PRESETS: dict[str, dict[str, int]] = {
    "codex-first": {"codex": 85, "claude": 15, "openai_api": 0},
    "agent-preferred": {"codex": 55, "claude": 20, "openai_api": 25},
    "balanced": {"codex": 50, "claude": 30, "openai_api": 20},
    "claude-first": {"codex": 20, "claude": 80, "openai_api": 0},
    "api-minimal": {"codex": 70, "claude": 30, "openai_api": 0},
    "api-assisted": {"codex": 50, "claude": 25, "openai_api": 25},
}

AGENT_PREFERENCE_POLICY = {
    "codex_claude_utilization_threshold_percent": 30,
    "eligible_work_agent_preference_percent_range": [70, 80],
    "eligible_work_agent_preference_target_percent": 75,
    "metered_openai_api_reserved_for": [
        "structured Responses API work",
        "image generation",
        "ProReq planning",
        "other API-only behavior",
    ],
    "notes": "When Codex/Claude weekly utilization is above 30% and capacity remains usable, prefer agent lanes for roughly 70-80% of eligible non-API-only work.",
}

DEFAULT_POLICY = {
    "schema_version": SCHEMA_VERSION,
    "profile": "codex-first",
    "providers": {
        "codex": {
            "share": 85,
            "kind": "agent",
            "runtime": "codex",
            "model": "gpt-5.3-codex-spark",
            "cost_mode": "subscription_or_limit",
            "enabled": True,
            "notes": "Prefer Codex when interactive/agent limit is available.",
        },
        "claude": {
            "share": 15,
            "kind": "agent",
            "runtime": "claude-code",
            "model": "claude-sonnet-4-6",
            "cost_mode": "subscription_or_limit",
            "enabled": True,
            "notes": "Fallback for agent work when Codex is unavailable or weighted routing selects it.",
        },
        "openai_api": {
            "share": 0,
            "kind": "api",
            "runtime": "api-openai",
            "model": "${CENTO_OPENAI_WORKER_MODEL}",
            "cost_mode": "metered",
            "enabled": False,
            "notes": "Use only when a pipeline explicitly needs API-only behavior such as structured Responses or image generation.",
        },
    },
    "agent_preference_policy": AGENT_PREFERENCE_POLICY,
}


class PolicyError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def policy_path() -> Path:
    return Path(os.environ.get("CENTO_COMPUTE_POLICY_PATH", DEFAULT_POLICY_PATH)).expanduser()


def runtime_registry_path() -> Path:
    return Path(os.environ.get("CENTO_AGENT_RUNTIME_CONFIG", DEFAULT_RUNTIME_REGISTRY_PATH)).expanduser()


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(payload, dict):
        raise PolicyError(f"JSON root must be an object: {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def validate_share(name: str, value: int) -> int:
    if value < 0 or value > 100:
        raise PolicyError(f"{name} share must be between 0 and 100")
    return value


def build_policy(*, profile: str, codex: int, claude: int, openai_api: int) -> dict[str, Any]:
    codex = validate_share("codex", codex)
    claude = validate_share("claude", claude)
    openai_api = validate_share("openai_api", openai_api)
    if codex + claude <= 0:
        raise PolicyError("at least one agent runtime share is required: codex + claude must be > 0")
    policy = json.loads(json.dumps(DEFAULT_POLICY))
    policy["profile"] = profile
    policy["updated_at"] = now_iso()
    policy["providers"]["codex"]["share"] = codex
    policy["providers"]["codex"]["enabled"] = codex > 0
    policy["providers"]["claude"]["share"] = claude
    policy["providers"]["claude"]["enabled"] = claude > 0
    policy["providers"]["openai_api"]["share"] = openai_api
    policy["providers"]["openai_api"]["enabled"] = openai_api > 0
    policy["agent_runtime_weights"] = {
        "codex": codex,
        "claude-code": claude,
    }
    policy["metered_api_policy"] = {
        "openai_api_share": openai_api,
        "prefer_agent_when_possible": openai_api < max(codex, claude),
        "requires_explicit_api_runtime": True,
        "agent_preference_policy": AGENT_PREFERENCE_POLICY,
    }
    policy["agent_preference_policy"] = AGENT_PREFERENCE_POLICY
    return policy


def load_policy() -> dict[str, Any]:
    payload = read_json(policy_path())
    if not payload:
        return json.loads(json.dumps(DEFAULT_POLICY))
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise PolicyError(f"Unsupported compute policy schema: {payload.get('schema_version')}")
    return payload


def runtime_entry_updates(policy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    providers = policy.get("providers") if isinstance(policy.get("providers"), dict) else {}
    codex = providers.get("codex") if isinstance(providers.get("codex"), dict) else {}
    claude = providers.get("claude") if isinstance(providers.get("claude"), dict) else {}
    return {
        "codex": {
            "weight": int(codex.get("share") or 0),
            "preferred": int(codex.get("share") or 0) >= int(claude.get("share") or 0),
            "model": str(codex.get("model") or "gpt-5.3-codex-spark"),
            "budget_note": f"Compute policy `{policy.get('profile')}` assigns Codex share {int(codex.get('share') or 0)}.",
        },
        "claude-code": {
            "weight": int(claude.get("share") or 0),
            "preferred": int(claude.get("share") or 0) > int(codex.get("share") or 0),
            "model": str(claude.get("model") or "claude-sonnet-4-6"),
            "budget_note": f"Compute policy `{policy.get('profile')}` assigns Claude share {int(claude.get('share') or 0)}.",
        },
    }


def apply_policy(policy: dict[str, Any]) -> dict[str, Any]:
    path = runtime_registry_path()
    registry = read_json(path)
    if not registry:
        registry = {"routing": "weighted", "runtimes": []}
    runtimes = registry.get("runtimes")
    if not isinstance(runtimes, list):
        raise PolicyError(f"Runtime registry must include a runtimes list: {path}")
    updates = runtime_entry_updates(policy)
    seen: set[str] = set()
    for entry in runtimes:
        if not isinstance(entry, dict):
            continue
        runtime_id = str(entry.get("id") or "")
        if runtime_id not in updates:
            continue
        seen.add(runtime_id)
        entry.update(updates[runtime_id])
        if not entry.get("agent"):
            entry["agent"] = "codex" if runtime_id == "codex" else "claude-code"
    for runtime_id, update in updates.items():
        if runtime_id in seen:
            continue
        runtimes.append(
            {
                "id": runtime_id,
                "display_name": "Codex" if runtime_id == "codex" else "Claude Code",
                "provider": "openai" if runtime_id == "codex" else "anthropic",
                "agent": "codex" if runtime_id == "codex" else "claude-code",
                "command_env": "CENTO_CODEX_BIN" if runtime_id == "codex" else "CENTO_CLAUDE_BIN",
                "default_binary": "codex" if runtime_id == "codex" else "claude",
                **update,
            }
        )
    registry["routing"] = "weighted"
    registry["compute_policy"] = {
        "schema_version": SCHEMA_VERSION,
        "profile": policy.get("profile"),
        "policy_path": str(policy_path()),
        "applied_at": now_iso(),
        "openai_api_share": policy.get("providers", {}).get("openai_api", {}).get("share", 0),
    }
    write_json(path, registry)
    return registry


def summarize(policy: dict[str, Any], registry: dict[str, Any] | None = None) -> dict[str, Any]:
    providers = policy.get("providers") if isinstance(policy.get("providers"), dict) else {}
    runtime_weights = {}
    if registry:
        for entry in registry.get("runtimes", []):
            if isinstance(entry, dict):
                runtime_weights[str(entry.get("id") or "")] = int(entry.get("weight") or 0)
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_path": str(policy_path()),
        "runtime_registry_path": str(runtime_registry_path()),
        "profile": policy.get("profile", ""),
        "provider_shares": {key: int(value.get("share") or 0) for key, value in providers.items() if isinstance(value, dict)},
        "runtime_weights": runtime_weights,
        "openai_api_enabled": bool(providers.get("openai_api", {}).get("enabled")) if isinstance(providers.get("openai_api"), dict) else False,
        "agent_preference_policy": policy.get("agent_preference_policy", AGENT_PREFERENCE_POLICY),
        "recommendation": "Use agent-work auto routing for agent tasks; use api-openai only when the command explicitly requires API-only structured or image behavior.",
    }


def print_payload(payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=False))
        return
    print(f"profile: {payload.get('profile', '')}")
    print(f"policy: {payload.get('policy_path', '')}")
    print(f"runtime registry: {payload.get('runtime_registry_path', '')}")
    print("provider shares:")
    for key, value in payload.get("provider_shares", {}).items():
        print(f"- {key}: {value}")
    if payload.get("runtime_weights"):
        print("runtime weights:")
        for key, value in payload.get("runtime_weights", {}).items():
            print(f"- {key}: {value}")
    preference = payload.get("agent_preference_policy") if isinstance(payload.get("agent_preference_policy"), dict) else {}
    if preference:
        print(
            "agent preference: "
            f"{preference.get('eligible_work_agent_preference_target_percent')}% when utilization >= "
            f"{preference.get('codex_claude_utilization_threshold_percent')}%"
        )
    print(f"openai api enabled: {payload.get('openai_api_enabled')}")


def command_show(args: argparse.Namespace) -> int:
    policy = load_policy()
    registry = read_json(runtime_registry_path())
    print_payload(summarize(policy, registry), as_json=args.json)
    return 0


def command_set(args: argparse.Namespace) -> int:
    policy = build_policy(profile=args.profile, codex=args.codex, claude=args.claude, openai_api=args.openai_api)
    registry = read_json(runtime_registry_path())
    if not args.dry_run:
        write_json(policy_path(), policy)
        registry = apply_policy(policy)
    payload = summarize(policy, registry)
    payload["dry_run"] = bool(args.dry_run)
    print_payload(payload, as_json=args.json)
    return 0


def command_preset(args: argparse.Namespace) -> int:
    shares = PRESETS[args.name]
    args.profile = args.name
    args.codex = shares["codex"]
    args.claude = shares["claude"]
    args.openai_api = shares["openai_api"]
    return command_set(args)


def command_apply(args: argparse.Namespace) -> int:
    policy = load_policy()
    registry = apply_policy(policy) if not args.dry_run else read_json(runtime_registry_path())
    payload = summarize(policy, registry)
    payload["dry_run"] = bool(args.dry_run)
    print_payload(payload, as_json=args.json)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage Cento compute provider shares for Codex, Claude, and metered OpenAI API use.")
    sub = parser.add_subparsers(dest="command", required=True)

    show = sub.add_parser("show", help="Show the active compute policy and runtime weights.")
    show.add_argument("--json", action="store_true")
    show.set_defaults(func=command_show)

    preset = sub.add_parser("preset", help="Apply a named provider-share preset.")
    preset.add_argument("name", choices=sorted(PRESETS))
    preset.add_argument("--dry-run", action="store_true")
    preset.add_argument("--json", action="store_true")
    preset.set_defaults(func=command_preset)

    set_cmd = sub.add_parser("set", help="Set exact provider shares.")
    set_cmd.add_argument("--profile", default="custom")
    set_cmd.add_argument("--codex", type=int, required=True)
    set_cmd.add_argument("--claude", type=int, required=True)
    set_cmd.add_argument("--openai-api", type=int, required=True, dest="openai_api")
    set_cmd.add_argument("--dry-run", action="store_true")
    set_cmd.add_argument("--json", action="store_true")
    set_cmd.set_defaults(func=command_set)

    apply_cmd = sub.add_parser("apply", help="Reapply the saved compute policy to the Agent Work runtime registry.")
    apply_cmd.add_argument("--dry-run", action="store_true")
    apply_cmd.add_argument("--json", action="store_true")
    apply_cmd.set_defaults(func=command_apply)

    args = parser.parse_args()
    try:
        return int(args.func(args))
    except PolicyError as exc:
        parser.exit(2, f"[ERROR] {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
