#!/usr/bin/env bash

set -euo pipefail

unset TMUX TMUX_PANE

target=${CENTO_CODEX_TMUX_SESSION:-}

apply_tmux_theme() {
    local session=$1
    tmux set-option -t "$session" status on \; \
        set-option -t "$session" status-position bottom \; \
        set-option -t "$session" status-style 'bg=#180604,fg=#c49a86' \; \
        set-option -t "$session" status-left-length 26 \; \
        set-option -t "$session" status-left '#[fg=#050403,bg=#ff6a00,bold] #S:#I:#P #[fg=#ff6a00,bg=#180604]> ' \; \
        set-option -t "$session" status-right '#[fg=#ffb000]#(date +%%Y-%%m-%%d" "%%H:%%M) #[fg=#ff7a3d][cento:linux]' \; \
        set-option -t "$session" window-status-format '#[fg=#a77b68] #I:#W ' \; \
        set-option -t "$session" window-status-current-format '#[fg=#050403,bg=#ffb000,bold] #I:#W ' \; \
        set-option -t "$session" pane-border-style 'fg=#7a2b1b' \; \
        set-option -t "$session" pane-active-border-style 'fg=#ff6a00' \; \
        set-option -t "$session" message-style 'bg=#240806,fg=#ffd166' \; \
        set-option -t "$session" mode-style 'bg=#ff6a00,fg=#050403' >/dev/null 2>&1 || true
}

if command -v tmux >/dev/null 2>&1 && tmux list-sessions >/dev/null 2>&1; then
    if [[ -z "$target" ]]; then
        target=$(
            tmux list-panes -a -F '#{session_name}	#{pane_current_command}	#{pane_title}	#{session_attached}	#{session_created}' 2>/dev/null \
                | awk -F '	' 'tolower($2) ~ /^(node|codex)$/ || tolower($3) ~ /codex/' \
                | awk -F '	' '$4 == 0' \
                | sort -t '	' -k5,5nr \
                | awk -F '	' '{ print $1; exit }'
        )
    fi
    if [[ -z "$target" ]]; then
        target=$(
            tmux list-panes -a -F '#{session_name}	#{pane_current_command}	#{pane_title}	#{session_attached}	#{session_created}' 2>/dev/null \
                | awk -F '	' 'tolower($2) ~ /^(node|codex)$/ || tolower($3) ~ /codex/' \
                | sort -t '	' -k5,5nr -k4,4nr \
                | awk -F '	' '{ print $1; exit }'
        )
    fi
    if [[ -z "$target" ]]; then
        target=$(
            tmux list-sessions -F '#{session_name}	#{session_attached}	#{session_created}' 2>/dev/null \
                | sort -t '	' -k3,3nr -k2,2nr \
                | awk -F '	' '{ print $1; exit }'
        )
    fi
    if [[ -n "$target" ]]; then
        apply_tmux_theme "$target"
        exec tmux attach-session -t "$target"
    fi
fi

clear
printf '\033[38;5;202m> INDUSTRIAL TERMINAL\033[0m\n\n'
printf 'No tmux session found for Codex.\n\n'
exec "${SHELL:-/usr/bin/env bash}" -l
