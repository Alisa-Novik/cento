#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT_DIR / "workspace" / "runs" / "funnel"
DOCS_PATH = ROOT_DIR / "docs" / "funnel.md"
DEFAULT_DATA_DIR = Path(os.environ.get("CENTO_FUNNEL_HOME", Path.home() / ".local" / "share" / "cento" / "funnel"))
DATA_FILE = Path(os.environ.get("CENTO_FUNNEL_DATA", DEFAULT_DATA_DIR / "state.json"))


class FunnelError(Exception):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify(value: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    slug = "-".join(part for part in slug.split("-") if part)
    if not slug:
        raise FunnelError("Slug value cannot be empty.")
    return slug


def seed_state() -> dict[str, Any]:
    created = now_iso()
    return {
        "schema_version": 1,
        "created_at": created,
        "updated_at": created,
        "sources": [
            {
                "id": "linkedin-posts",
                "name": "LinkedIn Posts",
                "channel": "linkedin",
                "owner": "cento",
                "status": "active",
                "intent": "Convert career-consulting content into advisory conversations.",
                "default_funnel": "career-consulting-discovery",
                "utm": {"source": "linkedin", "medium": "organic", "campaign": "career-consulting"},
            },
            {
                "id": "telegram-referrals",
                "name": "Telegram Referrals",
                "channel": "telegram",
                "owner": "cento",
                "status": "active",
                "intent": "Capture warm referrals from Telegram communities and direct messages.",
                "default_funnel": "career-consulting-discovery",
                "utm": {"source": "telegram", "medium": "referral", "campaign": "career-consulting"},
            },
            {
                "id": "github-profile",
                "name": "GitHub Profile",
                "channel": "github",
                "owner": "cento",
                "status": "watching",
                "intent": "Turn technical credibility into consulting or automation conversations.",
                "default_funnel": "automation-advisory",
                "utm": {"source": "github", "medium": "profile", "campaign": "automation-advisory"},
            },
        ],
        "funnels": [
            {
                "id": "career-consulting-discovery",
                "name": "Career Consulting Discovery",
                "offer_id": "career-strategy-sprint",
                "sources": ["linkedin-posts", "telegram-referrals"],
                "stages": [
                    {"id": "captured", "name": "Captured", "goal": "Lead exists with source and intent."},
                    {"id": "qualified", "name": "Qualified", "goal": "Fit, urgency, and budget are understood."},
                    {"id": "conversation", "name": "Conversation", "goal": "Discovery call or async consult is started."},
                    {"id": "proposal", "name": "Proposal", "goal": "Offer and next step are sent."},
                    {"id": "won", "name": "Won", "goal": "Payment or signed commitment is complete."},
                ],
            },
            {
                "id": "automation-advisory",
                "name": "Automation Advisory",
                "offer_id": "automation-diagnostic",
                "sources": ["github-profile"],
                "stages": [
                    {"id": "captured", "name": "Captured", "goal": "Inbound or observed signal is logged."},
                    {"id": "triaged", "name": "Triaged", "goal": "Business workflow pain is identified."},
                    {"id": "conversation", "name": "Conversation", "goal": "Technical advisory conversation is active."},
                    {"id": "next-action", "name": "Next Action", "goal": "Pilot, audit, or referral is assigned."},
                ],
            },
        ],
        "leads": [
            {
                "id": "ada-lovelace-linkedin",
                "name": "Ada Lovelace",
                "source_id": "linkedin-posts",
                "funnel_id": "career-consulting-discovery",
                "stage_id": "qualified",
                "status": "open",
                "value_estimate": 2500,
                "notes": "Interested in product leadership positioning and interview prep.",
                "next_action": "Send discovery questions and schedule a short consult.",
                "created_at": created,
                "updated_at": created,
            }
        ],
        "events": [
            {
                "id": f"{created}-seed",
                "type": "lead_created",
                "source_id": "linkedin-posts",
                "funnel_id": "career-consulting-discovery",
                "lead_id": "ada-lovelace-linkedin",
                "note": "Seed career-consulting lead created during funnel init.",
                "value": 0,
                "created_at": created,
            }
        ],
        "offers": [
            {
                "id": "career-strategy-sprint",
                "name": "Career Strategy Sprint",
                "price_range": "$1,500-$3,000",
                "promise": "Clarify positioning, improve assets, and create an execution plan.",
            },
            {
                "id": "automation-diagnostic",
                "name": "Automation Diagnostic",
                "price_range": "$750-$2,500",
                "promise": "Map a business workflow and identify high-leverage automation steps.",
            },
        ],
        "actions": [
            {
                "id": "follow-up-qualified-leads",
                "name": "Follow up with qualified open leads",
                "cadence": "daily",
                "query": {"status": "open", "stage_id": "qualified"},
            }
        ],
    }


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_state(required: bool = True) -> dict[str, Any]:
    if not DATA_FILE.exists():
        if required:
            raise FunnelError(f"No funnel state found at {DATA_FILE}. Run `cento funnel init` first.")
        return seed_state()
    try:
        payload = json.loads(DATA_FILE.read_text())
    except json.JSONDecodeError as exc:
        raise FunnelError(f"Invalid funnel JSON at {DATA_FILE}: {exc}") from exc
    validate_state(payload)
    return payload


def write_state(state: dict[str, Any]) -> None:
    state["updated_at"] = now_iso()
    validate_state(state)
    ensure_parent(DATA_FILE)
    DATA_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def validate_unique(items: list[dict[str, Any]], key: str, label: str) -> None:
    seen: set[str] = set()
    for item in items:
        value = str(item.get(key, ""))
        if not value:
            raise FunnelError(f"{label} item is missing required `{key}`.")
        if value in seen:
            raise FunnelError(f"Duplicate {label} id: {value}")
        seen.add(value)


def validate_state(state: dict[str, Any]) -> None:
    for collection in ("sources", "funnels", "leads", "events", "offers", "actions"):
        if not isinstance(state.get(collection), list):
            raise FunnelError(f"Funnel state must contain a `{collection}` list.")
        validate_unique(state[collection], "id", collection)

    source_ids = {item["id"] for item in state["sources"]}
    funnel_ids = {item["id"] for item in state["funnels"]}
    lead_ids = {item["id"] for item in state["leads"]}
    offer_ids = {item["id"] for item in state["offers"]}

    for funnel in state["funnels"]:
        if funnel.get("offer_id") and funnel["offer_id"] not in offer_ids:
            raise FunnelError(f"Funnel {funnel['id']} references unknown offer {funnel['offer_id']}.")
        for source_id in funnel.get("sources", []):
            if source_id not in source_ids:
                raise FunnelError(f"Funnel {funnel['id']} references unknown source {source_id}.")

    for lead in state["leads"]:
        if lead.get("source_id") not in source_ids:
            raise FunnelError(f"Lead {lead['id']} references unknown source {lead.get('source_id')}.")
        if lead.get("funnel_id") not in funnel_ids:
            raise FunnelError(f"Lead {lead['id']} references unknown funnel {lead.get('funnel_id')}.")

    for event in state["events"]:
        if event.get("source_id") and event["source_id"] not in source_ids:
            raise FunnelError(f"Event {event['id']} references unknown source {event['source_id']}.")
        if event.get("funnel_id") and event["funnel_id"] not in funnel_ids:
            raise FunnelError(f"Event {event['id']} references unknown funnel {event['funnel_id']}.")
        if event.get("lead_id") and event["lead_id"] not in lead_ids:
            raise FunnelError(f"Event {event['id']} references unknown lead {event['lead_id']}.")


def print_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> None:
    if not rows:
        print("No records.")
        return
    widths = {key: len(title) for key, title in columns}
    for row in rows:
        for key, _title in columns:
            widths[key] = max(widths[key], len(str(row.get(key, ""))))
    print("  ".join(title.ljust(widths[key]) for key, title in columns))
    print("  ".join("-" * widths[key] for key, _title in columns))
    for row in rows:
        print("  ".join(str(row.get(key, "")).ljust(widths[key]) for key, _title in columns))


def latest_run_path(name: str, suffix: str) -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    return RUNS_DIR / f"{datetime.now().astimezone().strftime('%Y%m%d-%H%M%S')}-{name}.{suffix}"


def command_init(args: argparse.Namespace) -> int:
    state = seed_state()
    if DATA_FILE.exists() and not args.force:
        read_state(required=True)
        print(f"Funnel state already exists: {DATA_FILE}")
        print("Use `cento funnel init --force` to replace it.")
        return 0
    write_state(state)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"initialized: {DATA_FILE}")
    print(f"runs_dir: {RUNS_DIR}")
    return 0


