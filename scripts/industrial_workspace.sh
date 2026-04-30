#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
STATE_ROOT="${XDG_STATE_HOME:-$HOME/.local/state}/cento/industrial-os"
WORKSPACE="${CENTO_INDUSTRIAL_WORKSPACE:-1}"
PRESERVE_WORKSPACE="${CENTO_INDUSTRIAL_PRESERVE_WORKSPACE:-9}"
LOG_DIR="$ROOT_DIR/logs/industrial-workspace"
LOG_FILE="$LOG_DIR/$(date '+%Y%m%d-%H%M%S')-industrial-workspace.log"
PANEL_SCRIPT="$ROOT_DIR/scripts/industrial_panel.py"
HERO_ART="${CENTO_INDUSTRIAL_HERO_ART:-$ROOT_DIR/assets/industrial-os/volcano-pane.png}"
TERMINAL_ART="${CENTO_INDUSTRIAL_TERMINAL_ART:-$ROOT_DIR/assets/industrial-os/activity-pane.png}"
JOBS_ART="${CENTO_INDUSTRIAL_JOBS_ART:-$ROOT_DIR/assets/industrial-os/jobs-pane.png}"
CLUSTER_ART="${CENTO_INDUSTRIAL_CLUSTER_ART:-$ROOT_DIR/assets/industrial-os/cluster-pane.png}"
ACTIVITY_ART="${CENTO_INDUSTRIAL_ACTIVITY_ART:-$ROOT_DIR/assets/industrial-os/activity-pane.png}"
AGENTS_ART="${CENTO_INDUSTRIAL_AGENTS_ART:-$ACTIVITY_ART}"
ACTIONS_ART="${CENTO_INDUSTRIAL_ACTIONS_ART:-$ROOT_DIR/assets/industrial-os/actions-pane.png}"
BACKGROUND_MODE="${CENTO_INDUSTRIAL_BACKGROUND_MODE:-images}"
BLACK_ONLY="${CENTO_INDUSTRIAL_BLACK_ONLY:-0}"
TERMINAL_SHELL="${SHELL:-/usr/bin/env bash}"
PANEL_FONT_SIZE="${CENTO_INDUSTRIAL_PANEL_FONT_SIZE:-11.0}"
HERO_FONT_SIZE="${CENTO_INDUSTRIAL_HERO_FONT_SIZE:-9.0}"
TERMINAL_FONT_SIZE="${CENTO_INDUSTRIAL_TERMINAL_FONT_SIZE:-12.0}"
KITTY_PANEL_OPTIONS=(
    -o "font_size=$PANEL_FONT_SIZE"
    -o "window_padding_width=5"
    -o "disable_ligatures=always"
    -o "background_opacity=0.90"
    -o "cursor_blink_interval=0"
    -o "confirm_os_window_close=0"
)
KITTY_TERMINAL_OPTIONS=(
    -o "font_size=$TERMINAL_FONT_SIZE"
    -o "window_padding_width=7"
    -o "background_opacity=0.82"
    -o "background=#180604"
    -o "foreground=#f4e8dc"
    -o "selection_background=#8f1f0a"
    -o "selection_foreground=#050403"
    -o "cursor=#ffb000"
    -o "cursor_text_color=#050403"
    -o "url_color=#ff9a3d"
    -o "color0=#0b0302"
    -o "color1=#ff3500"
    -o "color2=#6be675"
    -o "color3=#ffb000"
    -o "color4=#cf4f2e"
    -o "color5=#d95f2a"
    -o "color6=#e0a070"
    -o "color7=#f4e8dc"
    -o "color8=#6d2618"
    -o "color9=#ff6a00"
    -o "color10=#a4ff9b"
    -o "color11=#ffd166"
    -o "color12=#ff7a3d"
    -o "color13=#ff9a3d"
    -o "color14=#ffd2a6"
    -o "color15=#fff4e8"
    -o "cursor_blink_interval=0"
    -o "confirm_os_window_close=0"
)

GENERATED_CLASSES=(
    "cento-industrial-hero"
    "cento-industrial-terminal"
    "cento-industrial-jobs"
    "cento-industrial-cluster"
    "cento-industrial-agents"
    "cento-industrial-actions"
)

usage() {
    cat <<'USAGE'
Usage: industrial_workspace.sh [options]

Options:
  --workspace NAME_OR_NUMBER     Workspace to compose. Default: 1
  --preserve-workspace NAME      Where non-preset windows from workspace 1 are moved. Default: 9
  --backgrounds images|black     Use pane images or plain black backgrounds. Default: images
  --black-only                   Alias for --backgrounds black
  -h, --help                     Show this help.
USAGE
}

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S %z')" "$*"
}

