#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

TARGET=""
FORCE=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --path)
            TARGET=$2
            shift 2
            ;;
        --force)
            FORCE=1
            shift
            ;;
        *)
            cento_die "Unknown argument: $1"
            ;;
    esac
done

[[ -n "$TARGET" ]] || cento_die "Usage: $0 --path /path/to/project [--force]"

TARGET=$(cento_abs_path "$TARGET")
NAME=$(basename "$TARGET")

if [[ -e "$TARGET" && "$FORCE" -ne 1 && -n "$(find "$TARGET" -mindepth 1 -maxdepth 1 2>/dev/null)" ]]; then
    cento_die "Target exists and is not empty: $TARGET. Use --force to continue."
fi

cento_ensure_dir "$TARGET"
cento_ensure_dir "$TARGET/scripts"
cento_ensure_dir "$TARGET/data"
cento_ensure_dir "$TARGET/docs"
cento_ensure_dir "$TARGET/workspace"

TEMPLATE="$SCRIPT_DIR/../templates/project/README.md"
sed "s/__PROJECT_NAME__/$NAME/g" "$TEMPLATE" >"$TARGET/README.md"

cat >"$TARGET/docs/notes.md" <<EOF
# Notes

- Project: $NAME
- Created: $(date --iso-8601=seconds 2>/dev/null || date)
EOF

cat >"$TARGET/.gitignore" <<'EOF'
workspace/
*.log
EOF

touch "$TARGET/scripts/.gitkeep" "$TARGET/data/.gitkeep" "$TARGET/workspace/.gitkeep"

printf '%s\n' "$TARGET"
