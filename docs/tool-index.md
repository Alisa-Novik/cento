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

## Validator Tier 0

- `id`: `validator-tier0`
- `lane`: `agent ops`
- `kind`: `python`
- `entrypoint`: `./scripts/validator_tier0.py`
- description: Create validation packets and run deterministic Tier 0 checks with mandatory timing and AI budget stats.
- commands:
  - `cento validator-tier0 stories`
  - `cento validator-tier0 run workspace/runs/validator-tier0/e2e/sample-pass.json`
  - `cento validator-tier0 e2e`
  - `cento validator-tier0 run workspace/runs/agent-work/no-model-validation-e2e/validation.json --run-dir workspace/runs/agent-work/no-model-validation-e2e/tier0`

## Story Manifest

- `id`: `story-manifest`
- `lane`: `agent ops`
- `kind`: `python`
- `entrypoint`: `./scripts/story_manifest.py`
- description: Validate, draft, and render Cento agent-work story.json manifests.
- commands:
  - `cento story-manifest draft --title "Fix dashboard" --package app --expected-output workspace/runs/agent-work/drafts/fix-dashboard/evidence.md`
  - `cento story-manifest validate workspace/runs/agent-work/no-model-validation-e2e/story.json`
  - `cento story-manifest render-hub workspace/runs/agent-work/1000086/story.json`

## Validation Manifest

- `id`: `validation-manifest`
- `lane`: `agent ops`
- `kind`: `python`
- `entrypoint`: `./scripts/validation_manifest.py`
- description: Generate deterministic validation.json checks from story.json and enforce no-model coverage guardrails.
- commands:
  - `cento validation-manifest draft workspace/runs/agent-work/no-model-validation-e2e/story.json --output workspace/runs/agent-work/no-model-validation-e2e/validation.json`
  - `cento validation-manifest validate workspace/runs/agent-work/no-model-validation-e2e/validation.json`

## No-model Validation E2E

- `id`: `no-model-validation-e2e`
- `lane`: `agent ops`
- `kind`: `python`
- `entrypoint`: `./scripts/no_model_validation_e2e.py`
- description: Run generated story manifest, generated validation manifest, agent-work preflight, and Tier 0 validation in one zero-AI evidence loop.
- commands:
  - `cento no-model-validation-e2e`
  - `cento no-model-validation-e2e --run-dir workspace/runs/agent-work/no-model-validation-e2e`

## Manifest Validate

- `id`: `manifest-validate`
- `lane`: `agent ops`
- `kind`: `python`
- `entrypoint`: `./scripts/manifest_validate.py`
- description: Deterministically validate story.json and validation.json pairs, including evidence paths, API specs, and allowlisted commands without AI.
- commands:
  - `cento manifest-validate --story workspace/runs/agent-work/1000088/story.json --validation workspace/runs/agent-work/1000088/validation.json --json --report workspace/runs/agent-work/1000088/validation-report.md`
  - `python3 ./scripts/manifest_validate.py --story workspace/runs/agent-work/1000088/story.json --json`

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

## Cento Taskstream CLI

- `id`: `agent-work`
- `lane`: `agent ops`
- `kind`: `python`
- `entrypoint`: `./scripts/agent_work.py`
- description: Cento Taskstream CLI for assigning, splitting, dispatching, reviewing, archiving, and cutting over Cento agent tasks across the Mac/Linux cluster.
- commands:
  - `cento agent-work bootstrap`
  - `cento agent-work create --title "Fix dashboard" --manifest workspace/runs/agent-work/drafts/fix-dashboard/story.json --node linux --agent codex`
  - `CENTO_AGENT_WORK_BACKEND=dual cento agent-work create --title "Validate parity" --manifest workspace/runs/agent-work/drafts/validate-parity/story.json --node linux --agent codex`
  - `cento agent-work preflight workspace/runs/agent-work/no-model-validation-e2e/story.json --validation-manifest workspace/runs/agent-work/no-model-validation-e2e/validation.json`
  - `cento agent-work split --title "Improve mission control" --nodes linux,macos --task "Backend status" --task "Mac tile view"`
  - `cento agent-work list`
  - `cento agent-work show 123`
  - `cento agent-work claim 123 --node linux --agent codex`
  - `cento agent-work update 123 --status review --note "implemented and tested"`
  - `CENTO_AGENT_WORK_BACKEND=dual cento agent-work update 123 --status validating --note "builder update path check"`
  - `CENTO_AGENT_WORK_BACKEND=dual cento agent-work validate 123 --result pass --note "validation accepted" --evidence workspace/runs/agent-work/validation-report.md`
  - `CENTO_AGENT_WORK_BACKEND=dual cento agent-work cutover-parity --all --run-dir workspace/runs/agent-work/cutover`
  - `cento agent-work backup --run-dir workspace/runs/agent-work/cutover/e2e-check`
  - `cento agent-work restore --bundle workspace/runs/agent-work/cutover/e2e-check/backup --verify`
  - `cento agent-work archive --query "cutover"`
  - `cento agent-work cutover-status`
  - `cento agent-work cutover-freeze`
  - `cento agent-work cutover-verify --run-dir workspace/runs/agent-work/cutover/e2e-check`
  - `cento agent-work cutover-finalize --force`
  - `cento agent-work review-drain --package mission-control --dry-run`
  - `cento agent-work review-drain --package mission-control --apply`
  - `cento agent-work prompt 123`
  - `cento agent-work dispatch 123 --node linux --dry-run`
  - `CENTO_AGENT_WORK_BACKEND=dual make agent-work-e2e`
  - `CENTO_AGENT_WORK_BACKEND=dual make agent-work-dual-backend-stress`
  - `cento agent-work runs`
  - `cento agent-work runs --json --active`
  - `cento agent-work run-status RUN_ID --json`

