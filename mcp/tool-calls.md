# Tool Calls

Use these patterns when an MCP-capable client is attached to the repo-root `.mcp.json`.

## Intent to server

- Inspect local files, templates, docs, or generated artifacts:
  Use `filesystem`.
- Inspect or mutate Cento board, story, cluster, bridge, or platform state:
  Use `cento`.
- Pull remote documentation or a raw URL into context:
  Use `fetch`.
- Search, inspect, or mutate GitHub issues, pull requests, and repository metadata:
  Use `github`.

## Preferred order

1. Start with `cento` for board, story, cluster, bridge, or platform state.
2. Start with `filesystem` for repo-local code, docs, templates, and generated artifacts.
3. Use `fetch` only when the needed source is outside the repo.
4. Use `github` when the task is genuinely repository-hosted rather than just local code reading.

## Practical examples

- "Show me how `cento crm serve` is wired."
  Start with `filesystem` against `scripts/crm_module.py` and `docs/crm-module.md`.
- "What should an agent pick up next?"
  Use `cento_agent_work_list`, then `cento_agent_work_show` for candidate issues.
- "Validate story #60 and render its hub."
  Use `cento_story_manifest_validate`, then `cento_story_manifest_render_hub`.
- "What is the cluster doing?"
  Use `cento_context`, `cento_cluster_status`, and `cento_bridge_mesh_status`.
- "Read the latest external API docs for a dependency."
  Use `fetch` on the official documentation URL.
- "List open PRs touching the Telegram tool."
  Use `github` against the relevant repository and PR search surface.

## Notes

- Keep local-first behavior. Prefer repo files before external fetches.
- Keep secrets out of `.mcp.json`. Put them in your shell environment or `.env.mcp`.
- Treat `.mcp.json` as shared configuration and `.env.mcp` as machine-local state.
- Set `CENTO_MCP_READ_ONLY=1` when you want board and cluster inspection without write tools.
