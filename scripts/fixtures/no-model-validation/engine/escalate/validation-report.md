# No-Model Validation Report

- Status: **ESCALATE**
- Summary: 1 escalation reason(s) require human or coordinated follow-up.
- Story: `scripts/fixtures/no-model-validation/engine/escalate/story.json`
- Validation: `scripts/fixtures/no-model-validation/engine/escalate/validation.json`
- Report JSON: `scripts/fixtures/no-model-validation/engine/escalate/validation-report.json`
- Evidence paths: `4`

## Allowed Commands

- `./commands/other.sh`

## Checks

| Check | Type | Status | Reason | Evidence |
| --- | --- | --- | --- | --- |
| story.schema_version | field | PASS | present | `scripts/fixtures/no-model-validation/engine/escalate/story.json` |
| story.issue.id | field | PASS | present | `scripts/fixtures/no-model-validation/engine/escalate/story.json` |
| story.issue.title | field | PASS | present | `scripts/fixtures/no-model-validation/engine/escalate/story.json` |
| story.issue.package | field | PASS | present | `scripts/fixtures/no-model-validation/engine/escalate/story.json` |
| story.lane.owner | field | PASS | present | `scripts/fixtures/no-model-validation/engine/escalate/story.json` |
| story.lane.role | field | PASS | present | `scripts/fixtures/no-model-validation/engine/escalate/story.json` |
| story.lane.node | field | PASS | present | `scripts/fixtures/no-model-validation/engine/escalate/story.json` |
| story.lane.role | field | PASS | role is valid | `scripts/fixtures/no-model-validation/engine/escalate/story.json` |
| story.paths.run_dir | field | PASS | run_dir exists | `scripts/fixtures/no-model-validation/engine/escalate` |
| story.scope.acceptance | field | PASS | acceptance list is present | `scripts/fixtures/no-model-validation/engine/escalate/story.json` |
| story.validation.no_model_eligible | field | PASS | explicitly eligible | `scripts/fixtures/no-model-validation/engine/escalate/story.json` |
| story.validation.mode | field | PASS | present | `scripts/fixtures/no-model-validation/engine/escalate/story.json` |
| story.validation.commands | field | PASS | command list present | `scripts/fixtures/no-model-validation/engine/escalate/story.json` |
| story.expected_outputs | field | PASS | present | `scripts/fixtures/no-model-validation/engine/escalate/story.json` |
| Fixture API | api_spec | PASS | API endpoint spec is explicit | `scripts/fixtures/no-model-validation/engine/escalate/story.json` |
| story.expected_outputs[0] | artifact | PASS | expected output exists | `scripts/fixtures/no-model-validation/engine/escalate/evidence/ready.txt` |
| Disallowed command | command | ESCALATE | command is not allowlisted | `` |
| Ready evidence | file | PASS | file exists | `scripts/fixtures/no-model-validation/engine/escalate/evidence/ready.txt` |
| Fixture API method | json_field | PASS | JSON field is present | `scripts/fixtures/no-model-validation/engine/escalate/story.json` |

## Missing Items

- None.

## Failed Commands

- None.

## Evidence Paths

- `scripts/fixtures/no-model-validation/engine/escalate/evidence/ready.txt`
- `scripts/fixtures/no-model-validation/engine/escalate/story.json`
- `scripts/fixtures/no-model-validation/engine/escalate/validation-report.md`
- `scripts/fixtures/no-model-validation/engine/escalate/validation-report.json`

## Escalation Reasons

- `command is not in the allowed command list: ./commands/escalate.sh`
