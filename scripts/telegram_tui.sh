#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
CACHE_DIR="$ROOT_DIR/workspace/tmp/bin"
BINARY="$CACHE_DIR/cento-telegram-tui"
SOURCE_FILE="$ROOT_DIR/scripts/telegram_tui.go"
GO_MOD="$ROOT_DIR/go.mod"
GO_SUM="$ROOT_DIR/go.sum"

cento_require_cmd go
cento_ensure_dir "$CACHE_DIR"
export CENTO_ROOT_DIR="$ROOT_DIR"

if [[ ! -x "$BINARY" || "$SOURCE_FILE" -nt "$BINARY" || "$GO_MOD" -nt "$BINARY" || ( -f "$GO_SUM" && "$GO_SUM" -nt "$BINARY" ) ]]; then
    (cd -- "$ROOT_DIR" && go build -o "$BINARY" ./scripts/telegram_tui.go)
fi

exec "$BINARY" "$@"
