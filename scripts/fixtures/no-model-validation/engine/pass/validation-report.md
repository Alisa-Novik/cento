# No-Model Validation Report

- Status: **PASS**
- Summary: All deterministic manifest checks passed.
- Story: `scripts/fixtures/no-model-validation/engine/pass/story.json`
- Validation: `scripts/fixtures/no-model-validation/engine/pass/validation.json`
- Report JSON: `scripts/fixtures/no-model-validation/engine/pass/validation-report.json`
- Evidence paths: `5`

## Allowed Commands

- `./commands/pass.sh`

## Checks

| Check | Type | Status | Reason | Evidence |
| --- | --- | --- | --- | --- |
| story.schema_version | field | PASS | present | `scripts/fixtures/no-model-validation/engine/pass/story.json` |
| story.issue.id | field | PASS | present | `scripts/fixtures/no-model-validation/engine/pass/story.json` |
| story.issue.title | field | PASS | present | `scripts/fixtures/no-model-validation/engine/pass/story.json` |
| story.issue.package | field | PASS | present | `scripts/fixtures/no-model-validation/engine/pass/story.json` |
| story.lane.owner | field | PASS | present | `scripts/fixtures/no-model-validation/engine/pass/story.json` |
| story.lane.role | field | PASS | present | `scripts/fixtures/no-model-validation/engine/pass/story.json` |
| story.lane.node | field | PASS | present | `scripts/fixtures/no-model-validation/engine/pass/story.json` |
| story.lane.role | field | PASS | role is valid | `scripts/fixtures/no-model-validation/engine/pass/story.json` |
| story.paths.run_dir | field | PASS | run_dir exists | `scripts/fixtures/no-model-validation/engine/pass` |
| story.scope.acceptance | field | PASS | acceptance list is present | `scripts/fixtures/no-model-validation/engine/pass/story.json` |
| story.validation.no_model_eligible | field | PASS | explicitly eligible | `scripts/fixtures/no-model-validation/engine/pass/story.json` |
| story.validation.mode | field | PASS | present | `scripts/fixtures/no-model-validation/engine/pass/story.json` |
| story.validation.commands | field | PASS | command list present | `scripts/fixtures/no-model-validation/engine/pass/story.json` |
| story.expected_outputs | field | PASS | present | `scripts/fixtures/no-model-validation/engine/pass/story.json` |
| Fixture API | api_spec | PASS | API endpoint spec is explicit | `scripts/fixtures/no-model-validation/engine/pass/story.json` |
| story.expected_outputs[0] | artifact | PASS | expected output exists | `scripts/fixtures/no-model-validation/engine/pass/evidence/generated-by-command.txt` |
| story.expected_outputs[1] | artifact | PASS | expected output exists | `scripts/fixtures/no-model-validation/engine/pass/screenshots/summary.png` |
| Generate pass evidence | command | PASS | command succeeded | `` |
| Generated evidence exists | file | PASS | file exists | `scripts/fixtures/no-model-validation/engine/pass/evidence/generated-by-command.txt` |
| Fixture API method | json_field | PASS | JSON field is present | `scripts/fixtures/no-model-validation/engine/pass/story.json` |
| Story file URL is reachable | url | PASS | file URL exists | `scripts/fixtures/no-model-validation/engine/pass/story.json` |
| Screenshot evidence exists | screenshot | PASS | screenshot evidence exists | `scripts/fixtures/no-model-validation/engine/pass/screenshots/summary.png` |

## Missing Items

- None.

## Failed Commands

- None.

## Evidence Paths

- `scripts/fixtures/no-model-validation/engine/pass/evidence/generated-by-command.txt`
- `scripts/fixtures/no-model-validation/engine/pass/screenshots/summary.png`
- `scripts/fixtures/no-model-validation/engine/pass/story.json`
- `scripts/fixtures/no-model-validation/engine/pass/validation-report.md`
- `scripts/fixtures/no-model-validation/engine/pass/validation-report.json`

## Escalation Reasons

- None.
