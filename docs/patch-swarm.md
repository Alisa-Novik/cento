# Patch Swarm / Parallel Software Delivery Product Spec

Patch Swarm is the Cento-native MVP for cost-effective, massively parallel AI development. It creates many cheap candidate patches, validates and ranks them deterministically, and allows only one serialized integration execution to hand winners to the Safe Integrator path.

The current implementation is fixture-first by default. Live `api-openai` execution is fail-closed behind explicit budget caps, `OPENAI_API_KEY`, and a bounded sandbox candidate limit. Applying selected winners is routed through Factory/Safe Integrator worktrees, not the main worktree.

This is the canonical product architecture document for the Patch Swarm / Parallel Software Delivery system. Supporting lifecycle, implementation, and validation details live in:

- [Patch Swarm Lifecycle](./patch-swarm-lifecycle.md)
- [Patch Swarm Implementation Map](./patch-swarm-implementation-map.md)
- [Patch Swarm Validation Matrix](./patch-swarm-validation-matrix.md)
- [Patch Swarm Artifact Schema](./parallel-delivery/patch-swarm-artifacts.md)
- [Patch Swarm Request Splitter and 100-Task Planner](./parallel-delivery/patch-swarm-planner.md)
- [Patch Swarm ProReq and ChatGPT Pro Prompt Bundles](./parallel-delivery/patch-swarm-proreq-prompts.md)
- [Patch Swarm Path Leasing and Workset Compatibility](./parallel-delivery/patch-swarm-leasing.md)
- [Patch Swarm Worker Pool and Process Visibility](./parallel-delivery/patch-swarm-worker-status.md)
- [Patch Swarm Deterministic Validation and Fixture E2E](./parallel-delivery/patch-swarm-validation-e2e.md)
- [Patch Swarm Taskstream Handoff](./parallel-delivery/patch-swarm-taskstream.md)
- [Patch Swarm Console Status](./parallel-delivery/patch-swarm-console.md)
- [Patch Swarm Patch Bundle Collection and Safety Validation](./parallel-delivery/patch-bundle-validation.md)
- [Parallel Delivery Safe Apply And Release Candidate](./parallel-delivery/release-candidate-safe-apply.md)
- [Fixture Sickness Reuse Gate](./fixture-sickness.md)

## Product Definition

Patch Swarm is Cento's local-first parallel software delivery system. Given one high-level product request, it creates a run, converts the request into a ProReq/product request packet, splits it into up to 100 bounded candidate patch tasks, leases exclusive paths with Workset, emits Codex/worker prompts, collects patch bundles, validates them deterministically through Build and Factory checks, integrates safe patches sequentially or by dependency order through the Safe Integrator path, produces a release candidate, and writes durable evidence under `workspace/runs/`.

Patch Swarm is not unbounded multi-agent editing. It is candidate generation plus controlled integration. Workers may generate candidate diffs or structured artifacts in parallel, but repository mutation stays behind deterministic validation, recorded ordering, and Factory/Safe Integrator apply gates.

The concrete existing run root is `workspace/runs/parallel-delivery/patch-swarm/<run_id>/`. The product contract below uses `workspace/runs/<run_id>/` as the logical shape for future operators and docs; implementation slices must either map that logical shape to the existing run root or migrate with compatibility receipts.

## Operator Story

Given one product request, Cento creates a run, splits the request into up to 100 bounded candidate patch tasks, leases exclusive paths, emits Codex/worker prompts, collects patch bundles, validates them deterministically, integrates safe patches sequentially or by dependency order, produces a release candidate, and writes durable evidence.

The operator should be able to ask for one product outcome, watch candidate and integration state in Console/Taskstream summaries, inspect the release candidate and evidence, and continue from the recorded next action without reading raw worker transcripts by default.

## Non-Goals

- No unbounded concurrent writers against the same worktree.
- No bypass around Factory, Workset, Build, or Safe Integrator when those surfaces already own the behavior.
- No direct Taskstream, Redmine, or story database writes.
- No live provider fanout without explicit budget caps, provider receipts, and fail-closed admission checks.
- No automatic merge to main in the Patch Swarm product contract.
- No registry claim that planned commands exist until the runtime implements them.

