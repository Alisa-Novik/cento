#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI_DOCS_PATH = ROOT / "data" / "cento-cli.json"
TOOLS_JSON_PATH = ROOT / "data" / "tools.json"
ALIASES_PATH = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "cento" / "aliases.sh"
CENTO_BIN = Path.home() / "bin" / "cento"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive and scripted docs browser for cento.")
    parser.add_argument("--json", action="store_true", help="Print the raw canonical CLI docs JSON.")
    parser.add_argument("--path", action="store_true", help="Print the canonical CLI docs JSON path.")
    parser.add_argument("--entry", help="Print docs for one built-in command, tool id, or alias name.")
    parser.add_argument("--overview", action="store_true", help="Print a non-interactive CLI overview.")
    parser.add_argument("--section", choices=["all", "builtins", "tools", "aliases"], default="all", help="Limit list or interactive mode to one section.")
    parser.add_argument("--list", action="store_true", help="List entries in the selected section.")
    return parser.parse_args()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def parse_aliases(path: Path) -> list[dict[str, str]]:
    aliases: list[dict[str, str]] = []
    if not path.exists():
        return aliases
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or not line.startswith("cento_alias "):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        name = parts[1]
        description = "User alias"
        if "--description" in parts:
            idx = parts.index("--description")
            if idx + 1 < len(parts):
                description = parts[idx + 1].strip('"')
        command = line.split("--", 1)[1].strip() if "--" in line else ""
        aliases.append(
            {
                "id": name,
                "type": "alias",
                "name": name,
                "summary": description,
                "usage": f"cento {name}",
                "details": [f"Configured command: {command}"] if command else [],
                "examples": [f"cento {name}"],
            }
        )
    return sorted(aliases, key=lambda item: item["name"])


def format_overview() -> str:
    docs = load_json(CLI_DOCS_PATH)
    lines = [docs.get("summary", ""), "", f"Usage: {docs.get('usage', '')}"]
    notes = docs.get("notes", [])
    if notes:
        lines.extend(["", "Notes:"])
        for note in notes:
            lines.append(f"  - {note}")
    lines.extend(["", "Built-ins:"])
    for command in docs.get("commands", []):
        lines.append(f"  {command.get('usage', '')}  {command.get('summary', '')}")
    routing = docs.get("routing", [])
    if routing:
        lines.extend(["", "Routing:"])
        for item in routing:
            lines.append(f"  {item.get('usage', '')}  {item.get('summary', '')}")
    return "\n".join(lines)


def build_entries() -> list[dict]:
    cli_docs = load_json(CLI_DOCS_PATH)
    tools = load_json(TOOLS_JSON_PATH).get("tools", [])
    entries: list[dict] = []
    for command in cli_docs.get("commands", []):
        entries.append(
            {
                "id": command["name"],
                "type": "builtin",
                "name": command["name"],
                "summary": command.get("summary", ""),
                "usage": command.get("usage", ""),
                "flags": command.get("flags", []),
                "examples": command.get("examples", []),
                "details": command.get("details", []),
            }
        )
    for tool in tools:
        entries.append(
            {
                "id": tool["id"],
                "type": "tool",
                "name": tool["id"],
                "summary": tool.get("description", ""),
                "usage": f"cento {tool['id']}",
                "examples": tool.get("commands", []),
                "details": [
                    f"Name: {tool.get('name', tool['id'])}",
                    f"Kind: {tool.get('kind', 'unknown')}",
                    f"Entrypoint: {tool.get('entrypoint', '')}",
                ] + [f"Note: {note}" for note in tool.get("notes", [])],
            }
        )
    entries.extend(parse_aliases(ALIASES_PATH))
    return entries


def section_entries(entries: list[dict], section: str) -> list[dict]:
    if section == "all":
        return entries
    wanted = {"builtins": "builtin", "tools": "tool", "aliases": "alias"}[section]
    return [entry for entry in entries if entry["type"] == wanted]


def format_entry(entry: dict) -> str:
    lines = [f"{entry['type']}: {entry['name']}", "", f"Summary: {entry.get('summary', '')}", f"Usage:   {entry.get('usage', '')}"]
    flags = entry.get("flags", [])
    if flags:
        lines.extend(["", "Flags:"])
        for flag in flags:
            lines.append(f"  {flag.get('name', '')}")
            lines.append(f"    {flag.get('summary', '')}")
            if flag.get("usage"):
                lines.append(f"    usage: {flag['usage']}")
    details = entry.get("details", [])
    if details:
        lines.extend(["", "Details:"])
        for detail in details:
            lines.append(f"  - {detail}")
    examples = entry.get("examples", [])
    if examples:
        lines.extend(["", "Examples:"])
        for example in examples:
            lines.append(f"  {example}")
    return "\n".join(lines)


def print_list(entries: list[dict]) -> int:
    for entry in entries:
        print(f"{entry['type']:<7}  {entry['name']:<16}  {entry.get('summary', '')}")
    return 0


def resolve_entry(entries: list[dict], name: str) -> dict | None:
    for entry in entries:
        if entry["name"] == name or entry["id"] == name:
            return entry
    return None


def run_entry(entry: dict) -> None:
    command = entry.get("usage", "").strip()
    if not command:
        return
    parts = command.split()
    if CENTO_BIN.exists() and parts and parts[0] == "cento":
        parts[0] = str(CENTO_BIN)
    subprocess.run(parts, check=False)


def interactive(entries: list[dict], section: str) -> int:
    current_section = section
    current = section_entries(entries, current_section)
    while True:
        print()
        print("cento interactive")
        print("Commands: number = view docs, /term = filter, all|builtins|tools|aliases = section, q = quit")
        print()
        for index, entry in enumerate(current, start=1):
            print(f"{index:>2}. [{entry['type']}] {entry['name']:<16} {entry.get('summary', '')}")
        print()
        choice = input("> ").strip()
        if choice in {"q", "quit", "exit"}:
            return 0
        if choice in {"all", "builtins", "tools", "aliases"}:
            current_section = choice
            current = section_entries(entries, current_section)
            continue
        if choice.startswith("/"):
            term = choice[1:].strip().lower()
            base = section_entries(entries, current_section)
            current = [entry for entry in base if term in entry["name"].lower() or term in entry.get("summary", "").lower()]
            continue
        if not choice.isdigit():
            continue
        index = int(choice) - 1
        if index < 0 or index >= len(current):
            continue
        entry = current[index]
        print()
        print(format_entry(entry))
        print()
        follow_up = input("Enter = back, r = run, q = quit: ").strip().lower()
        if follow_up == "q":
            return 0
        if follow_up == "r":
            run_entry(entry)
    return 0


def main() -> int:
    args = parse_args()
    if args.path:
        print(CLI_DOCS_PATH)
        return 0
    if args.json:
        print(CLI_DOCS_PATH.read_text())
        return 0
    if args.overview:
        print(format_overview())
        return 0
    entries = build_entries()
    if args.entry:
        entry = resolve_entry(entries, args.entry)
        if entry is None:
            print(f"Unknown cento docs entry: {args.entry}", file=sys.stderr)
            return 1
        print(format_entry(entry))
        return 0
    if args.list or not sys.stdin.isatty():
        return print_list(section_entries(entries, args.section))
    return interactive(entries, args.section)


if __name__ == "__main__":
    raise SystemExit(main())
