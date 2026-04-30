# Agent Work Deliverables Hub

Every agent-work package that produces user-facing deliverables should include a stable navigation hub. The hub prevents review from depending on chat history.

## Required Files

- `deliverables.json`: source manifest for links, story status, commands, screenshots, and review checklist.
- `start-here.html`: generated manager-facing hub.
- `validation.md`: evidence log with commands, results, and screenshot paths.
- `screenshots/`: visual evidence referenced by the hub.

## Workflow

1. Add or update `workspace/runs/agent-work/<id>/deliverables.json`.
2. Generate the hub:

   ```bash
   python3 scripts/deliverables_hub.py workspace/runs/agent-work/<id>/deliverables.json --check-links
   ```

3. Capture desktop and mobile screenshots of `start-here.html`.
4. Move the Redmine story to `Validating` when implementation is ready.
5. A separate Validator agent checks the hub, screenshots, and evidence, then moves the story to `Review` with `agent_work.py validate`.

## Review Gate

A story is not ready for Validator pass unless the hub points to:

- app or primary deliverable link
- install or usage docs when relevant
- validation log
- screenshots or equivalent rendered evidence
- current Redmine story status

## Recommended Redmine Note Shape

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
