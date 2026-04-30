# Claude Coordination Review

Claude was reachable on the Linux node through `~/.npm-global/bin/claude` after adding that directory to `PATH`.

Read-only recommendation summary:

1. Add capped auto-dispatch to the coordinator so queued work can flow to workers with hard gates and an audit file.
2. Add a `--runtime codex|claude-code` option to the coordinator so reasoning-heavy read-only coordination can use Claude Code when desired.
3. Teach the coordinator prompt to recommend `agent-work handoff --dispatch-validator` so validating work does not wait for manual validator dispatch.

Implemented now:

- A safer first coordination primitive: `agent-work dispatch-pool`.
- It plans cheap Spark/Codex dispatches by default.
- It requires `--execute` before any agents are launched.
- It skips non-dispatchable nodes and non-Agent Task issues by default.

Deferred:

- Fully autonomous coordinator dispatch should build on `dispatch-pool --execute` after operator review.
- Claude coordinator runtime should be added where `scripts/agent_coordinator.py` lands cleanly; the Linux node currently has that file as uncommitted work.
