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