def command_show(_args: argparse.Namespace) -> int:
    state = read_state()
    print(f"data: {DATA_FILE}")
    print(f"runs: {RUNS_DIR}")
    print(f"sources: {len(state['sources'])}")
    print(f"funnels: {len(state['funnels'])}")
    print(f"leads: {len(state['leads'])}")
    print(f"events: {len(state['events'])}")
    return 0


def command_sources(_args: argparse.Namespace) -> int:
    state = read_state()
    print_table(state["sources"], [("id", "ID"), ("channel", "Channel"), ("status", "Status"), ("default_funnel", "Default Funnel")])
    return 0


def command_funnels(_args: argparse.Namespace) -> int:
    state = read_state()
    rows = []
    for funnel in state["funnels"]:
        rows.append(
            {
                "id": funnel["id"],
                "offer_id": funnel.get("offer_id", ""),
                "sources": ",".join(funnel.get("sources", [])),
                "stages": len(funnel.get("stages", [])),
            }
        )
    print_table(rows, [("id", "ID"), ("offer_id", "Offer"), ("sources", "Sources"), ("stages", "Stages")])
    return 0


def command_leads(_args: argparse.Namespace) -> int:
    state = read_state()
    print_table(
        state["leads"],
        [("id", "ID"), ("name", "Name"), ("source_id", "Source"), ("funnel_id", "Funnel"), ("stage_id", "Stage"), ("next_action", "Next Action")],
    )
    return 0


