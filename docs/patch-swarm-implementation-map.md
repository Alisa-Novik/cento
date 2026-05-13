# Patch Swarm Implementation Map

This map decomposes the Patch Swarm / Parallel Software Delivery product contract into future implementation slices. Each milestone should preserve the existing Cento surfaces: `cento parallel-delivery`, `cento factory`, `cento workset`, `cento build`, `cento agent-work`, `cento mcp`, ProReq, Taskstream visibility, and Factory/Safe Integrator.

## Milestone 0: Canonical Spec and Docs

Purpose: Create the source-of-truth product architecture, lifecycle, implementation map, and validation matrix.

Owned artifacts: `docs/patch-swarm.md`, `docs/patch-swarm-lifecycle.md`, `docs/patch-swarm-implementation-map.md`, `docs/patch-swarm-validation-matrix.md`, `workspace/runs/patch-swarm-call-1-product-architecture/`.

Likely commands/subcommands: `cento docs parallel-delivery`, `cento docs factory`, `cento docs workset`, `cento docs build`.

Inputs: Existing docs, registered tool metadata, operator mission.

Outputs: Canonical docs and evidence summary.

Validation commands: grep required headings/states/contracts; run docs smoke commands.

Evidence files: `discovery.log`, `docs-created-or-updated.txt`, `spec-summary.md`, `validation.log`.

Failure handling: Record failed validation with exact missing section or command output.

Acceptance criteria: Docs exist, are linked from the canonical spec, and define product, CLI contract, artifacts, states, safety, e2e done, and future slices.

## Milestone 1: Run Directory and Artifact Schema

Purpose: Implement the logical `workspace/runs/<run_id>/` schema while staying compatible with current `workspace/runs/parallel-delivery/patch-swarm/<run_id>/` artifacts.

Owned artifacts: `run.json`, `evidence/commands.log`, `evidence/artifacts.json`, schema validation fixtures.

Likely commands/subcommands: `cento parallel-delivery init --request-file REQUEST.md [--run-id RUN_ID]`, current `cento parallel-delivery patch-swarm plan --run-id RUN_ID`.

Inputs: Request file, optional run ID, current registry path conventions.

Outputs: Run directory, initialized `run.json`, artifact index, command log.

Validation commands: `test -f RUN/run.json`, JSON schema check, path-root guard, resume/idempotency check.

Evidence files: `run.json`, `evidence/commands.log`, `evidence/artifacts.json`.

Failure handling: Reject duplicate run IDs unless resume is explicit; fail closed on paths outside `workspace/runs/`.

Acceptance criteria: A request creates one durable run root and no unrelated repository files are mutated.

## Milestone 2: Request Intake / ProReq Packet

Purpose: Convert the operator request into a strict ProReq/product request packet that drives planning and validation.

Owned artifacts: `request/request.md`, `request/proreq.json`, intake receipt, normalized request title.

Likely commands/subcommands: `cento parallel-delivery init --request-file REQUEST.md`, ProReq-compatible helper calls, current Hard ProReq/ProReq-light surfaces where appropriate.

Inputs: Request markdown, optional product metadata, risk/budget limits.

Outputs: `request/proreq.json` with goals, acceptance checks, constraints, read context, owned path candidates, validation expectations, budget, and non-goals.

Validation commands: JSON schema check; required fields check; secret/path safety scan.

Evidence files: Intake receipt, request hash, `evidence/commands.log`.

Failure handling: Reject missing acceptance criteria, local secret values, direct DB mutation requests, or unbounded worker instructions.

Acceptance criteria: Every downstream task can cite the ProReq acceptance contract and risk limits.

## Milestone 3: Factory Task Splitter

Purpose: Split the ProReq packet into 2-100 bounded candidate patch tasks without inventing a second planner.

Owned artifacts: `plan/decomposition.json`, `plan/task_graph.json`, `plan/risks.json`.

Likely commands/subcommands: `cento parallel-delivery plan --run RUN_ID --max-tasks 100`, `cento factory plan`, existing Patch Swarm decomposition helpers.

Inputs: `request/proreq.json`, existing repo context, max task count.

Outputs: Candidate tasks with `task_id`, title, owned path candidates, read-only paths, dependencies, acceptance contract, validation commands, and risks.

Validation commands: Task count `<= 100`; no task lacks acceptance contract; dependency graph is acyclic; shared-file pressure is surfaced.

