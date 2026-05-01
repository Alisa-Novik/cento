# Validator Tier 0

`cento validator-tier0` is the one-hour E2E implementation of the cheap validator direction. It creates validation packets, runs deterministic checks, and emits mandatory timing and AI budget stats.

## Commands

```bash
cento validator-tier0 stories
cento validator-tier0 run workspace/runs/validator-tier0/e2e/sample-pass.json
cento validator-tier0 e2e
```

## Stories

### AI-VAL-001: Create Minimal Validation Packet Format

A low-risk task has task, claim, risk, checks, requested decision, timestamp, and source manifest.

### AI-VAL-002: Evaluate Deterministic Tier 0 Checks

`file_exists`, `command`, and `json_field` checks return `passed`, `failed`, `missing`, or `blocked`.

### AI-VAL-003: Emit Mandatory Timing And AI Budget Stats

Each run records `total_duration_ms`, per-check `duration_ms`, `ai_calls_used`, and `estimated_ai_cost`.

### AI-VAL-004: Prove E2E With Pass And Fail Examples

One passing sample approves and one failing sample returns a non-approve decision with reason.

## Outputs

The tool writes generated run evidence under `workspace/runs/validator-tier0/`, which is intentionally ignored by git:

- `validation-packet.json`
- `validation-result.json`
- `validation-summary.md`
- `stats.json`
- `e2e-summary.json`
- `e2e-summary.md`

## Budget

Tier 0 runtime AI budget is always zero. The first implementation deliberately defers model judging, auto-escalation, and dashboard UI.