## Agent Manager

- `id`: `agent-manager`
- `lane`: `agent ops`
- `kind`: `python`
- `entrypoint`: `./scripts/agent_manager.py`
- description: Control-plane scanner for Cento agents that detects stale, idle, stuck, errored, duplicated, manual, and low-value runs and writes actionable reports.
- commands:
  - `cento agent-manager scan`
  - `cento agent-manager scan --json`
  - `cento agent-manager report`
  - `cento agent-manager recommend --limit 10`
  - `cento agent-manager classify --issue-id 81`
  - `cento agent-manager mark-stale RUN_ID --reason "stuck validator" --dry-run`
  - `cento agent-manager mark-blocked 81 --reason "stuck validator" --evidence RUN_ID --dry-run`
  - `cento agent-manager terminate-tmux cento-agent-81-095103 --reason "stuck validator" --dry-run`
  - `make agent-manager ARGS="pool-stats --json"`

## Cento Factory

- `id`: `factory`
- `lane`: `planning`
- `kind`: `python`
- `entrypoint`: `./scripts/factory.py`
- description: Manifest-driven factory workflow that turns a high-level request into intake artifacts, a validated factory-plan.json, story manifests, validation manifests, queue ledgers, owned-path leases, worktree metadata, prompt bundles, patch collection, integration dry-runs, isolated Safe Integrator branches, per-patch validation, rollback metadata, release candidates, release status, and static evidence hubs without default AI dispatch.
- commands:
  - `cento factory intake "develop me a career consulting module" --dry-run --out workspace/runs/factory/factory-planning-e2e`
  - `cento factory plan workspace/runs/factory/factory-planning-e2e --no-model`
  - `cento factory materialize workspace/runs/factory/factory-planning-e2e`
  - `cento factory create-issues workspace/runs/factory/factory-planning-e2e --dry-run`
  - `cento factory preflight workspace/runs/factory/factory-planning-e2e --json`
  - `cento factory queue workspace/runs/factory/factory-planning-e2e`
  - `cento factory lease workspace/runs/factory/factory-planning-e2e --task crm-schema-extension --dry-run`
  - `cento factory dispatch workspace/runs/factory/factory-planning-e2e --lane builder --max 4 --dry-run`
  - `cento factory collect workspace/runs/factory/factory-planning-e2e`
  - `cento factory validate workspace/runs/factory/factory-planning-e2e`
  - `cento factory integrate workspace/runs/factory/factory-planning-e2e --dry-run`
  - `cento factory integrate factory-integration-e2e --plan`
  - `cento factory integrate factory-integration-e2e --prepare-branch --branch factory/factory-integration-e2e/integration`
  - `cento factory integrate factory-integration-e2e --apply --validate-each --limit 3`
  - `cento factory validate-integrated factory-integration-e2e`
  - `cento factory release-candidate factory-integration-e2e`
  - `cento factory sync-taskstream factory-integration-e2e --dry-run`
  - `cento factory release workspace/runs/factory/factory-planning-e2e --json`
  - `cento factory render-hub workspace/runs/factory/factory-planning-e2e`
  - `cento factory status workspace/runs/factory/factory-planning-e2e`

## Cento Console App

- `id`: `agent-work-app`
- `lane`: `agent ops`
- `kind`: `python`
- `entrypoint`: `./scripts/agent_work_app.py`
- description: Self-hosted Cento Console web app with Taskstream, Cluster, Consulting, and Docs sections, plus background process control, health checks, and migration import sync.
- commands:
  - `cento agent-work-app start`
  - `cento agent-work-app stop`
  - `cento agent-work-app status`
  - `cento agent-work-app import-redmine`
  - `cento agent-work-app install-sync`
  - `cento agent-work backup`
  - `cento agent-work restore --bundle workspace/runs/agent-work/cutover/e2e-check/backup --verify`
  - `cento agent-work archive --query "migration"`
  - `cento agent-work cutover-status`

## Story Screenshot Runner

- `id`: `story-screenshot-runner`
- `lane`: `agent ops`
- `kind`: `python`
- `entrypoint`: `./scripts/story_screenshot_runner.py`
- description: Read screenshot requirements from story.json, capture desktop and mobile evidence with Playwright, and write deterministic metadata plus an index for Docs/Evidence and Validator lanes.
- commands:
  - `cento story-screenshot-runner workspace/runs/agent-work/59/story.json`
  - `cento story-screenshot-runner workspace/runs/agent-work/59/story.json --force`
  - `./scripts/story_screenshot_runner.py workspace/runs/agent-work/59/story.json --force`

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

## Cento Temporary Commands

- `id`: `temp`
- `lane`: `ops`
- `kind`: `shell`
- `entrypoint`: `./scripts/cento_temp.sh`
- description: Short-lived operator wrappers for fragile one-off commands that should not be pasted as multiline shell.
- commands:
  - `cento run temp 1`
  - `cento run temp 1 status`
  - `cento run temp 1 rollback`