Evidence files: Planner receipt, task graph, risks summary.

Failure handling: Reject over-broad tasks, overlapping candidate ownership not resolvable by Workset, and duplicate workflow plans.

Acceptance criteria: The planner emits a bounded graph that can be leased by Workset.

## Milestone 4: Workset Path Leasing

Purpose: Turn task-owned path candidates into exclusive leases and read-only classifications.

Owned artifacts: `leases/path_leases.json`, lease failure reports, Workset-compatible manifest.

Likely commands/subcommands: `cento workset check WORKSET`, `cento parallel-delivery plan --run RUN_ID --max-tasks N` with lease emission, future `cento parallel-delivery emit-prompts`.

Inputs: Task graph, repo path inventory, protected paths, generated artifact targets.

Outputs: Non-overlapping leases, blocked paths, explicit serialized integrator tasks for shared edits.

Validation commands: `cento workset check`; overlap/glob/absolute path rejection tests; protected path fixtures.

Evidence files: `leases/path_leases.json`, Workset check receipt, lease conflict report.

Failure handling: Reject overlapping writes; move shared edits into serialized integrator tasks only when deterministic and recorded.

Acceptance criteria: No task can dispatch without an exclusive lease or read-only classification.

## Milestone 5: Worker Prompt Packet Emission

Purpose: Emit worker-ready prompt packets that preserve task boundaries and evidence requirements.

Owned artifacts: `prompts/task-0001.md`, prompt index, prompt emission receipt.

Likely commands/subcommands: `cento parallel-delivery emit-prompts --run RUN_ID --out workspace/runs/RUN_ID/prompts`, `cento build prompt MANIFEST`.

Inputs: ProReq packet, task graph, leases, validation commands, unsafe rejection rules.

Outputs: Prompt markdown per task, prompt manifest, task states moved to `prompt_emitted`.

Validation commands: grep prompt for task ID, owned paths, acceptance contract, validation commands, patch bundle schema, and dirty-work preservation rule.

Evidence files: Prompt emission receipt, prompt index, state transition log.

Failure handling: Refuse prompt emission for tasks without acceptance contract, validation command, or path lease.

Acceptance criteria: Each prompt is self-contained enough for a worker and cannot authorize writes outside its lease.

## Milestone 6: Patch Bundle Collection

Purpose: Collect worker outputs into normalized patch bundles and preserve raw evidence.

Owned artifacts: `workers/<task_id>/patch.bundle.json`, `workers/<task_id>/patch.diff`, `workers/<task_id>/state.json`, worker evidence directory.

Likely commands/subcommands: `cento parallel-delivery collect --run RUN_ID --patch-dir workspace/runs/RUN_ID/inbox`, current `cento parallel-delivery patch-swarm execute RUN_ID --fixture|--live`, `cento build bundle synthesize`.

Inputs: Inbox path, worker artifacts, candidate patches, transcripts, evidence files.

Outputs: Normalized bundle records, per-task state changes to `patch_submitted`, collection receipt.

Validation commands: JSON schema check; diff path exists; base ref present; claimed/changed paths present.

Evidence files: Collection receipt, worker evidence, bundle index.

Failure handling: Reject malformed bundles, stale base refs, missing diffs, and changed paths outside claimed paths before validation.

Acceptance criteria: Every submitted patch has a structured bundle and traceable evidence.

## Milestone 7: Deterministic Task Validation

Purpose: Validate each patch before it can enter the integration queue.

Owned artifacts: `validation/<task_id>.validation.json`, `validation/matrix.json`, rejection receipts.

Likely commands/subcommands: `cento parallel-delivery validate --run RUN_ID`, `cento build artifact check`, `cento build integrate --dry-run`, `cento factory validate-fanout RUN_ID --max-parallel N --json`.

Inputs: Patch bundles, leases, task acceptance contracts, validation commands.

Outputs: Per-task pass/fail receipts, validation matrix, rejection reasons.

Validation commands: Schema, path lease, dirty-work, secret scan, direct DB mutation scan, required command evidence, focused tests.

Evidence files: Validation receipts, command logs, rejected patch evidence.

Failure handling: Reject unsafe tasks but continue the run if at least one safe patch remains.

Acceptance criteria: Only `validation_passed` tasks can become `queued_for_integration`.

## Milestone 8: Safe Integrator

