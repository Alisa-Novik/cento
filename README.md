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
- `data/cento-cli.json` canonical JSON docs for the root cento CLI built-ins
- `mcp/` repo-root MCP setup and tool-call guidance
- `templates/` project and report templates
- `standards/` repo-wide implementation and UX standards
- `themes/` curated theme packs for terminal and editor tooling
- `workflows/` operating playbooks
- `workspace/` output directories for generated runs and reports
- `docs/` generated or maintained reference docs

## Included tools

- `cento.sh`
  Unified cento CLI facade for built-ins, tool dispatch, user-defined aliases, and shell integration install paths.
- `bluetooth_audio_doctor.py`
  Diagnose Bluetooth and Bluetooth-audio issues, generate a report, and run safe fixes.
- `audio_quick_connect.sh`
  Quickly connect a paired Bluetooth audio device by name or address.
- `dashboard_server.py`
  Run a localhost web dashboard for current state, recent activity, aliases, tools, and repo progress.
- `bridge.sh`
  Create a reverse SSH tunnel through the OCI VM so another machine can SSH back into this host through the VM relay.
- `cluster.sh`
  Manage Cento nodes, remote execution, bridge healing, git drift checks, and parallel agent jobs.
- `cluster_job_runner.py`
  Plan feature requests into node-assigned agent tasks, dispatch them in parallel, and collect logs plus worktree artifacts.
- `agent_work_app.py`
  Run the Cento Console web app with Taskstream, Cluster, Consulting, and Docs sections, plus background process control, health checks, and migration import sync.
- `network.sh`
  Route `cento network --tui` and `cento network --web`.
- `network_web_server.py`
  Serve the cluster network dashboard from node registry and bridge state.
- `jobs.sh`
  Open the cluster jobs web dashboard.
- `jobs_server.py`
  Serve live cluster job manifests, task state, node assignments, and log tails.
- `daily_tui.sh`
  Bubble Tea launcher for Daily Execution Support, backed by a cached Go binary.
- `daily_tui.go`
  Local-first execution cockpit for morning brief, midday recalibration, evening wrap-up, history, and settings.
- `telegram_tui.sh`
  Bubble Tea launcher for the Telegram TUI, backed by a cached Go binary.
- `telegram_tui.go`
  Bubble Tea implementation for the Telegram tool surface.
- `crm_module.py`
  Run the embedded CRM module for questionnaire capture, career-intake dossiers, saved profiles, and CRM docs.
- `funnel_module.py`
  Track traffic sources, funnels, leads, events, offers, next actions, and Markdown funnel reports.
- `burp_suite_community.sh`
  Download, set up, and control PortSwigger Burp Suite Community through cento wrappers.
- `mcp_tooling.py`
  Initialize, validate, and document the repo-root MCP configuration.
- `cento_interactive.sh`
  Bubble Tea launcher for `cento interactive`, backed by a cached Go binary.
- `cento_interactive.go`
  Bubble Tea implementation for the root cento interactive browser.
- `cento_interactive.py`
  Non-interactive docs backend for `cento docs` and scripted lookups.
- `scan_onepager.py`
  Scan cento content and generate an archived HTML one-pager.
- `story_screenshot_runner.py`
  Capture desktop and mobile screenshots from `story.json` with deterministic evidence and an index.
- `manifest_validate.py`
  Deterministically validate `story.json` and `validation.json` pairs, including evidence paths, API specs, and allowlisted commands without AI.
- `kitty_theme_manager.sh`
  Sync custom Kitty themes, present theme choices interactively, and reload Kitty plus tmux context.
- `wallpaper_manager.sh`
  Choose, preview, apply, and persist desktop wallpapers for i3 and feh.
- `display_layout_fix.sh`
  Detect two monitors, stack them vertically, and repair your xrandr layout.
- `i3reorg.sh`
  Keep numeric i3 workspaces on the bottom monitor, move common windows to preferred workspaces, and place the study YouTube window on L2.
