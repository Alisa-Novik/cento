#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
TMP_HOME=$(mktemp -d)

cleanup() {
    rm -rf "$TMP_HOME"
}
trap cleanup EXIT

export HOME="$TMP_HOME"
export XDG_CONFIG_HOME="$HOME/.config"
export PATH="$HOME/bin:$PATH"
export TMUX_TMPDIR="$HOME/tmux"
unset TMUX

mkdir -p "$HOME/bin" "$TMUX_TMPDIR"
printf '%s\n' \
    '#!/usr/bin/env bash' \
    'set -euo pipefail' \
    "exec \"$ROOT_DIR/scripts/cento.sh\" \"\$@\"" > "$HOME/bin/cento"
chmod +x "$HOME/bin/cento"

"$ROOT_DIR/scripts/cento.sh" install terminal >/tmp/cento-terminal-e2e-install-1.txt
"$ROOT_DIR/scripts/cento.sh" install terminal >/tmp/cento-terminal-e2e-install-2.txt

[[ -f "$HOME/.config/cento/init.zsh" ]]
[[ -f "$HOME/.config/cento/completions/_cento" ]]
[[ -f "$HOME/.zshrc" ]]

[[ $(grep -c '# >>> cento init >>>' "$HOME/.zshrc") -eq 1 ]]

grep -Fq 'compdef _cento cento' "$HOME/.config/cento/init.zsh"
grep -Fq 'cento_prompt_segment' "$HOME/.config/cento/init.zsh"
grep -Fq '[cento:%s:%s]' "$HOME/.config/cento/init.zsh"

[[ ! -f "$HOME/.config/cento/tmux.conf" ]]

"$ROOT_DIR/scripts/cento.sh" install tmux >/tmp/cento-terminal-e2e-tmux.txt
[[ -f "$HOME/.config/cento/tmux.conf" ]]
[[ -f "$HOME/.tmux.conf" ]]
[[ $(grep -c '# >>> cento tmux >>>' "$HOME/.tmux.conf") -eq 1 ]]
grep -Fq 'source-file' "$HOME/.tmux.conf"
grep -Fq 'cento tmux badge' "$HOME/.config/cento/tmux.conf"
grep -Fq '@cento_status_left_base' "$HOME/.config/cento/tmux.conf"

[[ $("${HOME}/bin/cento" tmux badge) == "cento" ]]
[[ $(CENTO_TMUX_BADGE=lab "${HOME}/bin/cento" tmux badge) == "lab" ]]
[[ $(CENTO_TMUX_BADGE=lab CENTO_TMUX_BADGE_HOST=1 "${HOME}/bin/cento" tmux badge) == lab:* ]]

"$ROOT_DIR/scripts/cento.sh" docs tmux >/tmp/cento-terminal-e2e-docs.txt
"$ROOT_DIR/scripts/cento.sh" tmux status >/tmp/cento-terminal-e2e-status.txt

if command -v zsh >/dev/null 2>&1; then
    zsh -n "$HOME/.config/cento/init.zsh"
fi

printf 'terminal integration e2e passed\n'
