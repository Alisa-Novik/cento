#!/usr/bin/env bash

set -euo pipefail

COPY_FILE="/home/alice/projects/cento/workspace/runs/temp/cento-ultimate-ai-reference.md"

if [[ $# -ne 1 || "${1:-}" != "run" ]]; then
  printf 'Usage: cento temp run\n' >&2
  exit 2
fi

if [[ ! -f "$COPY_FILE" ]]; then
  printf 'Cento temp copy file is missing: %s\n' "$COPY_FILE" >&2
  exit 1
fi

if ! command -v pbcopy >/dev/null 2>&1; then
  printf 'pbcopy is not available on PATH.\n' >&2
  exit 1
fi

pbcopy < "$COPY_FILE"
printf 'Copied: %s\n' "$COPY_FILE"