- `quick_help.sh`
  Open a rofi-style searchable help palette for cento commands, tools, and aliases.
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
- `factory.py`
  Create no-model Factory runs with intake artifacts, validated `factory-plan.json`, story manifests, validation manifests, queue ledgers, owned-path lease simulation, worktree metadata, prompt bundles, patch collection, integration dry-runs, release status, and static evidence hubs.

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
make audio-quick-connect DEVICE='"Black Diamond"'
make kitty-theme
make kitty-theme ARGS='--theme "Cento Rose Pine"'
make wallpaper
make wallpaper ARGS="--choose"
make display
make display ARGS="--show"
make i3reorg
make i3reorg ARGS="--dry-run"
make i3reorg ARGS="--study"
make dashboard
make dashboard ARGS="--open"
make idea-board
make idea-board ARGS="--open"
make bridge ARGS="start"
make bridge ARGS="mac-command"
make cento ARGS='cluster plan "implement feature A"'
make cento ARGS='cluster implement "implement feature A" --dry-run'
make jobs ARGS="--open"
make network ARGS="--web"
make network ARGS="--tui --no-remote"
make tg
make tg ARGS="status"
make tg ARGS="docs"
make crm
make crm ARGS="questionnaire"
make crm ARGS="init"
make crm ARGS='intake init --person "Ada Lovelace" --target-role "Product Manager"'
make crm ARGS='intake plan --person "Ada Lovelace"'
make crm ARGS="serve --open"
make agent-work-app-start
make agent-work-app-status
make agent-work-app-sync
make agent-work-app-stop
make agent-manager ARGS="scan"
make agent-manager ARGS="recommend --limit 10"
make cento ARGS='factory intake "develop me a career consulting module" --dry-run --out workspace/runs/factory/factory-planning-e2e'
make cento ARGS="factory plan workspace/runs/factory/factory-planning-e2e --no-model"
make cento ARGS="factory materialize workspace/runs/factory/factory-planning-e2e"
make cento ARGS="factory queue workspace/runs/factory/factory-planning-e2e"
make cento ARGS="factory lease workspace/runs/factory/factory-planning-e2e --task crm-schema-extension --dry-run"
make cento ARGS="factory dispatch workspace/runs/factory/factory-planning-e2e --lane builder --max 4 --dry-run"
make cento ARGS="factory collect workspace/runs/factory/factory-planning-e2e"
make cento ARGS="factory validate workspace/runs/factory/factory-planning-e2e"
make cento ARGS="factory integrate workspace/runs/factory/factory-planning-e2e --dry-run"
make cento ARGS="factory release workspace/runs/factory/factory-planning-e2e --json"
make cento ARGS="factory render-hub workspace/runs/factory/factory-planning-e2e"
make funnel ARGS="init"
make funnel ARGS="sources"
make funnel ARGS="report"
make funnel-check
make burp ARGS="setup"
make burp ARGS="controller start --use-defaults"
make burp ARGS="status"
make redmine-e2e
make mcp
make mcp ARGS="doctor"
make mcp ARGS="init --write-env"
make scan QUERY="mcp"
make scan QUERY="telegram" ARGS="--no-open"
cento story-screenshot-runner workspace/runs/agent-work/59/story.json --force
make quick-help
make cento ARGS="tools"
make cento ARGS="interactive"
make cento ARGS="docs conf"
make cento ARGS="completion zsh"
make cento ARGS="install terminal"
make terminal-e2e
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
./scripts/i3reorg.sh --dry-run
./scripts/dashboard_server.py
./scripts/cluster.sh plan "implement feature A"
./scripts/cluster.sh implement "implement feature A" --dry-run
./scripts/jobs.sh --open
./scripts/network.sh --web
./scripts/network.sh --tui --no-remote
./scripts/telegram_tui.sh
./scripts/telegram_tui.sh status
go run ./scripts/telegram_tui.go
./scripts/crm_module.py
./scripts/crm_module.py questionnaire
./scripts/crm_module.py init
./scripts/crm_module.py intake init --person "Ada Lovelace" --target-role "Product Manager"
./scripts/crm_module.py intake plan --person "Ada Lovelace"
./scripts/crm_module.py serve --open
./scripts/crm_module.py show
./scripts/agent_work_app.py start
./scripts/agent_work_app.py status
./scripts/agent_work_app.py import-redmine
./scripts/agent_work_app.py install-sync
./scripts/agent_work.py backup
./scripts/agent_work.py restore --bundle workspace/runs/agent-work/cutover/e2e-check/backup
./scripts/agent_work.py archive --query "cutover"
./scripts/agent_work.py cutover-status
./scripts/agent_work.py cutover-verify --run-dir workspace/runs/agent-work/cutover/e2e-check
./scripts/agent_work.py cutover-finalize --force
./scripts/manifest_validate.py --story workspace/runs/agent-work/1000088/story.json --validation workspace/runs/agent-work/1000088/validation.json --json --report workspace/runs/agent-work/1000088/validation-report.md
./scripts/factory_e2e.py --fixture career-consulting --out workspace/runs/factory/factory-planning-e2e
./scripts/funnel_module.py init
./scripts/funnel_module.py report
./scripts/burp_suite_community.sh setup
./scripts/burp_suite_community.sh controller start --use-defaults
./scripts/burp_suite_community.sh status
./scripts/mcp_tooling.py
./scripts/mcp_tooling.py doctor
./scripts/mcp_tooling.py init --write-env
./scripts/scan_onepager.py --query "mcp"
./scripts/scan_onepager.py --query "telegram" --no-open
./scripts/story_screenshot_runner.py workspace/runs/agent-work/59/story.json --force
./scripts/quick_help.sh
./scripts/cento_interactive.sh
./scripts/cento_interactive.sh --section builtins
./scripts/cento_interactive.py --entry conf
./scripts/cento.sh tools
./scripts/cento.sh completion zsh
./scripts/cento.sh install terminal
./scripts/cento.sh tmux status
./scripts/cento.sh dark
./scripts/terminal_integration_e2e.sh
python3 ./scripts/bluetooth_audio_doctor.py "Black Diamond"
./scripts/audio_quick_connect.sh "Black Diamond"
```

## Standards

Repo-wide conventions live under `standards/`.

- `standards/tui.md` defines the default pattern for interactive terminal apps.
- `standards/tool-registration.md` defines how tools get registered and documented.
- `standards/mcp.md` defines the repo-root MCP configuration pattern.
- `data/cento-cli.json` is the canonical JSON source for root cento built-ins, flags, and usage examples.

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

- built-ins such as `cento tools`, `cento interactive` as the Bubble Tea browser, `cento docs`, `cento aliases`, `cento conf`, `cento completion zsh`, `cento install terminal`, and `cento tmux status`
- direct routing into registered tools such as `cento kitty-theme-manager --plain-menu`
- user-defined shortcuts such as `cento dark`, `cento monk`, and `cento cyber` from `~/.config/cento/aliases.sh`

The cento config is a small Bash file. `cento conf` opens it in your editor, and `cento conf --path` prints its path. It defines aliases only.

For terminal integration, `cento completion zsh` prints the Zsh completion
function and `cento install terminal` installs Zsh/Oh My Zsh completion plus a
right-prompt segment such as `[cento:linux:host]`. It writes managed files under
`~/.config/cento` and injects one guarded source block into `~/.zshrc`. Tmux
status integration is opt-in with `cento install tmux`. The install paths are
idempotent. See `docs/terminal-integration.md` and verify changes with `make
terminal-e2e`.

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
cento interactive
cento docs
cento docs conf
cento aliases
cento conf
cento conf --path
cento completion zsh
cento install terminal
cento tmux status
cento mcp doctor
cento mcp init --write-env
cento mcp docs
cento scan --query "mcp"
cento scan --query "crm" --no-open
cento kitty-theme-manager --list-custom
cento wallpaper-manager --choose
cento audio-quick-connect "Black Diamond"
cento audio "Black Diamond"
cento dashboard
cento dashboard --open
cento jobs
cento jobs --open
cento idea-board
cento idea-board --open
cento network --web
cento network --tui
cento daily
cento tg
cento tg status
cento crm integration
cento crm
cento crm questionnaire
cento crm init
cento crm intake init --person "Ada Lovelace"
cento crm intake plan --person "Ada Lovelace"
cento crm serve --open
cento crm integration
cento crm show
cento crm docs
cento burp setup
cento burp controller start --use-defaults
cento burp status
cento burp stop
cento wallpaper
cento display-layout-fix
cento i3reorg
cento displayfix
cento quick-help
cento quickhelp
cento monk
cento cyber
cento dark
```