## Existing Cento Surfaces Used

| Surface | Role in Patch Swarm |
| --- | --- |
| `cento parallel-delivery` | Registered orchestration surface for run creation, Patch Swarm planning, execution, validation, status, and evidence. |
| `cento parallel-delivery patch-swarm` | Current implemented command family for fixture/live candidate generation, ranking, Safe Integrator handoff, validation, status, and e2e proof. |
| `cento factory` | Durable planning, patch collection, `validate-fanout`, Safe Integrator apply plans, release candidates, release evidence, rollback, and Taskstream sync previews. |
| `cento workset` | Exclusive write path checks, worker boundaries, dependency gates, parallel artifact collection, and sequential integration discipline. |
| `cento build` | Manifest-owned local build packages, worker prompts, worker artifact checks, patch bundles, safe apply receipts, and deterministic patch safety checks. |
| Taskstream | Operator-visible status and summaries through existing MCP or `cento agent-work` surfaces; never direct DB mutation. |
| `cento mcp` | Repo-local MCP server for safe board, story, cluster, bridge, and agent-work context when an MCP client is available. |
| ProReq | Product request packet and requirements contract that constrains decomposition, acceptance, paths, validation, risk, and budget. |
| Safe Integrator | The only real patch apply boundary after validation; applies selected bundles in recorded sequential or dependency order. |
| `cento agent-work` | Existing agent-visible work/status bridge when work needs durable operator or Taskstream visibility. |
| Console visibility | Shows run summaries, candidates, gates, validation, decisions, release candidate status, and evidence links without exposing secrets or huge transcripts. |

## User-Facing CLI Contract

The existing implemented surface is `cento parallel-delivery patch-swarm ...`. The target operator facade below is the planned product contract for future implementation slices. Until implemented, these commands are documented as planned contract, and implementation must route to existing `parallel-delivery`, `factory`, `workset`, and `build` behavior instead of creating a competing scheduler.

```bash
cento parallel-delivery init --request-file REQUEST.md [--run-id RUN_ID]
cento parallel-delivery plan --run RUN_ID --max-tasks 100
cento parallel-delivery emit-prompts --run RUN_ID --out workspace/runs/RUN_ID/prompts
cento parallel-delivery collect --run RUN_ID --patch-dir workspace/runs/RUN_ID/inbox
cento parallel-delivery validate --run RUN_ID
cento parallel-delivery integrate --run RUN_ID [--strategy sequential|dependency-order]
cento parallel-delivery rc --run RUN_ID
cento parallel-delivery status --run RUN_ID
cento parallel-delivery evidence --run RUN_ID
cento parallel-delivery demo --request-file examples/parallel-delivery/simple-request.md --max-tasks 3
```

