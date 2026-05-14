#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
CACHE_DIR="$ROOT_DIR/workspace/tmp/bin"
BINARY="$CACHE_DIR/cento-industrial-pet-tui"
SOURCE_FILE="$ROOT_DIR/scripts/industrial_pet_tui.go"
DATABASE_FILE="$ROOT_DIR/data/industrial-pet.json"
IMAGE_FILE="$ROOT_DIR/assets/industrial-os/darth-lolipopus.png"
PANE_IMAGE_FILE="$ROOT_DIR/assets/industrial-os/darth-lolipopus-pane.png"
GO_MOD="$ROOT_DIR/go.mod"
GO_SUM="$ROOT_DIR/go.sum"

cento_require_cmd go
cento_ensure_dir "$CACHE_DIR"
export CENTO_ROOT_DIR="$ROOT_DIR"
unset NO_COLOR
export CLICOLOR=1
export CLICOLOR_FORCE=1
export COLORTERM="${COLORTERM:-truecolor}"

if [[ ! -x "$BINARY" || "$SOURCE_FILE" -nt "$BINARY" || "$DATABASE_FILE" -nt "$BINARY" || ( -f "$IMAGE_FILE" && "$IMAGE_FILE" -nt "$BINARY" ) || ( -f "$PANE_IMAGE_FILE" && "$PANE_IMAGE_FILE" -nt "$BINARY" ) || "$GO_MOD" -nt "$BINARY" || ( -f "$GO_SUM" && "$GO_SUM" -nt "$BINARY" ) ]]; then
    (cd -- "$ROOT_DIR" && go build -o "$BINARY" ./scripts/industrial_pet_tui.go)
fi

exec "$BINARY" "$@"
