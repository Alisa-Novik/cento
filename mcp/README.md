# MCP Setup

The repo root now carries the baseline MCP setup for `cento`.

Files:

- `.mcp.json`
  Canonical client-facing MCP server config for this repo.
- `.env.mcp.example`
  Example environment file for values referenced by `.mcp.json`.
- `mcp/tool-calls.md`
  Tool-call guidance for common agent tasks against this repo.
- `scripts/cento_mcp_server.py`
  Repo-local Cento MCP server for board, story, cluster, and bridge operations.

Common flow:

1. Copy `.env.mcp.example` to `.env.mcp`.
2. Fill in any needed secrets such as `GITHUB_PERSONAL_ACCESS_TOKEN`.
3. Run `cento mcp doctor`.
4. Point your MCP-capable client at the repo-root `.mcp.json`.

The current baseline enables four common server lanes:

- `cento` for structured Cento agent-work, story manifest, cluster, and bridge operations
- `filesystem` for local repo access
- `fetch` for remote document fetches
- `github` for GitHub-backed repository work when a token is provided

For Cento-specific workflows, prefer the `cento` server over shelling out manually. See `docs/cento-mcp-server.md`.