## Cento Docs

Root built-ins, flags, and usage examples are now documented in the canonical JSON file `data/cento-cli.json`.

Use these entrypoints:

```bash
cento docs
cento docs conf
cento docs --json
cento docs --path
cento interactive
```

`cento interactive` now opens a Bubble Tea TUI for built-ins, tools, aliases, and their documented usage. `cento docs` remains the non-interactive JSON-backed docs path.

## Burp Suite Community

`cento burp` downloads, sets up, and controls PortSwigger Burp Suite Community.
The default setup path uses the official Community JAR and creates
`~/.local/bin/burp-community` for direct launches.

Examples:

```bash
cento burp download
cento burp download --type linux
cento burp setup
cento burp controller start --use-defaults
cento burp run
cento burp status
cento burp logs --follow
cento burp stop
cento burp docs
```

Managed files live under `~/.local/share/cento/burp/`. See
`docs/burp-suite-community.md` for the command surface and automation notes.

## MCP Setup

`cento` now carries MCP setup directly in the repo root so an MCP-capable client can attach without extra scavenging.

It includes:

- `.mcp.json` as the canonical repo-root config
- `.env.mcp.example` for expected environment values
- `mcp/tool-calls.md` for intent-to-tool guidance
- `scripts/cento_mcp_server.py` as the local `cento` MCP server for board, story, cluster, bridge, and platform operations
- `cento mcp` for init, doctor, docs, and path inspection

