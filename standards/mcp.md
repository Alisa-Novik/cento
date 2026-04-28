# MCP Standard

## Purpose

`cento` should carry one obvious place to configure MCP servers and one obvious place to document how they should be used.

## Root files

- `.mcp.json` is the canonical repo-root MCP config.
- `.env.mcp.example` documents the environment variables that `.mcp.json` expects.
- `mcp/` holds MCP-specific companion docs such as tool-call guidance.

## Repo expectations

- Add or update MCP docs in `README.md` and a focused doc under `docs/`.
- Register user-facing MCP helpers in `data/tools.json`.
- Expose validation through `make check` and, when useful, a runnable `make` target.
- Keep machine-local secrets out of git-tracked files.

## Operational expectations

- Prefer local filesystem access before external servers.
- Keep the default server set small and fast.
- Use environment variables for secrets and absolute machine-local paths.
- Provide a doctor or validation path before asking users to rely on the config.
