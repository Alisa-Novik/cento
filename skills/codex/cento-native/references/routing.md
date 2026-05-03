# Cento Routing Reference

Use this when the user asks for a Cento command, temporary automation, cross-node operation, or AI-native Cento workflow.

## Discovery Checklist

Run the smallest set that answers the routing question:

```bash
cento gather-context --no-remote
cento tools
cento aliases
cento platforms
cento docs TOOL
rg -n 'KEYWORD|TOOL_ID|subcommand|usage' data scripts docs --glob '!docs/nav.html' --glob '!workspace/**' --glob '!logs/**'
```

If the user references "registered tools", inspect `data/tools.json`. If they reference "temp commands", use `cento temp` first, then `cluster`, `bridge`, and `batch-exec`.

## Common Routes

- Local context: `cento gather-context --no-remote`
- Cross-node context: `cento gather-context`
- Platform support: `cento platforms macos` or `cento platforms linux`
- Registered command list: `cento tools`
- Built-in docs: `cento docs`
- Aliases: `cento aliases`
- Generic temp command: `cento temp add ID --title TITLE --node local|macos|linux --command-file /tmp/command.sh`
- Show temp command: `cento temp show ID`
- Run temp command: `cento temp run ID`
- Remove temp command: `cento temp remove ID`
- Mac temp command: `cento cluster exec macos -- '...'`
- Linux temp command: `cento cluster exec linux -- '...'`
- VM socket to Mac/Linux: `cento bridge to-mac -- '...'` or `cento bridge to-linux -- '...'`
- One command across directories: `cento batch-exec --root DIR --pattern GLOB --command '...'`
- Search and archive a one-pager: `cento scan --query "..." --no-open`
- Repo snapshot: `cento repo-snapshot`
- Agent task: `cento agent-work create ...`

## When To Edit Registry

Edit `data/tools.json` only when adding or changing a durable Cento tool. Do not edit it for:

- one-time diagnostics
- user-local commands
- temporary shell snippets
- experiments that can live under `workspace/runs`
- command bundles the user only needs to run once

When registry edits are necessary, also validate JSON and tool visibility:

```bash
python3 -m json.tool data/tools.json >/tmp/cento-tools-json-check.txt
cento tools | rg TOOL_ID
cento platforms macos
```

## Cross-Node Notes

The expected nodes are:

- macOS: `/Users/anovik-air/cento`
- Linux: `/home/alice/projects/cento`

Prefer Cento wrappers over raw SSH. Use raw SSH only when wrapper discovery shows it is necessary.

Do not assume Linux is reachable. Check `cento gather-context`, `cento cluster status`, or `cento bridge check` first.

Mac and Linux registries can drift. If `cento temp ...` is unknown on one node, check the other node before concluding the tool does not exist.