Examples:

```bash
cento mcp doctor
cento mcp init --write-env
cento mcp docs
cento mcp paths
python3 scripts/cento_mcp_server.py --list-tools
```

See `docs/cento-mcp-server.md` for the tool surface and Codex/Claude Code workflow.

## Scan One Pager

`cento scan` generates a polished HTML one-pager for a repo scan topic, serves it on a local high port, and archives the previous output automatically.

It:

- scans cento source and docs for a query
- writes the current page to `workspace/runs/scan-onepager/latest/index.html`
- serves the latest page on `http://127.0.0.1:47873/` or the next free high port
- moves the previous latest output into `workspace/runs/scan-onepager/archive/`
- includes an explanation layer plus top files and snippets

Examples:

```bash
cento daily
cento scan --query "mcp"
cento scan --query "telegram" --no-open
cento scan --query "crm" --case-sensitive
```

## Daily Execution Support

The Daily tool is registered as `cento daily` and opens a Bubble Tea execution cockpit.

It:

- generates a structured morning brief
- supports accept, adjust, and rewrite decisions
- captures midday recalibration and evening wrap-up
- stores local continuity in `workspace/runs/daily/history.json`
- isolates mock brief generation behind a `BriefGenerator` interface for later LLM replacement

Example:

```bash
cento daily
```

## Cluster Jobs

`cento cluster` can now plan and run feature implementation jobs across the configured nodes.

It:

- stores job manifests in `workspace/runs/cluster-jobs/<job-id>/job.json`
- decomposes a feature request into node-assigned agent tasks
- runs tasks in parallel by default through the existing cluster execution layer
- creates isolated git worktrees under `workspace/cluster-worktrees/<job-id>/<task-id>`
- captures task logs, generated scripts, summaries, status, diffstat, and patches
- uses `CENTO_CLUSTER_AGENT` or `--agent-command` to override the default `codex exec` command

Examples:

```bash
cento cluster plan "implement feature A"
cento cluster run 20260428-120000-feature-a --dry-run
cento cluster implement "implement feature A"
cento cluster implement "implement feature A" --nodes linux,macos --dry-run
```

## Network Dashboard

`cento dashboard` is the combined web dashboard for overview, network, and jobs. `cento network` remains the focused cluster visibility command.

It:

- opens the existing Bubble Tea node monitor with `cento network --tui`
- serves a cluster web dashboard with `cento network --web`
- reads the cluster registry from `~/.config/cento/cluster.json`
- shows relay, nodes, bridge mesh output, cluster status, and job counts

Examples:

```bash
cento network --web
cento network --web --open
cento network --tui --no-remote
```

## Jobs Dashboard

