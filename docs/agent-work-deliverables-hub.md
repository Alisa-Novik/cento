# Agent Work Deliverables Hub

Every agent-work package that produces user-facing deliverables should include a stable navigation hub. The hub prevents review from depending on chat history.

## Required Files

- `deliverables.json`: source manifest for links, story status, commands, screenshots, and review checklist.
- `start-here.html`: generated manager-facing hub.
- `validation.md`: evidence log with commands, results, and screenshot paths.
- `validation-report.md` / `validation-report.json`: canonical validation result pair when the story or validation manifest exposes a report.
- `screenshots/`: visual evidence referenced by the hub.
- `story.json`: shared contract for stable discovery of deliverables and expected outputs (stored in the same run directory).

## Standard Artifact Names

- `expected_outputs[]`: durable files the reviewer should open. Report-like outputs stay listed here so they appear in the hub's `Use First` section.
- `validation.report`: optional story or validation-manifest field that names the validation result report. Use a string path or an object with `path`, `json`, `result`, `label`, and `description`.
- `validation_results[]`: generated hub cards with `title`, `href`, `description`, `code`, and optional `badge`. The hub renders these as validation result links with status pills.
- `validation-report.md`: canonical human-readable validation report link.
- `validation-report.json`: machine-readable companion next to the markdown report.
- `reporting-evidence.md`: story-owned no-model evidence report for this package. If the story also exposes it through `validation.report`, the hub gives it a badge in `Validation Results`.

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
- If a no-model or validator report exists, surface it in `validation_results[]` so the hub can badge the report itself instead of burying it in the generic evidence list.

## Review Gate

A story is not ready for Validator pass unless the hub points to:

- app or primary deliverable link
- install or usage docs when relevant
- validation log
- validation result report link and badge when a report exists
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
