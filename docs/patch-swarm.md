# Patch Swarm

Patch Swarm is the Cento-native MVP for cost-effective, massively parallel AI development. It creates many cheap candidate patches, validates and ranks them deterministically, and allows only one serialized integration execution to hand winners to the Safe Integrator path.

The current implementation is fixture-first by default. Live `api-openai` execution is fail-closed behind explicit budget caps, `OPENAI_API_KEY`, and a bounded sandbox candidate limit. Applying selected winners is routed through Factory/Safe Integrator worktrees, not the main worktree.

## Command Surface

```bash
cento parallel-delivery patch-swarm plan --candidate-target 100 --max-parallel-agents 5 --json
cento parallel-delivery patch-swarm execute RUN_ID --fixture --json
cento parallel-delivery patch-swarm execute RUN_ID --live --budget-cap-usd 1 --max-budget-usd 1 --api-sandbox-candidates 1 --json
cento parallel-delivery patch-swarm integrate RUN_ID --dry-run --json
cento parallel-delivery patch-swarm integrate RUN_ID --apply --factory-run workspace/runs/factory/patch-swarm-RUN_ID --validate-each --json
cento parallel-delivery patch-swarm validate RUN_ID --json
cento parallel-delivery patch-swarm status RUN_ID --json
cento parallel-delivery patch-swarm e2e --candidate-target 30 --max-parallel-agents 3 --fixture --json
```

Walk Autopilot can also run or inspect the dry-run coordinator:

```bash
cento walk-autopilot patch-swarm run --candidate-target 100 --max-parallel-agents 5 --json
cento walk-autopilot patch-swarm status --json
```

The regular Walk Autopilot loop can include one Patch Swarm fixture e2e per loop with `--patch-swarm`.

## Architecture

Patch Swarm always uses ten ProReq execution lanes plus one dedicated integrator execution.

The ten lanes are:

- `request-decomposer`
- `codex-exec-adapter`
- `claude-code-adapter`
- `openai-patch-proposal-adapter`
- `candidate-normalizer`
- `dedupe-clustering`
- `deterministic-validator-fanout`
- `cost-latency-ledger`
- `dev-pipeline-studio-ui`
- `autopilot-coordinator-hooks`

Providers are normalized into `candidate_patch.v1` receipts:

- `codex-exec`: local command runtime using the existing `codex-fast` profile.
- `claude-code`: local command runtime using the new `claude-code-fast` profile.
- `api-openai`: structured API worker path using `patch_proposal.v1`.

The fixture e2e writes patch diff artifacts, validates them, clusters duplicates, ranks winners, selects one winner per ProReq lane, and writes `safe_integrator_handoff.json`. Candidate targets can be small for sandbox validation or larger for scale tests.

When `integrate --apply` or `--factory-run` is used, Patch Swarm converts selected `candidate_patch.v1` receipts into Factory patch bundles, writes a Factory apply plan, runs Factory `validate-fanout`, and only then attempts Safe Integrator worktree apply.

## UI Integration

Patch Swarm now has a standalone Cento Console module at:

- `/patch-swarm`
- `/patch-swarm/runs/:run_id`

The product UI is separate from Dev Pipeline Studio. It provides local Git repo discovery, a task composer, run history, candidate review, diff preview, winner approval, rejection notes, and a supervised apply button. Dev Pipeline Studio remains the advanced diagnostics/configuration view for the underlying pipeline template.

The local HTTP API is:

```text
GET  /api/patch-swarm/repos
GET  /api/patch-swarm/runs
POST /api/patch-swarm/runs
GET  /api/patch-swarm/runs/:run_id
POST /api/patch-swarm/runs/:run_id/approve
POST /api/patch-swarm/runs/:run_id/reject
POST /api/patch-swarm/runs/:run_id/apply
```

Product runs add thin metadata around the existing artifact contract:

- `product_metadata.json`
- `supervised_approval.json`
- `candidate_decisions.json`
- `product_safe_integrator_apply.json` for external-repo Safe Integrator worktree apply receipts

Patch Swarm is also still registered as a Dev Pipeline Studio template.

The run writes:

- `workspace/runs/parallel-delivery/patch-swarm/<run>/ui_state.json`
- `workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/patch-swarm/latest_ui_state.json`

The UI state includes candidate totals, provider counts, lane status, ranking, selected winners, validation, cost ledger, handoff links, product metadata, approval state, and candidate decisions.

## Cost And Safety

The default path is deterministic fixture execution. It does not call OpenAI, does not launch live Codex or Claude workers, and does not apply patches to the operator worktree.

Live execution should stay behind explicit budget gates. The architecture requires provider receipts and cost ledgers before integration. The integrator remains serialized, and Safe Integrator handoff is the boundary before any real apply path.

Live Patch Swarm execution requires:

- a live-enabled plan,
- `--budget-cap-usd` or `--budget-cap`,
- estimated provider spend below the cap,
- hard cap at or below the rollout ceiling,
- `OPENAI_API_KEY` when the `api-openai` sandbox limit is greater than zero.

Each execution writes `usage_guard.json`, `provider_usage.jsonl`, and `candidate_spend_ledger.jsonl`. If any gate fails, no provider command is launched and the run records a blocked receipt.

## Validation Evidence

The first MVP e2e run was:

```bash
cento parallel-delivery patch-swarm e2e --run-id patch-swarm-e2e-20260505 --candidate-target 100 --max-parallel-agents 5 --providers codex-exec,claude-code,api-openai --fixture --json
```

It produced:

- `workspace/runs/parallel-delivery/patch-swarm/patch-swarm-e2e-20260505/patch_swarm_manifest.json`
- `workspace/runs/parallel-delivery/patch-swarm/patch-swarm-e2e-20260505/candidate_index.json`
- `workspace/runs/parallel-delivery/patch-swarm/patch-swarm-e2e-20260505/integration_execution/integration_execution.json`
- `workspace/runs/parallel-delivery/patch-swarm/patch-swarm-e2e-20260505/safe_integrator_handoff.json`
- `workspace/runs/parallel-delivery/patch-swarm/patch-swarm-e2e-20260505/validation_summary.json`
- `workspace/runs/parallel-delivery/patch-swarm/patch-swarm-e2e-20260505/decision_report.md`

Result: 100 candidates, 10 ProReq executions, 10 selected winners, validation passed. Fixture runs record zero metered API spend.