init_logging() {
    cento_ensure_dir "$LOG_DIR"
    cento_ensure_dir "$STATE_ROOT"
    exec > >(tee -a "$LOG_FILE") 2>&1
    ln -sfn "$LOG_FILE" "$LOG_DIR/latest.log"
    log "Log file: $LOG_FILE"
}

run_i3() {
    local command=$1
    log "i3-msg $command"
    i3-msg "$command" >/dev/null
}

tree_file() {
    local name=$1
    printf '%s/%s.json' "$STATE_ROOT" "$name"
}

window_id_for_class() {
    local klass=$1
    local tree
    tree=$(tree_file "i3-tree-class")
    i3-msg -t get_tree > "$tree"
    python3 - "$klass" "$tree" <<'PY'
import json
import sys
from pathlib import Path

target = sys.argv[1].lower()
tree = json.loads(Path(sys.argv[2]).read_text())


def walk(node):
    props = node.get("window_properties") or {}
    if props.get("class", "").lower() == target and node.get("window") is not None:
        print(node["id"])
        raise SystemExit(0)
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        walk(child)


walk(tree)
raise SystemExit(1)
PY
}

wait_for_class() {
    local klass=$1
    local con_id=""
    local attempt
    for attempt in {1..50}; do
        con_id=$(window_id_for_class "$klass" 2>/dev/null || true)
        if [[ -n "$con_id" ]]; then
            printf '%s\n' "$con_id"
            return 0
        fi
        sleep 0.2
    done
    return 1
}

move_existing_workspace_windows() {
    local tree
    tree=$(tree_file "i3-tree-preserve")
    i3-msg -t get_tree > "$tree"
    python3 - "$WORKSPACE" "$tree" <<'PY' | while IFS=$'\t' read -r con_id title klass; do
import json
import sys
from pathlib import Path

workspace = sys.argv[1]
tree = json.loads(Path(sys.argv[2]).read_text())


def workspace_matches(name):
    return name == workspace or name.startswith(f"{workspace}:")


def walk(node):
    if node.get("type") == "workspace" and workspace_matches(node.get("name", "")):
        collect(node)
        return
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        walk(child)


def collect(node):
    if node.get("window") is not None:
        props = node.get("window_properties") or {}
        klass = props.get("class") or ""
        title = props.get("title") or node.get("name") or ""
        lower = klass.lower()
        title_lower = title.lower()
        if (
            lower == "discord"
            or lower.startswith("cento-industrial-")
            or title_lower == "discord"
            or title_lower.startswith("[class=")
        ):
            return
        print(f"{node['id']}\t{title}\t{klass}")
        return
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        collect(child)


walk(tree)
PY
        [[ -n "$con_id" ]] || continue
        log "Preserving workspace $WORKSPACE window on $PRESERVE_WORKSPACE: $klass $title"
        i3-msg "[con_id=$con_id] move container to workspace number $PRESERVE_WORKSPACE" >/dev/null || true
    done
}

clear_stale_placeholders() {
    local tree
    tree=$(tree_file "i3-tree-placeholders")
    i3-msg -t get_tree > "$tree"
    python3 - "$WORKSPACE" "$PRESERVE_WORKSPACE" "$tree" <<'PY' | while IFS=$'\t' read -r con_id title; do
import json
import sys
from pathlib import Path

workspace = sys.argv[1]
preserve_workspace = sys.argv[2]
tree = json.loads(Path(sys.argv[3]).read_text())
placeholder_names = {
    "discord",
    "industrial hero",
    "terminal",
    "jobs dashboard",
    "cluster status",
    "system resources",
    "activity feed",
    "agent runs",
    "quick actions",
}


def workspace_matches(name):
    return (
        name == workspace
        or name == preserve_workspace
        or name.startswith(f"{workspace}:")
        or name.startswith(f"{preserve_workspace}:")
    )


def walk(node, current_workspace=""):
    if node.get("type") == "workspace":
        current_workspace = node.get("name") or ""
    title = node.get("name") or ""
    lowered = title.lower()
    props = node.get("window_properties") or {}
    klass = props.get("class") or ""
    is_placeholder = node.get("window") is None and node.get("type") == "con"
    is_stale_window = node.get("window") is not None and not klass
    if current_workspace and workspace_matches(current_workspace) and (is_placeholder or is_stale_window):
        if (
            lowered in placeholder_names
            or "cento-industrial-" in lowered
            or "(?i)^discord$" in lowered
            or lowered.startswith("[class=")
        ):
            print(f"{node['id']}\t{title}")
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        walk(child, current_workspace)


walk(tree)
PY
        [[ -n "$con_id" ]] || continue
        log "Closing stale Industrial OS placeholder: $title"
        i3-msg "[con_id=$con_id] focus" >/dev/null 2>&1 || true
        i3-msg "kill" >/dev/null 2>&1 || true
    done
}