| Subcommand | Purpose | Inputs | Outputs | State transition | Evidence written | Failure behavior |
| --- | --- | --- | --- | --- | --- | --- |
| `init` | Create a run from an operator request and normalize it into the ProReq packet. | `REQUEST.md`, optional `RUN_ID`. | `run.json`, `request/request.md`, `request/proreq.json`. | `request_received -> run_created`. | `evidence/commands.log`, request receipt. | Reject missing request files, unsafe paths, or duplicate run IDs unless resume is explicit. |
| `plan` | Decompose the ProReq packet into bounded candidate tasks and graph edges. | `run.json`, `proreq.json`, `--max-tasks` up to 100. | `plan/decomposition.json`, `plan/task_graph.json`, `plan/risks.json`. | `run_created -> plan_generated -> tasks_created`. | Planner receipt and risks. | Reject over-100 tasks, missing acceptance contracts, duplicate workflow attempts, and unresolved shared-path ambiguity. |
| `emit-prompts` | Emit worker-ready Codex/worker prompt packets after leases are valid. | Task graph, path leases, output directory. | `prompts/task-0001.md`, prompt index. | `paths_leased -> worker_prompts_emitted`. | Prompt emission receipt. | Reject tasks without acceptance contracts, validation commands, or exclusive path lease/read-only classification. |
| `collect` | Collect submitted patch bundles from workers or fixture inboxes. | Inbox path with bundle JSON and diff files. | `workers/<task_id>/patch.bundle.json`, `workers/<task_id>/patch.diff`, transcript/evidence links. | `workers_dispatched -> patch_bundles_collected`. | Collection receipt and per-task state updates. | Reject malformed schemas, missing diffs, stale base metadata, or changed paths outside claimed paths. |
| `validate` | Run deterministic validation for each submitted patch bundle. | Run directory and validation commands. | `validation/*.validation.json`, `validation/matrix.json`. | `patch_bundles_collected -> validation_started -> validation_passed|validation_failed`. | Validation logs and rejection reasons. | Reject unsafe diffs, missing evidence, skipped required checks, secret leaks, direct DB mutation, and path lease violations. |
| `integrate` | Build and execute the Safe Integrator queue in recorded order. | Validated tasks, strategy `sequential` or `dependency-order`. | `integration/queue.json`, integrated/rejected/conflict ledgers. | `validation_passed -> integration_started -> integration_completed`. | Integration receipt and ordering ledger. | Reject nondeterministic ordering, conflicts without quarantine, dirty unrelated work, or patches requiring reset/checkout/clean/stash. |
| `rc` | Build the release candidate from integrated patches or an explicit no-op result. | Integration receipts and validation matrix. | `rc/release-candidate.json`, `rc/build.log`, `rc/validation.log`. | `integration_completed -> rc_built -> rc_validated`. | RC receipt and validation log. | Fail if integration is incomplete, RC validation fails, or evidence is missing. |
| `status` | Report current run state and operator-visible summary. | `RUN_ID`. | Human or JSON status summary. | No mutation except optional status read receipt. | Optional status receipt. | Return failed/unknown with missing artifact paths instead of guessing. |
| `evidence` | Render the durable evidence summary and artifact index. | Run directory. | `evidence/summary.md`, `evidence/artifacts.json`, `evidence/commands.log`. | `rc_validated -> completed` when evidence is durable. | Evidence summary and artifact manifest. | Do not mark completed if evidence cannot be written. |
| `demo` | Future compact e2e proof using 2-3 bounded tasks. | Example request, `--max-tasks 3`. | Full run directory and final status. | Full lifecycle to `completed` or explicit `failed`. | Demo summary and receipts. | Must include one unsafe rejection and one safe integration or fail with concrete evidence. |

## Artifact Lifecycle

The minimum logical run shape is:

```text
workspace/runs/<run_id>/
  run.json
  request/
    request.md
    proreq.json
  plan/
    decomposition.json
    task_graph.json
    risks.json
  leases/
    path_leases.json
  prompts/
    task-0001.md
    task-0002.md
  workers/
    task-0001/
      state.json
      transcript.md
      patch.bundle.json
      patch.diff
      evidence/
    task-0002/
      state.json
      transcript.md
      patch.bundle.json
      patch.diff
      evidence/
  validation/
    task-0001.validation.json
    task-0002.validation.json
    matrix.json
  integration/
    queue.json
    integrated-patches.json
    rejected-patches.json
    conflicts.json
  rc/
    release-candidate.json
    build.log
    validation.log
  evidence/
    summary.md
    commands.log
    artifacts.json
```

Minimum `run.json` schema:

```json
{
  "run_id": "patch-swarm-YYYYMMDD-HHMMSS-slug",
  "request_title": "string",
  "state": "request_received|run_created|plan_generated|tasks_created|paths_leased|worker_prompts_emitted|workers_dispatched|patch_bundles_collected|validation_started|validation_passed|validation_failed|integration_started|integration_completed|rc_built|rc_validated|completed|failed|aborted",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "max_candidate_tasks": 100,
  "max_concurrent_workers": 1,
  "integration_strategy": "sequential|dependency-order",
  "artifacts": {}
}
```

Minimum task schema:

```json
{
  "task_id": "task-0001",
  "title": "string",
  "state": "created|leased|prompt_emitted|dispatched|patch_submitted|validation_running|validation_passed|validation_failed|queued_for_integration|integrated|rejected|superseded|aborted",
  "owned_paths": [],
  "read_only_paths": [],
  "dependencies": [],
  "acceptance_contract": [],
  "validation_commands": [],
  "patch_bundle": null,
  "evidence": []
}
```

Minimum patch bundle schema:

```json
{
  "task_id": "task-0001",
  "base_ref": "string",
  "worker_id": "string",
  "claimed_paths": [],
  "changed_paths": [],
  "diff_path": "patch.diff",
  "summary": "string",
  "tests_run": [],
  "evidence_files": [],
  "risks": [],
  "requires_manual_review": false
}
```

## Run State Machine

Allowed run states:

```text
request_received
run_created
plan_generated
tasks_created
paths_leased
worker_prompts_emitted
workers_dispatched
patch_bundles_collected
validation_started
validation_passed
validation_failed
integration_started
integration_completed
rc_built
rc_validated
completed
failed
aborted
```

Allowed transitions:

```text
request_received -> run_created
run_created -> plan_generated
plan_generated -> tasks_created
tasks_created -> paths_leased
paths_leased -> worker_prompts_emitted
worker_prompts_emitted -> workers_dispatched
workers_dispatched -> patch_bundles_collected
patch_bundles_collected -> validation_started
validation_started -> validation_passed
validation_started -> validation_failed
validation_passed -> integration_started
validation_failed -> integration_started when at least one patch passed validation
validation_failed -> failed when no safe patch remains and the request cannot be satisfied
integration_started -> integration_completed
integration_completed -> rc_built
rc_built -> rc_validated
rc_validated -> completed
any nonterminal state -> failed with evidence
any nonterminal state -> aborted with operator reason
```

Rules:

- A run cannot enter `workers_dispatched` until prompts exist.
- A run cannot enter `integration_started` until at least one patch has passed validation.
- A run cannot enter `rc_built` until integration has completed or the queue is empty with an explicit no-op result.
- A run cannot enter `completed` until durable evidence exists.
- Failed tasks do not necessarily fail the run if at least one safe patch can be integrated.
- The run fails if no patch can be integrated and the request cannot be satisfied.

## Worker / Task State Machine

Allowed task states:

```text
created
leased
prompt_emitted
dispatched
patch_submitted
validation_running
validation_passed
validation_failed
queued_for_integration
integrated
rejected
superseded
aborted
```

Allowed transitions:

```text
created -> leased
leased -> prompt_emitted
prompt_emitted -> dispatched
dispatched -> patch_submitted
patch_submitted -> validation_running
validation_running -> validation_passed
validation_running -> validation_failed
validation_passed -> queued_for_integration
queued_for_integration -> integrated
queued_for_integration -> rejected
validation_failed -> rejected
created|leased|prompt_emitted|dispatched -> aborted
any nonterminal task -> superseded when a newer valid task replaces it with evidence
```

Rules:

- A task cannot become `prompt_emitted` without an acceptance contract.
- A task cannot become `dispatched` without an exclusive path lease or explicit read-only classification.
- A task cannot become `queued_for_integration` unless validation passed.
- A task cannot become `integrated` if it changes paths outside its lease.
- A task with a stale base, unsafe diff, secret leak, or direct Taskstream DB mutation must be rejected.
- A rejected task must retain evidence explaining the rejection.

## What "100 Agents" Means Safely

"100 agents" means:

```text
up to 100 candidate patch tasks
+ bounded concurrent execution
+ exclusive path leases
+ deterministic validation before integration
+ sequential or dependency-ordered safe integration
+ evidence-backed acceptance
```

It does not mean 100 unbounded concurrent writers. Patch Swarm may generate up to 100 candidate tasks or candidate patches, but each task must be bounded by an owned path set, read-only path set, acceptance contract, validation command set, and integration strategy. The default `max_concurrent_workers` may be as low as `1` for safety; higher concurrency is allowed only when Workset proves non-overlapping write paths and the budget/admission gates pass.

