# AI Self-Improvement Nightly

`cento parallel-delivery self-improve` runs the gated nightly Cento self-improvement loop.

The loop performs four ordered Hard ProReq planning passes:

1. Scope and guardrails.
2. Architecture.
3. Integration and workset strategy.
4. Validation, promotion recommendation, and next-cycle request.

Each pass consumes the prior pass results, failures, guidance, and next-step request. A degraded pass may feed the next pass only as failure evidence.

## Commands

```bash
cento parallel-delivery self-improve run --json
cento parallel-delivery self-improve e2e --candidate-target 30 --max-parallel-agents 3 --budget-cap-usd 1 --max-budget-usd 1 --apply --validate-each --auto-merge-gate --json
cento parallel-delivery self-improve validate --json
cento parallel-delivery self-improve status --json
cento parallel-delivery self-improve install-cron --time 02:30
cento parallel-delivery self-improve uninstall-cron
```

## Artifacts

Nightly artifacts are written under:

```text
workspace/runs/ai-self-improvement-nightly/<timestamp>/
workspace/runs/ai-self-improvement-nightly/latest/
```

The stable artifact set is:

- `nightly_cycle_manifest.json`
- `pass_01_child_run_summary.json` through `pass_04_child_run_summary.json`
- `validation_gates.json`
- `loop_metrics.json`
- `promotion_recommendation.json`
- `evidence_handoff.json`
- `next_cycle_request.json`

If `latest/next_cycle_request.json` is missing, the seed comes from the newest previous continuous ProReq handoff under `workspace/runs/ai-cento-native-continuous-proreq/*/validation_handoff.json`.

## Gates

Blocking gates fail the cycle when Pro artifacts are missing or blank, a child pass is degraded, a workset does not pass its declared path policy, or `latest/` is stale.

Image generation is nonblocking. A `gpt-image-2` 403 is recorded as evidence and does not fail backend planning.

Generated new-file worksets require an explicit create-file policy:

```bash
cento workset check WORKSET --runtime api-openai
```

Plain `cento workset check WORKSET` remains strict and rejects missing write paths.

## Compute Routing

The nightly loop records the Cento compute policy in each manifest and next-cycle request.

When Codex/Claude weekly utilization is above 30% and capacity remains usable, follow-up work should prefer Codex/Claude agent lanes over metered OpenAI API for about 70-80% of eligible non-API-only cases. OpenAI API remains reserved for structured Responses API, image generation, ProReq planning, and other API-only behavior.

The loop never executes implementation worksets automatically. It plans, validates, summarizes, recommends promotion, writes the next request, and stops.

The separate e2e autopilot command consumes the latest `next_cycle_request.json` and continues through Patch Swarm, Factory `validate-fanout`, bounded Safe Integrator apply, and `factory merge --auto-merge-main --dry-run`. See `docs/ai-self-improvement-autopilot.md`.
