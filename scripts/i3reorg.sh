#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

DRY_RUN=0
FOCUS_WORKSPACE=""
BOTTOM_OUTPUT=""
TOP_OUTPUT=""
INITIAL_WORKSPACE=""
STUDY_MODE=0
STUDY_WORKSPACE="L2"
STUDY_URL="https://www.youtube.com/watch?v=QYpDQxHfTPk"
STUDY_TITLE_CRITERION='[class="(?i)^(firefox|firefox_firefox|navigator)$" title="(?i).*(study with me|abao|tokyo|QYpDQxHfTPk).*YouTube.*"]'
STUDY_MARK="cento_study"

usage() {
    cat <<'USAGE'
Usage: i3reorg.sh [options]

Move common desktop apps onto the expected i3 workspaces:
  1  Firefox
  2  terminals used for tmux, nvim, and shell work
  4  Discord
  5  Telegram

Study mode keeps the Abao/Tokyo study-with-me YouTube window on the top
monitor in workspace L2, fullscreen.

Options:
  --dry-run            Print the i3-msg commands without running them
  --focus WORKSPACE    Focus a workspace after moving windows
  --bottom-output OUT   Force the output that should hold workspaces 1-5
  --top-output OUT      Force the output that should hold study workspace L2
  --study              Put the study YouTube window on L2 fullscreen
  --study-workspace WS Override the study workspace name
  --study-url URL      URL documented/opened for the study video
  -h, --help           Show this help
USAGE
}

run_i3() {
    local command=$1
    if [[ "$DRY_RUN" -eq 1 ]]; then
        printf 'i3-msg %q\n' "$command"
        return 0
    fi

    local output
    if output=$(i3-msg "$command" 2>&1); then
        return 0
    fi

    if [[ "$output" == *"Nothing to move"* ]]; then
        return 0
    fi

    printf '%s\n' "$output" >&2
    return 1
}

move_to_workspace() {
    local workspace=$1
    shift

    local criterion
    for criterion in "$@"; do
        run_i3 "$criterion move container to workspace number $workspace"
    done
}

detect_bottom_output() {
    i3-msg -t get_outputs | python3 -c '
import json
import sys

outputs = [
    item for item in json.load(sys.stdin)
    if item.get("active") and item.get("rect")
]
if not outputs:
    raise SystemExit("no active i3 outputs found")

bottom = max(
    outputs,
    key=lambda item: (
        item["rect"].get("y", 0),
        item["rect"].get("height", 0),
        item["rect"].get("width", 0),
    ),
)
print(bottom["name"])
'
}

detect_top_output() {
    i3-msg -t get_outputs | python3 -c '
import json
import sys

outputs = [
    item for item in json.load(sys.stdin)
    if item.get("active") and item.get("rect")
]
if not outputs:
    raise SystemExit("no active i3 outputs found")

top = min(
    outputs,
    key=lambda item: (
        item["rect"].get("y", 0),
        item["rect"].get("height", 0),
        item["rect"].get("width", 0),
    ),
)
print(top["name"])
'
}

detect_focused_workspace() {
    i3-msg -t get_workspaces | python3 -c '
import json
import sys

for workspace in json.load(sys.stdin):
    if workspace.get("focused"):
        print(workspace["name"])
        raise SystemExit(0)
raise SystemExit("no focused workspace found")
'
}

study_window_exists() {
    i3-msg -t get_tree | python3 -c '
import json
import re
import sys

tree = json.load(sys.stdin)
class_re = re.compile(r"^(firefox|firefox_firefox|navigator)$", re.I)
title_re = re.compile(r"(study with me|abao|tokyo|QYpDQxHfTPk).*YouTube", re.I)

def walk(node):
    props = node.get("window_properties") or {}
    title = props.get("title") or node.get("name") or ""
    class_name = props.get("class") or ""
    if class_re.search(class_name) and title_re.search(title):
        return True
    return any(walk(child) for child in node.get("nodes", []) + node.get("floating_nodes", []))

raise SystemExit(0 if walk(tree) else 1)
'
}

anchor_workspace_to_bottom() {
    local workspace=$1
    run_i3 "workspace number $workspace; move workspace to output $BOTTOM_OUTPUT"
}