## Path Leasing and Workset Boundaries

Workset is the path boundary authority. A task lease must list exact owned paths, read-only paths, dependencies, blocked paths, and any generated artifact destinations. Globs, absolute paths, overlapping write paths, protected files, and shared-file edits are rejected unless the shared edit is moved into an explicit serialized integrator task.

Workers can read context outside their owned paths only when the planner marks those files read-only. They cannot write run artifacts outside the run root, cannot mutate unrelated dirty work, and cannot create new persistent tool or CLI registry entries unless the task explicitly owns those files and the schema/docs alignment checks pass.

## Planning and Prompt Packet Generation

Planning starts from the ProReq/product request packet. The Factory-equivalent decomposition produces task records with title, owned paths, read-only paths, dependencies, acceptance contract, validation commands, risks, and prompt constraints. Prompt packets are emitted only after path leases exist and must include:

- the operator request summary,
- the task acceptance contract,
- owned and read-only paths,
- validation commands to run or explain,
- patch bundle schema,
- explicit unsafe rejection rules,
- the run evidence directory,
- instructions to preserve unrelated dirty work.

Codex-ready worker packets are generated by `cento parallel-delivery patch-swarm worker-packets` and documented in `docs/parallel-delivery/patch-swarm-codex-worker-packets.md`. They are local copy/paste artifacts, not live dispatch.

Bounded worker dispatch/status planning is generated by `cento parallel-delivery patch-swarm dispatch --dry-run` and documented in `docs/parallel-delivery/patch-swarm-worker-status.md`. It represents up to 100 candidate tasks, writes queue and status ledgers, and keeps process visibility local/read-only unless a future live backend is explicitly validated.

## Patch Bundle Contract

Patch bundles are structured receipts, not free-form chat summaries. A bundle must include the task ID, worker ID, base ref, claimed paths, changed paths, diff path, summary, tests run, evidence files, risks, and manual-review flag. The diff must apply to the recorded base in an isolated validation path or be rejected as stale.

Workers may submit `candidate_patch.v1` receipts through the current Patch Swarm path, Workset worker artifacts, or Build patch bundles. The Safe Integrator handoff must normalize accepted candidates into Factory-compatible patch bundles before any real apply attempt.

## Deterministic Validation Contract

Validation is deterministic first. The validator checks schema, base ref, path lease compliance, diff safety, secret patterns, direct DB mutation attempts, required command evidence, changed path ownership, dependency status, and focused tests. `cento build` and `cento factory validate-fanout` are the preferred validation surfaces where their contracts fit. AI review is advisory only and must be converted back into deterministic receipts before integration.

## Safe Integration Contract

Safe integration is serialized or dependency ordered. The integration queue records every patch candidate, ordering reason, dependency edge, apply command, validation command, and result. Integration applies only validated bundles through Factory/Safe Integrator worktrees or equivalent receipts. It must reject nondeterministic ordering, dirty unrelated work, missing rollback metadata, and any apply path that requires `git reset`, `git checkout`, `git clean`, or `git stash` to succeed.

## Release Candidate Contract

A release candidate is a recorded candidate release state, not a merge. It must include integrated patch IDs, rejected patch IDs, validation summary, build log, residual risks, rollback notes, evidence paths, and the next operator action. The release candidate can be a no-op only when the integration queue is empty and the run records why no safe patch was needed or possible.

The implemented local receipt path is `cento parallel-delivery release-candidate create`. It reads an accepted `cento.parallel_delivery.integration_receipt.v1`, verifies each accepted bundle receipt and patch SHA-256, refuses rejected or non-integratable bundles, dry-runs every patch by default, and writes apply receipts plus rollback metadata. `--mode apply` requires an explicit isolated target worktree and writes `release-candidate.json`, `release-notes.md`, and `integrated.diff` only after all accepted bundles apply sequentially and final validation passes.

## Evidence Contract

