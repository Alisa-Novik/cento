#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
BIN_DIR="$HOME/bin"

install_packages() {
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update
        sudo apt-get install -y bash python3 make git curl openssh-client ripgrep fd-find jq fzf nodejs npm golang-go
        return
    fi
    if command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y bash python3 make git curl openssh-clients ripgrep fd-find jq fzf nodejs npm golang
        return
    fi
    printf 'No supported package manager found. Install bash python3 make git curl ssh rg fd jq fzf node/npm go manually.\n' >&2
}

write_wrapper() {
    local path=$1
    local target=$2
    mkdir -p "$BIN_DIR"
    cat > "$path" <<EOF_WRAPPER
#!/usr/bin/env bash
set -euo pipefail
exec "$target" "\$@"
EOF_WRAPPER
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
    [[ "$(uname -s)" == "Linux" ]] || {
        printf 'install_linux.sh must be run on Linux.\n' >&2
        exit 1
    }

    install_packages
    write_wrapper "$BIN_DIR/cento" "$ROOT_DIR/scripts/cento.sh"
    write_wrapper "$BIN_DIR/codex-bt-audio-doctor" "$ROOT_DIR/scripts/bluetooth_audio_doctor.py"
    write_wrapper "$BIN_DIR/codex-kitty-theme" "$ROOT_DIR/scripts/kitty_theme_manager.sh"
    if ! command -v fd >/dev/null 2>&1 && command -v fdfind >/dev/null 2>&1; then
        ln -sfn "$(command -v fdfind)" "$BIN_DIR/fd"
    fi
    ensure_path_block
    "$BIN_DIR/cento" install zsh || true
    printf 'Linux cento install complete.\n'
}

main "$@"
