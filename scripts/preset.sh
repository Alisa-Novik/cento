#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

usage() {
    cat <<'USAGE'
Usage: cento preset <command> [args...]

Commands:
  list                         List available presets
  industrial-os [options]      Apply the Industrial OS i3 preset
  industrial [options]         Alias for industrial-os
  apply industrial-os [options]
                               Apply a named preset

Examples:
  cento preset list
  cento preset industrial-os
  cento preset industrial-os --workspace
  cento preset industrial-os --session
  cento preset industrial-os --dashboard-only --open
USAGE
}

list_presets() {
    printf '%-18s  %s\n' "industrial-os" "Black/orange i3 theme, generated wallpaper, Polybar, Rofi, Kitty, and themed dashboard."
}

dispatch_preset() {
    local preset=${1:-}
    shift || true
    case "$preset" in
        industrial-os|industrial)
            exec "$SCRIPT_DIR/industrial_os_preset.sh" "$@"
            ;;
        ""|-h|--help|help)
            usage
            ;;
        *)
            printf 'Unknown preset: %s\n\n' "$preset" >&2
            usage >&2
            exit 1
            ;;
    esac
}

main() {
    local command=${1:-list}
    if [[ $# -gt 0 ]]; then
        shift
    fi

    case "$command" in
        list|ls)
            list_presets
            ;;
        apply)
            dispatch_preset "$@"
            ;;
        industrial-os|industrial)
            dispatch_preset "$command" "$@"
            ;;
        help|-h|--help)
            usage
            ;;
        *)
            printf 'Unknown preset command: %s\n\n' "$command" >&2
            usage >&2
            exit 1
            ;;
    esac
}

main "$@"
