# MCP Tooling

`cento` now includes repo-root MCP configuration and a small helper tool surface.

## Files

- `.mcp.json`
  Canonical MCP server configuration for this repo.
- `.env.mcp.example`
  Example environment file for MCP-related variables.
- `mcp/README.md`
  Root-level setup notes.
- `mcp/tool-calls.md`
  Tool-call guidance and intent mapping.
- `scripts/cento_mcp_server.py`
  Repo-local Cento MCP stdio server for agent-work, story manifests, cluster state, bridge state, and platform lookup.

## Command surface

- `cento mcp init`
  Create `.env.mcp` from the example file when needed.
- `cento mcp doctor`
  Validate `.mcp.json`, inspect referenced environment variables, and check launcher commands.
- `cento mcp docs`
  Print this documentation.
- `cento mcp paths`
  Print the key repo-root MCP paths.

## Default servers

- `cento`
  Structured Cento operations for local agents. Use it for board, story, cluster, and bridge workflows.
- `filesystem`
  Local repo access scoped by `CENTO_ROOT`.
- `fetch`
  External document fetches.
- `github`
  GitHub repository access when `GITHUB_PERSONAL_ACCESS_TOKEN` is set.

## Setup

```bash
cd /home/alice/projects/cento
cp .env.mcp.example .env.mcp
cento mcp doctor
```

After that, point your MCP-capable client at the repo-root `.mcp.json`.

## Cento Server

Smoke-test the local Cento MCP server:

```bash
python3 scripts/cento_mcp_server.py --list-tools
python3 scripts/cento_mcp_server.py --call-tool cento_agent_work_list --arguments '{}'
```

Detailed usage lives in `docs/cento-mcp-server.md`.