def command_events(_args: argparse.Namespace) -> int:
    state = read_state()
    print_table(
        state["events"],
        [("created_at", "Created"), ("type", "Type"), ("source_id", "Source"), ("lead_id", "Lead"), ("value", "Value"), ("note", "Note")],
    )
    return 0


def command_event(args: argparse.Namespace) -> int:
    state = read_state()
    source_ids = {source["id"] for source in state["sources"]}
    funnel_ids = {funnel["id"] for funnel in state["funnels"]}
    lead_ids = {lead["id"] for lead in state["leads"]}

    if args.source and args.source not in source_ids:
        raise FunnelError(f"Unknown source `{args.source}`. Run `cento funnel sources`.")
    if args.funnel and args.funnel not in funnel_ids:
        raise FunnelError(f"Unknown funnel `{args.funnel}`. Run `cento funnel funnels`.")
    if args.lead and args.lead not in lead_ids:
        raise FunnelError(f"Unknown lead `{args.lead}`. Run `cento funnel leads`.")

    created = now_iso()
    existing_event_ids = {event["id"] for event in state["events"]}
    base_event_id = f"{created}-{slugify(args.type)}"
    event_id = base_event_id
    suffix = 2
    while event_id in existing_event_ids:
        event_id = f"{base_event_id}-{suffix}"
        suffix += 1
    event = {
        "id": event_id,
        "type": args.type,
        "source_id": args.source,
        "funnel_id": args.funnel,
        "lead_id": args.lead,
        "note": args.note or "",
        "value": args.value,
        "created_at": created,
    }
    state["events"].append(event)
    write_state(state)
    print(f"event_added: {event['id']}")
    return 0