Every run writes durable evidence under `workspace/runs/`. Minimum evidence includes command logs, artifact index, summary markdown, state transitions, validation matrix, rejection reasons, integration queue, release candidate, and Console/Taskstream summary path. Evidence must avoid secrets, raw environment dumps, API keys, `.env.mcp`, and huge raw transcripts unless a transcript is stored as a run artifact and summarized safely.

## Console and Taskstream Visibility

Console and Taskstream should show summaries, not raw secrets or huge transcripts. The visible summary fields are:

- `run_id`
- request title
- current run state
- candidate task count
- active worker count
- passed, failed, rejected, and integrated task counts
- leased path summary
- validation summary
- integration queue status
- release candidate status
- evidence summary path
- next operator action

Cento may publish status through existing MCP or `cento agent-work` surfaces. Cento must not mutate Taskstream, Redmine, or story state through direct DB writes.

## Unsafe Inputs and Rejection Rules

Patch Swarm must deterministically reject inputs or patches that:

- change files outside their leased paths
- modify secrets or include local secret values
- copy `.env.mcp` or API keys into repo artifacts
- copy .env.mcp through any transcript, evidence file, or generated artifact path
- attempt direct database writes to Taskstream/Redmine/story state
- skip required validation commands
- claim tests passed without evidence
- overwrite unrelated dirty work
- require `git reset`, `git checkout`, `git clean`, or `git stash` to apply
- modify `data/tools.json` or `data/cento-cli.json` without matching existing schema and docs
- introduce duplicate workflows instead of using existing Cento surfaces
- use nondeterministic integration without recorded ordering
- change generated run artifacts outside `workspace/runs/<run_id>/`
- delete durable evidence

## E2E Demo Definition of Done

The end-to-end demo is done when a local operator can run a bounded demo proving:

- one request creates a run directory
- the request is converted into a ProReq/product request packet
- Factory or an equivalent planner creates 2-3 bounded tasks
- Workset creates non-overlapping path leases
- worker prompts are emitted
- at least one synthetic or real patch bundle is collected
- validation runs deterministically
- an unsafe patch is rejected with evidence
- a safe patch is integrated in recorded order
- a release candidate artifact is written
- summary evidence is written under `workspace/runs/<run_id>/evidence/`
- `status` reports the final state

For Call 1, done means this canonical spec, lifecycle diagram, implementation map, validation matrix, and run evidence exist and pass grep/docs-command validation.

## Future Implementation Calls

Future implementation should proceed in slices:

1. Run directory and artifact schema.
2. Request intake and ProReq packet generation.
3. Factory task splitter.
4. Workset path leasing.
5. Worker prompt packet emission.
6. Patch bundle collection.
7. Deterministic task validation.
8. Safe Integrator queue and apply handoff.
9. Release candidate build.
10. Console/Taskstream summary visibility.
11. Bounded e2e demo harness.

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
cento parallel-delivery patch-swarm e2e --candidate-target 100 --max-parallel-agents 5 --fixture --json
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

Run list and detail payloads include `run_kind`, which is `product` for local repo product runs and `engine` for lower-level Patch Swarm pipeline runs. Detail payloads also include `action_gates`:

- `can_approve` plus `approve_disabled_reason`
- `can_apply` plus `apply_disabled_reason`
- `can_reject` plus `reject_disabled_reason`

The frontend renders review actions from these backend gates. The backend still enforces the same gates on approve, reject, and apply requests.

Product runs add thin metadata around the existing artifact contract:

- `product_metadata.json`
- `product_run_create_receipt.json`
- `supervised_approval.json`
- `candidate_decisions.json`
- `product_safe_integrator_apply.json` for Patch Swarm product worktree apply receipts
- `product_no_mutation_create.json`, `product_no_mutation_apply.json`, and `product_no_mutation_checks.json`

Patch Swarm is also still registered as a Dev Pipeline Studio template.

The run writes:

- `workspace/runs/parallel-delivery/patch-swarm/<run>/ui_state.json`
- `workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/patch-swarm/latest_ui_state.json`

The UI state includes candidate totals, provider counts, lane status, ranking, selected winners, validation, cost ledger, handoff links, product metadata, approval state, and candidate decisions.