close_generated_panes() {
    local -a pids=()
    mapfile -t pids < <(pgrep -f '(^|[ /])kitty( |$).*--class[= ]cento-industrial-' || true)
    if [[ ${#pids[@]} -gt 0 ]]; then
        log "Stopping ${#pids[@]} stale Industrial OS Kitty panes"
        kill "${pids[@]}" >/dev/null 2>&1 || true
    fi

    local klass
    local attempt
    for attempt in {1..30}; do
        local remaining=0
        for klass in "${GENERATED_CLASSES[@]}"; do
            if window_id_for_class "$klass" >/dev/null 2>&1; then
                remaining=1
                break
            fi
        done
        [[ "$remaining" -eq 0 ]] && break
        sleep 0.2
    done

    clear_stale_placeholders
    sleep 0.2
}

backgrounds_enabled() {
    [[ "$BLACK_ONLY" != "1" ]] || return 1
    case "$BACKGROUND_MODE" in
        black|none|off|0|false) return 1 ;;
        *) return 0 ;;
    esac
}

panel_art() {
    case "$1" in
        hero) printf '%s\n' "$HERO_ART" ;;
        terminal) printf '%s\n' "$TERMINAL_ART" ;;
        jobs) printf '%s\n' "$JOBS_ART" ;;
        cluster) printf '%s\n' "$CLUSTER_ART" ;;
        activity) printf '%s\n' "$ACTIVITY_ART" ;;
        agents) printf '%s\n' "$AGENTS_ART" ;;
        actions) printf '%s\n' "$ACTIONS_ART" ;;
        *) return 1 ;;
    esac
}

append_background_options() {
    local panel=$1
    local tint=${2:-0.88}
    local art
    art=$(panel_art "$panel" 2>/dev/null || true)
    if backgrounds_enabled && [[ -n "$art" && -f "$art" ]]; then
        options+=(
            -o "background_opacity=1.0"
            -o "background=#050403"
            -o "background_image=$art"
            -o "background_image_layout=cscaled"
            -o "background_image_linear=yes"
            -o "background_tint=$tint"
        )
    else
        options+=(
            -o "background_opacity=1.0"
            -o "background=#050403"
            -o "background_image=none"
        )
    fi
}

append_solid_background_options() {
    options+=(
        -o "background_opacity=1.0"
        -o "background=#050403"
        -o "background_image=none"
    )
}

launch_panel() {
    local klass=$1
    local title=$2
    local panel=$3
    local -a options=("${KITTY_PANEL_OPTIONS[@]}")
    local -a command=(env CENTO_INDUSTRIAL_HERO_BACKGROUND=0 python3 "$PANEL_SCRIPT" "$panel")
    if [[ "$panel" == "hero" ]]; then
        options=(
            -o "font_size=$HERO_FONT_SIZE"
            -o "window_padding_width=5"
            -o "foreground=#f4e8dc"
            -o "selection_background=#8f1f0a"
            -o "selection_foreground=#050403"
            -o "cursor=#ffb000"
            -o "cursor_text_color=#050403"
            -o "url_color=#ff9a3d"
            -o "cursor_blink_interval=0"
            -o "confirm_os_window_close=0"
        )
        append_background_options "$panel" "0.90"
        command=(env CENTO_INDUSTRIAL_HERO_BACKGROUND=1 python3 "$PANEL_SCRIPT" "$panel")
    elif [[ "$panel" == "jobs" ]]; then
        append_background_options "$panel" "0.92"
        command=("$ROOT_DIR/scripts/industrial_jobs_tui.sh")
    elif [[ "$panel" == "cluster" ]]; then
        append_background_options "$panel" "0.90"
        command=("$ROOT_DIR/scripts/industrial_cluster_tui.sh")
    elif [[ "$panel" == "agents" ]]; then
        append_solid_background_options
        command=("$ROOT_DIR/scripts/industrial_aux_tui.sh" "$panel")
    elif [[ "$panel" == "activity" || "$panel" == "actions" ]]; then
        append_background_options "$panel" "0.92"
        command=("$ROOT_DIR/scripts/industrial_aux_tui.sh" "$panel")
    fi
    setsid -f kitty \
        "${options[@]}" \
        --class "$klass" \
        --title "$title" \
        --working-directory "$ROOT_DIR" \
        "${command[@]}" >/dev/null 2>&1 || true
}

