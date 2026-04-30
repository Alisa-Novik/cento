---
name: cento-mcp
description: Use when Codex needs to inspect or operate Cento agent-work, story manifests, cluster state, or cross-node coordination through the repo-local Cento MCP server.
---

# Cento MCP

Prefer the `cento` MCP server for board and cluster operations when it is available. Use shell commands for code edits, tests, git, and tasks that are not exposed by the MCP server.

## First Step

Call `cento_context` before cross-node assumptions. Use `remote=false` for fast local context and `remote=true` when Linux/macOS reachability matters.

## Board Workflow

Use these MCP tools instead of ad hoc shell commands:

- `cento_agent_work_list` to find queued, running, review, or blocked work.
- `cento_agent_work_show` to inspect scope and acceptance criteria.
- `cento_agent_work_claim` before making edits.
- `cento_agent_work_update` for status and coordination notes.
- `cento_agent_work_handoff` after builder work is ready.
- `cento_agent_work_validate_run` for validation evidence.

## Story Evidence

Use:

- `cento_story_manifest_validate`
- `cento_story_manifest_render_hub`

Keep story artifacts under `workspace/runs/agent-work/<issue-id>/`.

## Cluster State

Use:

- `cento_cluster_status`
- `cento_bridge_mesh_status`
- `cento_platforms`

Do not copy `.env.mcp` between machines. Each node owns its own machine-local MCP environment.

## Write Safety

Write tools are explicit. If `CENTO_MCP_READ_ONLY=1`, do not work around it with shell mutations unless the user directly asks you to make changes and the task requires it.
