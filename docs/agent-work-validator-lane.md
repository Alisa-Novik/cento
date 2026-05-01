# Agent Work Validator Lane

Cento agent work uses separate Builder and Validator lanes.

## Builder Contract

Builder agents own implementation. They do not move issues to Review.

Builder ready command:

```bash
python3 scripts/agent_work.py handoff ISSUE_ID \
  --summary "Implemented..." \
  --changed-file PATH \
  --command "test command" \
  --evidence PATH
```

Builder output should include:

- changed files
- commands run
- expected behavior
- draft evidence paths
- known risks or limitations

## Deterministic-First Validation

Validation is no-model by default. The Validator lane proves work with durable evidence instead of asking a model to infer whether the issue is done.

The story manifest's `validation` block is the routing contract. It records `mode`, `risk`, `no_model_eligible`, `escalation_triggers`, and `commands`, which tells the validator whether it can stay local or must escalate to a model or human handoff.

Preferred evidence types are:

- command output from a narrow validation command
- file existence or file content checks
- URL or API smoke checks
- desktop or mobile screenshots
- generated validation reports and review summaries

If a story cannot be decided from deterministic evidence, the validator should fail or block with the missing evidence named explicitly. Subjective judgment belongs in the story manifest as a manual-review requirement or in a separate human/device handoff, not inside an unannounced model judge.

Rollout commands:

```bash
cento agent-work validate-run ISSUE_ID \
  --manifest workspace/runs/agent-work/ISSUE_ID/validation.json \
  --story-manifest workspace/runs/agent-work/ISSUE_ID/story.json

cento agent-work validate ISSUE_ID \
  --result pass \
  --evidence workspace/runs/agent-work/ISSUE_ID/validation-report.md \
  --note "..."
```

`validate-run` remains the executable check path. `validate` records the board state after the evidence has passed.

## Validator Contract

Validator agents own review evidence. They should not implement product code unless a validation harness fix is explicitly required.

Validator pass command:

```bash
python3 scripts/agent_work.py validate-run ISSUE_ID --manifest workspace/runs/agent-work/ISSUE_ID/validation.json
python3 scripts/agent_work.py validate-run ISSUE_ID --manifest workspace/runs/agent-work/ISSUE_ID/validation.json --story-manifest workspace/runs/agent-work/ISSUE_ID/story.json
```

Validator fail command:

```bash
python3 scripts/agent_work.py validate ISSUE_ID --result fail --evidence PATH --note "Failed because..."
```

Validator review notes use a stable four-section format to keep manager routing deterministic:

- `Delivered`
- `Validation`
- `Evidence`
- `Residual risk`

Example:

```text
h3. Validator PASS

*Delivered*
* Core docs and hub generated.

*Validation*
* Tests, docs checks, and screenshot capture completed.

*Evidence*
* Validation evidence:
*  - @workspace/runs/agent-work/28/validation-report.md@
* Screenshot evidence:
*  - @workspace/runs/agent-work/28/screenshots/start-here-desktop.png@

*Residual risk*
* None.
```

Strict review-gate command:

```bash
python3 scripts/agent_work.py validate ISSUE_ID \
  --story-manifest workspace/runs/agent-work/ISSUE_ID/story.json \
  --result pass \
  --note "...review note body..."
```

The gate enforces `story.json` review requirements after check execution:

- required evidence existence (local paths or `@...@` note references)
- required review sections
- required residual risk non-empty when configured
- required syntax/API/screenshot/visual evidence categories when configured

Missing required evidence returns an actionable failure, e.g.

```text
Review note is missing section: Residual risk
Required evidence path is missing: workspace/runs/agent-work/57/screenshot-missing.png
Syntax/test evidence is required: no passing syntax/test check result found.
Visual inspection evidence is required: note does not include visual inspection notes and no visual evidence artifact exists.
```

Validator checks should include, when relevant:

