#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
BIN_DIR="$HOME/bin"

need_brew() {
    command -v brew >/dev/null 2>&1 || {
        printf 'Homebrew is required on macOS: https://brew.sh\n' >&2
        exit 1
    }
}

install_formula() {
    local formula=$1
    if ! brew list "$formula" >/dev/null 2>&1; then
        brew install "$formula"
    fi
}

write_wrapper() {
    local path=$1
    local body=$2
    mkdir -p "$BIN_DIR"
    printf '%s\n' "$body" > "$path"
    chmod +x "$path"
}

ensure_path_block() {
    local zshrc="$HOME/.zshrc"
    touch "$zshrc"
    if grep -Fq '":$HOME/bin:"' "$zshrc"; then
        return 0
    fi
    cat >> "$zshrc" <<'EOF_ZSH'

case ":$PATH:" in
  *":$HOME/bin:"*) ;;
  *) export PATH="$HOME/bin:$PATH" ;;
esac
EOF_ZSH
}

main() {
    [[ "$(uname -s)" == "Darwin" ]] || {
        printf 'install_macos.sh must be run on macOS.\n' >&2
        exit 1
    }

    need_brew
    install_formula bash
    install_formula node
    install_formula go
    install_formula ripgrep
    install_formula fd
    install_formula fzf
    install_formula jq

    write_wrapper "$BIN_DIR/cento" "#!/opt/homebrew/bin/bash
set -euo pipefail
export PATH=\"/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:\$PATH\"
exec /opt/homebrew/bin/bash \"$ROOT_DIR/scripts/cento.sh\" \"\$@\""

    write_wrapper "$BIN_DIR/codex-bt-audio-doctor" "#!/opt/homebrew/bin/bash
set -euo pipefail
export PATH=\"/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:\$PATH\"
exec python3 \"$ROOT_DIR/scripts/bluetooth_audio_doctor.py\" \"\$@\""

    write_wrapper "$BIN_DIR/codex-kitty-theme" "#!/opt/homebrew/bin/bash
set -euo pipefail
export PATH=\"/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:\$PATH\"
exec /opt/homebrew/bin/bash \"$ROOT_DIR/scripts/kitty_theme_manager.sh\" \"\$@\""

    ensure_path_block
    "$BIN_DIR/cento" install terminal
    printf 'macOS cento install complete.\n'
}

main "$@"
