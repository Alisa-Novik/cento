# cento

`cento` is a local-first Codex automation toolkit project.

It is intentionally usage-agnostic. The repo is meant to hold practical automation building blocks:

- shell scripts
- lightweight Python utilities
- reusable templates
- repeatable workflows
- a central tool registry
- scratch workspace directories for runs and reports

The bias is toward low-dependency tooling that works well from a terminal and can be composed by humans or AI agents.

## Layout

- `scripts/` executable tools
- `scripts/lib/` shared shell helpers
- `data/tools.json` central registry of available tools
- `templates/` project and report templates
- `themes/` curated theme packs for terminal and editor tooling
- `workflows/` operating playbooks
- `workspace/` output directories for generated runs and reports
- `docs/` generated or maintained reference docs

## Included tools

- `cento.sh`
  Unified cento CLI facade for built-ins, tool dispatch, and user-defined aliases.
- `bluetooth_audio_doctor.py`
  Diagnose Bluetooth and Bluetooth-audio issues, generate a report, and run safe fixes.
- `kitty_theme_manager.sh`
  Sync custom Kitty themes, present theme choices interactively, and reload Kitty plus tmux context.
- `wallpaper_manager.sh`
  Choose, preview, apply, and persist desktop wallpapers for i3 and feh.
- `display_layout_fix.sh`
  Detect two monitors, stack them vertically, and repair your xrandr layout.
- `system_inventory.sh`
  Capture a host inventory report for debugging or baseline documentation.
- `repo_snapshot.sh`
  Create a compact repo state report for handoffs, reviews, and debugging.
- `project_scaffold.sh`
  Scaffold a new generic project directory from lightweight templates.
- `batch_exec.sh`
  Run one command across many directories with dry-run and git-only modes.
- `search_report.sh`
  Turn codebase or filesystem searches into a Markdown report.
- `tool_index.py`
  Generate `docs/tool-index.md` from the central registry.

## Common commands

```bash
make check
make tree
make index
make inventory
make snapshot TARGET="$PWD"
make scaffold NAME="new-project"
make batch ROOT="$HOME/projects" PATTERN="*" CMD='git status --short'
make search QUERY="TODO" ROOT="$HOME/projects/cento"
make bt-audio-doctor DEVICE='"Black Diamond"'
make bt-audio-doctor DEVICE='"Black Diamond"' ARGS="--fix"
make kitty-theme
make kitty-theme ARGS='--theme "Cento Rose Pine"'
make wallpaper
make wallpaper ARGS="--choose"
make display
make display ARGS="--show"
make cento ARGS="tools"
make cento ARGS="dark"
```

## Direct script usage

```bash
./scripts/system_inventory.sh
./scripts/repo_snapshot.sh --target "$PWD"
./scripts/project_scaffold.sh --path "$HOME/projects/demo-kit"
./scripts/batch_exec.sh --root "$HOME/projects" --pattern "*" --command 'git status --short'
./scripts/search_report.sh --query "bluetooth" --root "$HOME/projects/cento"
./scripts/kitty_theme_manager.sh
./scripts/wallpaper_manager.sh --choose
./scripts/display_layout_fix.sh --show
./scripts/cento.sh tools
./scripts/cento.sh dark
python3 ./scripts/bluetooth_audio_doctor.py "Black Diamond"
```

## Design principles

- Prefer shell for glue code and operational automation.
- Use Python only where structured parsing or reporting materially helps.
- Keep reports human-readable.
- Avoid mandatory external dependencies where standard tools suffice.
- Make every tool usable standalone, not only through `make`.

## Canonical wrappers

- `~/bin/cento` points at this repo's unified CLI facade.
- `~/bin/codex-bt-audio-doctor` points at this repo's Bluetooth doctor.
- `~/bin/codex-kitty-theme` points at this repo's Kitty theme manager.


## Cento CLI

`cento` is the unified entrypoint for the repo. It provides:

