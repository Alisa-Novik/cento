# Tool Index

## Cento CLI

- `id`: `cento-cli`
- `lane`: `general ops`
- `kind`: `shell`
- `entrypoint`: `./scripts/cento.sh`
- `wrapper`: `~/bin/cento`
- description: Unified cento facade for built-ins, terminal docs browsing, tool dispatch, and user-defined aliases.
- commands:
  - `cento help`
  - `cento interactive`
  - `cento docs`
  - `cento docs conf`
  - `cento docs --json`
  - `cento docs --path`
  - `cento tools`
  - `cento aliases`
  - `cento conf`
  - `cento conf --path`
  - `cento completion zsh`
  - `cento install all`
  - `cento install zsh`
  - `cento install tmux`
  - `cento run scan --query "mcp"`
  - `cento platforms`
  - `cento platforms macos`
  - `cento platforms linux`
  - `cento platforms --markdown`

## OCI SSH Bridge

- `id`: `bridge`
- `lane`: `remote access`
- `kind`: `shell`
- `entrypoint`: `./scripts/bridge.sh`
- description: Create a reverse SSH tunnel through the OCI VM so another machine can SSH back into this host through the VM relay.
- commands:
  - `cento bridge start`
  - `cento bridge status`
  - `cento bridge stop`
  - `cento bridge restart`
  - `cento bridge foreground`
  - `cento bridge command`
  - `cento bridge mac-command`
  - `cento bridge docs`
  - `cento bridge check`
  - `cento bridge from-mac`
  - `cento bridge --from-mac`
  - `cento bridge from-mac -- 'cd "$HOME/projects/cento" && ./scripts/cento.sh platforms linux'`
  - `cento bridge expose-linux`
  - `cento bridge install-linux-service`
  - `cento bridge install-mac-service`
  - `cento bridge expose-mac`
  - `cento bridge to-linux`
  - `cento bridge to-mac`
  - `cento bridge mesh-status`
  - `cento bridge to-linux -- 'cd "$HOME/projects/cento" && ./scripts/cento.sh gather-context --no-remote | head -90'`
  - `cento bridge to-mac -- '/Users/anovik-air/bin/cento gather-context --no-remote | head -90'`
  - `cento bridge context-linux`
  - `cento bridge context-mac`

## Daily Execution Support

- `id`: `daily`
- `lane`: `execution`
- `kind`: `shell`
- `entrypoint`: `./scripts/daily_tui.sh`
- description: Bubble Tea execution cockpit for morning brief, midday recalibration, evening wrap-up, and local continuity.
- commands:
  - `cento daily`

## Telegram TUI

- `id`: `tui`
- `lane`: `communications`
- `kind`: `shell`
- `entrypoint`: `./scripts/telegram_tui.sh`
- description: Bubble Tea Telegram TUI with cached Go launcher, local config, and planned CRM hooks.
- commands:
  - `cento tui`
  - `cento tui status`
  - `cento tui config --path`
  - `cento tui docs`
  - `cento crm integration --provider telegram`

## CRM Module

- `id`: `crm`
- `lane`: `career consulting`
- `kind`: `python`
- `entrypoint`: `./scripts/crm_module.py`
- description: Embedded cento CRM with questionnaire bootstrap, career-intake dossiers, local JSON persistence, and a self-hosted no-build SPA.
- commands:
  - `cento crm`
  - `cento crm questionnaire`
  - `cento crm init`
  - `cento crm intake init --person "Ada Lovelace"`
  - `cento crm intake add --person "Ada Lovelace" --kind resume --file ./resume.pdf`
  - `cento crm intake plan --person "Ada Lovelace"`
  - `cento crm integration --provider redmine --person "Ada Lovelace" --start-workflow --dry-run`
  - `cento crm serve --open`
  - `cento crm show`
  - `cento crm docs`

## Burp Suite Community

- `id`: `burp`
- `lane`: `security testing`
- `kind`: `shell`
- `entrypoint`: `./scripts/burp_suite_community.sh`
- description: Download, set up, and control PortSwigger Burp Suite Community through cento wrappers.
- commands:
  - `cento burp download`
  - `cento burp download --type linux`
  - `cento burp setup`
  - `cento burp controller start --use-defaults`
  - `cento burp run -- --help`
  - `cento burp status`
  - `cento burp stop`
  - `cento burp docs`

