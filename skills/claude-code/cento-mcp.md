# Claude Code: Cento MCP

Use the repo-local `cento` MCP server for Cento board, story, cluster, and bridge operations. Use shell commands for code edits, tests, git, and implementation work.

## Preferred MCP Tools

- `cento_context`: gather current local or cross-node context.
- `cento_agent_work_list`: list board work.
- `cento_agent_work_show`: inspect one issue.
- `cento_agent_work_claim`: claim work before editing.
- `cento_agent_work_update`: post status and coordination notes.
- `cento_agent_work_handoff`: produce builder handoff evidence.
- `cento_agent_work_validate_run`: run validation evidence.
- `cento_story_manifest_validate`: validate `story.json`.
- `cento_story_manifest_render_hub`: generate `deliverables.json` and `start-here.html`.
- `cento_cluster_status`: inspect cluster state.
- `cento_bridge_mesh_status`: inspect secure mesh state.

## Operating Rules

1. Start with `cento_context` when work spans machines.
2. Inspect the issue with `cento_agent_work_show` before changing files.
3. Claim the issue before implementation.
4. Keep durable evidence in `workspace/runs/agent-work/<issue-id>/`.
5. Validate with `validation.json` before moving work to Review or Done.
6. Use explicit write tools for Redmine and story state; do not invent direct database writes.
7. Keep `.env.mcp` machine-local.

If MCP is unavailable, fall back to the equivalent `cento agent-work ...` shell commands and mention that fallback in the final report.
