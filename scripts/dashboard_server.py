#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shlex
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from jobs_server import load_jobs
from network_web_server import cluster_snapshot

ROOT_DIR = Path(__file__).resolve().parent.parent
TOOLS_JSON = ROOT_DIR / 'data' / 'tools.json'
CONFIG_DIR = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'cento'
ALIASES_FILE = CONFIG_DIR / 'aliases.sh'
LOG_ROOT = ROOT_DIR / 'logs'
KITTY_THEME_LOG = LOG_ROOT / 'kitty-theme-manager' / 'latest.log'
WALLPAPER_ENV = CONFIG_DIR / 'wallpaper.env'
DISPLAY_ENV = CONFIG_DIR / 'display.env'
PRESET_ENV = CONFIG_DIR / 'preset.env'
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 46268
PORT_SPAN = 12
REQUEST_LOG_LIMIT = 40
REPO_PATH = ROOT_DIR
DASHBOARD_THEME = os.environ.get('CENTO_DASHBOARD_THEME', 'default')

REQUEST_LOG: list[dict[str, str]] = []
REQUEST_LOCK = threading.Lock()
LOG_DIR = LOG_ROOT / 'dashboard'
LOG_FILE: Path | None = None


def log_line(message: str) -> None:
    timestamp = datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %z')
    line = f'[{timestamp}] {message}'
    print(line, file=sys.stderr, flush=True)
    if LOG_FILE is not None:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open('a', encoding='utf-8') as handle:
            handle.write(line + '\n')


def init_log_file() -> None:
    global LOG_FILE
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE = LOG_DIR / f"{datetime.now().astimezone().strftime('%Y%m%d-%H%M%S')}-dashboard.log"
    latest = LOG_DIR / 'latest.log'
    try:
        if latest.exists() or latest.is_symlink():
            latest.unlink()
        latest.symlink_to(LOG_FILE.name)
    except OSError:
        pass


def run_command(cmd: list[str], timeout: int = 10) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except Exception:
        return ''
    chunks = [result.stdout.strip(), result.stderr.strip()]
    return '\n'.join(chunk for chunk in chunks if chunk).strip()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def parse_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        raw_value = value.strip()
        try:
            parsed = shlex.split(raw_value)
        except ValueError:
            parsed = []
        data[key.strip()] = parsed[0] if len(parsed) == 1 else raw_value.strip('"')
    return data


def parse_aliases(path: Path) -> list[dict[str, str]]:
    aliases: list[dict[str, str]] = []
    if not path.exists():
        return aliases
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or not line.startswith('cento_alias '):
            continue
        try:
            tokens = shlex.split(line)
        except ValueError:
            continue
        if len(tokens) < 4 or tokens[0] != 'cento_alias':
            continue
        name = tokens[1]
        description = ''
        index = 2
        if index < len(tokens) and tokens[index] == '--description':
            if index + 1 < len(tokens):
                description = tokens[index + 1]
            index += 2
        if index < len(tokens) and tokens[index] == '--':
            index += 1
        command = ' '.join(tokens[index:])
        aliases.append({'name': name, 'description': description, 'command': command})
    return sorted(aliases, key=lambda item: item['name'])


def parse_connected_audio() -> list[dict[str, str]]:
    devices_text = run_command(['bluetoothctl', 'devices', 'Connected'], timeout=8)
    devices: list[dict[str, str]] = []
    for line in devices_text.splitlines():
        match = re.match(r'Device\s+([0-9A-F:]+)\s+(.+)$', line.strip())
        if not match:
            continue
        address, name = match.groups()
        info = run_command(['bluetoothctl', 'info', address], timeout=8)
        if re.search(r'Icon:\s+audio-|UUID:\s+(Audio Sink|Advanced Audio Distribu|Headset|Handsfree)', info):
            battery_match = re.search(r'Battery Percentage:\s+0x[0-9A-Fa-f]+\s+\((\d+)\)', info)
            devices.append({
                'name': name,
                'address': address,
                'battery': battery_match.group(1) + '%' if battery_match else 'unknown',
            })
    return devices


