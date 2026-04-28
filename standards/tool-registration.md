# Tool Registration Standard

When adding or changing a user-facing tool in `cento`:

1. Put the canonical launcher in `scripts/`.
2. Register the tool in `data/tools.json` with commands, outputs, and notes.
   - Declare supported operating systems in `platforms` using values such as `linux` and `macos`; the root `cento` dispatcher enforces this before launching registered tools.
3. Update `README.md` so the tool appears in the included tools, examples, and any relevant sections.
4. Regenerate `docs/tool-index.md` from the registry.
5. Add or update a dedicated doc in `docs/` when the tool has its own workflow.
6. Update `Makefile` validation or runnable targets when needed.
7. Check `AGENTS.md` and `standards/` if the change affects repo-wide conventions.

8. When the root `cento` built-ins change, update `data/cento-cli.json` and the related CLI docs surfaces.