## MCP Tooling

- `id`: `mcp`
- `lane`: `general ops`
- `kind`: `python`
- `entrypoint`: `./scripts/mcp_tooling.py`
- description: Manage repo-root MCP config, env templates, validation, and tool-call docs.
- commands:
  - `cento mcp doctor`
  - `cento mcp init --write-env`
  - `cento mcp docs`
  - `cento mcp paths`

## Cento MCP Server

- `id`: `cento-mcp`
- `lane`: `agent ops`
- `kind`: `python`
- `entrypoint`: `./scripts/cento_mcp_server.py`
- description: Local MCP stdio server that exposes safe Cento agent-work, story manifest, cluster, bridge, and context tools.
- commands:
  - `python3 scripts/cento_mcp_server.py --list-tools`
  - `python3 scripts/cento_mcp_server.py --call-tool cento_agent_work_list --arguments '{}'`
  - `python3 scripts/cento_mcp_server.py --call-tool cento_context --arguments '{"remote":false}'`
  - `cento mcp doctor`

## Scan One Pager

- `id`: `scan`
- `lane`: `general ops`
- `kind`: `python`
- `entrypoint`: `./scripts/scan_onepager.py`
- description: Scan cento for a topic and generate an archived HTML one-pager with explanation and snippets.
- commands:
  - `cento scan --query "mcp"`
  - `cento scan --query "telegram" --no-open`
  - `cento scan --query "crm" --case-sensitive`
  - `cento scan --query "mcp" --port 47890`

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

## Audio Quick Connect

- `id`: `audio-quick-connect`
- `lane`: `general ops`
- `kind`: `shell`
- `entrypoint`: `./scripts/audio_quick_connect.sh`
- description: Quickly connect a paired Bluetooth audio device by name or address with a short retry path and per-run logs.
- commands:
  - `./scripts/audio_quick_connect.sh "Black Diamond"`
  - `./scripts/audio_quick_connect.sh "Bose"`
  - `cento audio-quick-connect "Black Diamond"`

## Dashboard

- `id`: `dashboard`
- `lane`: `general ops`
- `kind`: `python`
- `entrypoint`: `./scripts/dashboard_server.py`
- description: Run a localhost web dashboard with current state, recent cento activity, aliases, tools, and repo progress.
- commands:
  - `./scripts/dashboard_server.py`
  - `./scripts/dashboard_server.py --open`
  - `./scripts/dashboard_server.py --theme industrial --open`
  - `./scripts/dashboard_server.py --host 127.0.0.1 --port 46268`
  - `cento dashboard`

## Desktop Presets

- `id`: `preset`
- `lane`: `desktop ops`
- `kind`: `shell`
- `entrypoint`: `./scripts/preset.sh`
- description: Apply managed Cento desktop presets such as the Industrial OS i3 theme and dashboard.
- commands:
  - `cento preset list`
  - `cento preset industrial-os`
  - `cento preset industrial-os --workspace`
  - `cento preset industrial-os --workspace --black-only`
  - `cento preset industrial-os --session`
  - `cento preset industrial-os --dashboard-only --open`
  - `cento dashboard --theme industrial --open`

## Quick Help

- `id`: `quick-help`
- `lane`: `general ops`
- `kind`: `shell`
- `entrypoint`: `./scripts/quick_help.sh`
- description: Rofi-based searchable help palette for cento built-ins, tools, and aliases.
- commands:
  - `./scripts/quick_help.sh`
  - `./scripts/quick_help.sh --show`
  - `cento quick-help`

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

## i3 Reorg

- `id`: `i3reorg`
- `lane`: `desktop ops`
- `kind`: `shell`
- `entrypoint`: `./scripts/i3reorg.sh`
- description: Move numeric i3 workspaces to the bottom monitor, apply the preferred app map, and optionally place the Abao/Tokyo study YouTube window on top workspace L2 fullscreen.
- commands:
  - `./scripts/i3reorg.sh`
  - `./scripts/i3reorg.sh --dry-run`
  - `./scripts/i3reorg.sh --bottom-output DP-4.8`
  - `./scripts/i3reorg.sh --study`
  - `cento i3reorg`
  - `cento i3reorg --study`
  - `cento i3reorg --focus 2`

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

## Restart Discord

