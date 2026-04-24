#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a Markdown index from data/tools.json.")
    parser.add_argument("--registry", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    registry = Path(args.registry)
    output = Path(args.output)
    payload = json.loads(registry.read_text())
    tools = payload.get("tools", [])

    lines: list[str] = ["# Tool Index", ""]
    for tool in tools:
        lines.append(f"## {tool['name']}")
        lines.append("")
        lines.append(f"- `id`: `{tool['id']}`")
        lines.append(f"- `lane`: `{tool.get('lane', 'unknown')}`")
        lines.append(f"- `kind`: `{tool.get('kind', 'unknown')}`")
        lines.append(f"- `entrypoint`: `{tool.get('entrypoint', '')}`")
        if tool.get("wrapper"):
            lines.append(f"- `wrapper`: `{tool['wrapper']}`")
        lines.append(f"- description: {tool.get('description', '')}")
        commands = tool.get("commands", [])
        if commands:
            lines.append("- commands:")
            for command in commands:
                lines.append(f"  - `{command}`")
        lines.append("")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines).rstrip() + "\n")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
