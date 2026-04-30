# Cento CLI

The canonical JSON source for the root `cento` built-in command surface is:

- `data/cento-cli.json`

Use these entrypoints:

- `cento help`
  Print root CLI help.
- `cento docs`
  Print CLI docs from the canonical JSON source.
- `cento docs --json`
  Print the raw JSON source.
- `cento docs --path`
  Print the JSON path.
- `cento docs conf`
  Print docs for one built-in command.
- `cento interactive`
  Open the Bubble Tea TUI for built-ins, tools, and aliases.
- `cento install terminal`
  Install Zsh/Oh My Zsh completion plus the Cento right-prompt segment.
- `cento tmux status`
  Show tmux badge integration state.

Built-ins currently documented in JSON:

- `help`
- `interactive`
- `docs`
- `tools`
- `aliases`
- `conf`
- `completion`
- `install`
- `tmux`
- `run`

Routing rules:

- `cento TOOL [args...]`
  Dispatch to a registered tool id from `data/tools.json`.
- `cento ALIAS [args...]`
  Dispatch to a configured alias from `~/.config/cento/aliases.sh`.

Terminal integration:

- `cento install zsh`
  Writes `~/.config/cento/init.zsh`, installs `_cento`, and appends one guarded
  source block to `~/.zshrc`. The snippet works with plain Zsh and Oh My Zsh
  and adds a right-prompt segment like `[cento:linux:host]`.
- `cento install tmux`
  Writes `~/.config/cento/tmux.conf`, appends one guarded source block to
  `~/.tmux.conf`, and reloads tmux when a server is running.
- `cento install terminal`
  Installs the Zsh/Oh My Zsh prompt and completion path only.

See `docs/terminal-integration.md` for the AI-facing implementation contract
and e2e verification flow.
