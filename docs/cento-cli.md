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

Built-ins currently documented in JSON:

- `help`
- `interactive`
- `docs`
- `tools`
- `aliases`
- `conf`
- `completion`
- `install`
- `run`

Routing rules:

- `cento TOOL [args...]`
  Dispatch to a registered tool id from `data/tools.json`.
- `cento ALIAS [args...]`
  Dispatch to a configured alias from `~/.config/cento/aliases.sh`.