launch_terminal() {
    local -a options=("${KITTY_TERMINAL_OPTIONS[@]}")
    append_background_options "terminal" "0.94"
    setsid -f kitty \
        "${options[@]}" \
        --class "cento-industrial-terminal" \
        --title "cento terminal" \
        --working-directory "$HOME" \
        "$ROOT_DIR/scripts/industrial_codex_terminal.sh" >/dev/null 2>&1 || true
}

ensure_discord() {
    if window_id_for_class "discord" >/dev/null 2>&1; then
        run_i3 "[class=\"(?i)^discord$\"] move container to workspace number $WORKSPACE"
        return
    fi
    if command -v discord >/dev/null 2>&1; then
        log "Launching Discord"
        setsid -f discord >/dev/null 2>&1 || true
    else
        log "Discord command not found; continuing without Discord"
    fi
}

ensure_all_windows() {
    run_i3 "workspace number $WORKSPACE"
    ensure_discord
    launch_panel "cento-industrial-hero" "industrial os" "hero"
    launch_terminal
    launch_panel "cento-industrial-jobs" "jobs dashboard" "jobs"
    launch_panel "cento-industrial-cluster" "cluster status" "cluster"
    launch_panel "cento-industrial-agents" "agent runs" "agents"
    launch_panel "cento-industrial-actions" "quick actions" "actions"

    local klass
    for klass in "discord" "${GENERATED_CLASSES[@]}"; do
        if ! wait_for_class "$klass" >/dev/null; then
            log "Window class not detected before layout: $klass"
        fi
    done
}

tile_geometries() {
    local tree
    tree=$(tree_file "i3-tree-layout")
    i3-msg -t get_tree > "$tree"
    python3 - "$WORKSPACE" "$tree" <<'PY'
import json
import sys
from pathlib import Path

workspace = sys.argv[1]
tree = json.loads(Path(sys.argv[2]).read_text())


def workspace_matches(name):
    return name == workspace or name.startswith(f"{workspace}:")


def find_workspace(node):
    if node.get("type") == "workspace" and workspace_matches(node.get("name", "")):
        return node
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        found = find_workspace(child)
        if found:
            return found
    return None


def row(classes, ratios, x, y, width, height, gap):
    usable = max(1, width - gap * (len(classes) - 1))
    left = x
    for index, (klass, ratio) in enumerate(zip(classes, ratios)):
        if index == len(classes) - 1:
            tile_width = max(80, x + width - left)
        else:
            tile_width = max(80, round(usable * ratio))
        print(f"{klass}\t{left}\t{y}\t{tile_width}\t{height}")
        left += tile_width + gap


workspace_node = find_workspace(tree)
if not workspace_node:
    raise SystemExit("workspace not found")

rect = workspace_node.get("rect") or {}
outer = 5
gap = 6
x = int(rect.get("x", 0)) + outer
y = int(rect.get("y", 0)) + outer
width = max(960, int(rect.get("width", 1920)) - outer * 2)
height = max(640, int(rect.get("height", 1080)) - outer * 2)
top_height = round((height - gap) * 0.68)
bottom_height = height - top_height - gap
if bottom_height < 190:
    bottom_height = 190
    top_height = max(280, height - bottom_height - gap)

row(
    ["discord", "cento-industrial-hero", "cento-industrial-terminal"],
    [0.31, 0.39, 0.30],
    x,
    y,
    width,
    top_height,
    gap,
)
row(
    [
        "cento-industrial-jobs",
        "cento-industrial-cluster",
        "cento-industrial-agents",
        "cento-industrial-actions",
    ],
    [0.34, 0.22, 0.22, 0.22],
    x,
    y + top_height + gap,
    width,
    bottom_height,
    gap,
)
PY
}