- `id`: `rd`
- `lane`: `desktop ops`
- `kind`: `shell`
- `entrypoint`: `./scripts/restart_discord.sh`
- description: Terminate and relaunch Discord through the available desktop launcher.
- commands:
  - `cento rd`

## Tool Index Generator

- `id`: `tool-index`
- `lane`: `general ops`
- `kind`: `python`
- `entrypoint`: `./scripts/tool_index.py`
- description: Generate a Markdown tool index from the central registry.
- commands:
  - `python3 ./scripts/tool_index.py --registry data/tools.json --output docs/tool-index.md`

## Platform Report

- `id`: `platform-report`
- `lane`: `general ops`
- `kind`: `python`
- `entrypoint`: `./scripts/platform_report.py`
- description: Report declared macOS and Linux support for registered cento tools and generate docs/platform-support.md.
- commands:
  - `cento platforms`
  - `cento platforms macos`
  - `python3 ./scripts/platform_report.py --markdown --output docs/platform-support.md`

## Quick Help FZF

- `id`: `quick-help-fzf`
- `lane`: `general ops`
- `kind`: `shell`
- `entrypoint`: `./scripts/quick_help_fzf.sh`
- description: Cross-platform fzf command palette for cento built-ins, tools, and aliases.
- commands:
  - `cento quick-help-fzf`
  - `cento quick-help-fzf --print`

## macOS Installer

- `id`: `install-macos`
- `lane`: `setup`
- `kind`: `shell`
- `entrypoint`: `./scripts/install_macos.sh`
- description: Install local macOS dependencies, wrappers, PATH block, and Zsh integration for cento.
- commands:
  - `./scripts/install_macos.sh`

## Linux Installer

- `id`: `install-linux`
- `lane`: `setup`
- `kind`: `shell`
- `entrypoint`: `./scripts/install_linux.sh`
- description: Install local Linux dependencies, wrappers, PATH block, and Zsh integration for cento.
- commands:
  - `./scripts/install_linux.sh`

## Cento Notify

- `id`: `notify`
- `lane`: `agent ops`
- `kind`: `shell`
- `entrypoint`: `./scripts/notify.sh`
- description: Send cluster notifications to configured ntfy targets such as iPhone and Apple Watch mirrored alerts.
- commands:
  - `cento notify setup iphone TOPIC`
  - `cento notify status`
  - `cento notify iphone "Cluster job finished"`
  - `cento notify all "Linux healed"`
  - `cento notify test iphone`

## Cento Cluster Control

- `id`: `cluster`
- `lane`: `agent ops`
- `kind`: `shell`
- `entrypoint`: `./scripts/cluster.sh`
- description: Manage Cento node identity, cluster registry, colored status, remote execution, bridge healing, and read-only git drift checks.
- commands:
  - `cento cluster init`
  - `cento cluster nodes`
  - `cento cluster status`
  - `cento cluster exec linux -- tmux ls`
  - `cento cluster exec macos -- cento gather-context --no-remote`
  - `cento cluster sync`
  - `cento cluster heal`
  - `cento cluster heal linux`
  - `cento cluster heartbeat iphone`
  - `cento cluster metric memory`
  - `cento cluster ask "send me notification with total memory consumption on the cluster"`
  - `cento cluster activity linux`
  - `cento cluster activity --json linux`
  - `cento cluster exec linux -- 'cd /home/alice/projects/cento && pwd'`
  - `scripts/cluster_health_e2e.sh`
  - `cento cluster companion-setup iphone`

## Gather Context

- `id`: `gather-context`
- `lane`: `agent ops`
- `kind`: `python`
- `entrypoint`: `./scripts/gather_context.py`
- description: Gather AI-ready local and remote Cento context including platform support, repo state, command paths, MCP hints, and SSH connectivity.
- commands:
  - `cento gather-context`
  - `cento gather-context --no-remote`
  - `cento gather-context --json`
  - `cento gather-context --output workspace/runs/cento-context.md`

## Cento Network Monitor

- `id`: `network-tui`
- `lane`: `agent ops`
- `kind`: `shell`
- `entrypoint`: `./scripts/network_tui.sh`
- description: Cluster-focused Bubble Tea monitor for Cento nodes, connection state, activity state, tmux presence, VM mesh sockets, and companion-device reachability.
- commands:
  - `cento network-tui`
  - `cento network-tui --no-remote`
  - `./scripts/network_tui.sh`

