# Platform Support

This file is generated from `data/tools.json`.

## Summary

- macOS tools: 19
- Linux tools: 28
- both platforms: 18
- Linux only: 10
- macOS only: 1

## Tool Matrix

| Tool | macOS | Linux | Description |
|---|---:|---:|---|
| `audio-quick-connect` | no | yes | Quickly connect a paired Bluetooth audio device by name or address with a short retry path and per-run logs. |
| `batch-exec` | yes | yes | Run one shell command across multiple directories with dry-run and git-only support. |
| `bluetooth-audio-doctor` | no | yes | Diagnose Bluetooth and Bluetooth-audio failures, generate detailed reports, and apply safe repair actions. |
| `bridge` | yes | yes | Create a reverse SSH tunnel through the OCI VM so another machine can SSH back into this host through the VM relay. |
| `burp` | no | yes | Download, set up, and control PortSwigger Burp Suite Community through cento wrappers. |
| `cento-cli` | yes | yes | Unified cento facade for built-ins, terminal docs browsing, tool dispatch, and user-defined aliases. |
| `crm` | yes | yes | Embedded cento CRM with questionnaire bootstrap, career-intake dossiers, local JSON persistence, and a self-hosted no-build SPA. |
| `daily` | yes | yes | Bubble Tea execution cockpit for morning brief, midday recalibration, evening wrap-up, and local continuity. |
| `dashboard` | no | yes | Run a localhost web dashboard with current state, recent cento activity, aliases, tools, and repo progress. |
| `display-layout-fix` | no | yes | Detect two connected monitors, stack them vertically, and refresh wallpaper plus polybar. |
| `gather-context` | yes | yes | Gather AI-ready local and remote Cento context including platform support, repo state, command paths, MCP hints, and SSH connectivity. |
| `i3reorg` | no | yes | Move numeric i3 workspaces to the bottom monitor, apply the preferred app map, and optionally place the Abao/Tokyo study YouTube window on top workspace L2 fullscreen. |
| `install-linux` | no | yes | Install local Linux dependencies, wrappers, PATH block, and Zsh integration for cento. |
| `install-macos` | yes | no | Install local macOS dependencies, wrappers, PATH block, and Zsh integration for cento. |
| `kitty-theme-manager` | yes | yes | Manage Kitty themes with interactive selection, persistent logs, and tmux-aware refresh behavior. |
| `mcp` | yes | yes | Manage repo-root MCP config, env templates, validation, and tool-call docs. |
| `network-tui` | yes | yes | Platform-agnostic Bubble Tea monitor for local and remote Cento node health, platform support, command paths, repo status, and bridge connectivity. |
| `platform-report` | yes | yes | Report declared macOS and Linux support for registered cento tools and generate docs/platform-support.md. |
| `project-scaffold` | yes | yes | Scaffold a generic project with starter README, notes, scripts, data, and workspace folders. |
| `quick-help` | no | yes | Rofi-based searchable help palette for cento built-ins, tools, and aliases. |
| `quick-help-fzf` | yes | yes | Cross-platform fzf command palette for cento built-ins, tools, and aliases. |
| `rd` | no | yes | Terminate and relaunch Discord through the available desktop launcher. |
| `repo-snapshot` | yes | yes | Create a compact repo status report including tree, git status, diffstat, and recent commits. |
| `scan` | yes | yes | Scan cento for a topic and generate an archived HTML one-pager with explanation and snippets. |
| `search-report` | yes | yes | Search a filesystem tree and write a Markdown report with matches and context. |
| `system-inventory` | yes | yes | Capture a Markdown baseline of host, shell, tooling, and environment state. |
| `tool-index` | yes | yes | Generate a Markdown tool index from the central registry. |
| `tui` | yes | yes | Bubble Tea Telegram TUI with cached Go launcher, local config, and planned CRM hooks. |
| `wallpaper-manager` | no | yes | Choose, preview, apply, and persist desktop wallpapers for i3 and feh. |

## Available On Both

- `batch-exec`
- `bridge`
- `cento-cli`
- `crm`
- `daily`
- `gather-context`
- `kitty-theme-manager`
- `mcp`
- `network-tui`
- `platform-report`
- `project-scaffold`
- `quick-help-fzf`
- `repo-snapshot`
- `scan`
- `search-report`
- `system-inventory`
- `tool-index`
- `tui`

## Linux Only

- `audio-quick-connect`
- `bluetooth-audio-doctor`
- `burp`
- `dashboard`
- `display-layout-fix`
- `i3reorg`
- `install-linux`
- `quick-help`
- `rd`
- `wallpaper-manager`

## macOS Only

- `install-macos`