tile_geometries_after_discord() {
    local tree
    tree=$(tree_file "i3-tree-layout-adjusted")
    i3-msg -t get_tree > "$tree"
    python3 - "$WORKSPACE" "$tree" <<'PY'
import json
import sys
from pathlib import Path

workspace = sys.argv[1]
tree = json.loads(Path(sys.argv[2]).read_text())


def workspace_matches(name):
    return name == workspace or name.startswith(f"{workspace}:")


def find_workspace(node):
    if node.get("type") == "workspace" and workspace_matches(node.get("name", "")):
        return node
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        found = find_workspace(child)
        if found:
            return found
    return None


def find_class(node, klass):
    props = node.get("window_properties") or {}
    if props.get("class", "").lower() == klass and node.get("window") is not None:
        return node
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        found = find_class(child, klass)
        if found:
            return found
    return None


def row(classes, ratios, x, y, width, height, gap):
    usable = max(1, width - gap * (len(classes) - 1))
    left = x
    for index, (klass, ratio) in enumerate(zip(classes, ratios)):
        if index == len(classes) - 1:
            tile_width = max(80, x + width - left)
        else:
            tile_width = max(80, round(usable * ratio))
        print(f"{klass}\t{left}\t{y}\t{tile_width}\t{height}")
        left += tile_width + gap


workspace_node = find_workspace(tree)
if not workspace_node:
    raise SystemExit("workspace not found")

rect = workspace_node.get("rect") or {}
outer = 5
gap = 6
x = int(rect.get("x", 0)) + outer
y = int(rect.get("y", 0)) + outer
width = max(960, int(rect.get("width", 1920)) - outer * 2)
height = max(640, int(rect.get("height", 1080)) - outer * 2)
top_height = round((height - gap) * 0.68)
bottom_height = height - top_height - gap
if bottom_height < 190:
    bottom_height = 190
    top_height = max(280, height - bottom_height - gap)

discord = find_class(workspace_node, "discord")
desired_discord_width = round((width - gap * 2) * 0.31)
discord_right = x + desired_discord_width
if discord:
    drect = discord.get("rect") or {}
    discord_right = max(discord_right, int(drect.get("x", x)) + int(drect.get("width", 0)))

right_edge = x + width
remaining = max(640, right_edge - discord_right - gap)
hero_width = max(320, round((remaining - gap) * 0.58))
terminal_width = max(320, right_edge - (discord_right + gap) - hero_width - gap)
hero_x = discord_right + gap
terminal_x = hero_x + hero_width + gap
if terminal_x + terminal_width > right_edge:
    terminal_width = max(320, right_edge - terminal_x)

print(f"cento-industrial-hero\t{hero_x}\t{y}\t{hero_width}\t{top_height}")
print(f"cento-industrial-terminal\t{terminal_x}\t{y}\t{terminal_width}\t{top_height}")
row(
    [
        "cento-industrial-jobs",
        "cento-industrial-cluster",
        "cento-industrial-agents",
        "cento-industrial-actions",
    ],
    [0.34, 0.22, 0.22, 0.22],
    x,
    y + top_height + gap,
    width,
    bottom_height,
    gap,
)
PY
}

place_window() {
    local klass=$1
    local x=$2
    local y=$3
    local width=$4
    local height=$5
    local con_id
    con_id=$(window_id_for_class "$klass" 2>/dev/null || true)
    if [[ -z "$con_id" ]]; then
        log "Skipping missing window class: $klass"
        return
    fi

    run_i3 "[con_id=$con_id] move container to workspace number $WORKSPACE"
    run_i3 "[con_id=$con_id] floating enable"
    run_i3 "[con_id=$con_id] border pixel 4"
    run_i3 "[con_id=$con_id] resize set $width px $height px"
    run_i3 "[con_id=$con_id] move position $x px $y px"
}

focus_window() {
    local klass=$1
    local con_id
    con_id=$(window_id_for_class "$klass" 2>/dev/null || true)
    if [[ -n "$con_id" ]]; then
        run_i3 "[con_id=$con_id] focus"
    fi
}

arrange_tiles() {
    run_i3 "workspace number $WORKSPACE"
    while IFS=$'\t' read -r klass x y width height; do
        [[ -n "$klass" ]] || continue
        [[ "$klass" == "discord" ]] || continue
        place_window "$klass" "$x" "$y" "$width" "$height"
    done < <(tile_geometries)
    while IFS=$'\t' read -r klass x y width height; do
        [[ -n "$klass" ]] || continue
        place_window "$klass" "$x" "$y" "$width" "$height"
    done < <(tile_geometries_after_discord)
    run_i3 "workspace number $WORKSPACE"
    focus_window "cento-industrial-terminal"
}

compose_workspace() {
    cento_require_cmd i3-msg
    cento_require_cmd kitty
    cento_require_cmd python3
    close_generated_panes
    move_existing_workspace_windows
    clear_stale_placeholders
    ensure_all_windows
    arrange_tiles
    log "Industrial workspace $WORKSPACE composed"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --workspace)
            WORKSPACE=$2
            shift 2
            ;;
        --preserve-workspace)
            PRESERVE_WORKSPACE=$2
            shift 2
            ;;
        --backgrounds)
            BACKGROUND_MODE=$2
            shift 2
            ;;
        --black-only)
            BACKGROUND_MODE=black
            BLACK_ONLY=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            cento_die "Unknown argument: $1"
            ;;
    esac
done

init_logging
compose_workspace