- syntax, tests, or API smoke checks
- generated hub/link validation
- browser or device screenshots
- visual inspection notes
- replacement evidence completeness

## Review Gate

`Review` is validator-gated. Builders use `Validating`; validators use `validate --result pass`.

For deterministic reviewer notes, gate-compatible notes should include:

- `Delivered`
- `Validation`
- `Evidence`
- `Residual risk`

This keeps implementation and evidence independent enough to scale across Codex, Codex Spark, Claude, or future cloud workers.

## validation.json

Each story can provide a manifest for repeatable validation:

```json
{
  "run_dir": "workspace/runs/agent-work/28",
  "requires": {
    "builder_report": "workspace/runs/agent-work/28/builder-report.md",
    "ui_screenshots": true,
    "validator_agents": ["alice-validator"]
  },
  "checks": [
    {
      "name": "Python syntax",
      "type": "command",
      "command": "python3 -m py_compile scripts/agent_work.py"
    },
    {
      "name": "Docs exist",
      "type": "file",
      "path": "docs/agent-work-validator-lane.md",
      "non_empty": true
    },
    {
      "name": "Hub mobile screenshot",
      "type": "screenshot",
      "url": "file:///{root}/workspace/runs/agent-work/18/start-here.html",
      "output": "workspace/runs/agent-work/28/screenshots/mobile-start-here.png",
      "viewport": "390,844"
    }
  ]
}
```

Supported check types today: `command`, `file`, `url`, and `screenshot`.

Set `CENTO_VALIDATOR_AGENTS=alice-validator,ci-validator` to restrict direct Validator passes. A manifest can also restrict validators with `requires.validator_agents`.

## review-summary.json

Validators also write `workspace/runs/agent-work/ISSUE_ID/review-summary.json`. The Review board renders this first so humans see the result, checks, evidence count, and next action before any raw logs.

```json
{
  "schema": "cento.review-summary.v1",
  "issue": {"id": 123, "subject": "Example task"},
  "result": "pass",
  "result_after_gate": "pass",
  "summary": "Validation passed: 4/4 checks passed.",
  "checks": [
    {"name": "Python syntax", "status": "passed", "detail": "exit 0", "type": "command"}
  ],
  "evidence": [
    {"type": "report", "path": "workspace/runs/agent-work/123/validation-report.md"}
  ],
  "recommended_action": "Approve",
  "review_gate_failures": [],
  "agent": "alice-validator",
  "node": "linux",
  "updated_at": "2026-04-30T00:00:00+00:00"
}
```

`validate-run` generates this artifact automatically. Direct `validate` also generates it, using the supplied note and evidence paths.

Story capture workflow for screenshot evidence:

```json
{
  "run_dir": "workspace/runs/agent-work/59",
  "requires": {
    "validator_agents": ["alice-validator"]
  },
  "checks": [
    {
      "name": "story screenshot metadata",
      "type": "file",
      "path": "workspace/runs/agent-work/59/screenshot-evidence.json",
      "non_empty": true
    }
  ]
}
```

For repeatable evidence, run `cento story-screenshot-runner <story.json>` from the Builder before validator handoff, then include both `screenshot-evidence.json` and `screenshot-index.md` in the required evidence list.

## Issue #57 Example (Pass/Fail)

These issue-local artifacts demonstrate gate pass/fail behavior:

```bash
python3 scripts/agent_work.py validate-run 57 \
  --manifest workspace/runs/agent-work/57/validation.json \
  --story-manifest workspace/runs/agent-work/57/story-pass.json \
  --note "$(cat workspace/runs/agent-work/57/review-note-pass.md)"

python3 scripts/agent_work.py validate-run 57 \
  --manifest workspace/runs/agent-work/57/validation.json \
  --story-manifest workspace/runs/agent-work/57/story-fail.json \
  --note "$(cat workspace/runs/agent-work/57/review-note-fail.md)"
```
