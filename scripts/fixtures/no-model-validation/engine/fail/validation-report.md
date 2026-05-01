# No-Model Validation Report

- Status: **FAIL**
- Summary: 3 deterministic check(s) failed or required evidence was missing.
- Story: `scripts/fixtures/no-model-validation/engine/fail/story.json`
- Validation: `scripts/fixtures/no-model-validation/engine/fail/validation.json`
- Report JSON: `scripts/fixtures/no-model-validation/engine/fail/validation-report.json`
- Evidence paths: `4`

## Allowed Commands

- `./commands/fail.sh`

## Checks

| Check | Type | Status | Reason | Evidence |
| --- | --- | --- | --- | --- |
| story.schema_version | field | PASS | present | `scripts/fixtures/no-model-validation/engine/fail/story.json` |
| story.issue.id | field | PASS | present | `scripts/fixtures/no-model-validation/engine/fail/story.json` |
| story.issue.title | field | PASS | present | `scripts/fixtures/no-model-validation/engine/fail/story.json` |
| story.issue.package | field | PASS | present | `scripts/fixtures/no-model-validation/engine/fail/story.json` |
| story.lane.owner | field | PASS | present | `scripts/fixtures/no-model-validation/engine/fail/story.json` |
| story.lane.role | field | PASS | present | `scripts/fixtures/no-model-validation/engine/fail/story.json` |
| story.lane.node | field | PASS | present | `scripts/fixtures/no-model-validation/engine/fail/story.json` |
| story.lane.role | field | PASS | role is valid | `scripts/fixtures/no-model-validation/engine/fail/story.json` |
| story.paths.run_dir | field | PASS | run_dir exists | `scripts/fixtures/no-model-validation/engine/fail` |
| story.scope.acceptance | field | PASS | acceptance list is present | `scripts/fixtures/no-model-validation/engine/fail/story.json` |
| story.validation.no_model_eligible | field | PASS | explicitly eligible | `scripts/fixtures/no-model-validation/engine/fail/story.json` |
| story.validation.mode | field | PASS | present | `scripts/fixtures/no-model-validation/engine/fail/story.json` |
| story.validation.commands | field | PASS | command list present | `scripts/fixtures/no-model-validation/engine/fail/story.json` |
| story.expected_outputs | field | PASS | present | `scripts/fixtures/no-model-validation/engine/fail/story.json` |
| Fixture API | api_spec | PASS | API endpoint spec is explicit | `scripts/fixtures/no-model-validation/engine/fail/story.json` |
| story.expected_outputs[0] | artifact | PASS | expected output exists | `scripts/fixtures/no-model-validation/engine/fail/evidence/present.txt` |
| story.expected_outputs[1] | artifact | FAIL | required output is missing | `` |
| Failing command | command | FAIL | exit code 7, expected 0 | `` |
| Missing evidence | file | FAIL | file is missing | `` |
| Fixture API method | json_field | PASS | JSON field is present | `scripts/fixtures/no-model-validation/engine/fail/story.json` |

## Missing Items

- `scripts/fixtures/no-model-validation/engine/fail/evidence/missing-output.txt`
- `evidence/missing-output.txt`

## Failed Commands

- `./commands/fail.sh`

## Evidence Paths

- `scripts/fixtures/no-model-validation/engine/fail/evidence/present.txt`
- `scripts/fixtures/no-model-validation/engine/fail/story.json`
- `scripts/fixtures/no-model-validation/engine/fail/validation-report.md`
- `scripts/fixtures/no-model-validation/engine/fail/validation-report.json`

## Escalation Reasons

- None.