def parse_paired_audio() -> list[dict[str, str]]:
    devices_text = run_command(['bluetoothctl', 'devices', 'Paired'], timeout=8)
    devices: list[dict[str, str]] = []
    for line in devices_text.splitlines():
        match = re.match(r'Device\s+([0-9A-F:]+)\s+(.+)$', line.strip())
        if not match:
            continue
        address, name = match.groups()
        info = run_command(['bluetoothctl', 'info', address], timeout=8)
        if re.search(r'Icon:\s+audio-|UUID:\s+(Audio Sink|Advanced Audio Distribu|Headset|Handsfree)', info):
            connected = 'yes' if 'Connected: yes' in info else 'no'
            devices.append({'name': name, 'address': address, 'connected': connected})
    return devices


def current_theme() -> str:
    if KITTY_THEME_LOG.exists():
        for line in reversed(KITTY_THEME_LOG.read_text().splitlines()):
            match = re.search(r'Selected theme:\s+(.+)$', line)
            if match:
                return match.group(1).strip()
            match = re.search(r'Applied Kitty theme:\s+(.+)$', line)
            if match:
                return match.group(1).strip()
    return 'unknown'


def current_wallpaper() -> str:
    data = parse_env_file(WALLPAPER_ENV)
    value = data.get('CURRENT_WALLPAPER') or data.get('CENTO_WALLPAPER')
    return Path(value).name if value else 'unknown'


def current_preset() -> str:
    data = parse_env_file(PRESET_ENV)
    return data.get('CENTO_PRESET_NAME') or data.get('CENTO_PRESET') or 'default'


def display_summary() -> dict[str, Any]:
    connected: list[str] = []
    text = run_command(['xrandr', '--query'], timeout=8)
    for line in text.splitlines():
        if ' connected' in line:
            connected.append(line.split()[0])
    env = parse_env_file(DISPLAY_ENV)
    return {
        'connected': connected,
        'top': env.get('CENTO_DISPLAY_TOP', 'unknown'),
        'bottom': env.get('CENTO_DISPLAY_BOTTOM', 'unknown'),
    }


def repo_status() -> dict[str, Any]:
    porcelain = run_command(['git', '-C', str(REPO_PATH), 'status', '--short'], timeout=10)
    modified = added = deleted = renamed = untracked = 0
    files: list[str] = []
    for line in porcelain.splitlines():
        if not line:
            continue
        files.append(line)
        code = line[:2]
        if code == '??':
            untracked += 1
            continue
        if 'M' in code:
            modified += 1
        if 'A' in code:
            added += 1
        if 'D' in code:
            deleted += 1
        if 'R' in code:
            renamed += 1
    commits_raw = run_command(['git', '-C', str(REPO_PATH), 'log', '--pretty=format:%h\t%ad\t%s', '--date=short', '-n', '6'], timeout=10)
    commits: list[dict[str, str]] = []
    for line in commits_raw.splitlines():
        parts = line.split('\t', 2)
        if len(parts) == 3:
            commits.append({'sha': parts[0], 'date': parts[1], 'subject': parts[2]})
    branch = run_command(['git', '-C', str(REPO_PATH), 'branch', '--show-current'], timeout=5) or 'unknown'
    return {
        'branch': branch,
        'modified': modified,
        'added': added,
        'deleted': deleted,
        'renamed': renamed,
        'untracked': untracked,
        'dirty': any([modified, added, deleted, renamed, untracked]),
        'files': files[:20],
        'commits': commits,
    }


def parse_log_line_time(line: str) -> datetime | None:
    match = re.match(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [+-]\d{4})\]', line)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S %z')
    except ValueError:
        return None