`cento dashboard` includes live cluster jobs. `cento jobs` remains the focused dashboard for cluster job execution.

It:

- reads cluster job manifests from `workspace/runs/cluster-jobs`
- refreshes job state and task log tails every two seconds
- shows feature text, status, node assignment, task scripts, logs, summaries, and work artifact paths

Examples:

```bash
cento jobs
cento jobs --open
cento jobs --port 47883
```

## Idea Board

The idea board is a local web tool for documenting, categorizing, and scoring future Cento project ideas.

It:

- opens as `cento idea-board --open`
- stores editable seed data in `data/idea-board.json`
- tracks category, status, horizon, tags, next step, cluster rationale, and 1-5 scores
- keeps the first project list focused on cluster-powered Cento ideas

Example:

```bash
cento idea-board --open
```

## Telegram TUI

The Telegram tool is registered as `cento tg` and is now implemented as a Bubble Tea TUI.

It:

- opens as `cento tg`
- stores local Telegram config under `~/.config/cento/telegram.json`
- follows the repo TUI standard in `standards/tui.md`
- documents deferred Telegram and CRM integration work
- reserves `cento crm integration` as the CRM-side placeholder path

Examples:

```bash
cento tg
cento tg status
cento tg config --path
cento tg post --text "Hello from cento"
cento tg history --limit 20
cento tg docs
cento crm integration
```

## CRM Module

The CRM module keeps your career-consulting CRM embedded inside `cento` rather than as a disconnected app.

It:

- opens as `cento crm`
- provides an interactive questionnaire plus a self-hosted local CRM app
- creates career-intake dossiers for Telegram conversations, LinkedIn profiles, resumes, target companies, and notes
- generates Codex-ready prompts for resume, LinkedIn, cover-letter, interview, and action-plan artifacts
- bootstraps operational state under `workspace/runs/crm-app/`
- serves an instant no-build SPA through `cento crm serve`
- exposes module documentation through `cento crm docs`

Examples:

```bash
cento crm
cento crm questionnaire
cento crm init
cento crm intake init --person "Ada Lovelace" --target-role "Product Manager" --target-companies "Stripe,Notion,OpenAI,Linear,Figma"
cento crm intake add --person "Ada Lovelace" --kind resume --file ./resume.pdf
cento crm intake add --person "Ada Lovelace" --kind telegram --text "Raw conversation summary..."
cento crm intake plan --person "Ada Lovelace"
cento crm integration --provider redmine --person "Ada Lovelace" --start-workflow --dry-run
cento crm serve --open
cento crm integration
cento crm show
cento crm paths
cento crm docs
```

## Cento Funnel

`cento funnel` is the local-first business layer between content, traffic, leads, offers, and follow-up work.

It:

- stores funnel state in `~/.local/share/cento/funnel/state.json`
- tracks sources, funnel stages, leads, events, offers, and reusable next actions
- seeds practical LinkedIn, Telegram, GitHub, career-consulting, and automation-advisory examples
- writes Markdown reports under `workspace/runs/funnel/`
- supports isolated experiments with `CENTO_FUNNEL_DATA=/tmp/state.json`

Examples:

```bash
cento funnel init
cento funnel show
cento funnel sources
cento funnel funnels
cento funnel leads
cento funnel event conversation_started --source linkedin-posts --funnel career-consulting-discovery --lead ada-lovelace-linkedin --note "Booked async consult"
cento funnel report
cento funnel docs
make funnel-check
```

## Quick Help

The quick help tool is a rofi-style command palette for `cento`, closer to a searchable `:help` than a plain README.

It:

- indexes cento built-ins such as `help`, `tools`, `aliases`, and `conf`
- indexes registered tools from `data/tools.json`
- indexes your personal aliases from `~/.config/cento/aliases.sh`
- lets you fuzzy-search everything through `rofi`
- shows inline details before you run something
- can run the selected command or copy it to the clipboard

Examples:

```bash
./scripts/quick_help.sh
cento quick-help
cento quickhelp
```

## Dashboard

The dashboard is the combined launcher and status surface for `cento`.

It:

- opens as `cento dashboard`
- combines overview, network state, and cluster jobs in one server
- exposes `/api/state`, `/api/network`, and `/api/jobs`
- includes your configured aliases, registered tools, recent activity, and repo state
- shows wallpaper, connected audio, displays, cluster nodes, and current jobs
- writes logs to `logs/dashboard/`
- supports the Industrial OS skin with `--theme industrial`

Examples:

```bash
./scripts/dashboard_server.py
./scripts/dashboard_server.py --theme industrial --open
./scripts/telegram_tui.sh
./scripts/telegram_tui.sh status
go run ./scripts/telegram_tui.go
./scripts/crm_module.py
./scripts/crm_module.py questionnaire
./scripts/crm_module.py init
./scripts/crm_module.py serve --open
./scripts/crm_module.py show
./scripts/mcp_tooling.py
./scripts/mcp_tooling.py doctor
./scripts/mcp_tooling.py init --write-env
./scripts/dashboard.sh --plain-menu
./scripts/dashboard.sh --list
cento dashboard
cento dashboard --theme industrial --open
```

## Agent Manager

`cento agent-manager` is the operator control plane for Cento agent runs. It correlates run ledgers, issue state, tmux sessions, process trees, log files, and pool state to identify stale, idle, stuck, errored, duplicated, manual, and low-value agent activity.

Examples:

```bash
cento agent-manager scan
cento agent-manager scan --json
cento agent-manager report
cento agent-manager recommend --limit 10
cento agent-manager classify --issue-id 81
cento agent-manager mark-stale RUN_ID --reason "stuck validator" --dry-run
cento agent-manager mark-blocked 81 --reason "stuck validator" --evidence RUN_ID --dry-run
cento agent-manager terminate-tmux cento-agent-81-095103 --reason "stuck validator" --dry-run
```

Reports are written under `workspace/runs/agent-manager/`. Management actions default to dry-run unless `--apply` is passed.

## Desktop Presets

`cento preset` applies managed desktop presets for i3-based Linux sessions.

The Industrial OS preset:

- applies the `Cento Industrial OS` Kitty theme
- generates a black/orange industrial wallpaper under `~/.local/share/cento/industrial-os/`
- writes managed Polybar, Rofi, and Picom files under `~/.config/cento/industrial-os/`
- adds a guarded block to `~/.config/i3/config` so i3 reloads start the preset session
- keeps dashboard startup on the explicit `--dashboard-only --open` path
- binds `Mod+Shift+I` to compose workspace 1 into the Discord, hero, terminal, jobs, cluster, activity, and quick-actions layout with background images on every generated pane
- supports `cento preset industrial-os --workspace --black-only` to compose the same workspace with plain black pane backgrounds
- routes `Mod+h/j/k/l` through a visual focus helper on the Industrial OS cockpit, with normal i3 focus behavior as fallback elsewhere
- writes preset logs to `logs/industrial-os/` and workspace compose logs to `logs/industrial-workspace/`

Examples:

```bash
cento preset list
cento preset industrial-os
cento preset industrial-os --workspace
cento preset industrial-os --workspace --black-only
cento preset industrial-os --session
cento preset industrial-os --dashboard-only --open
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

## i3 Reorg

The i3 reorg tool moves common desktop windows onto the preferred workspace map. Study mode keeps the Abao/Tokyo study-with-me YouTube window on the top monitor in workspace `L2`, fullscreen. In the i3 key layout, `L2` is the left/A workspace and `R2` is the right/D workspace.

It:

- moves Firefox to workspace 1
- moves common terminal windows and tmux/nvim/vim-titled windows to workspace 2
- moves Discord to workspace 4
- moves Telegram to workspace 5
- keeps workspaces 1 through 5 on the bottom monitor
- moves the Abao/Tokyo study video to workspace L2 on the top monitor with `--study`
- opens `https://www.youtube.com/watch?v=QYpDQxHfTPk` in Firefox when study mode cannot find an existing study window
- supports a dry run before applying i3 commands

Examples:

```bash
./scripts/i3reorg.sh --dry-run
./scripts/i3reorg.sh --bottom-output DP-4.8
./scripts/i3reorg.sh --study
./scripts/i3reorg.sh --focus 2
cento i3reorg
cento i3reorg --study
cento i3reorg --focus 2
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
