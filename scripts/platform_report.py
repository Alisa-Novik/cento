#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PLATFORMS = ("linux", "macos")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report cento tool platform support.")
    parser.add_argument("--registry", default="data/tools.json", help="Path to data/tools.json.")
    parser.add_argument("--platform", choices=PLATFORMS, help="Only list tools available on this platform.")
    parser.add_argument("--markdown", action="store_true", help="Write a Markdown report.")
    parser.add_argument("--output", help="Markdown output path.")
    return parser.parse_args()


def tool_platforms(tool: dict) -> list[str]:
    platforms = tool.get("platforms") or list(PLATFORMS)
    return [platform for platform in platforms if platform in PLATFORMS]


def load_tools(path: Path) -> list[dict]:
    payload = json.loads(path.read_text())
    return sorted(payload.get("tools", []), key=lambda item: item["id"])


def supports(tool: dict, platform: str) -> bool:
    return platform in tool_platforms(tool)


def render_markdown(tools: list[dict]) -> str:
    both = [tool for tool in tools if all(supports(tool, platform) for platform in PLATFORMS)]
    linux_only = [tool for tool in tools if supports(tool, "linux") and not supports(tool, "macos")]
    macos_only = [tool for tool in tools if supports(tool, "macos") and not supports(tool, "linux")]

    lines = [
        "# Platform Support",
        "",
        "This file is generated from `data/tools.json`.",
        "",
        "## Summary",
        "",
        f"- macOS tools: {sum(1 for tool in tools if supports(tool, 'macos'))}",
        f"- Linux tools: {sum(1 for tool in tools if supports(tool, 'linux'))}",
        f"- both platforms: {len(both)}",
        f"- Linux only: {len(linux_only)}",
        f"- macOS only: {len(macos_only)}",
        "",
        "## Tool Matrix",
        "",
        "| Tool | macOS | Linux | Description |",
        "|---|---:|---:|---|",
    ]
    for tool in tools:
        macos = "yes" if supports(tool, "macos") else "no"
        linux = "yes" if supports(tool, "linux") else "no"
        description = tool.get("description", "").replace("|", "\\|")
        lines.append(f"| `{tool['id']}` | {macos} | {linux} | {description} |")

    groups = (
        ("Available On Both", both),
        ("Linux Only", linux_only),
        ("macOS Only", macos_only),
    )
    for title, group in groups:
        lines.extend(["", f"## {title}", ""])
        if group:
            for tool in group:
                lines.append(f"- `{tool['id']}`")
        else:
            lines.append("- none")

    return "\n".join(lines).rstrip() + "\n"


def print_text(tools: list[dict], platform: str | None) -> None:
    selected = [tool for tool in tools if platform is None or supports(tool, platform)]
    width = max(len(tool["id"]) for tool in selected) if selected else 4
    for tool in selected:
        plats = ",".join(tool_platforms(tool))
        print(f"{tool['id']:<{width}}  {plats:<12}  {tool.get('description', '')}")


def main() -> int:
    args = parse_args()
    registry = Path(args.registry)
    tools = load_tools(registry)

    if args.markdown or args.output:
        markdown = render_markdown(tools)
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(markdown)
            print(output)
        else:
            sys.stdout.write(markdown)
        return 0

    print_text(tools, args.platform)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
