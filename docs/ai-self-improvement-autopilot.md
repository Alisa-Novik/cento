# AI Self-Improvement Autopilot

`cento parallel-delivery self-improve e2e` is the guarded end-to-end autopilot path for turning the latest self-improvement planning request into Patch Swarm candidates, Factory validation evidence, one bounded Safe Integrator apply, and an auto-merge dry-run receipt.

It never pushes and never directly mutates `main`.

## Command

```bash
cento parallel-delivery self-improve e2e \
  --candidate-target 30 \
  --max-parallel-agents 3 \
  --budget-cap-usd 1 \
  --max-budget-usd 1 \
  --apply \
  --validate-each \
  --auto-merge-gate \
  --json
```

Use `--fixture-only` for a no-API sandbox:

```bash
cento parallel-delivery self-improve e2e \
  --fixture-only \
  --candidate-target 10 \
  --max-parallel-agents 2 \
  --apply \
  --validate-each \
  --auto-merge-gate \
  --json
```

## Safety Model

The e2e seeds from `workspace/runs/ai-self-improvement-nightly/latest/next_cycle_request.json`. If that file is absent, non-fixture mode runs the existing four-pass `self-improve run` planning loop first. Fixture mode uses the deterministic seed fallback and skips planning dispatch.

Patch Swarm candidates are retargeted to a run-scoped sandbox so fixture apply evidence does not depend on dirty or untracked operator files. When `--apply` is set, Factory applies at most `--limit` selected candidate, default `1`, in the Safe Integrator worktree.

`--auto-merge-gate` runs:

```bash
cento factory merge FACTORY_RUN --auto-merge-main --dry-run --json
```

The e2e does not pass `--push`. A blocked dry-run receipt caused by dirty main or wrong branch is valid environment evidence, not a merge attempt.

## Spend Caps

Default non-fixture mode includes one metered `api-openai` sandbox candidate through the `api-patch-proposal` profile in `.cento/api_workers.yaml`.

The API sandbox blocks before dispatch when:

- `OPENAI_API_KEY` is missing,
- estimated spend exceeds `--budget-cap-usd`,
- `--budget-cap-usd` exceeds `--max-budget-usd`,
- the hard cap exceeds the rollout ceiling.

Patch Swarm writes `usage_guard.json`, `provider_usage.jsonl`, and `candidate_spend_ledger.jsonl`. The e2e also writes `spend_summary.json`.

## Artifacts

Each run writes under:

```text
workspace/runs/ai-self-improvement-e2e/<run-id>/
workspace/runs/ai-self-improvement-e2e/latest/
```

Stable artifacts:

- `e2e_manifest.json`
- `self_improve_source.json`
- `patch_swarm_result.json`
- `factory_promotion.json`
- `safe_integrator_apply.json`
- `auto_merge_gate.json`
- `spend_summary.json`
- `validation_summary.json`
- `handoff.md`

The Patch Swarm and Factory run directories are linked from the e2e manifest.

## Statuses

`ready_for_apply` means selected candidates were promoted to Factory, `validate-fanout` passed, and no apply was requested.

`applied` means one Safe Integrator worktree apply succeeded and release candidate evidence was written.

`auto_merge_blocked_by_environment` means Safe Integrator evidence passed, then the auto-merge dry-run blocked on environment gates such as dirty main or not being on `main`. No merge or push happened.

`blocked` means a required source, budget, Patch Swarm, Factory, apply, or validation gate failed before a non-destructive success state.
