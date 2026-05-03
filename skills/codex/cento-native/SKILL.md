---
name: cento-native
description: Use when working with Cento as a native automation platform: discovering existing Cento tools before creating commands, routing user intent to registered tools, using temp/one-off command paths, deciding when agent-work is required, operating across Mac/Linux/iPhone nodes, or changing Cento skills, MCP, Taskstream, cluster, mobile, or command behavior.
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

## Routing Rules

Prefer existing paths in this order:

1. MCP tools, when a structured Cento MCP surface exists for the operation.
2. Registered CLI tools from `cento tools` / `data/tools.json`.
3. Existing aliases from `cento aliases`.
4. Existing scripts under `scripts/` only after confirming they are the registered entrypoint or intended backend.
5. New code or registry entries only when discovery shows no existing path fits.

For ChatGPT Pro / "smart bro" prompt handoff, the stable bridge command is always exactly:

```bash
cento temp run
```

Do not add an ID, suffix, postfix, or alternate wrapper for this workflow. When the operator asks for a prompt to ChatGPT Pro, write or update the prompt Markdown under `workspace/runs/temp/chatgpt-pro/`, point the default temp command entry `cento-dev-scale-pro-prompt` at that Markdown file, run `cento temp run` automatically, and report that it copied the prompt to the clipboard.

For other Cento temporary operator commands, use the generic `temp` tool instead of asking the human to paste multiline shell:

```bash
cento temp add ID --title TITLE --node local|macos|linux --command-file /tmp/command.sh
cento temp show ID
cento temp run ID
cento temp remove ID
```

For other one-off or temporary shell work, do not add a registered tool by default. Use the existing one-off command surface:

```bash
cento cluster exec macos -- '...'
cento cluster exec linux -- '...'
cento bridge to-mac -- '...'
cento bridge to-linux -- '...'
cento batch-exec --root DIR --pattern GLOB --command '...'
```

Use `batch-exec` for "run this shell command over directories". Use `cluster exec` or `bridge to-*` for node-targeted temporary commands. Register a new tool only when the command is durable, user-facing, documented, and not covered by existing Cento routing.

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
- If a user asks for a ChatGPT Pro prompt bridge, update the default prompt entry and run `cento temp run` with no ID. If a user asks for a different temp command, create a `cento temp add ...` entry and give them `cento temp run ID`; do not add a permanent registry entry unless asked.
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
