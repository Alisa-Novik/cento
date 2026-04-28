#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
CACHE_DIR="$ROOT_DIR/workspace/tmp/bin"
BINARY="$CACHE_DIR/cento-interactive"
GO_SOURCE="$ROOT_DIR/scripts/cento_interactive.go"
PY_SOURCE="$ROOT_DIR/scripts/cento_interactive.py"
GO_MOD="$ROOT_DIR/go.mod"
GO_SUM="$ROOT_DIR/go.sum"

use_python=0
for arg in "$@"; do
    case "$arg" in
        --json|--path|--entry|--overview|--list)
            use_python=1
            ;;
    esac
done

if [[ "$use_python" -eq 1 ]]; then
    exec python3 "$PY_SOURCE" "$@"
fi

cento_require_cmd go
cento_ensure_dir "$CACHE_DIR"
export CENTO_ROOT_DIR="$ROOT_DIR"

if [[ ! -x "$BINARY" || "$GO_SOURCE" -nt "$BINARY" || "$GO_MOD" -nt "$BINARY" || ( -f "$GO_SUM" && "$GO_SUM" -nt "$BINARY" ) ]]; then
    (cd -- "$ROOT_DIR" && go build -o "$BINARY" ./scripts/cento_interactive.go)
fi

exec "$BINARY" "$@"
