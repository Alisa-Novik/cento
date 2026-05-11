# Factory 1,000 Patch Swarm Roadmap

Cento Factory is moving toward this target:

`1,000 parallel candidate patches -> manifest-driven integration -> mostly deterministic validation -> task done in seconds for $1-2 -> self-improve and repeat`.

The six-hour factory-scale final test is the controlled proof path. It schedules 30 ProReq-light executions, logs 300 ProReq-light command calls, and runs 10 Patch Swarm fixture e2e milestones that generate 1,000 candidate patch receipts. ProReq-light remains local and API-safe by default, Patch Swarm stays fixture/candidate-receipt first, and any real apply remains behind Factory/Safe Integrator worktrees.

## Milestones

### 1. Coordinator kernel, cron, append-only ledgers

- `exec-001` `coordinator-kernel`: define the factory-scale coordinator kernel and run contract.
- `exec-002` `cron-deadline-lock`: install deadline-aware cron with flock overlap prevention.
- `exec-003` `append-only-ledgers`: prove events, calls, metrics, and spend ledgers are append-only.

### 2. ProReq-light batch runner and isolated run roots

- `exec-004` `batch-runner`: select exactly one pending ProReq-light execution per tick.
- `exec-005` `isolated-run-roots`: keep each ProReq-light pipeline root away from the active Dev Pipeline Studio root.
- `exec-006` `call-ledger-contract`: record ten explicit ProReq-light command calls per execution.

### 3. Patch Swarm ingestion from ProReq-light outputs

- `exec-007` `proreq-output-ingestion`: normalize ProReq-light outputs into Patch Swarm milestone handoffs.
- `exec-008` `milestone-grouping`: bind every three ProReq-light executions to one Patch Swarm run.
- `exec-009` `candidate-receipt-linking`: link generated candidate receipts back to their ProReq-light inputs.

### 4. Provider adapters for Codex/Claude/API candidate receipts

- `exec-010` `codex-candidate-adapter`: shape Codex Exec patch proposals into `candidate_patch.v1` receipts.
- `exec-011` `claude-candidate-adapter`: shape Claude Code proposals into the same provider-neutral receipt.
- `exec-012` `api-candidate-adapter`: keep OpenAI API candidates behind explicit budget gates.

### 5. Deterministic validation fanout and failure taxonomy

- `exec-013` `validator-fanout`: run deterministic validation across candidate receipts.
- `exec-014` `failure-taxonomy`: classify schema, ownership, patch-shape, duplicate, and test failures.
- `exec-015` `quarantine-ledger`: append rejected candidates and reasons without mutating accepted evidence.

### 6. Manifest-driven Safe Integrator queue

- `exec-016` `integrator-queue`: queue selected winners for the Factory Safe Integrator.
- `exec-017` `worktree-apply-plan`: require apply through Factory/Safe Integrator worktrees only.
- `exec-018` `rollback-receipts`: attach rollback and validation receipts to every integration plan.

### 7. Cost/latency admission controller

- `exec-019` `cost-admission`: reject live provider fanout without explicit budget and hard cap.
- `exec-020` `latency-budget`: track seconds per candidate, selected patch, and validation tier.
- `exec-021` `duplicate-saturation`: stop candidate generation when duplicate clusters saturate.

### 8. Dev Pipeline / Factory operator observability

- `exec-022` `operator-status`: render log-derived status for the six-hour run.
- `exec-023` `factory-ui-state`: expose candidate counts, provider mix, and handoffs to Dev Pipeline state.
- `exec-024` `handoff-evidence`: keep operator handoff markdown current as a derived artifact.

### 9. Self-improvement task generator

- `exec-025` `improvement-miner`: mine failure taxonomy and metrics for self-improvement tasks.
- `exec-026` `task-generator`: draft bounded Agent Work follow-ups for repeated blockers.
- `exec-027` `promotion-gates`: promote only improvements with passing deterministic validation.

### 10. 1,000-patch Factory pilot and scale report

- `exec-028` `thousand-candidate-pilot`: complete ten fixture Patch Swarm runs for 1,000 candidates.
- `exec-029` `scale-report`: summarize cost, latency, validation, and integration readiness.
- `exec-030` `repeat-loop`: feed the next self-improvement loop from the scale report.

## Run Contract

Start a default six-hour run:

```bash
cento walk-autopilot factory-scale start --duration-hours 6 --proreq-executions 30 --min-proreq-calls 100 --patch-swarm --json
```

Cron uses the managed marker `# BEGIN CENTO FACTORY SCALE FINAL TEST`, runs every 12 minutes, uses `flock`, and checks the run deadline before each tick. Each tick selects one pending ProReq-light execution and appends ten command-call records:

- `intake`
- `context`
- `screenshot`
- `pro-request`
- `codex-plan`
- `backend-work`
- `integration-plan`
- `validation-plan`
- `deliver --no-full-check --json`
- `evidence`

Every third ProReq-light execution runs:

```bash
cento parallel-delivery patch-swarm e2e --candidate-target 100 --max-parallel-agents 5 --fixture --json
```

## Artifacts

Runs live under `workspace/runs/walk-autopilot/factory-scale-<timestamp>/`:

- `roadmap.md`
- `config.json`
- `execution-manifest.json`
- `events.jsonl`
- `thoughts.jsonl`
- `proreq-light-calls.jsonl`
- `metrics.jsonl`
- `spend-ledger.jsonl`
- `handoff.md`
- `cron.md`
- `proreq-executions/exec-001..exec-030/`
- `patch-swarm/milestone-01..milestone-10/`

## Safety Boundaries

- Default ProReq-light execution logs explicit local command calls in isolated roots; `--execute-proreq` is required to run the ProReq-light commands.
- Live OpenAI API, image API, and OpenAI API patch workers are not enabled by this final test.
- Patch Swarm fixture e2e writes candidate receipts and Safe Integrator handoffs; it does not apply selected patches.
- Main-worktree mutation is allowed only through Factory/Safe Integrator worktrees after explicit validation gates.