Purpose: Integrate validated patches in recorded sequential or dependency order through Factory/Safe Integrator.

Owned artifacts: `integration/queue.json`, `integration/integrated-patches.json`, `integration/rejected-patches.json`, `integration/conflicts.json`.

Likely commands/subcommands: `cento parallel-delivery integrate --run RUN_ID --strategy sequential|dependency-order`, current `cento parallel-delivery patch-swarm integrate RUN_ID --dry-run|--apply`, `cento factory integrate RUN_ID --plan|--apply --validate-each`.

Inputs: Validated patches, dependency graph, integration strategy, Factory patch bundles.

Outputs: Integration queue, apply plan, integrated/rejected/conflict ledgers, Safe Integrator receipts.

Validation commands: Queue order check; apply dry-run; validate each integrated patch; no reset/checkout/clean/stash requirement.

Evidence files: Safe Integrator handoff, Factory apply plan, integration receipts, rollback metadata.

Failure handling: Quarantine conflicts, reject nondeterministic ordering, and fail the run only when no safe integration path can satisfy the request.

Acceptance criteria: Integrated patches have recorded order, validation evidence, and rollback metadata.

## Milestone 9: Release Candidate Build

Purpose: Produce a release candidate artifact after integration or an explicit no-op result.

Owned artifacts: `rc/release-candidate.json`, `rc/build.log`, `rc/validation.log`.

Likely commands/subcommands: `cento parallel-delivery rc --run RUN_ID`, `cento factory release-candidate RUN_ID`, `cento factory validate-integrated RUN_ID`.

Inputs: Integration receipts, validation matrix, build/test commands, residual risks.

Outputs: Release candidate JSON, build log, validation log, operator next action.

Validation commands: RC schema check; integrated patch count check; final validation command set; evidence completeness check.

Evidence files: RC receipt, build log, validation log, evidence summary link.

Failure handling: Fail closed if RC validation fails or if integration evidence is incomplete.

Acceptance criteria: The RC is inspectable, reproducible, and linked from evidence.

## Milestone 10: Console / Taskstream Visibility

Purpose: Show concise operator state without exposing secrets or huge transcripts.

Owned artifacts: Console API payloads, `ui_state.json`, Taskstream/agent-work summary receipts.

Likely commands/subcommands: `cento parallel-delivery status --run RUN_ID`, `cento parallel-delivery evidence --run RUN_ID`, current Console `/patch-swarm` API, `cento agent-work` summaries, MCP status calls.

Inputs: Run state, task counts, leases, validation matrix, integration queue, release candidate status, evidence summary.

Outputs: Visible fields: run ID, request title, state, counts, leased path summary, validation summary, integration queue status, RC status, evidence path, next action.

Validation commands: Console API fixture checks; no raw secret values; no direct Taskstream/Redmine DB writes; status matches run artifacts.

Evidence files: `ui_state.json`, status receipt, Taskstream sync preview or agent-work summary.

Failure handling: Show degraded/unavailable summaries with artifact paths instead of mutating state directly.

Acceptance criteria: Operators can understand progress and next action without opening raw transcripts.

## Milestone 11: E2E Demo Harness

Purpose: Provide a bounded local demo that proves the full contract with 2-3 tasks.

Owned artifacts: Example request, fixture patch bundles, demo run directory, final evidence summary.

Likely commands/subcommands: `cento parallel-delivery demo --request-file examples/parallel-delivery/simple-request.md --max-tasks 3`, current `cento parallel-delivery patch-swarm e2e --candidate-target 30 --max-parallel-agents 3 --fixture --json`, `python3 scripts/patch_swarm_product_e2e.py`.

Inputs: Simple request fixture, safe patch fixture, unsafe patch fixture, validation commands.

Outputs: Run directory, ProReq packet, 2-3 tasks, non-overlapping leases, prompts, collected bundles, validation, rejected unsafe patch, integrated safe patch, RC, evidence summary, final status.

Validation commands: One-command e2e; grep final evidence; JSON schema checks; no selected repo mutation check; docs smoke where relevant.

Evidence files: Demo summary, commands log, artifacts manifest, RC, validation matrix, status receipt.

Failure handling: Demo fails if it cannot prove both safe integration and unsafe rejection with evidence.

Acceptance criteria: A local operator can run the demo repeatedly and get deterministic evidence without live provider spend.
