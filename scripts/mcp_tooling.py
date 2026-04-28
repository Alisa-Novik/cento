#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / '.mcp.json'
ENV_EXAMPLE_PATH = ROOT / '.env.mcp.example'
ENV_PATH = ROOT / '.env.mcp'
DOC_PATH = ROOT / 'docs' / 'mcp-tooling.md'
ROOT_DOC_PATH = ROOT / 'mcp' / 'README.md'
CALLS_DOC_PATH = ROOT / 'mcp' / 'tool-calls.md'


@dataclass
class DoctorIssue:
    level: str
    message: str


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip()
    return values


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def collect_env_names(config: dict) -> list[str]:
    names: set[str] = set()
    for server in config.get('mcpServers', {}).values():
        for value in server.get('args', []):
            if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                names.add(value[2:-1])
        for value in server.get('env', {}).values():
            if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                names.add(value[2:-1])
    return sorted(names)


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def command_summary(config: dict) -> list[tuple[str, str, bool]]:
    rows: list[tuple[str, str, bool]] = []
    for name, server in sorted(config.get('mcpServers', {}).items()):
        command = str(server.get('command', '')).strip()
        rows.append((name, command, bool(command) and command_exists(command)))
    return rows


def run_init(force: bool, write_env: bool) -> int:
    if write_env:
        if ENV_PATH.exists() and not force:
            print(f'.env.mcp already exists: {ENV_PATH}')
        else:
            ENV_PATH.write_text(ENV_EXAMPLE_PATH.read_text())
            print(f'Wrote {ENV_PATH}')
    print(f'MCP config path: {CONFIG_PATH}')
    print(f'Docs: {DOC_PATH}')
    print(f'Tool calls: {CALLS_DOC_PATH}')
    return 0


def run_doctor(as_json: bool) -> int:
    issues: list[DoctorIssue] = []
    if not CONFIG_PATH.exists():
        issues.append(DoctorIssue('error', f'Missing config: {CONFIG_PATH}'))
        result = {'ok': False, 'issues': [issue.__dict__ for issue in issues]}
        if as_json:
            print(json.dumps(result, indent=2))
        else:
            print('MCP doctor')
            print(f'error: {issues[0].message}')
        return 1

    try:
        config = load_config()
    except json.JSONDecodeError as exc:
        issues.append(DoctorIssue('error', f'Invalid JSON in {CONFIG_PATH}: {exc}'))
        result = {'ok': False, 'issues': [issue.__dict__ for issue in issues]}
        if as_json:
            print(json.dumps(result, indent=2))
        else:
            print('MCP doctor')
            print(f'error: {issues[0].message}')
        return 1

    env_file_values = parse_env_file(ENV_PATH)
    env_names = collect_env_names(config)
    env_status: list[dict[str, str | bool]] = []
    for name in env_names:
        value = os.environ.get(name, env_file_values.get(name, ''))
        ok = bool(value)
        env_status.append({'name': name, 'configured': ok})
        if not ok:
            issues.append(DoctorIssue('warn', f'Missing value for {name} in environment or .env.mcp'))

    command_rows = []
    for server_name, command, ok in command_summary(config):
        command_rows.append({'server': server_name, 'command': command, 'available': ok})
        if not ok:
            issues.append(DoctorIssue('warn', f"Command '{command}' for server '{server_name}' is not available"))

    result = {
        'ok': not any(issue.level == 'error' for issue in issues),
        'config_path': str(CONFIG_PATH),
        'env_path': str(ENV_PATH),
        'servers': sorted(config.get('mcpServers', {}).keys()),
        'commands': command_rows,
        'environment': env_status,
        'issues': [issue.__dict__ for issue in issues],
    }

    if as_json:
        print(json.dumps(result, indent=2))
        return 0 if result['ok'] else 1

    print('MCP doctor')
    print(f'config_path: {CONFIG_PATH}')
    print(f'env_path: {ENV_PATH}')
    print(f'env_example_path: {ENV_EXAMPLE_PATH}')
    print('servers:')
    for server_name in result['servers']:
        print(f'  - {server_name}')
    print('commands:')
    for row in command_rows:
        state = 'ok' if row['available'] else 'missing'
        print(f"  - {row['server']}: {row['command']} [{state}]")
    print('environment:')
    for row in env_status:
        state = 'set' if row['configured'] else 'missing'
        print(f"  - {row['name']}: {state}")
    if issues:
        print('issues:')
        for issue in issues:
            print(f'  - {issue.level}: {issue.message}')
    else:
        print('issues:')
        print('  - none')
    return 0 if result['ok'] else 1


def run_docs() -> int:
    print(DOC_PATH.read_text())
    return 0


def run_paths() -> int:
    print(f'config_path={CONFIG_PATH}')
    print(f'env_example_path={ENV_EXAMPLE_PATH}')
    print(f'env_path={ENV_PATH}')
    print(f'root_doc_path={ROOT_DOC_PATH}')
    print(f'calls_doc_path={CALLS_DOC_PATH}')
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Manage repo-root MCP config and documentation for cento.')
    subparsers = parser.add_subparsers(dest='command')

    init_parser = subparsers.add_parser('init', help='Initialize local MCP helper files.')
    init_parser.add_argument('--force', action='store_true', help='Overwrite .env.mcp when present.')
    init_parser.add_argument('--write-env', action='store_true', help='Write .env.mcp from the example template.')

    doctor_parser = subparsers.add_parser('doctor', help='Validate MCP config and local prerequisites.')
    doctor_parser.add_argument('--json', action='store_true', help='Emit JSON output.')

    subparsers.add_parser('docs', help='Print MCP docs.')
    subparsers.add_parser('paths', help='Print important MCP file paths.')
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or 'doctor'

    if command == 'init':
        return run_init(force=args.force, write_env=args.write_env)
    if command == 'doctor':
        return run_doctor(as_json=args.json)
    if command == 'docs':
        return run_docs()
    if command == 'paths':
        return run_paths()

    parser.print_help(sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
