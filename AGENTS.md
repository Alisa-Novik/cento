# AGENTS

Repo guidance for AI agents working in `cento`:

- Treat `scripts/` as the canonical home for automation tools.
- Prefer shell scripts for orchestration and Python for structured reporting.
- Keep new tools registered in `data/tools.json`.
- Keep `README.md` and `Makefile` aligned with the actual tool surface.
- Write generated artifacts to `workspace/runs/` unless a tool has a better explicit target.