def command_report(args: argparse.Namespace) -> int:
    state = read_state()
    by_source: dict[str, dict[str, Any]] = {
        source["id"]: {"source": source["id"], "leads": 0, "events": 0, "value": 0} for source in state["sources"]
    }
    for lead in state["leads"]:
        by_source.setdefault(lead["source_id"], {"source": lead["source_id"], "leads": 0, "events": 0, "value": 0})
        by_source[lead["source_id"]]["leads"] += 1
    for event in state["events"]:
        source_id = event.get("source_id") or "unknown"
        by_source.setdefault(source_id, {"source": source_id, "leads": 0, "events": 0, "value": 0})
        by_source[source_id]["events"] += 1
        by_source[source_id]["value"] += event.get("value") or 0

    lines = ["# Cento Funnel Report", "", f"- generated_at: `{now_iso()}`", f"- data: `{DATA_FILE}`", ""]
    lines.extend(["## Source Summary", "", "| Source | Leads | Events | Value |", "|---|---:|---:|---:|"])
    for row in sorted(by_source.values(), key=lambda item: item["source"]):
        lines.append(f"| `{row['source']}` | {row['leads']} | {row['events']} | {row['value']} |")
    lines.extend(["", "## Open Leads", ""])
    for lead in state["leads"]:
        if lead.get("status") == "open":
            lines.append(f"- `{lead['id']}` {lead.get('name', '')}: {lead.get('next_action', '')}")

    report = "\n".join(lines).rstrip() + "\n"
    output = Path(args.output) if args.output else latest_run_path("report", "md")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report)
    print(output)
    if not args.quiet:
        print(report.rstrip())
    return 0


def command_docs(_args: argparse.Namespace) -> int:
    if not DOCS_PATH.exists():
        raise FunnelError(f"Funnel docs missing: {DOCS_PATH}")
    print(DOCS_PATH.read_text().rstrip())
    return 0


def command_paths(_args: argparse.Namespace) -> int:
    print(f"data: {DATA_FILE}")
    print(f"runs: {RUNS_DIR}")
    print(f"docs: {DOCS_PATH}")
    return 0


def command_validate(_args: argparse.Namespace) -> int:
    read_state(required=True)
    print(f"valid: {DATA_FILE}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage local Cento Funnel sources, leads, events, and reports.")
    subparsers = parser.add_subparsers(dest="command")

    init = subparsers.add_parser("init", help="Create starter funnel data.")
    init.add_argument("--force", action="store_true", help="Replace existing funnel state.")
    init.set_defaults(func=command_init)

    for name, func, help_text in (
        ("show", command_show, "Show funnel state counts and paths."),
        ("sources", command_sources, "List traffic sources."),
        ("funnels", command_funnels, "List funnels and stages."),
        ("leads", command_leads, "List tracked leads."),
        ("events", command_events, "List tracked events."),
        ("docs", command_docs, "Print funnel documentation."),
        ("paths", command_paths, "Print data, run, and docs paths."),
        ("validate", command_validate, "Validate the local funnel JSON state."),
    ):
        subparser = subparsers.add_parser(name, help=help_text)
        subparser.set_defaults(func=func)

    event = subparsers.add_parser("event", help="Append a funnel event.")
    event.add_argument("type", help="Event type, for example lead_created, conversation_started, revenue_won.")
    event.add_argument("--source", help="Source id.")
    event.add_argument("--funnel", help="Funnel id.")
    event.add_argument("--lead", help="Lead id.")
    event.add_argument("--note", help="Short event note.")
    event.add_argument("--value", type=float, default=0, help="Optional numeric value.")
    event.set_defaults(func=command_event)

    report = subparsers.add_parser("report", help="Generate a Markdown funnel report under workspace/runs/funnel/.")
    report.add_argument("--output", help="Explicit output path.")
    report.add_argument("--quiet", action="store_true", help="Only print the report path.")
    report.set_defaults(func=command_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    try:
        return args.func(args)
    except FunnelError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