ensure_study_window() {
    if study_window_exists; then
        return 0
    fi

    if [[ "$DRY_RUN" -eq 1 ]]; then
        printf 'firefox --new-window %q\n' "$STUDY_URL"
        printf 'i3-msg %q\n' "mark --replace $STUDY_MARK"
        return 0
    fi

    cento_have_cmd firefox || cento_die "Study window not found and firefox is not available to open $STUDY_URL"
    setsid firefox --new-window "$STUDY_URL" >/dev/null 2>&1 &
    sleep 3
    run_i3 "mark --replace $STUDY_MARK"
}

place_study_window() {
    ensure_study_window
    run_i3 "workspace $STUDY_WORKSPACE; move workspace to output $TOP_OUTPUT"
    run_i3 "$STUDY_TITLE_CRITERION move container to workspace $STUDY_WORKSPACE"
    run_i3 "[con_mark=\"$STUDY_MARK\"] move container to workspace $STUDY_WORKSPACE"
    run_i3 "$STUDY_TITLE_CRITERION fullscreen enable"
    run_i3 "[con_mark=\"$STUDY_MARK\"] fullscreen enable"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --focus)
            [[ $# -ge 2 ]] || cento_die "--focus requires a workspace number"
            FOCUS_WORKSPACE=$2
            shift 2
            ;;
        --bottom-output)
            [[ $# -ge 2 ]] || cento_die "--bottom-output requires an output name"
            BOTTOM_OUTPUT=$2
            shift 2
            ;;
        --top-output)
            [[ $# -ge 2 ]] || cento_die "--top-output requires an output name"
            TOP_OUTPUT=$2
            shift 2
            ;;
        --study)
            STUDY_MODE=1
            shift
            ;;
        --study-workspace)
            [[ $# -ge 2 ]] || cento_die "--study-workspace requires a workspace name"
            STUDY_WORKSPACE=$2
            shift 2
            ;;
        --study-url)
            [[ $# -ge 2 ]] || cento_die "--study-url requires a URL"
            STUDY_URL=$2
            shift 2
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

if [[ "$DRY_RUN" -eq 0 ]]; then
    cento_require_cmd i3-msg
    cento_require_cmd python3
    INITIAL_WORKSPACE=$(detect_focused_workspace)
fi

if [[ -z "$BOTTOM_OUTPUT" ]]; then
    if [[ "$DRY_RUN" -eq 1 ]] && ! cento_have_cmd i3-msg; then
        BOTTOM_OUTPUT="<bottom-output>"
    else
        cento_require_cmd i3-msg
        cento_require_cmd python3
        BOTTOM_OUTPUT=$(detect_bottom_output)
    fi
fi

if [[ "$STUDY_MODE" -eq 1 && -z "$TOP_OUTPUT" ]]; then
    if [[ "$DRY_RUN" -eq 1 ]] && ! cento_have_cmd i3-msg; then
        TOP_OUTPUT="<top-output>"
    else
        cento_require_cmd i3-msg
        cento_require_cmd python3
        TOP_OUTPUT=$(detect_top_output)
    fi
fi

for workspace in 1 2 3 4 5; do
    anchor_workspace_to_bottom "$workspace"
done

move_to_workspace 1 \
    '[class="(?i)^(firefox|firefox_firefox|navigator)$"]' \
    '[instance="(?i)^firefox$"]'

move_to_workspace 2 \
    '[class="(?i)^(kitty|alacritty|gnome-terminal|gnome-terminal-server|xterm|urxvt|rxvt|wezterm|org.wezfurlong.wezterm|foot)$"]' \
    '[title="(?i).*(tmux|nvim|vim).*"]'

move_to_workspace 4 \
    '[class="(?i)^discord$"]' \
    '[instance="(?i)^discord$"]'

move_to_workspace 5 \
    '[class="(?i)^(telegramdesktop|telegram-desktop)$"]' \
    '[instance="(?i)^(telegramdesktop|telegram-desktop)$"]'

if [[ "$STUDY_MODE" -eq 1 ]]; then
    place_study_window
fi

if [[ -n "$FOCUS_WORKSPACE" ]]; then
    run_i3 "workspace number $FOCUS_WORKSPACE"
elif [[ -n "$INITIAL_WORKSPACE" ]]; then
    run_i3 "workspace $INITIAL_WORKSPACE"
fi

printf 'Reorganized i3 windows on %s: 1=Firefox, 2=terminals, 4=Discord, 5=Telegram\n' "$BOTTOM_OUTPUT"
if [[ "$STUDY_MODE" -eq 1 ]]; then
    printf 'Study mode: %s on %s at %s (%s)\n' "$STUDY_WORKSPACE" "$TOP_OUTPUT" "$STUDY_TITLE_CRITERION" "$STUDY_URL"
fi
