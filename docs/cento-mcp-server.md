# Cento MCP Server

`scripts/cento_mcp_server.py` is a local stdio MCP server for agent operations in this repo. It gives MCP clients a structured Cento surface so agents do not have to invent shell commands for normal board, story, and cluster work.

## Setup

```bash
cd /path/to/cento
cp .env.mcp.example .env.mcp
cento mcp doctor
python3 scripts/cento_mcp_server.py --list-tools
```

Point your MCP-capable client at the repo-root `.mcp.json`. The server name is `cento`.

Useful environment values:

```bash
CENTO_ROOT=/path/to/cento
CENTO_MCP_READ_ONLY=0
CENTO_MCP_TIMEOUT=30
```

Set `CENTO_MCP_READ_ONLY=1` when you want the agent to inspect state without changing Redmine, validation reports, or generated hubs.

## Tool Surface

Read tools:

- `cento_context`: gather local or local+remote Cento context.
- `cento_platforms`: inspect platform support from `data/tools.json`.
- `cento_cluster_status`: inspect cluster status.
- `cento_bridge_mesh_status`: inspect secure bridge mesh status.
- `cento_agent_work_list`: list agent-work issues.
- `cento_agent_work_show`: inspect one issue.
- `cento_story_manifest_validate`: validate a story manifest.

Explicit write tools:

- `cento_agent_work_create`: create an agent-work issue.
- `cento_agent_work_claim`: claim an issue.
- `cento_agent_work_update`: update status, ownership, and notes.
- `cento_agent_work_handoff`: write a builder handoff report.
- `cento_agent_work_validate_run`: run validation and record validator results.
- `cento_story_manifest_render_hub`: generate `deliverables.json` and `start-here.html` from `story.json`.

The server does not expose arbitrary shell execution. It wraps a small allowlisted Cento command surface and returns command results as JSON.

## Smoke Tests

List MCP tools:

```bash
python3 scripts/cento_mcp_server.py --list-tools
```

List board work:

```bash
python3 scripts/cento_mcp_server.py \
  --call-tool cento_agent_work_list \
  --arguments '{}'
```

Inspect one issue:

```bash
python3 scripts/cento_mcp_server.py \
  --call-tool cento_agent_work_show \
  --arguments '{"issue":60}'
```

Validate a story:

```bash
python3 scripts/cento_mcp_server.py \
  --call-tool cento_story_manifest_validate \
  --arguments '{"manifest":"workspace/runs/agent-work/60/story.json","check_links":true}'
```

## Agent Workflow

For normal agent work:

1. Use `cento_context` before making cross-node assumptions.
2. Use `cento_agent_work_list` and `cento_agent_work_show` to choose work.
3. Use `cento_agent_work_claim` before editing.
4. Produce `story.json`, `validation.json`, and evidence under `workspace/runs/agent-work/<issue-id>/`.
5. Use `cento_story_manifest_validate` and `cento_story_manifest_render_hub`.
6. Use `cento_agent_work_handoff` and `cento_agent_work_validate_run`.
7. Close with `cento_agent_work_update` only after validation passes.

Shell remains appropriate for coding, tests, git, and file edits. MCP should be preferred for board and cluster state because it returns structured results and keeps the command surface stable.

## Guardrails

- `.env.mcp` remains machine-local and must not be copied between nodes.
- Tool paths that accept files are constrained to the Cento repo root.
- Write tools are explicit and can be disabled with `CENTO_MCP_READ_ONLY=1`.
- The server returns `ok`, `exit_code`, `command`, `stdout`, and `stderr` for wrapped commands.
- The Linux and macOS nodes should each run their own local server from their own checkout.