## Cost And Safety

The default product path is deterministic fixture execution. It does not call OpenAI, does not launch live Codex or Claude workers, and does not apply patches to the selected repo worktree. Product apply creates or reuses a Patch Swarm-owned product worktree under `workspace/runs/patch-swarm-product-worktrees/` and writes no-mutation receipts for the selected repo.

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

The product release-candidate e2e command is:

```bash
python3 scripts/patch_swarm_product_e2e.py
```

It creates clean, unprotected-dirty, and protected-dirty fixture repos, starts the Cento Console in-process, drives the `/api/patch-swarm/*` product lifecycle, checks no selected-repo mutation, applies one approved candidate in a Patch Swarm product worktree, and captures `/patch-swarm` plus `/patch-swarm/runs/:run_id` screenshots at `390x900`, `1365x1000`, and `2048x1000`. The summary is written to `workspace/runs/patch-swarm-product-e2e/<run-id>/summary.json`.

## What Patch Swarm Is

Patch Swarm is the Parallel Delivery path for turning one product request into bounded implementation candidates, validating the candidates with local deterministic gates, and integrating only receipt-backed results. It is centered on the existing `cento parallel-delivery` command family and reuses Build, Workset, Factory, Taskstream, and Console surfaces rather than creating a second scheduler.

The operator-facing output is not a raw worker transcript. A healthy run produces a request artifact, split plan, task graph, path leases, worker packets, patch bundle receipts, integration plan, validation summary, release candidate, status payload, and evidence index under `workspace/runs/`.

## Safe Mental Model

- A target of 100 means up to 100 candidate tasks in the plan, not 100 uncontrolled live writers.
- `--max-parallel-agents` bounds active fixture or worker batches.
- Workset-compatible path leases keep write ownership explicit before workers touch code.
- Patch bundles are collected and validated before integration.
- Integration remains sequential or dependency ordered and is recorded in receipts.
- Fixture mode is the default adoption gate; live providers, live workers, and live Taskstream mutation stay explicit opt-ins.
- Dirty work is preserved. Patch Swarm should inspect and classify dirty targets instead of wiping the worktree.

## Quickstart

Run the local fixture gate from the repo root:

```bash
cento parallel-delivery patch-swarm e2e --candidate-target 100 --max-parallel-agents 5 --fixture --json
cento parallel-delivery validate --json
cento parallel-delivery status --json
```

Then inspect the emitted run directory from the JSON payload. The key files are `validation-summary.json`, `validation-report.md`, `integration/integration-plan.json`, `integration/conflict-report.md`, and `release-candidate/release-candidate.json`.

## Full Fixture Demo

The full deterministic demo is:

```bash
cento parallel-delivery patch-swarm e2e --candidate-target 100 --max-parallel-agents 5 --fixture --json
```

Expected behavior:

- 100 candidate tasks are planned.
- Worker batches are bounded to 5 at a time.
- One unsafe fixture bundle is rejected.
- Accepted bundles are ordered in `integration/integration-plan.json`.
- No live provider call, live worker launch, selected-repo mutation, or Taskstream mutation occurs.
- Durable evidence is written under `workspace/runs/parallel-delivery/e2e-fixture/<run-id>/`.

## ChatGPT Pro / ProReq Flow

ProReq and ChatGPT Pro prompts are generated as local prompt bundles. The operator can review or paste them manually, but prompt generation does not require a live provider by default.

```bash
cento parallel-delivery patch-swarm prompts --run-dir workspace/runs/parallel-delivery/proreq-fixture --count 20 --lane all --json
```

Each prompt should include mission, owned paths, prohibited paths or safety rules, validation commands, evidence expectations, and a Codex output contract. The generated prompt bundle can be connected to `cento temp` when the existing temp bridge is available.

## Codex Paste Flow

Codex worker packets are generated from a split plan and task graph. Each packet is intended for one Codex thread or worker lane and should be pasted only after the operator has reviewed path ownership and validation requirements.

Typical packet contents:

