# Tool Index

## Cento CLI

- `id`: `cento-cli`
- `lane`: `general ops`
- `kind`: `shell`
- `entrypoint`: `./scripts/cento.sh`
- `wrapper`: `~/bin/cento`
- description: Unified cento facade for built-ins, tool dispatch, and user-defined aliases.
- commands:
  - `./scripts/cento.sh tools`
  - `./scripts/cento.sh aliases`
  - `./scripts/cento.sh conf`
  - `./scripts/cento.sh monk`
  - `./scripts/cento.sh cyber`

## Bluetooth Audio Doctor

- `id`: `bluetooth-audio-doctor`
- `lane`: `general ops`
- `kind`: `python`
- `entrypoint`: `./scripts/bluetooth_audio_doctor.py`
- `wrapper`: `~/bin/codex-bt-audio-doctor`
- description: Diagnose Bluetooth and Bluetooth-audio failures, generate detailed reports, and apply safe repair actions.
- commands:
  - `python3 ./scripts/bluetooth_audio_doctor.py "Black Diamond"`
  - `python3 ./scripts/bluetooth_audio_doctor.py "Black Diamond" --fix`
  - `python3 ./scripts/bluetooth_audio_doctor.py "Black Diamond" --fix --repair-pairing`

## Display Layout Fix

- `id`: `display-layout-fix`
- `lane`: `general ops`
- `kind`: `shell`
- `entrypoint`: `./scripts/display_layout_fix.sh`
- description: Detect two connected monitors, stack them vertically, and refresh wallpaper plus polybar.
- commands:
  - `./scripts/display_layout_fix.sh --show`
  - `./scripts/display_layout_fix.sh --save-defaults`
  - `./scripts/display_layout_fix.sh --top DP-4.8 --bottom HDMI-0 --save-defaults`

## Wallpaper Manager

- `id`: `wallpaper-manager`
- `lane`: `general ops`
- `kind`: `shell`
- `entrypoint`: `./scripts/wallpaper_manager.sh`
- description: Choose, preview, apply, and persist desktop wallpapers for i3 and feh.
- commands:
  - `./scripts/wallpaper_manager.sh --choose`
  - `./scripts/wallpaper_manager.sh --set green_arctic.jpg`
  - `./scripts/wallpaper_manager.sh --apply-current`
  - `./scripts/wallpaper_manager.sh --list`

## Kitty Theme Manager

- `id`: `kitty-theme-manager`
- `lane`: `general ops`
- `kind`: `shell`
- `entrypoint`: `./scripts/kitty_theme_manager.sh`
- `wrapper`: `~/bin/codex-kitty-theme`
- description: Manage Kitty themes with interactive selection, persistent logs, and tmux-aware refresh behavior.
- commands:
  - `./scripts/kitty_theme_manager.sh`
  - `./scripts/kitty_theme_manager.sh --plain-menu`
  - `./scripts/kitty_theme_manager.sh --theme "Cento Rose Pine"`
  - `tail -n 80 ./logs/kitty-theme-manager/latest.log`

## System Inventory

- `id`: `system-inventory`
- `lane`: `general ops`
- `kind`: `shell`
- `entrypoint`: `./scripts/system_inventory.sh`
- description: Capture a Markdown baseline of host, shell, tooling, and environment state.
- commands:
  - `./scripts/system_inventory.sh`
  - `./scripts/system_inventory.sh --output ~/reports/system.md`

## Repo Snapshot

- `id`: `repo-snapshot`
- `lane`: `general ops`
- `kind`: `shell`
- `entrypoint`: `./scripts/repo_snapshot.sh`
- description: Create a compact repo status report including tree, git status, diffstat, and recent commits.
- commands:
  - `./scripts/repo_snapshot.sh --target .`
  - `./scripts/repo_snapshot.sh --target ~/projects/cento`

## Project Scaffold

- `id`: `project-scaffold`
- `lane`: `general ops`
- `kind`: `shell`
- `entrypoint`: `./scripts/project_scaffold.sh`
- description: Scaffold a generic project with starter README, notes, scripts, data, and workspace folders.
- commands:
  - `./scripts/project_scaffold.sh --path ~/projects/example-kit`

## Batch Exec

- `id`: `batch-exec`
- `lane`: `general ops`
- `kind`: `shell`
- `entrypoint`: `./scripts/batch_exec.sh`
- description: Run one shell command across multiple directories with dry-run and git-only support.
- commands:
  - `./scripts/batch_exec.sh --root ~/projects --pattern '*' --command 'git status --short'`
  - `./scripts/batch_exec.sh --root ~/projects --pattern '*' --git-only --dry-run --command 'pwd'`

## Search Report

- `id`: `search-report`
- `lane`: `general ops`
- `kind`: `shell`
- `entrypoint`: `./scripts/search_report.sh`
- description: Search a filesystem tree and write a Markdown report with matches and context.
- commands:
  - `./scripts/search_report.sh --query TODO --root ~/projects/cento`
  - `./scripts/search_report.sh --query bluetooth --root ~/projects`

## Tool Index Generator

- `id`: `tool-index`
- `lane`: `general ops`
- `kind`: `python`
- `entrypoint`: `./scripts/tool_index.py`
- description: Generate a Markdown tool index from the central registry.
- commands:
  - `python3 ./scripts/tool_index.py --registry data/tools.json --output docs/tool-index.md`
