# Optimizing AI: Cheap Validator Tiers

Tag: `optimizing-ai`

Direction: use tools created by AI to reduce AI waste, improve agent throughput, and make the next generation of tools cheaper to operate.

## Thesis

Most validator work should not spend scarce Spark/Codex budget. If builders emit structured evidence, validation can become a small decision problem:

1. Check deterministic facts.
2. Ask a cheap model only after deterministic validation has proven useful and there are real ambiguous packets.
3. Escalate to Codex manually when the validator must reason across code, diagnose failures, or produce a fix.

## Validator Routing

```text
builder output
  -> validation packet
  -> deterministic gate
  -> optional cheap model judge later
  -> manual Codex follow-up only for complex or failed cases
```

Use this default ladder:

- Tier 0 -> no model: command exit codes, file existence, JSON schema, API smoke checks, screenshot dimensions, log pass/fail markers.
- Tier 1 -> deferred cheap model: read a compact validation packet and return `approve`, `needs_fix`, or `blocked`.
- Tier 2 -> manual Codex follow-up: inspect code, debug ambiguous failures, write repairs, or validate high-risk architectural changes.

## Required Validation Packet

Every builder or deterministic validator should produce a small packet before review:

```json
{
  "schema": "cento.validation-packet.v1",
  "task": "#123",
  "claim": "Review page shows structured summary above logs.",
  "risk": "low",
  "checks": [
    {
      "name": "syntax",
      "status": "passed",
      "evidence": "node --check templates/agent-work-app/app.js"
    },
    {
      "name": "api",
      "status": "passed",
      "evidence": "GET /api/review/123 includes review_summary"
    },
    {
      "name": "screenshot",
      "status": "passed",
      "evidence": "workspace/runs/agent-work/123/screenshots/review.png"
    }
  ],
  "decision_requested": "approve"
}
```

## Cheap Judge Prompt

The Tier 1 model should receive only the packet, not the repo:

```text
You are a strict Cento validation judge.
Return only JSON with:
  decision: approve | needs_fix | blocked
  reason: one short sentence
  missing_evidence: string[]

Rules:
- Approve only if all required checks passed and evidence paths are present.
- Use needs_fix if implementation evidence exists but a check failed.
- Use blocked if external access, credentials, devices, or human decisions are required.
- Do not infer from missing data.
```

Expected output:

```json
{
  "decision": "approve",
  "reason": "All required checks passed and screenshot evidence is present.",
  "missing_evidence": []
}
```

## One-Hour Implementation Policy

- Default simple validators to Tier 0.
- Do not introduce Tier 1 model judging until deterministic validation has real usage data.
- Reserve Codex for implementing the validator and explicit human-requested follow-up, not automatic escalation.
- Track estimated AI cost per issue, even when the value is zero.
- Prefer a plain JSON or Markdown run summary over new dashboard UI in the first hour.

## Implemented Slice

- `cento validator-tier0 stories`
- `cento validator-tier0 run MANIFEST`
- `cento validator-tier0 e2e`

See `docs/validator-tier0.md` for stories, commands, and outputs.