def summarize_log(path: Path) -> dict[str, str]:
    lines = path.read_text(errors='replace').splitlines()
    last_meaningful = ''
    recorded_at = datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat()
    for line in reversed(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if 'Log file:' in stripped:
            continue
        last_meaningful = stripped
        parsed = parse_log_line_time(stripped)
        if parsed:
            recorded_at = parsed.isoformat()
        break
    return {
        'tool': path.parent.name,
        'path': str(path),
        'summary': last_meaningful or 'log recorded',
        'recorded_at': recorded_at,
    }


def recent_activity(limit: int = 12) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    if not LOG_ROOT.exists():
        return entries
    for path in sorted(LOG_ROOT.glob('*/*.log')):
        try:
            entries.append(summarize_log(path))
        except Exception:
            continue
    entries.sort(key=lambda item: item['recorded_at'], reverse=True)
    return entries[:limit]


def latest_runs() -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    if not LOG_ROOT.exists():
        return entries
    for tool_dir in sorted(LOG_ROOT.iterdir()):
        latest = tool_dir / 'latest.log'
        if latest.exists() and latest.is_symlink():
            try:
                path = latest.resolve(strict=True)
            except FileNotFoundError:
                continue
            entries.append(summarize_log(path))
    entries.sort(key=lambda item: item['tool'])
    return entries


def dashboard_links() -> list[dict[str, str]]:
    return [
        {
            'name': 'Overview',
            'command': 'cento dashboard --open',
            'href': '#top',
            'default_url': 'http://127.0.0.1:46268',
            'description': 'Central launcher and toolkit state dashboard.',
        },
        {
            'name': 'Jobs',
            'command': 'cento jobs --open',
            'href': '#jobs-panel',
            'default_url': 'http://127.0.0.1:47883',
            'description': 'Cluster job manifests, task state, node assignments, and log tails.',
        },
        {
            'name': 'Network',
            'command': 'cento network --web --open',
            'href': '#network-panel',
            'default_url': 'http://127.0.0.1:47882',
            'description': 'Cluster node registry, bridge mesh state, and cluster health.',
        },
        {
            'name': 'Idea Board',
            'command': 'cento idea-board --open',
            'href': 'http://127.0.0.1:47872',
            'default_url': 'http://127.0.0.1:47872',
            'description': 'Editable project idea board and cluster roadmap.',
        },
        {
            'name': 'CRM',
            'command': 'cento crm serve --open',
            'href': '#dashboards-panel',
            'default_url': 'local CRM server',
            'description': 'Career consulting CRM profiles, intake, and artifacts.',
        },
    ]


def runs_today() -> int:
    today = datetime.now().date()
    count = 0
    if not LOG_ROOT.exists():
        return count
    for path in LOG_ROOT.glob('*/*.log'):
        try:
            if datetime.fromtimestamp(path.stat().st_mtime).date() == today:
                count += 1
        except OSError:
            continue
    return count


def load_tools() -> list[dict[str, Any]]:
    data = read_json(TOOLS_JSON)
    tools = data.get('tools', []) if isinstance(data, dict) else []
    return sorted(tools, key=lambda item: item.get('id', ''))


def safe_jobs_snapshot() -> dict[str, Any]:
    try:
        return load_jobs()
    except Exception as exc:
        return {
            'updated_at': datetime.now().astimezone().isoformat(),
            'run_root': '',
            'jobs': [],
            'error': str(exc),
        }


def safe_network_snapshot() -> dict[str, Any]:
    try:
        return cluster_snapshot()
    except Exception as exc:
        return {
            'updated_at': datetime.now().astimezone().isoformat(),
            'nodes': [],
            'relay': {},
            'jobs': {'total': 0, 'failed': 0, 'succeeded': 0, 'planned': 0, 'dry_run': 0},
            'status': {'stdout': '', 'stderr': str(exc), 'ok': False},
            'mesh': {'stdout': '', 'stderr': '', 'ok': False},
            'error': str(exc),
        }


def overview_snapshot() -> dict[str, Any]:
    tools = load_tools()
    aliases = parse_aliases(ALIASES_FILE)
    repo = repo_status()
    connected_audio = parse_connected_audio()
    paired_audio = parse_paired_audio()
    displays = display_summary()
    latest = latest_runs()
    return {
        'generated_at': datetime.now().astimezone().isoformat(),
        'overview': {
            'tools_count': len(tools),
            'aliases_count': len(aliases),
            'runs_today': runs_today(),
            'repo_dirty': repo['dirty'],
        },
        'state': {
            'preset': current_preset(),
            'theme': current_theme(),
            'wallpaper': current_wallpaper(),
            'audio_connected': connected_audio,
            'audio_paired': paired_audio,
            'displays': displays,
        },
        'repo': repo,
        'tools': [
            {
                'id': tool.get('id', ''),
                'name': tool.get('name', tool.get('id', '')),
                'description': tool.get('description', ''),
                'kind': tool.get('kind', ''),
            }
            for tool in tools
        ],
        'aliases': aliases,
        'activity': recent_activity(),
        'latest_runs': latest,
        'dashboards': dashboard_links(),
        'requests': list(REQUEST_LOG),
    }


def render_page() -> str:
    industrial_css = """
    body.industrial {
      --bg: #050403;
      --panel: #0b0705;
      --panel-2: #130b07;
      --text: #f4e8dc;
      --muted: #a88b78;
      --accent: #ff5a00;
      --accent-2: #ffb000;
      --ok: #6be675;
      --warn: #ff3500;
      --border: rgba(255,90,0,0.42);
      --shadow: inset 0 0 0 1px rgba(255,90,0,0.08), 0 18px 48px rgba(0,0,0,0.48);
      background: #050403;
    }
    body.industrial::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background:
        linear-gradient(180deg, rgba(255,90,0,0.06), transparent 26%),
        repeating-linear-gradient(0deg, rgba(255,255,255,0.025) 0, rgba(255,255,255,0.025) 1px, transparent 1px, transparent 5px);
      opacity: 0.8;
    }
    body.industrial .shell { max-width: 1540px; padding-top: 18px; }
    body.industrial .panel {
      border-radius: 6px;
      background: linear-gradient(180deg, rgba(17,10,7,0.96), rgba(5,4,3,0.94));
      border-color: var(--border);
    }
    body.industrial .hero h1 {
      color: var(--accent);
      text-transform: uppercase;
      font-size: 24px;
    }
    body.industrial h2 {
      color: var(--accent);
      font-size: 13px;
    }
    body.industrial .chip,
    body.industrial li.item,
    body.industrial .dashboard-card,
    body.industrial pre {
      border-radius: 4px;
      border-color: rgba(255,90,0,0.26);
      background: rgba(255,90,0,0.045);
    }
    body.industrial .dashboard-card:hover {
      border-color: rgba(255,90,0,0.72);
      background: rgba(255,90,0,0.12);
    }
    body.industrial .metric .value,
    body.industrial .title { color: var(--text); }
    body.industrial .meta,
    body.industrial .muted { color: var(--muted); }
    body.industrial .kv div { border-bottom-color: rgba(255,90,0,0.16); }
    body.industrial a,
    body.industrial code { color: var(--accent); }
    """
    theme_class = 'industrial' if DASHBOARD_THEME == 'industrial' else ''
    title = 'industrial os' if DASHBOARD_THEME == 'industrial' else 'cento dashboard'
    subtitle = (
        'Engineering dashboard for cluster jobs, system resources, and desktop state.'
        if DASHBOARD_THEME == 'industrial'
        else 'Local control surface for your toolkit, recent activity, and repo progress.'
    )
    page = """<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>__DASHBOARD_TITLE__</title>
  <style>
    :root {
      --bg: #101218;
      --panel: #171b24;
      --panel-2: #1f2530;
      --text: #edf2f7;
      --muted: #99a6bb;
      --accent: #7dd3fc;
      --accent-2: #f59e0b;
      --ok: #34d399;
      --warn: #fb7185;
      --border: rgba(255,255,255,0.08);
      --shadow: 0 24px 80px rgba(0,0,0,0.28);
      font-family: "Iosevka Etoile", "JetBrains Mono", monospace;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background:
        radial-gradient(circle at top left, rgba(125,211,252,0.12), transparent 32%),
        radial-gradient(circle at top right, rgba(245,158,11,0.12), transparent 28%),
        linear-gradient(180deg, #0c0f14 0%, #101218 100%);
      color: var(--text);
    }
    .shell {
      max-width: 1360px;
      margin: 0 auto;
      padding: 28px 22px 56px;
    }
    .hero {
      display: grid;
      grid-template-columns: 2.1fr 1fr;
      gap: 18px;
      margin-bottom: 18px;
    }
    .panel {
      background: linear-gradient(180deg, rgba(31,37,48,0.94), rgba(23,27,36,0.94));
      border: 1px solid var(--border);
      border-radius: 20px;
      box-shadow: var(--shadow);
      padding: 18px 20px;
    }
    .hero h1 {
      margin: 0 0 10px;
      font-size: 28px;
      letter-spacing: 0.02em;
    }
    .muted { color: var(--muted); }
    .chips { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px; }
    .chip {
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 8px 12px;
      background: rgba(255,255,255,0.03);
      font-size: 13px;
    }
    .metrics {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 16px;
      margin-bottom: 18px;
    }
    .metric .label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; }
    .metric .value { font-size: 28px; margin-top: 8px; }
    .grid {
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 18px;
    }
    .stack { display: grid; gap: 18px; }
    h2 {
      margin: 0 0 14px;
      font-size: 16px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
    }
    ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
    li.item {
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 12px 14px;
      background: rgba(255,255,255,0.02);
    }
    .dashboard-card {
      display: block;
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 12px 14px;
      background: rgba(125,211,252,0.05);
      color: var(--text);
    }
    .dashboard-card:hover {
      border-color: rgba(125,211,252,0.42);
      background: rgba(125,211,252,0.1);
    }
    .title { font-size: 14px; }
    .meta { color: var(--muted); font-size: 12px; margin-top: 4px; }
    .two-col { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
    .kv { display: grid; gap: 10px; }
    .kv div { display: flex; justify-content: space-between; gap: 12px; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 8px; }
    .compact-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
    .loading {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      color: var(--muted);
      min-height: 42px;
    }
    .spinner {
      width: 18px;
      height: 18px;
      border: 2px solid rgba(255,255,255,0.16);
      border-top-color: var(--accent);
      border-radius: 50%;
      animation: spin 0.85s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    pre {
      margin: 0;
      min-height: 120px;
      max-height: 260px;
      overflow: auto;
      white-space: pre-wrap;
      background: rgba(0,0,0,0.24);
      border: 1px solid rgba(255,255,255,0.06);
      border-radius: 12px;
      padding: 12px;
      color: var(--text);
    }
    .mono { font-family: inherit; }
    .ok { color: var(--ok); }
    .warn { color: var(--warn); }
    a { color: var(--accent); text-decoration: none; }
    code { color: var(--accent-2); }
    @media (max-width: 1100px) {
      .hero, .grid, .metrics, .two-col, .compact-grid { grid-template-columns: 1fr; }
    }
    __THEME_OVERRIDES__
  </style>
</head>
<body id='top' class='__BODY_CLASS__'>
  <div class='shell'>
    <section class='hero'>
      <div class='panel'>
        <h1>__DASHBOARD_TITLE__</h1>
        <div class='muted'>__DASHBOARD_SUBTITLE__</div>
        <div class='chips' id='hero-chips'></div>
      </div>
      <div class='panel'>
        <h2>Server</h2>
        <div class='kv'>
          <div><span>refresh</span><span>15s</span></div>
          <div><span>api</span><span><a href='/api/state'>/api/state</a></span></div>
          <div><span>repo</span><span class='mono'>~/projects/cento</span></div>
        </div>
      </div>
    </section>

    <section class='metrics'>
      <div class='panel metric'><div class='label'>Tools</div><div class='value' id='tools-count'>0</div></div>
      <div class='panel metric'><div class='label'>Aliases</div><div class='value' id='aliases-count'>0</div></div>
      <div class='panel metric'><div class='label'>Runs Today</div><div class='value' id='runs-today'>0</div></div>
      <div class='panel metric'><div class='label'>Repo State</div><div class='value' id='repo-dirty'>clean</div></div>
    </section>

    <section class='grid'>
      <div class='stack'>
        <div class='panel' id='network-panel'>
          <h2>Network</h2>
          <div class='compact-grid' id='network-metrics'><div class='loading'><span class='spinner'></span><span>Loading network...</span></div></div>
          <div class='two-col' style='margin-top: 14px;'>
            <div>
              <div class='title'>Nodes</div>
              <ul id='network-nodes'><li class='item'><div class='loading'><span class='spinner'></span><span>Checking nodes...</span></div></li></ul>
            </div>
            <div>
              <div class='title'>Status</div>
              <pre id='network-status'>Loading cluster status...</pre>
            </div>
          </div>
        </div>
        <div class='panel' id='jobs-panel'>
          <h2>Jobs</h2>
          <div class='compact-grid' id='job-metrics'><div class='loading'><span class='spinner'></span><span>Loading jobs...</span></div></div>
          <ul id='jobs-list' style='margin-top: 14px;'><li class='item'><div class='loading'><span class='spinner'></span><span>Reading job manifests...</span></div></li></ul>
        </div>
        <div class='panel'>
          <h2>Progress</h2>
          <div class='two-col'>
            <div>
              <div class='title'>Recent Activity</div>
              <ul id='activity-list'></ul>
            </div>
            <div>
              <div class='title'>Latest Tool Runs</div>
              <ul id='latest-runs'></ul>
            </div>
          </div>
        </div>
        <div class='panel'>
          <h2>Repo</h2>
          <div class='two-col'>
            <div class='kv' id='repo-kv'></div>
            <div>
              <div class='title'>Recent Commits</div>
              <ul id='commit-list'></ul>
            </div>
          </div>
        </div>
        <div class='panel'>
          <h2>Aliases</h2>
          <ul id='aliases-list'></ul>
        </div>
      </div>
      <div class='stack'>
        <div class='panel' id='dashboards-panel'>
          <h2>Dashboards</h2>
          <ul id='dashboards-list'></ul>
        </div>
        <div class='panel'>
          <h2>Current State</h2>
          <div class='kv' id='state-kv'></div>
        </div>
        <div class='panel'>
          <h2>Audio</h2>
          <ul id='audio-list'></ul>
        </div>
        <div class='panel'>
          <h2>Tools</h2>
          <ul id='tools-list'></ul>
        </div>
        <div class='panel'>
          <h2>Requests</h2>
          <ul id='requests-list'></ul>
        </div>
      </div>
    </section>
  </div>
  <script>
    function escapeHtml(value) {
      return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;');
    }

    function listItem(title, meta) {
      return `<li class="item"><div class="title">${escapeHtml(title)}</div><div class="meta">${escapeHtml(meta || '')}</div></li>`;
    }

    function dashboardItem(item) {
      const href = item.href || item.default_url || '#dashboards-panel';
      const target = href.startsWith('#') ? '' : ' target="_blank" rel="noreferrer"';
      const meta = [item.command, item.default_url, item.description].filter(Boolean).join(' | ');
      return `<li><a class="dashboard-card" href="${escapeHtml(href)}"${target}><div class="title">${escapeHtml(item.name)}</div><div class="meta">${escapeHtml(meta)}</div></a></li>`;
    }

    function smallMetric(label, value) {
      return `<div class="item"><div class="title">${escapeHtml(value)}</div><div class="meta">${escapeHtml(label)}</div></div>`;
    }

    function replaceHTML(id, value) {
      const element = document.getElementById(id);
      if (element.innerHTML !== value) {
        element.innerHTML = value;
      }
    }

    function replaceText(id, value) {
      const element = document.getElementById(id);
      const text = String(value);
      if (element.textContent !== text) {
        element.textContent = text;
      }
    }

    function renderNetwork(network) {
      network = network || {nodes: [], relay: {}, jobs: {}, status: {}};
      network.nodes = network.nodes || [];
      network.relay = network.relay || {};
      network.jobs = network.jobs || {};
      network.status = network.status || {};
      replaceHTML('network-metrics', [
        smallMetric('nodes', network.nodes.length),
        smallMetric('relay', network.relay.host || 'unknown'),
        smallMetric('cluster jobs', network.jobs.total || 0)
      ].join(''));
      replaceHTML('network-nodes', (network.nodes.length ? network.nodes : [{id:'No nodes configured', platform:'', repo:''}])
        .map(item => listItem(item.id, [item.platform, item.repo, item.socket].filter(Boolean).join(' | ')))
        .join(''));
      replaceText('network-status', [network.status.stdout, network.status.stderr].filter(Boolean).join('\\n') || 'No cluster status output.');
    }

    function renderJobs(jobs) {
      jobs = jobs || {jobs: []};
      jobs.jobs = jobs.jobs || [];
      replaceHTML('job-metrics', [
        smallMetric('total', jobs.jobs.length),
        smallMetric('failed', jobs.jobs.filter(item => item.status === 'failed').length),
        smallMetric('latest', jobs.jobs[0] ? jobs.jobs[0].status : 'none')
      ].join(''));
      replaceHTML('jobs-list', (jobs.jobs.length ? jobs.jobs.slice(0, 8) : [{id:'No cluster jobs', feature:'', status:''}])
        .map(item => listItem(`${item.id} ${item.status ? '(' + item.status + ')' : ''}`, item.feature || item.error || item.run_dir || ''))
        .join(''));
    }

    async function loadNetwork() {
      const response = await fetch('/api/network');
      renderNetwork(await response.json());
    }

    async function loadJobs() {
      const response = await fetch('/api/jobs');
      renderJobs(await response.json());
    }

    async function loadState() {
      const response = await fetch('/api/state');
      const data = await response.json();

      data.dashboards = data.dashboards || [];

      replaceText('tools-count', data.overview.tools_count);
      replaceText('aliases-count', data.overview.aliases_count);
      replaceText('runs-today', data.overview.runs_today);
      const repoDirty = document.getElementById('repo-dirty');
      replaceText('repo-dirty', data.overview.repo_dirty ? 'dirty' : 'clean');
      repoDirty.className = data.overview.repo_dirty ? 'value warn' : 'value ok';

      const chips = [
        `generated ${data.generated_at}`,
        `preset ${data.state.preset}`,
        `theme ${data.state.theme}`,
        `wallpaper ${data.state.wallpaper}`,
        `branch ${data.repo.branch}`
      ];
      replaceHTML('hero-chips', chips.map(item => `<div class="chip">${escapeHtml(item)}</div>`).join(''));

      const audioNames = data.state.audio_connected.length
        ? data.state.audio_connected.map(item => `${item.name} (${item.battery})`).join(', ')
        : 'none';
      replaceHTML('state-kv', [
        ['preset', data.state.preset],
        ['theme', data.state.theme],
        ['wallpaper', data.state.wallpaper],
        ['audio connected', audioNames],
        ['display top', data.state.displays.top],
        ['display bottom', data.state.displays.bottom],
        ['display outputs', data.state.displays.connected.join(', ') || 'unknown']
      ].map(([k, v]) => `<div><span>${escapeHtml(k)}</span><span>${escapeHtml(v)}</span></div>`).join(''));

      replaceHTML('audio-list', (data.state.audio_paired.length ? data.state.audio_paired : [{name:'No paired audio devices', address:'', connected:''}])
        .map(item => listItem(item.name, [item.address, item.connected ? `connected ${item.connected}` : ''].filter(Boolean).join(' | ')))
        .join(''));

      replaceHTML('repo-kv', [
        ['branch', data.repo.branch],
        ['modified', String(data.repo.modified)],
        ['added', String(data.repo.added)],
        ['deleted', String(data.repo.deleted)],
        ['renamed', String(data.repo.renamed)],
        ['untracked', String(data.repo.untracked)]
      ].map(([k, v]) => `<div><span>${escapeHtml(k)}</span><span>${escapeHtml(v)}</span></div>`).join(''));

      replaceHTML('commit-list', data.repo.commits.map(item => listItem(`${item.sha} ${item.subject}`, item.date)).join(''));
      replaceHTML('activity-list', data.activity.map(item => listItem(`${item.tool}: ${item.summary}`, item.recorded_at)).join(''));
      replaceHTML('latest-runs', data.latest_runs.map(item => listItem(item.tool, `${item.recorded_at} | ${item.summary}`)).join(''));
      replaceHTML('dashboards-list', data.dashboards.map(dashboardItem).join(''));
      replaceHTML('aliases-list', data.aliases.map(item => listItem(item.name, item.description || item.command)).join(''));
      replaceHTML('tools-list', data.tools.map(item => listItem(item.id, item.description || item.name)).join(''));
      replaceHTML('requests-list', (data.requests.length ? data.requests : [{path:'No requests yet', at:'', client:''}])
        .map(item => listItem(item.path, [item.at, item.client].filter(Boolean).join(' | ')))
        .join(''));
    }

    loadState();
    loadJobs();
    loadNetwork();
    setInterval(loadState, 15000);
    setInterval(loadJobs, 5000);
    setInterval(loadNetwork, 15000);
  </script>
</body>
</html>
"""
    return (
        page
        .replace('__DASHBOARD_TITLE__', html.escape(title))
        .replace('__DASHBOARD_SUBTITLE__', html.escape(subtitle))
        .replace('__BODY_CLASS__', theme_class)
        .replace('__THEME_OVERRIDES__', industrial_css if DASHBOARD_THEME == 'industrial' else '')
    )


class DashboardHandler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        with REQUEST_LOCK:
            REQUEST_LOG.append({
                'at': datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S'),
                'client': self.address_string(),
                'path': self.path,
            })
            del REQUEST_LOG[:-REQUEST_LOG_LIMIT]
        log_line('%s - - [%s] %s' % (self.address_string(), self.log_date_time_string(), fmt % args))

    def do_GET(self) -> None:
        if self.path in ('/', '/index.html'):
            body = render_page().encode('utf-8')
            self._send(200, body, 'text/html; charset=utf-8')
            return
        if self.path == '/api/state':
            payload = json.dumps(overview_snapshot(), indent=2).encode('utf-8')
            self._send(200, payload, 'application/json; charset=utf-8')
            return
        if self.path == '/api/jobs':
            payload = json.dumps(safe_jobs_snapshot(), indent=2).encode('utf-8')
            self._send(200, payload, 'application/json; charset=utf-8')
            return
        if self.path == '/api/network':
            payload = json.dumps(safe_network_snapshot(), indent=2).encode('utf-8')
            self._send(200, payload, 'application/json; charset=utf-8')
            return
        self._send(404, b'not found', 'text/plain; charset=utf-8')


def find_port(host: str, preferred: int) -> int:
    for port in range(preferred, preferred + PORT_SPAN):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    raise SystemExit(f'No free port found in range {preferred}-{preferred + PORT_SPAN - 1}')


def main() -> None:
    global DASHBOARD_THEME
    default_theme = os.environ.get('CENTO_DASHBOARD_THEME', 'default')
    if default_theme not in {'default', 'industrial'}:
        default_theme = 'default'
    parser = argparse.ArgumentParser(description='Run the cento localhost dashboard server.')
    parser.add_argument('--host', default=DEFAULT_HOST)
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    parser.add_argument('--theme', choices=['default', 'industrial'], default=default_theme, help='Dashboard visual theme.')
    parser.add_argument('--open', action='store_true', help='Open the dashboard URL in a browser.')
    args = parser.parse_args()
    DASHBOARD_THEME = args.theme

    init_log_file()
    host = args.host
    port = find_port(host, args.port)
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    url = f'http://{host}:{port}'
    log_line(f'cento dashboard listening on {url}')
    log_line('Press Ctrl-C to stop.')
    if LOG_FILE is not None:
        log_line(f'Log file: {LOG_FILE}')
    if args.open:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log_line('Stopping cento dashboard.')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