## Agent Work Tracker

- `id`: `agent-work`
- `lane`: `agent ops`
- `kind`: `python`
- `entrypoint`: `./scripts/agent_work.py`
- description: Redmine-backed Jira-style work tracker for assigning, splitting, dispatching, and reviewing Cento agent tasks across the Mac/Linux cluster.
- commands:
  - `cento agent-work bootstrap`
  - `cento agent-work create --title "Fix dashboard" --node linux --agent codex`
  - `cento agent-work split --title "Improve mission control" --nodes linux,macos --task "Backend status" --task "Mac tile view"`
  - `cento agent-work list`
  - `cento agent-work show 123`
  - `cento agent-work claim 123 --node linux --agent codex`
  - `cento agent-work update 123 --status review --note "implemented and tested"`
  - `cento agent-work prompt 123`
  - `cento agent-work dispatch 123 --node linux --dry-run`
  - `cento agent-work dispatch-pool --limit 3`
  - `cento agent-work dispatch-pool --limit 2 --runtime codex --model gpt-5.3-codex-spark --execute`
  - `cento agent-work runs`
  - `cento agent-work runs --json --active`
  - `cento agent-work run-status RUN_ID --json`

## Agent Pool Kicker

- `id`: `agent-pool-kick`
- `lane`: `agent ops`
- `kind`: `python`
- `entrypoint`: `./scripts/agent_pool_kick.py`
- description: Bounded worker-pool launcher that keeps builder, validator, small-task, and coordinator lanes moving without unbounded dispatch.
- commands:
  - `cento agent-pool-kick --dry-run`
  - `cento agent-pool-kick --max-launch 3 --dry-run`
  - `cento agent-pool-kick --max-launch 3 --model gpt-5.3-codex-spark`
  - `cento agent-pool-kick --builder-target 2 --validator-target 2 --small-target 1 --coordinator-target 1`
  - `python3 scripts/agent_pool_kick.py --dry-run`

## Agent Work Hygiene

- `id`: `agent-work-hygiene`
- `lane`: `agent ops`
- `kind`: `shell`
- `entrypoint`: `./scripts/agent_work_hygiene.sh`
- description: Collect a point-in-time reconciliation report of agent run ledgers, tmux sessions, and Codex/Claude processes.
- commands:
  - `cento agent-work-hygiene`
  - `cento agent-work-hygiene --issue 94`
  - `cento agent-work-hygiene --out-dir workspace/runs/agent-work/reconciliation`
  - `./scripts/agent_work_hygiene.sh`

## Cento Incident Response

- `id`: `incident`
- `lane`: `agent ops`
- `kind`: `python`
- `entrypoint`: `./scripts/incident_response.py`
- description: Bounded incident checks for Cento control-plane failures, with guarded SEV2 agent-work escalation for iPhone ce ingress failures.
- commands:
  - `cento incident check iphone-ce`
  - `cento incident check iphone-ce --json --no-create`
  - `cento incident status`
  - `cento incident install iphone-ce --interval 300 --dry-run`
  - `cento incident install iphone-ce --interval 300`
  - `cento incident uninstall iphone-ce`
  - `cento incident docs`

## opencode

- `id`: `opencode`
- `lane`: `ai tools`
- `kind`: `shell`
- `entrypoint`: `./scripts/opencode.sh`
- `wrapper`: `~/bin/opencode`
- description: Thin wrapper around opencode (Alisa-Novik fork of sst/opencode) — an open-source AI coding agent TUI.
- commands:
  - `cento opencode`
  - `cento opencode --version`
  - `cento opencode --help`
  - `cento opencode fork-status`

## Cento Mobile

- `id`: `mobile`
- `lane`: `mobile ops`
- `kind`: `shell`
- `entrypoint`: `./scripts/mobile.sh`
- description: Native iOS/PWA mobile helper commands, including repeatable iOS e2e validation against the local mobile gateway.
- commands:
  - `cento mobile e2e`
  - `CENTO_IOS_E2E_PHYSICAL=false cento mobile e2e`
  - `CENTO_MOBILE_TOKEN="$(cento mobile token-from-linux)" cento mobile e2e`
  - `cento mobile token-from-linux`
  - `cento mobile watch-status`
  - `cento mobile docs`
