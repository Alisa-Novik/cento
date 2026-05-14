---
name: cento-native
description: "Use when working with Cento as a native automation platform: discovering existing Cento tools before creating commands, routing user intent to registered tools, using temp/one-off command paths, deciding when agent-work is required, operating across Mac/Linux/iPhone nodes, or changing Cento skills, MCP, Taskstream, cluster, mobile, or command behavior."
---

# Cento Native

Treat Cento as the source of truth. Before inventing scripts, tools, registry entries, workflows, or cross-node commands, ask Cento what already exists and route through that surface.

## First Moves

From a Cento checkout, start with:

```bash
cento gather-context --no-remote
cento tools
```

Use full `cento gather-context` when Linux reachability matters. Treat `data/tools.json`, `cento tools`, `cento platforms`, and `cento docs` as the live command contract.

If the task is about one tool or command family, inspect it before editing:

```bash
cento docs TOOL_OR_BUILTIN
cento platforms macos
cento platforms linux
rg -n '"id": "TOOL_ID"|TOOL_ID|subcommand|usage' data scripts docs
```

## Self-Improvement Log

For each major Cento self-improvement step, check and maintain the append-only log at `docs/ai-self-improvement-log.md`.

- Before planning or implementing self-improvement work, read the latest relevant records when the change affects routing, autonomy, pipeline behavior, skill behavior, observability, validation, agent-work, or operator workflow.
- Compare the current request against prior records so Cento does not repeat unclear or already-completed loops without naming what is different now.
- At the end of each major step, append a new record using the schema in that doc.
- Record what changed, what worked, what did not work, validation/evidence, next steps, suggestions, and tags.
- Treat the log as append-only. Do not rewrite prior records; add corrections or follow-ups as new records unless a security redaction is required.

## Intent Recognition

Before choosing a Cento surface, infer the operator's intent from the whole message, recent context, attachments, and requested side effects. Use that intent to decide whether the work is read-only analysis, human-facing documentation, command-reference documentation, implementation, tasking, one-off execution, pipeline planning, cross-node work, or evidence/validation.

Prefer these defaults unless the user says otherwise:

- "somewhere in Docs", "save in Docs", or "human Docs" means human-facing Cento docs: readable files under `docs/`, Cento Console `/docs` links, and `docs/nav.html` when discoverability matters. `cento docs`, `data/cento-cli.json`, and `docs/tool-index.md` are command-reference surfaces, not the whole Docs intent.
- "within cento" means the Cento checkout and registered Cento surfaces, not an ad hoc home-directory artifact.
- "analysis", "summary", "suggestions", "check if", or "calculate" means read-only work unless the user later asks to implement or save the output.
- "create plan" means write an actionable plan artifact when the user asks to save it; "Implement the plan" means execute the latest accepted plan instead of stopping at another proposal.
- "e2e", "coordinate until done", or "until done" means carry implementation through validation and evidence, and create/use agent-work only when durable task coordination is part of the request.
- "use OCI CLI", "bucket", "namespace", or "Object Storage" means route through the registered `object-storage` surface before adding cloud-specific code.

If multiple interpretations fit, choose the lowest side-effect path that still satisfies the user. Ask only when the wrong intent would cause spend, broad dispatch, public exposure, destructive changes, or a materially different deliverable.

## Short Tools Summary

This summary is populated from `data/tools.json` / `cento tools` as a quick routing aid. Treat the live registry and `cento docs TOOL` as the source of truth; this section can lag or disagree briefly when registry, generated docs, and installed skill copies drift.

