# Validator Tier 0

`cento validator-tier0` is the one-hour E2E implementation of the cheap validator direction. It creates validation packets, runs deterministic checks, and emits mandatory timing and AI budget stats.

## Commands

```bash
cento validator-tier0 stories
cento validator-tier0 run workspace/runs/validator-tier0/e2e/sample-pass.json
cento validator-tier0 e2e
cento story-manifest draft --title "Fix dashboard" --package app --expected-output workspace/runs/agent-work/drafts/fix-dashboard/evidence.md
cento validation-manifest draft workspace/runs/agent-work/no-model-validation-e2e/story.json --output workspace/runs/agent-work/no-model-validation-e2e/validation.json
cento agent-work preflight workspace/runs/agent-work/no-model-validation-e2e/story.json --validation-manifest workspace/runs/agent-work/no-model-validation-e2e/validation.json
```

## Stories

### AI-VAL-001: Create Minimal Validation Packet Format

A low-risk task has task, claim, risk, checks, requested decision, timestamp, and source manifest.

### AI-VAL-002: Evaluate Deterministic Tier 0 Checks

`file_exists`, `command`, `json_field`, `contains_text`, `http_status`, and `image_nonblank` checks return `passed`, `failed`, `missing`, or `blocked`.

### AI-VAL-003: Emit Mandatory Timing And AI Budget Stats

Each run records `total_duration_ms`, per-check `duration_ms`, `ai_calls_used`, and `estimated_ai_cost`.

### AI-VAL-004: Prove E2E With Pass And Fail Examples

One passing sample approves and one failing sample returns a non-approve decision with reason.

### AI-VAL-005: Generate Draft Manifests Conservatively

Feature interpretation may generate draft Tier 0 manifests, but only for confidently inferred deterministic checks. Ambiguous or subjective acceptance criteria must become `manual_review` items.

Acceptance:

- User does not manually write routine manifest checks.
- Generated checks are limited to explicit artifacts and commands.
- The generator marks anything uncertain as `manual_review`.
- No generated manifest claims full validation coverage when manual review remains.

### AI-VAL-006: Gate Dispatch With Preflight

`agent-work preflight` checks `story.json` and `validation.json` before dispatch. It blocks when the validation draft is missing, expected outputs lack owners, automation coverage is below 95%, or any `manual_review` item is not explicitly `accepted`, `covered`, or `waived`.

## Generated Manifest Path

The no-model path is:

```text
feature interpretation
  -> story-manifest draft
  -> validation-manifest draft
  -> agent-work preflight
  -> validator-tier0 run
```

The generator only creates deterministic checks from explicit artifacts:

- `expected_outputs` become `file_exists`.
- `validation.commands` become `command`.
- `validation.required_text` becomes `contains_text`.
- `validation.json_fields` becomes `json_field`.
- `validation.urls` becomes `http_status`.
- `screenshots` become `file_exists` plus `image_nonblank`.

## Outputs

The tool writes generated run evidence under `workspace/runs/validator-tier0/`, which is intentionally ignored by git:

- `validation-packet.json`
- `validation-result.json`
- `validation-summary.md`
- `stats.json`
- `e2e-summary.json`
- `e2e-summary.md`

The generated-manifest E2E writes:

- `workspace/runs/agent-work/no-model-validation-e2e/story.json`
- `workspace/runs/agent-work/no-model-validation-e2e/validation.json`
- `workspace/runs/agent-work/no-model-validation-e2e/preflight.json`
- `workspace/runs/agent-work/no-model-validation-e2e/tier0/validation-result.json`
- `workspace/runs/agent-work/no-model-validation-e2e/e2e-summary.json`

## Budget

Tier 0 runtime AI budget is always zero. The current generated-manifest E2E completed with 100% automation coverage, 9 deterministic checks, 0 manual-review items, 0 AI calls, and 0 estimated AI cost.
