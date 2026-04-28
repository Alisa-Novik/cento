#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = ROOT / 'workspace' / 'runs' / 'scan-onepager'
SERVER_ROOT = OUTPUT_ROOT / 'latest'
SERVER_META_PATH = OUTPUT_ROOT / 'server.json'
SERVER_LOG_PATH = OUTPUT_ROOT / 'server.log'
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 47873
PORT_SPAN = 24
EXCLUDED_DIRS = {
    '.git',
    'workspace',
    'logs',
    'node_modules',
    '__pycache__',
    '.venv',
    'venv',
    '.pytest_cache',
}
MAX_FILE_SIZE = 512 * 1024
MAX_SNIPPETS_PER_FILE = 3
DEFAULT_RESULT_LIMIT = 12


@dataclass
class MatchSnippet:
    line_number: int
    text: str


@dataclass
class FileMatch:
    relative_path: str
    absolute_path: str
    count: int
    snippets: list[MatchSnippet]
    category: str
    extension: str


@dataclass
class ScanStats:
    query: str
    root: str
    generated_at: str
    scanned_files: int
    matched_files: int
    total_matches: int
    top_directories: list[tuple[str, int]]
    top_extensions: list[tuple[str, int]]
    top_files: list[FileMatch]
    explanation: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Scan cento source files and generate a single-page HTML report.')
    parser.add_argument('--query', required=True, help='Text or regex to scan for.')
    parser.add_argument('--root', default=str(ROOT), help='Directory to scan. Defaults to the cento repo root.')
    parser.add_argument('--output-root', default=str(OUTPUT_ROOT), help='Run directory root. Defaults to workspace/runs/scan-onepager.')
    parser.add_argument('--limit', type=int, default=DEFAULT_RESULT_LIMIT, help='Maximum number of files to show in the report.')
    parser.add_argument('--regex', action='store_true', help='Treat the query as a regular expression.')
    parser.add_argument('--case-sensitive', action='store_true', help='Use case-sensitive matching.')
    parser.add_argument('--open', dest='open_browser', action='store_true', default=True, help='Open the generated report in a browser. Enabled by default.')
    parser.add_argument('--no-open', dest='open_browser', action='store_false', help='Do not open the generated report in a browser.')
    parser.add_argument('--host', default=DEFAULT_HOST, help='Host for the local preview server.')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Preferred high port for the local preview server.')
    return parser.parse_args()


def compile_pattern(query: str, regex: bool, case_sensitive: bool) -> re.Pattern[str]:
    flags = 0 if case_sensitive else re.IGNORECASE
    if regex:
        return re.compile(query, flags)
    return re.compile(re.escape(query), flags)


def rotate_latest(output_root: Path) -> Path:
    latest_dir = output_root / 'latest'
    archive_root = output_root / 'archive'
    if latest_dir.exists() and any(latest_dir.iterdir()):
        archive_root.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        target = archive_root / timestamp
        suffix = 2
        while target.exists():
            target = archive_root / f'{timestamp}-{suffix}'
            suffix += 1
        shutil.move(str(latest_dir), str(target))
    latest_dir.mkdir(parents=True, exist_ok=True)
    return latest_dir


def should_skip(path: Path, root: Path) -> bool:
    rel_parts = path.relative_to(root).parts
    return any(part in EXCLUDED_DIRS for part in rel_parts)


def is_text_file(path: Path) -> bool:
    try:
        if path.stat().st_size > MAX_FILE_SIZE:
            return False
        sample = path.read_bytes()[:4096]
    except OSError:
        return False
    return b'\x00' not in sample


def category_for(path: Path) -> str:
    parts = path.parts
    if not parts:
        return 'root'
    head = parts[0]
    return {
        'scripts': 'automation and command entrypoints',
        'docs': 'documentation and reference material',
        'data': 'registry and structured configuration',
        'templates': 'templates and scaffolding',
        'standards': 'repo-wide standards',
        'workflows': 'operating playbooks',
        'themes': 'theme assets and presets',
        'mcp': 'MCP setup and tool-call guidance',
    }.get(head, 'project root and support files')


