# MCP Setup

The repo root now carries the baseline MCP setup for `cento`.

Files:

- `.mcp.json`
  Canonical client-facing MCP server config for this repo.
- `.env.mcp.example`
  Example environment file for values referenced by `.mcp.json`.
- `mcp/tool-calls.md`
  Tool-call guidance for common agent tasks against this repo.

Common flow:

1. Copy `.env.mcp.example` to `.env.mcp`.
2. Fill in any needed secrets such as `GITHUB_PERSONAL_ACCESS_TOKEN`.
3. Run `cento mcp doctor`.
4. Point your MCP-capable client at the repo-root `.mcp.json`.

The current baseline enables three common server lanes:

- `filesystem` for local repo access
- `fetch` for remote document fetches
- `github` for GitHub-backed repository work when a token is provided