| Tool | Use |
|---|---|
| `agent-pool-kick` | Keep bounded builder, validator, small-task, and coordinator lanes moving. |
| `agent-processes` | Inspect cluster-wide managed and manual agent sessions. |
| `agent-work` | Track, assign, dispatch, validate, and review Taskstream-backed agent work. |
| `agent-work-hygiene` | Reconcile agent ledgers, tmux sessions, and Codex/Claude processes. |
| `audio-quick-connect` | Connect paired Bluetooth audio devices on Linux. |
| `batch-exec` | Run one shell command across many directories. |
| `bluetooth-audio-doctor` | Diagnose and repair Bluetooth audio failures. |
| `bridge` | Manage OCI reverse SSH bridge and cross-node command routes. |
| `build` | Run manifest-owned local build worker and patch integration flows. |
| `burp` | Download, set up, and control Burp Suite Community. |
| `cento-cli` | Use the main Cento facade, built-ins, docs, tools, aliases, and completion. |
| `cento-mcp` | Expose safe Cento context, agent-work, story, cluster, and bridge MCP tools. |
| `cluster` | Manage nodes, cluster status, remote execution, bridge healing, and git drift. |
| `crm` | Run the embedded career CRM module and local SPA. |
| `daily` | Open the execution cockpit for daily planning and continuity. |
| `dashboard` | Serve the local Cento web dashboard. |
| `demo-evidence` | Record 10-30 second demo videos with receipts for Factory and worker evidence. |
| `discord` | Update, rerun, and inspect Discord on Linux. |
| `display-layout-fix` | Stack two monitors vertically and refresh wallpaper/polybar. |
| `factory` | Plan, queue, dispatch, collect, validate, integrate, and release multi-task runs. |
| `foundry` | Create Cento-native business tools through Factory, Workset, train promotion, storage policy, cost receipts, and demo evidence. |
| `gather-context` | Gather AI-ready local and remote Cento context. |
| `i3reorg` | Reorganize i3 workspaces across preferred monitor layout. |
| `incident` | Run bounded incident checks and guarded escalation. |
| `install-linux` | Install Linux Cento dependencies and shell integration. |
| `install-macos` | Install macOS Cento dependencies and shell integration. |
| `kitty-theme-manager` | Manage Kitty themes and tmux-aware refresh. |
| `mcp` | Manage repo-root MCP config, templates, validation, and docs. |
| `mobile` | Run native iOS/PWA helper and e2e validation commands. |
| `mozilla-vpn` | Control Mozilla VPN from the Linux desktop pane. |
| `network-tui` | Monitor cluster connection, node, tmux, and companion-device state. |
| `notify` | Send ntfy notifications to configured targets. |
| `object-storage` | Upload a run-scoped dummy file to OCI Object Storage and record receipts. |
| `opencode` | Launch the managed opencode fork wrapper. |
| `parallel-delivery` | Coordinate Hard ProReq fanout, Workset manifests, and validation/demo receipts. |
| `platform-report` | Report platform support and generate the support matrix. |
| `preset` | Apply desktop presets such as Industrial OS. |
| `project-scaffold` | Scaffold a generic project workspace. |
| `quick-help` | Open the Linux rofi help palette. |
| `quick-help-fzf` | Open the cross-platform fzf command palette. |
| `rd` | Compatibility shortcut for `cento discord rerun`. |
| `repo-snapshot` | Write a compact repo tree/status/diff/commit report. |
| `runtime` | Inspect and validate builder runtime profiles. |
| `scan` | Generate an archived HTML one-pager for a repo topic. |
| `search-report` | Search a tree and write a Markdown report. |
| `system-inventory` | Capture host, shell, tool, PATH, and repo baseline. |
| `temp` | Register short-lived operator commands and captured outputs. |
| `tool-index` | Generate `docs/tool-index.md` from the registry. |
| `tui` | Open the Telegram TUI. |
| `wallpaper-manager` | Choose, preview, apply, and persist i3/feh wallpapers. |
| `workset` | Run exclusive-path N-worker delivery with sequential integration. |

For Factory or Codex worker visual evidence, prefer:

```bash
cento demo-evidence record --factory-run workspace/runs/factory/<run-id> --task <task-id> --worker <worker-id> --duration 15
```

## Routing Rules

Prefer existing paths in this order:

1. MCP tools, when a structured Cento MCP surface exists for the operation.
2. Registered CLI tools from `cento tools` / `data/tools.json`.
3. Existing aliases from `cento aliases`.
4. Existing scripts under `scripts/` only after confirming they are the registered entrypoint or intended backend.
5. New code or registry entries only when discovery shows no existing path fits.

For the Cento temp clipboard bridge, never create a temp command registry entry. The only supported operator command is:

```bash
cento temp run
```

To change what it copies, edit only the `COPY_FILE` line in `scripts/cento_temp.sh`. Do not add ids, flags, list/show/add/remove, secret prompts, cross-node routing, or fallback chains to `cento temp`.

For other one-off or temporary shell work, do not add a registered tool by default. Use the existing one-off command surface:

```bash
cento cluster exec macos -- '...'
cento cluster exec linux -- '...'
cento bridge to-mac -- '...'
cento bridge to-linux -- '...'
cento batch-exec --root DIR --pattern GLOB --command '...'
```

