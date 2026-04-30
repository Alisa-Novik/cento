#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)

render_hero() {
    local columns=$1
    local lines=$2
    cd "$ROOT_DIR"
    COLUMNS=$columns \
    LINES=$lines \
    CENTO_INDUSTRIAL_HERO_BACKGROUND=1 \
    PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
    python3 "$SCRIPT_DIR/industrial_panel.py" hero --once --plain
}

assert_widths() {
    local columns=$1
    python3 -c '
from __future__ import annotations

import sys
import unicodedata

limit = int(sys.argv[1])
payload = sys.stdin.read().splitlines()


def char_width(char: str) -> int:
    codepoint = ord(char)
    if codepoint == 0 or codepoint < 32 or 0x7F <= codepoint < 0xA0:
        return 0
    if unicodedata.combining(char):
        return 0
    if 0xFE00 <= codepoint <= 0xFE0F:
        return 0
    if unicodedata.east_asian_width(char) in {"F", "W"}:
        return 2
    return 1


for number, line in enumerate(payload, 1):
    width = sum(char_width(char) for char in line)
    if width > limit:
        raise SystemExit(f"line {number} is {width} cells, expected <= {limit}: {line}")
' "$columns"
}

output=$(render_hero 120 48)
assert_widths 120 <<<"$output"

grep -Fq 'MISSION CONTROL // CENTRAL ACTION PANE' <<<"$output"
grep -Fq 'not a dashboard - an action router for the whole cockpit' <<<"$output"
grep -Fq 'MISSION BRIEF' <<<"$output"
grep -Fq 'ACTIVE WORK QUEUE' <<<"$output"
grep -Fq 'CONTEXT ENGINE' <<<"$output"
grep -Fq 'KEYBOARD / ACTION HUB' <<<"$output"
grep -Fq 'ACTIONS 12 READY' <<<"$output"
grep -Fq 'ACTION › implement action router' <<<"$output"

if grep -Fq '▀' <<<"$output"; then
    printf 'industrial panel e2e failed: hero rendered image blocks\n' >&2
    exit 1
fi

compact_output=$(render_hero 92 38)
assert_widths 92 <<<"$compact_output"
compact_lines=$(wc -l <<<"$compact_output")
if (( compact_lines > 38 )); then
    printf 'industrial panel e2e failed: compact hero uses %s lines\n' "$compact_lines" >&2
    exit 1
fi
grep -Fq 'ACTIVE WORK QUEUE' <<<"$compact_output"
grep -Fq 'CONTEXT ENGINE' <<<"$compact_output"
grep -Fq 'KEYBOARD / ACTION HUB' <<<"$compact_output"

printf 'industrial panel e2e passed\n'