def scan_files(root: Path, query: str, pattern: re.Pattern[str], limit: int) -> ScanStats:
    generated_at = datetime.now().astimezone().isoformat(timespec='seconds')
    scanned_files = 0
    total_matches = 0
    file_matches: list[FileMatch] = []
    directory_counter: Counter[str] = Counter()
    extension_counter: Counter[str] = Counter()

    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        if should_skip(path, root):
            continue
        if not is_text_file(path):
            continue
        scanned_files += 1
        relative = path.relative_to(root)
        try:
            text = path.read_text(errors='ignore')
        except OSError:
            continue
        count = 0
        snippets: list[MatchSnippet] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            line_hits = list(pattern.finditer(line))
            if not line_hits:
                continue
            count += len(line_hits)
            if len(snippets) < MAX_SNIPPETS_PER_FILE:
                snippets.append(MatchSnippet(line_number=line_number, text=line.strip()))
        if count == 0:
            continue
        total_matches += count
        rel_str = str(relative)
        top_dir = relative.parts[0] if len(relative.parts) > 1 else '.'
        directory_counter[top_dir] += count
        extension = path.suffix or '[no extension]'
        extension_counter[extension] += count
        file_matches.append(
            FileMatch(
                relative_path=rel_str,
                absolute_path=str(path),
                count=count,
                snippets=snippets,
                category=category_for(relative),
                extension=extension,
            )
        )

    file_matches.sort(key=lambda item: (-item.count, item.relative_path))
    top_files = file_matches[: max(limit, 1)]
    explanation = build_explanation(query, scanned_files, total_matches, file_matches, directory_counter)
    return ScanStats(
        query=query,
        root=str(root),
        generated_at=generated_at,
        scanned_files=scanned_files,
        matched_files=len(file_matches),
        total_matches=total_matches,
        top_directories=directory_counter.most_common(5),
        top_extensions=extension_counter.most_common(5),
        top_files=top_files,
        explanation=explanation,
    )


def build_explanation(query: str, scanned_files: int, total_matches: int, file_matches: list[FileMatch], directory_counter: Counter[str]) -> list[str]:
    if not file_matches:
        return [
            f'No matches were found for `{query}` in the scanned cento source set.',
            f'The scan covered {scanned_files} text files after excluding generated and runtime-heavy directories such as `.git`, `workspace`, and `logs`.',
        ]

    lines = [
        f'The scan found {total_matches} matches across {len(file_matches)} files, which means `{query}` is materially present in cento rather than appearing as a one-off reference.',
    ]
    strongest_file = file_matches[0]
    lines.append(
        f'The heaviest concentration is in `{strongest_file.relative_path}`, so that file is the best starting point if you want to change or understand this area quickly.'
    )
    if directory_counter:
        top_dir, top_count = directory_counter.most_common(1)[0]
        label = {
            'scripts': 'implementation and command wiring',
            'docs': 'documentation coverage',
            'data': 'registry and config metadata',
            'templates': 'template-level behavior',
            'standards': 'repo policy and conventions',
            'mcp': 'MCP-specific setup',
            '.': 'repo-root files',
        }.get(top_dir, f'the `{top_dir}` area')
        lines.append(
            f'Most matches cluster in `{top_dir}` ({top_count} hits), which points to {label} as the main location for this topic.'
        )
    if any(match.relative_path.startswith('docs/') for match in file_matches) and any(match.relative_path.startswith('scripts/') for match in file_matches):
        lines.append('The topic appears in both implementation and docs, so any future change should likely update code and documentation together.')
    return lines


def highlight(text: str, pattern: re.Pattern[str]) -> str:
    escaped = html.escape(text)
    return pattern.sub(lambda m: f'<mark>{html.escape(m.group(0))}</mark>', escaped)


