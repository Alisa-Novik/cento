#!/usr/bin/env python3
"""Append-only spend ledger helpers for Cento API and run accounting."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "cento.spend_ledger.entry.v1"

PRICE_BOOK: dict[str, dict[str, float]] = {
    "gpt-5.4-pro": {
        "input_token": 30.0 / 1_000_000,
        "output_token": 180.0 / 1_000_000,
    },
    "gpt-image-1": {
        "input_text_token": 5.0 / 1_000_000,
        "input_image_token": 10.0 / 1_000_000,
        "output_image_token": 40.0 / 1_000_000,
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return rows
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def write_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")


def stable_record_id(payload: dict[str, Any]) -> str:
    base = json.dumps(
        {
            "run_id": payload.get("run_id"),
            "lane": payload.get("lane"),
            "category": payload.get("category"),
            "model": payload.get("model"),
            "response_id": payload.get("response_id"),
            "status": payload.get("status"),
            "written_at": payload.get("written_at"),
        },
        sort_keys=True,
    )
    return "spend-" + hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def response_id_from_payload(payload: dict[str, Any]) -> str:
    for key in ("id", "response_id"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    response = payload.get("response")
    if isinstance(response, dict):
        return response_id_from_payload(response)
    return ""


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def token_usage(usage: dict[str, Any]) -> dict[str, int]:
    input_details = usage.get("input_tokens_details") if isinstance(usage.get("input_tokens_details"), dict) else {}
    output_details = usage.get("output_tokens_details") if isinstance(usage.get("output_tokens_details"), dict) else {}
    image_details = usage.get("image_tokens_details") if isinstance(usage.get("image_tokens_details"), dict) else {}
    return {
        "input_tokens": int(_number(usage.get("input_tokens"))),
        "output_tokens": int(_number(usage.get("output_tokens"))),
        "total_tokens": int(_number(usage.get("total_tokens"))),
        "input_text_tokens": int(_number(usage.get("input_text_tokens") or input_details.get("text_tokens") or usage.get("text_tokens"))),
        "input_image_tokens": int(_number(usage.get("input_image_tokens") or input_details.get("image_tokens") or image_details.get("input_tokens"))),
        "output_image_tokens": int(_number(usage.get("output_image_tokens") or output_details.get("image_tokens") or image_details.get("output_tokens"))),
    }


def estimate_cost_usd(model: str, category: str, usage: dict[str, Any]) -> tuple[float, str, dict[str, int]]:
    tokens = token_usage(usage)
    pricing = PRICE_BOOK.get(model)
    if not pricing:
        return 0.0, "unknown-pricing", tokens
    if not usage:
        return 0.0, "no-usage", tokens

    if category == "image":
        text_tokens = tokens["input_text_tokens"] or tokens["input_tokens"]
        image_input_tokens = tokens["input_image_tokens"]
        output_image_tokens = tokens["output_image_tokens"] or tokens["output_tokens"]
        cost = (
            text_tokens * pricing.get("input_text_token", 0.0)
            + image_input_tokens * pricing.get("input_image_token", 0.0)
            + output_image_tokens * pricing.get("output_image_token", 0.0)
        )
        return round(cost, 8), "estimated", tokens

    input_tokens = tokens["input_tokens"]
    output_tokens = tokens["output_tokens"]
    if input_tokens == 0 and output_tokens == 0 and tokens["total_tokens"]:
        return 0.0, "unknown-token-split", tokens
    cost = input_tokens * pricing.get("input_token", 0.0) + output_tokens * pricing.get("output_token", 0.0)
    return round(cost, 8), "estimated", tokens


def build_api_record(
    *,
    run_id: str,
    lane: str,
    category: str,
    model: str,
    status: str,
    usage: dict[str, Any] | None = None,
    response_id: str = "",
    response: dict[str, Any] | None = None,
    artifact: str = "",
    note: str = "",
    cost_usd: float | None = None,
    cost_accuracy: str = "",
) -> dict[str, Any]:
    usage_payload = usage if isinstance(usage, dict) else {}
    if not response_id and isinstance(response, dict):
        response_id = response_id_from_payload(response)
    estimate, estimated_accuracy, tokens = estimate_cost_usd(model, category, usage_payload)
    if cost_usd is None:
        cost_usd = estimate
    if not cost_accuracy:
        cost_accuracy = estimated_accuracy
    dedupe_key = f"openai:{response_id}" if response_id else ""
    record = {
        "schema_version": SCHEMA_VERSION,
        "written_at": now_iso(),
        "run_id": run_id,
        "lane": lane,
        "category": category,
        "provider": "openai",
        "model": model,
        "status": status,
        "response_id": response_id,
        "dedupe_key": dedupe_key,
        "usage": usage_payload,
        "normalized_tokens": tokens,
        "pricing": PRICE_BOOK.get(model, {}),
        "cost_usd": round(float(cost_usd), 8),
        "cost_accuracy": cost_accuracy,
        "billable": status not in {"skipped", "started"},
        "artifact": artifact,
        "note": note,
    }
    record["record_id"] = stable_record_id(record)
    return record


def build_factory_record(*, run_id: str, status: str, cost_usd: float = 0.0, note: str = "", artifact: str = "") -> dict[str, Any]:
    record = {
        "schema_version": SCHEMA_VERSION,
        "written_at": now_iso(),
        "run_id": run_id,
        "lane": "factory",
        "category": "factory",
        "provider": "local",
        "model": "",
        "status": status,
        "response_id": "",
        "dedupe_key": "",
        "usage": {},
        "normalized_tokens": {},
        "pricing": {},
        "cost_usd": round(float(cost_usd), 8),
        "cost_accuracy": "exact-zero" if cost_usd == 0 else "operator-supplied",
        "billable": bool(cost_usd),
        "artifact": artifact,
        "note": note,
    }
    record["record_id"] = stable_record_id(record)
    return record


def build_dashboard_delta_record(*, run_id: str, delta_usd: float, note: str = "") -> dict[str, Any]:
    record = {
        "schema_version": SCHEMA_VERSION,
        "written_at": now_iso(),
        "run_id": run_id,
        "lane": "dashboard",
        "category": "dashboard_delta",
        "provider": "openai",
        "model": "",
        "status": "unattributed",
        "response_id": "",
        "dedupe_key": "",
        "usage": {},
        "normalized_tokens": {},
        "pricing": {},
        "cost_usd": round(float(delta_usd), 8),
        "cost_accuracy": "dashboard-delta",
        "billable": True,
        "artifact": "",
        "note": note,
    }
    record["record_id"] = stable_record_id(record)
    return record


def build_dashboard_total_record(*, run_id: str, total_usd: float, note: str = "") -> dict[str, Any]:
    record = {
        "schema_version": SCHEMA_VERSION,
        "written_at": now_iso(),
        "run_id": run_id,
        "lane": "dashboard",
        "category": "dashboard_total_baseline",
        "provider": "openai",
        "model": "",
        "status": "baseline",
        "response_id": "",
        "dedupe_key": f"dashboard-total-baseline:{run_id}",
        "usage": {},
        "normalized_tokens": {},
        "pricing": {},
        "cost_usd": round(float(total_usd), 8),
        "cost_accuracy": "dashboard-total-snapshot",
        "billable": True,
        "artifact": "",
        "note": note,
    }
    record["record_id"] = stable_record_id(record)
    return record


def append_record(path: Path, record: dict[str, Any], *, dedupe: bool = True) -> dict[str, Any]:
    payload = dict(record)
    dedupe_key = str(payload.get("dedupe_key") or "")
    if dedupe and dedupe_key:
        for existing in read_jsonl(path):
            if str(existing.get("dedupe_key") or "") == dedupe_key and not existing.get("duplicate_of"):
                payload["duplicate_of"] = existing.get("record_id") or dedupe_key
                payload["billable"] = False
                payload["cost_usd"] = 0.0
                payload["cost_accuracy"] = "duplicate-response-id"
                payload["record_id"] = stable_record_id(payload)
                break
    write_jsonl(path, payload)
    return payload


def append_records(paths: list[Path], record: dict[str, Any]) -> list[dict[str, Any]]:
    return [append_record(path, record) for path in paths]


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    counted: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    for record in records:
        dedupe_key = str(record.get("dedupe_key") or "")
        if dedupe_key and dedupe_key in seen:
            duplicates.append(record)
            continue
        if dedupe_key:
            seen.add(dedupe_key)
        if record.get("duplicate_of"):
            duplicates.append(record)
            continue
        counted.append(record)

    by_category: dict[str, float] = {}
    unknown: list[dict[str, Any]] = []
    for record in counted:
        category = str(record.get("category") or "unknown")
        cost = float(record.get("cost_usd") or 0.0)
        by_category[category] = round(by_category.get(category, 0.0) + cost, 8)
        if str(record.get("cost_accuracy") or "").startswith("unknown"):
            unknown.append(record)

    api_categories = {"pro", "image", "api"}
    return {
        "schema_version": "cento.spend_ledger.summary.v1",
        "generated_at": now_iso(),
        "record_count": len(records),
        "counted_record_count": len(counted),
        "duplicate_count": len(duplicates),
        "response_id_count": len(seen),
        "total_cost_usd": round(sum(float(item.get("cost_usd") or 0.0) for item in counted), 8),
        "factory_cost_usd": round(by_category.get("factory", 0.0), 8),
        "api_cost_usd": round(sum(by_category.get(category, 0.0) for category in api_categories), 8),
        "pro_cost_usd": round(by_category.get("pro", 0.0), 8),
        "image_cost_usd": round(by_category.get("image", 0.0), 8),
        "dashboard_total_baseline_usd": round(by_category.get("dashboard_total_baseline", 0.0), 8),
        "unattributed_dashboard_delta_usd": round(by_category.get("dashboard_delta", 0.0), 8),
        "by_category": by_category,
        "unknown_record_count": len(unknown),
    }


def summarize_paths(paths: list[Path]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for path in paths:
        records.extend(read_jsonl(path))
    return summarize_records(records)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize Cento spend ledger JSONL files.")
    parser.add_argument("ledger", nargs="+", help="Ledger JSONL path(s).")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    summary = summarize_paths([Path(item) for item in args.ledger])
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"total_cost_usd: {summary['total_cost_usd']:.8f}")
        print(f"factory_cost_usd: {summary['factory_cost_usd']:.8f}")
        print(f"api_cost_usd: {summary['api_cost_usd']:.8f}")
        print(f"unattributed_dashboard_delta_usd: {summary['unattributed_dashboard_delta_usd']:.8f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
