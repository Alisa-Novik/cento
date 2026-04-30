# CLAUDE

Project guidance for Claude Code in `cento`:

- Prefer the repo-local `cento` MCP server for Cento board, story, cluster, and bridge operations.
- Read `skills/claude-code/cento-mcp.md` before operating agent-work or cluster state.
- Use shell commands for implementation, tests, git, and file inspection.
- Keep `.env.mcp` machine-local and never copy secrets between nodes.
- Record durable evidence under `workspace/runs/agent-work/<issue-id>/`.
- Do not mutate Redmine or story state through direct database writes when a Cento MCP or `cento agent-work` command exists.