def render_html(stats: ScanStats, pattern: re.Pattern[str], preview_url: str) -> str:
    directory_rows = ''.join(
        f'<li><strong>{html.escape(name)}</strong><span>{count} hits</span></li>' for name, count in stats.top_directories
    ) or '<li><strong>none</strong><span>0 hits</span></li>'
    extension_rows = ''.join(
        f'<li><strong>{html.escape(name)}</strong><span>{count} hits</span></li>' for name, count in stats.top_extensions
    ) or '<li><strong>none</strong><span>0 hits</span></li>'
    file_cards: list[str] = []
    for item in stats.top_files:
        snippet_rows = ''.join(
            f'<div class="snippet"><span class="line">L{snippet.line_number}</span><code>{highlight(snippet.text, pattern)}</code></div>'
            for snippet in item.snippets
        )
        file_cards.append(
            f'''<article class="card">
<h3>{html.escape(item.relative_path)}</h3>
<p class="meta">{item.count} matches · {html.escape(item.category)} · {html.escape(item.extension)}</p>
<p class="path">{html.escape(item.absolute_path)}</p>
{snippet_rows}
</article>'''
        )
    file_cards_html = ''.join(file_cards) or '<article class="card"><h3>No files matched</h3></article>'
    explanation_html = ''.join(f'<p>{html.escape(line)}</p>' for line in stats.explanation)
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Cento Scan · {html.escape(stats.query)}</title>
  <style>
    :root {{
      --bg: #f4efe7;
      --ink: #142127;
      --muted: #58686d;
      --card: rgba(255,255,255,0.82);
      --accent: #b85f2e;
      --accent-soft: #ead4c7;
      --line: rgba(20,33,39,0.12);
      --shadow: 0 24px 60px rgba(20,33,39,0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
      background:
        radial-gradient(circle at top left, rgba(184,95,46,0.18), transparent 30%),
        linear-gradient(160deg, #f6f0e8 0%, #efe6da 48%, #e8ddd0 100%);
      color: var(--ink);
    }}
    .page {{ max-width: 1180px; margin: 0 auto; padding: 40px 24px 56px; }}
    .hero {{
      display: grid;
      gap: 18px;
      padding: 28px;
      border: 1px solid var(--line);
      border-radius: 28px;
      background: rgba(255,255,255,0.68);
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
    }}
    .eyebrow {{ letter-spacing: 0.16em; text-transform: uppercase; color: var(--muted); font-size: 12px; }}
    h1 {{ margin: 0; font-size: clamp(36px, 7vw, 74px); line-height: 0.92; }}
    .hero p {{ margin: 0; font-size: 18px; max-width: 760px; color: var(--muted); }}
    .query {{ display: inline-flex; width: fit-content; padding: 10px 14px; border-radius: 999px; background: var(--accent-soft); color: var(--accent); font-weight: 700; }}
    .link {{ color: var(--accent); font-weight: 700; text-decoration: none; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; margin-top: 24px; }}
    .stat, .panel, .card {{ border: 1px solid var(--line); border-radius: 22px; background: var(--card); box-shadow: var(--shadow); }}
    .stat {{ padding: 18px; }}
    .stat strong {{ display: block; font-size: 34px; }}
    .stat span {{ color: var(--muted); font-size: 13px; text-transform: uppercase; letter-spacing: 0.08em; }}
    .grid {{ display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 18px; margin-top: 18px; }}
    .panel {{ padding: 22px; }}
    .panel h2 {{ margin: 0 0 12px; font-size: 20px; }}
    .panel p {{ margin: 0 0 10px; color: var(--muted); line-height: 1.5; }}
    .panel ul {{ list-style: none; padding: 0; margin: 0; display: grid; gap: 10px; }}
    .panel li {{ display: flex; justify-content: space-between; gap: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--line); }}
    .panel li:last-child {{ border-bottom: 0; padding-bottom: 0; }}
    .results {{ display: grid; gap: 16px; margin-top: 18px; }}
    .card {{ padding: 22px; }}
    .card h3 {{ margin: 0 0 8px; font-size: 24px; }}
    .meta, .path {{ margin: 0 0 10px; color: var(--muted); }}
    .path {{ font-size: 13px; word-break: break-all; }}
    .snippet {{ display: grid; grid-template-columns: 56px 1fr; gap: 12px; padding: 10px 0; border-top: 1px solid var(--line); }}
    .snippet:first-of-type {{ margin-top: 14px; }}
    .line {{ color: var(--accent); font-weight: 700; font-size: 13px; padding-top: 2px; }}
    code {{ font-family: "Berkeley Mono", "JetBrains Mono", "SFMono-Regular", monospace; white-space: pre-wrap; color: var(--ink); }}
    mark {{ background: rgba(184,95,46,0.18); color: var(--accent); padding: 0 3px; border-radius: 4px; }}
    .footer {{ margin-top: 18px; color: var(--muted); font-size: 14px; }}
    @media (max-width: 900px) {{
      .grid {{ grid-template-columns: 1fr; }}
      .page {{ padding: 18px 14px 30px; }}
      .hero, .panel, .card, .stat {{ border-radius: 18px; }}
      .snippet {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <div class="eyebrow">Cento Scan One Pager</div>
      <h1>Repository scan for {html.escape(stats.query)}</h1>
      <div class="query">{html.escape(stats.query)}</div>
      <p>{html.escape(stats.root)}</p>
      <p>Generated {html.escape(stats.generated_at)}. Preview is served at <a class="link" href="{html.escape(preview_url)}">{html.escape(preview_url)}</a>.</p>
    </section>

    <section class="stats">
      <div class="stat"><strong>{stats.scanned_files}</strong><span>Scanned files</span></div>
      <div class="stat"><strong>{stats.matched_files}</strong><span>Matched files</span></div>
      <div class="stat"><strong>{stats.total_matches}</strong><span>Total matches</span></div>
      <div class="stat"><strong>{len(stats.top_directories)}</strong><span>Active directories</span></div>
    </section>

    <section class="grid">
      <div class="panel">
        <h2>Explanation</h2>
        {explanation_html}
      </div>
      <div class="panel">
        <h2>Signal Map</h2>
        <ul>{directory_rows}</ul>
      </div>
    </section>

    <section class="grid">
      <div class="panel">
        <h2>Top file types</h2>
        <ul>{extension_rows}</ul>
      </div>
      <div class="panel">
        <h2>Operating model</h2>
        <p>This page is generated by <code>cento scan</code> from live repo contents.</p>
        <p>The current run writes to <code>workspace/runs/scan-onepager/latest/</code>.</p>
        <p>The previous latest output is moved into <code>workspace/runs/scan-onepager/archive/</code> before a new page is written.</p>
      </div>
    </section>

    <section class="results">
      {file_cards_html}
    </section>

    <div class="footer">Built for fast repo inspection inside cento.</div>
  </main>
</body>
</html>
'''


def maybe_open(url: str) -> None:
    if shutil.which('xdg-open'):
        subprocess.Popen(['xdg-open', url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    if shutil.which('open'):
        subprocess.Popen(['open', url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    webbrowser.open(url)


def is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def can_connect(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


def read_server_meta() -> dict[str, object]:
    if not SERVER_META_PATH.exists():
        return {}
    try:
        return json.loads(SERVER_META_PATH.read_text())
    except json.JSONDecodeError:
        return {}


def write_server_meta(host: str, port: int, pid: int) -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    SERVER_META_PATH.write_text(json.dumps({'host': host, 'port': port, 'pid': pid}, indent=2) + '\n')


def pick_port(host: str, preferred_port: int) -> int:
    for port in range(preferred_port, preferred_port + PORT_SPAN):
        if not can_connect(host, port):
            return port
    raise RuntimeError(f'No free port available in range {preferred_port}-{preferred_port + PORT_SPAN - 1}')


def start_server(host: str, preferred_port: int) -> tuple[str, int]:
    meta = read_server_meta()
    saved_host = str(meta.get('host', ''))
    saved_port = int(meta.get('port', 0) or 0)
    saved_pid = int(meta.get('pid', 0) or 0)
    if saved_host == host and saved_port and saved_pid and is_pid_alive(saved_pid) and can_connect(saved_host, saved_port):
        return saved_host, saved_port

    port = pick_port(host, preferred_port)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    with SERVER_LOG_PATH.open('a', encoding='utf-8') as log_handle:
        process = subprocess.Popen(
            [sys.executable, '-m', 'http.server', str(port), '--bind', host, '--directory', str(SERVER_ROOT)],
            stdout=log_handle,
            stderr=log_handle,
            start_new_session=True,
        )
    for _ in range(20):
        if can_connect(host, port):
            write_server_meta(host, port, process.pid)
            return host, port
        time.sleep(0.1)
    raise RuntimeError(f'Preview server did not start on {host}:{port}')


def write_outputs(output_root: Path, stats: ScanStats, pattern: re.Pattern[str], preview_url: str) -> Path:
    latest_dir = rotate_latest(output_root)
    html_path = latest_dir / 'index.html'
    json_path = latest_dir / 'summary.json'
    html_path.write_text(render_html(stats, pattern, preview_url))
    json_path.write_text(json.dumps({
        'query': stats.query,
        'root': stats.root,
        'generated_at': stats.generated_at,
        'scanned_files': stats.scanned_files,
        'matched_files': stats.matched_files,
        'total_matches': stats.total_matches,
        'preview_url': preview_url,
        'top_directories': stats.top_directories,
        'top_extensions': stats.top_extensions,
        'top_files': [
            {
                'relative_path': item.relative_path,
                'absolute_path': item.absolute_path,
                'count': item.count,
                'category': item.category,
                'extension': item.extension,
                'snippets': [snippet.__dict__ for snippet in item.snippets],
            }
            for item in stats.top_files
        ],
        'explanation': stats.explanation,
    }, indent=2) + '\n')
    return html_path


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f'Root directory does not exist: {root}')
    output_root = Path(args.output_root).resolve()
    pattern = compile_pattern(args.query, args.regex, args.case_sensitive)
    host, port = start_server(args.host, args.port)
    preview_url = f'http://{host}:{port}/'
    stats = scan_files(root, args.query, pattern, args.limit)
    write_outputs(output_root, stats, pattern, preview_url)
    if args.open_browser:
        maybe_open(preview_url)
    print(preview_url)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
