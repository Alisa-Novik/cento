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

If the user references "registered tools", inspect `data/tools.json`. If they reference the temp clipboard bridge, route only to `cento temp run`. For other one-off shell work, use `cluster`, `bridge`, or `batch-exec`.

## Intent Defaults

Classify intent before choosing a route:

- Human docs: "somewhere in Docs", "save in Docs", "human Docs", or a manager/operator handoff. Use readable `docs/` pages, Cento Console `/docs`, and `docs/nav.html` where discoverability matters.
- Command docs: "cento docs", "CLI docs", "tool docs", or "registry". Use `data/cento-cli.json`, `data/tools.json`, and generated references.
- Read-only: "analysis", "summary", "suggestions", "check if", "calculate". Inspect and report without code edits unless the user asks to save an artifact.
- Implementation: "implement", "fix", "add", "wire", "e2e", "coordinate until done". Make the change and validate it.
- Plan execution: "Implement the plan" means execute the latest accepted plan, not write a second plan.
- Cloud storage: "OCI CLI", "bucket", "namespace", "Object Storage". Prefer the registered `object-storage` route.

When intent is ambiguous, use the lowest side-effect route and ask only if the wrong route would create spend, public exposure, destructive changes, broad dispatch, or a meaningfully different artifact.

## Common Routes

- Local context: `cento gather-context --no-remote`
- Cross-node context: `cento gather-context`
- Platform support: `cento platforms macos` or `cento platforms linux`
- Registered command list: `cento tools`
- Built-in docs: `cento docs`
- Aliases: `cento aliases`
- Temp clipboard bridge: `cento temp run`
- Change copied Markdown: edit only `COPY_FILE` in `scripts/cento_temp.sh`
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

Mac and Linux registries can drift, but `cento temp` is intentionally not a cross-node command surface. If clipboard transport breaks, fix the local `pbcopy` shim instead of expanding `cento temp`.
