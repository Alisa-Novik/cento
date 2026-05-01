# Agent Work Deliverables Hub

Every agent-work package that produces user-facing deliverables should include a stable navigation hub. The hub prevents review from depending on chat history.

## Required Files

- `deliverables.json`: source manifest for links, story status, commands, screenshots, and review checklist.
- `start-here.html`: generated manager-facing hub.
- `validation.md`: evidence log with commands, results, and screenshot paths.
- `screenshots/`: visual evidence referenced by the hub.
- `story.json`: shared contract for stable discovery of deliverables and expected outputs (stored in the same run directory).

## Active Business Requests

- [Optimizing AI: Cheap Validator Tiers](file:///home/alice/projects/cento/workspace/runs/agent-work/18/start-here.html): `optimizing-ai` direction for using structured evidence, deterministic checks, and cheap model judges before spending Spark/Codex on validation.
- [Cento Agent Manager](cento-agent-manager.html): standard business request for a managed agent operations layer that scans stale, idle, stuck, errored, duplicate, and low-value agent activity and exposes a small hardcoded management toolkit.
- [Taskstream Retirement Roadmap](redmine-retirement-roadmap.md): prerequisite-to-task roadmap for discontinuing the migration-era board and making Cento Taskstream the only active system of record.

## Workflow

1. Add or update `workspace/runs/agent-work/<id>/deliverables.json`.
2. Generate the hub:

   ```bash
   python3 scripts/deliverables_hub.py workspace/runs/agent-work/<id>/deliverables.json --check-links
   ```

3. Capture desktop and mobile screenshots of `start-here.html`.
4. Move the issue to `Validating` when implementation is ready.
5. A separate Validator agent checks the hub, screenshots, and evidence, then moves the story to `Review` with `agent_work.py validate`.

## Navigation Rules for Review

- Keep generated artifacts under `workspace/runs/agent-work/<id>/` so manager-facing links stay stable.
- Use `start-here.html` as the primary navigation entry for an issue.
- Keep `deliverables.json` and `story.json` aligned so hub regeneration remains deterministic.

## Review Gate

A story is not ready for Validator pass unless the hub points to:

- app or primary deliverable link
- install or usage docs when relevant
- validation log
- screenshots or equivalent rendered evidence
- current issue status

## Recommended Note Shape

```text
h3. Ready for review

*Delivered*
* ...

*Validation*
* ...

*Evidence*
* @workspace/runs/agent-work/<id>/start-here.html@
* @workspace/runs/agent-work/<id>/validation.md@
```
