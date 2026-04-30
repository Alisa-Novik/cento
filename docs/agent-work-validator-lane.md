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

## Validator Contract

Validator agents own review evidence. They should not implement product code unless a validation harness fix is explicitly required.

Validator pass command:

```bash
python3 scripts/agent_work.py validate-run ISSUE_ID --manifest workspace/runs/agent-work/ISSUE_ID/validation.json
```

Validator fail command:

```bash
python3 scripts/agent_work.py validate ISSUE_ID --result fail --evidence PATH --note "Failed because..."
```

Validator checks should include, when relevant:

- syntax, tests, or API smoke checks
- generated hub/link validation
- browser or device screenshots
- visual inspection notes
- Redmine evidence completeness

## Review Gate

`Review` is validator-gated. Builders use `Validating`; validators use `validate --result pass`.

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