- built-ins such as `cento tools`, `cento aliases`, and `cento conf`
- direct routing into registered tools such as `cento kitty-theme-manager --plain-menu`
- user-defined shortcuts such as `cento dark`, `cento monk`, and `cento cyber` from `~/.config/cento/aliases.sh`

The cento config is a small Bash file. `cento conf` opens it in your editor, and `cento conf --path` prints its path. It defines aliases only.

Simple aliases use this form:

```bash
cento_alias dark --description "Apply a dark Kitty theme" -- "$HOME/bin/codex-kitty-theme" --theme "Cento Tokyo Night"
```

Combined aliases can compose multiple cento commands through `bash -lc`:

```bash
cento_alias monk --description "Templars + Rose Pine" -- bash -lc '"$HOME/bin/cento" kitty-theme-manager --theme "Cento Rose Pine" && "$HOME/bin/cento" wallpaper-manager --set "templars.png"'
```

Useful examples:

```bash
cento tools
cento aliases
cento conf
cento conf --path
cento kitty-theme-manager --list-custom
cento wallpaper-manager --choose
cento wallpaper
cento display-layout-fix
cento displayfix
cento monk
cento cyber
cento dark
```

## Display Layout Fix

The display layout fix tool replaces the old hardcoded horizontal `xrandr --right-of` startup command.

It:

- detects the two connected monitors from `xrandr`
- uses the primary output as the top monitor by default
- centers the narrower monitor under the wider one
- saves preferred top/bottom outputs in `~/.config/cento/display.env` when asked
- reapplies wallpaper and relaunches polybar after the layout change
- writes logs to `logs/display-layout-fix/`

Examples:

```bash
./scripts/display_layout_fix.sh --show
./scripts/display_layout_fix.sh --save-defaults
cento display-layout-fix
cento displayfix
```

## Wallpaper Manager

The wallpaper manager uses your current i3 wallpaper library in `~/.config/kitty/`, where your existing wallpaper images already live.

It:

- discovers the current wallpaper from i3 on first run
- presents wallpapers through `fzf` with Kitty-based preview when available
- applies the selected image with `feh`
- refreshes `picom` so Kitty transparency comes back after wallpaper changes
- saves the current wallpaper in `~/.config/cento/wallpaper.env`
- writes run logs to `logs/wallpaper-manager/`
- lets i3 restore the saved wallpaper on startup through `cento wallpaper-manager --apply-current`

Examples:

```bash
./scripts/wallpaper_manager.sh --choose
./scripts/wallpaper_manager.sh --set green_arctic.jpg
./scripts/wallpaper_manager.sh --list
cento wallpaper-manager --apply-current
cento wallpaper
```

## Kitty Theme Manager

The Kitty theme manager now uses a repo-controlled selector and direct theme apply flow, which behaves more predictably inside tmux than Kitty's built-in interactive theme UI.

It:

- syncs custom themes from `themes/kitty/` into `~/.config/kitty/themes/`
- presents an interactive theme chooser with `fzf` when available
- falls back to a numbered prompt automatically when `fzf` is unavailable or the session is not a real TTY
- supports `--plain-menu` to force the numbered prompt in tmux or other awkward terminal contexts
- applies the chosen theme by updating `~/.config/kitty/current-theme.conf`
- logs each run to `logs/kitty-theme-manager/` with `latest.log` pointing at the newest run
- reloads Kitty and refreshes tmux when run inside tmux

Examples:

```bash
./scripts/kitty_theme_manager.sh
./scripts/kitty_theme_manager.sh --plain-menu
./scripts/kitty_theme_manager.sh --theme "Cento Rose Pine"
./scripts/kitty_theme_manager.sh --list-custom
tail -n 80 logs/kitty-theme-manager/latest.log
```

## Next directions

- add more domain-specific automation packs under `workflows/`
- add optional install/bootstrap scripts for `~/bin` wrappers
- add standardized run manifests under `workspace/runs/`
- add tool composition scripts that chain multiple toolkit commands
