#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import factory_autopilot_policy as policy


ROOT = Path(__file__).resolve().parents[1]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def scan(backlogs: dict[str, int], *, queued: int = 3, safety: bool = True) -> dict[str, Any]:
    return {
        "schema_version": "factory-autopilot-scan/v1",
        "run_id": "policy-matrix",
        "factory_state": {
            "plan_exists": True,
            "task_count": 10,
            "materialized_tasks": 10,
            "queue_exists": True,
            "queue_errors": [],
            "queue_counts": {"queued": queued, "total": 10},
        },
        "backlogs": {
            "unvalidated_patch": backlogs.get("unvalidated_patch", 0),
            "validated_patch": backlogs.get("validated_patch", 0),
            "validation": backlogs.get("validation", 0),
            "integration": backlogs.get("integration", 0),
            "blocked": backlogs.get("blocked", 0),
            "ready_to_dispatch": queued,
        },
        "fanout_gate": {"storage_pressure": "low", "dry_run_allowed": True, "should_hold_live_fanout": False},
        "safety_gates": {"passed": safety, "reasons": [] if safety else ["agent_manager_critical"]},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Factory Autopilot policy decision matrix.")
    parser.add_argument("--out", default="workspace/runs/factory/factory-autopilot-policy-matrix-e2e")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    out = ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out)
    pol = policy.default_policy(5)
    cases = [
        ("dispatch-ready-clean", scan({}), {}, "dispatch_dry_run"),
        ("unvalidated-patches", scan({"unvalidated_patch": 2}), {}, "validate"),
        ("validated-patches", scan({"validated_patch": 2}), {}, "integrate_dry_run"),
        ("validation-backlog", scan({"validation": 3}), {}, "validate"),
        ("integration-backlog", scan({"integration": 3}), {}, "integrate_dry_run"),
        ("safety-hold", scan({}, safety=False), {}, "hold"),
        ("no-progress-stop", scan({}), {"no_progress_cycles": 2}, "stop"),
    ]
    results = []
    for name, scan_payload, state, expected in cases:
        decision = policy.decide(scan_payload, {"cycles_completed": 0, **state}, pol)
        results.append({"name": name, "expected": expected, "actual": decision["action"], "passed": decision["action"] == expected, "reasons": decision.get("reasons", [])})
    summary = {
        "schema_version": "factory-autopilot-policy-matrix-e2e/v1",
        "decision": "approve" if all(item["passed"] for item in results) else "blocked",
        "cases": results,
        "ai_calls_used": 0,
        "estimated_cost_usd": 0,
        "generated_at": now_iso(),
    }
    write_json(out / "policy-matrix-summary.json", summary)
    (out / "policy-matrix-summary.md").write_text(
        "\n".join(
            [
                "# Factory Autopilot Policy Matrix E2E",
                "",
                f"- Decision: `{summary['decision']}`",
                "- AI calls used: 0",
                "",
                "## Cases",
                "",
                *[f"- {'PASS' if item['passed'] else 'FAIL'} `{item['name']}` expected `{item['expected']}` actual `{item['actual']}`" for item in results],
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True) if args.json else f"summary: {rel(out / 'policy-matrix-summary.md')}")
    return 0 if summary["decision"] == "approve" else 1


if __name__ == "__main__":
    raise SystemExit(main())
