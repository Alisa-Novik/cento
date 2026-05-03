# Claude Code: Cento Native

Use this whenever work touches Cento tools, Taskstream/agent-work, MCP, cluster/bridge, mobile/iPhone, skills, or command routing.

## Core Contract

Treat Cento as the source of truth. Before creating scripts, registry entries, one-off commands, or new workflows, discover the existing Cento surface:

```bash
cento gather-context --no-remote
cento tools
cento aliases
cento platforms
```

Use full `cento gather-context` when Linux/macOS reachability matters. Use `data/tools.json`, `cento tools`, `cento docs`, and platform reports as the live command contract.

## Route Before Editing

Prefer existing paths in this order:

1. Repo-local Cento MCP tools for board, story, cluster, and bridge operations.
2. Registered CLI tools from `cento tools`.
3. Existing aliases from `cento aliases`.
4. Existing scripts under `scripts/`, after confirming the registered entrypoint.
5. New code or registry entries only when no existing route fits.

For Cento temporary operator commands, use the generic `temp` tool instead of asking the human to paste multiline shell:

```bash
cento temp add ID --title TITLE --node local|macos|linux --command-file /tmp/command.sh
cento temp show ID
cento temp run ID
cento temp remove ID
```

For other temporary or one-off shell work, do not add a permanent registered tool by default. Use:

```bash
cento cluster exec macos -- '...'
cento cluster exec linux -- '...'
cento bridge to-mac -- '...'
cento bridge to-linux -- '...'
cento batch-exec --root DIR --pattern GLOB --command '...'
```

Use `batch-exec` for one command over directories. Use `cluster exec` or `bridge to-*` for lower-level node-targeted temp commands. If `cento temp ...` is unknown on one node, check the other node before concluding it does not exist.

## Tasking

For Cento feature or behavior changes, create or identify agent-work unless the user explicitly says not to:

```bash
cento agent-work create --title "..." --description "..." --node macos --role builder --package agent-ops --json
```

If local tasking fails, try Linux:

```bash
cento cluster exec linux -- 'cd /home/alice/projects/cento && ./scripts/cento.sh agent-work create --title "..." --description "..." --node macos --role builder --package agent-ops --json'
```

If both task backends are unavailable, state the blocker and continue only if immediate action is needed.

## Safety

- Keep `.env.mcp` machine-local.
- Do not overwrite unrelated dirty work.
- Do not run platform-specific tools on the wrong node.
- Do not reset pairing, signing, launchd, tmux, Docker, bridge, or git state without explaining why.
- If the user says to reuse an existing Cento tool, scan before proposing implementation.

## Validation

Use focused checks:

```bash
python3 -m json.tool data/tools.json >/tmp/cento-tools-json-check.txt
cento tools
cento platforms macos
make check
```

For cross-node behavior, validate with `cento cluster status`, `cento bridge mesh-status`, or the exact `cluster exec` path used.
