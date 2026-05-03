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
- Read `CLUSTER_NOTICE.md` for current cluster coordination options, including cheap Spark/Codex worker pool guidance.

- Keep `data/cento-cli.json` aligned with `scripts/cento.sh` when the root CLI built-ins change.
- For Zsh, Oh My Zsh, or tmux integration changes, read `docs/terminal-integration.md` and run `make terminal-e2e`.

## ChatGPT Pro prompt bridge

- When the operator asks to create a prompt for ChatGPT Pro or "smart bro" and copy it to the clipboard, use the stable bridge command exactly as `cento temp run`.
- Do not add an ID, suffix, postfix, or alternate wrapper for this workflow. Do not tell the operator to run `cento temp run <id>` for the ChatGPT Pro prompt bridge.
- Write or update the prompt Markdown under `workspace/runs/temp/chatgpt-pro/`, point the default temp command entry `cento-dev-scale-pro-prompt` at that Markdown file, run `cento temp run` automatically, and visibly report that the prompt was copied to the clipboard.
- `cento temp run <id>` is only for advanced one-off temp commands, not for the ChatGPT Pro prompt bridge.