Use `batch-exec` for "run this shell command over directories". Use `cluster exec` or `bridge to-*` for node-targeted temporary commands. Register a new tool only when the command is durable, user-facing, documented, and not covered by existing Cento routing.

## Choose Correct Pipeline

Most Cento requests should route through an existing pipeline instead of a new script or ad hoc implementation. If a specific pipeline, tool, or command is named, use that surface. If the request is ambiguous, pick the lowest-compute pipeline that satisfies the intent and only ask the user when the choice changes side effects, spend, or scope in a way that cannot be inferred.

Default compute order:

1. Read-only inspection, dry-run, or prompt/artifact generation.
2. Deterministic local pipeline fallback with no live model calls.
3. Fixture or local-command execution.
4. API worker execution with explicit budget caps.
5. Pro, image generation, broad worker fanout, or live dispatch.

Pipeline routing defaults:

- Use `hard-proreq` / Dev Pipeline Studio Hard ProReq when the user asks for "proreq", "requirements", "manifest", "roadmap from my vision", "integration/validation guidance", or "ask ChatGPT Pro". Treat this as a prompt-and-artifact pipeline by default: parse the operator text into a ChatGPT image prompt for the screenshot lane and a ChatGPT Pro prompt/request for story manifests, integration manifests, validation manifests, and implementation guidance. Do not convert it directly into a hand-written doc unless the user explicitly asks for a doc output.
- Use `parallel-pipeline` or `cento workset` when the user asks to run parallel workers, execute code delivery, split work across exclusive write paths, or produce patch/artifact outputs from multiple workers.
- Use `factory` when the request is a durable multi-task project needing intake, queueing, leases, dispatch plans, patch collection, Safe Integrator state, release packets, or Taskstream synchronization.
- Use `scan` when the user asks for a one-page explanation of an existing repo topic or wants a codebase map without changing project state.
- Use `agent-work` when the user wants persistent task assignment, Taskstream issues, worker ownership, or human-visible operational tracking.

For ProReq requests, only enable live Pro/image/API dispatch when the user asks for it, the relevant environment is configured, or the named pipeline contract requires it. Otherwise generate the request artifacts and evidence through the no-model or lowest-compute path and clearly record that the live call was skipped.

## Tasking

For Cento feature requests, UI changes, automation changes, MCP changes, Taskstream/agent-work, cluster behavior, mobile/iPhone behavior, Agent Processes/TUI, or command behavior changes:

```bash
cento agent-work create --title "..." --description "..." --node macos --role builder --package agent-ops --json
```

If local tasking fails, try the Linux path:

```bash
cento cluster exec linux -- 'cd /home/alice/projects/cento && ./scripts/cento.sh agent-work create --title "..." --description "..." --node macos --role builder --package agent-ops --json'
```

If both task backends are unavailable, state that clearly and continue only if the user needs immediate action. Do not block pure status checks, explanations, log reads, restarts, or explicitly taskless requests on agent-work.

Choose packages conservatively: `agent-ops` for skills/routing/dispatch, `taskstream` for agent-work UI/workflow, `cluster` for bridge/mesh/node behavior, `iphone-cento` for mobile/iPhone, `mobile` for app-specific mobile work.

## Safety Rules

- Never copy `.env.mcp` or secrets between nodes.
- Never overwrite unrelated dirty work. Read `git status --short` and scope edits tightly.
- Do not run Linux-only tools on macOS or macOS-only tools on Linux unless changing platform support.
- Do not reset pairing, tunnel, signing, launchd, tmux, Docker, or git state without explaining why first.
- If a user asks for the temp clipboard bridge, keep the route at `cento temp run`; do not create named temp entries or ID-based run variants.
- If the user says "reuse existing Cento tool", scan `cento tools`, `cento aliases`, `data/tools.json`, and matching scripts before proposing edits.

## Validation

Use the narrowest reliable validation:

```bash
python3 -m json.tool data/tools.json >/tmp/cento-tools-json-check.txt
cento tools
cento platforms macos
make check
```

For shell wrappers, run `--help` or a dry-run path. For registry changes, verify the tool appears in `cento tools` and platform reports. For cross-node behavior, validate through `cento cluster status`, `cento bridge mesh-status`, or the specific `cluster exec` path used.

## References

Read [references/routing.md](references/routing.md) when deciding how to map an ambiguous user request to an existing Cento command, especially temporary command requests.