- thread title
- task ID
- mission
- discovery commands
- owned write paths
- read-only paths
- prohibited paths
- implementation steps
- tests and validation commands
- evidence paths
- patch bundle or handoff instructions
- blocker protocol

## Worker Packet Format

Worker packets must be scoped enough for an agent to act without inventing workflow. A worker packet is valid only when it names the task, lease, expected touched paths, acceptance contract, validation commands, evidence path, and safety constraints. It must not instruct a worker to wipe or broadly restore the worktree, copy secret files, or mutate Taskstream/Redmine outside the approved `cento agent-work` or MCP surfaces.

## Artifacts and Evidence

The fixture and product paths both converge on the same evidence model:

- `run.json`: run identity, state, constraints, provenance, and artifact pointers.
- `request.md` and `context-pack.json`: request and local context.
- `split-plan.json` and `task-graph.json`: bounded task plan and dependencies.
- `path-leases.json`: write ownership and guarded paths.
- `worker-packets/`: paste-ready worker instructions.
- `patch-bundles/` and validation receipts: accepted, rejected, and evidence-only results.
- `integration/integration-plan.json`: deterministic ordering and conflict buckets.
- `integration/conflict-report.md`: human-readable conflict triage.
- `validation-summary.json` and `validation-report.md`: final gate results.
- `release-candidate/release-candidate.json`: release packet status and evidence pointers.

## Safety Rules

- Keep fixture and dry-run behavior as the default.
- Require explicit operator flags for live provider fanout, live worker launch, and live Taskstream creation.
- Use existing Build, Workset, Factory, Taskstream, MCP, and `agent-work` surfaces.
- Reject or flag absolute paths, traversal paths, protected local secret paths, undeclared deletes, unowned renames, unsupported binary patches, and broad lockfile edits.
- Preserve unrelated dirty work and record dirty-target risk in evidence.
- Never copy local secret files or token values into prompts, bundles, docs, or evidence.

## Validation

The adoption gate is:

```bash
python3 -m json.tool data/tools.json
cento tools
cento docs parallel-delivery
python3 -m pytest -q tests/test_patch_swarm.py
python3 -m pytest -q tests -k "patch_swarm or parallel_delivery or build or workset or factory or cli or registry or docs"
cento parallel-delivery validate --json
cento parallel-delivery status --json
cento parallel-delivery patch-swarm e2e --candidate-target 100 --max-parallel-agents 5 --fixture --json
```

If `make patch-swarm-check` exists in the local Makefile, it should be a wrapper around deterministic local gates only.

## Console/status Visibility

Status JSON and Console should show the current run, candidate count, active or simulated worker batches, pending/accepted/rejected bundles, integration status, validation status, release candidate status, evidence links, and the next safe operator action. Console reads local artifacts and should not invent a separate state database for Patch Swarm.

## Troubleshooting

- If `validate --json` fails, inspect the failing gate and the evidence path in the JSON payload.
- If the 100-candidate fixture fails, inspect `validation-report.md`, `integration/conflict-report.md`, and rejected bundle receipts in the run directory.
- If status is empty, run the fixture E2E once and then rerun `cento parallel-delivery status --json`.
- If a path lease conflict appears, group the conflicting tasks sequentially or reduce the task split before dispatch.
- If live execution is blocked, first make the fixture path green and then inspect the explicit opt-in gate that refused the live action.

## Extension Guide

Add new Patch Swarm behavior by extending the existing `parallel-delivery` surface and associated helper module. A safe extension should add a fixture, schema or receipt updates, tests, docs, and evidence. Prefer additive command routes and stable JSON over rewriting the orchestration path. New lanes should declare owned paths, validation commands, evidence outputs, and failure handling before they are eligible for worker packets or integration.

## Adoption Narrative

Patch Swarm scales delivery without losing control because it separates exploration from mutation. Many candidate tasks can be planned, prompted, and evaluated, while write ownership, patch validation, integration, and release evidence remain deterministic. Staff engineers can review the artifacts asynchronously, leads can track progress through status and Console, and teams can adopt live workers only after the local fixture gate is routine.
