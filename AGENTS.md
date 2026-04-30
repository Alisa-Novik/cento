# AGENTS

Repo guidance for AI agents working in `cento`:

- Treat `scripts/` as the canonical home for automation tools.
- Prefer shell scripts for orchestration and Python for structured reporting.
- Keep new tools registered in `data/tools.json`.
- Keep `README.md` and `Makefile` aligned with the actual tool surface.
- Write generated artifacts to `workspace/runs/` unless a tool has a better explicit target.

- Consult `standards/` before changing repo-wide user-facing patterns; interactive terminal apps should follow `standards/tui.md`.
- Use `standards/mcp.md` whenever you add or change repo-root MCP config, env templates, or tool-call guidance.
- Prefer the repo-local `cento` MCP server for board, story, cluster, and bridge operations when an MCP client is available. Codex skill guidance lives in `skills/codex/cento-mcp/SKILL.md`.

- Keep `data/cento-cli.json` aligned with `scripts/cento.sh` when the root CLI built-ins change.
- For Zsh, Oh My Zsh, or tmux integration changes, read `docs/terminal-integration.md` and run `make terminal-e2e`.
