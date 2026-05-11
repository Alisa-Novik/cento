# AI Self-Improvement Append-Only Log

This is the durable human-facing Docs log for major Cento self-improvement work. It is meant to keep future agents from going in circles by making prior decisions, evidence, gaps, and next steps easy to check before changing Cento routing, autonomy, pipelines, skills, validation, observability, or operator workflow.

The scheduled planning loop in `docs/ai-self-improvement-nightly.md` can produce future recommendations. This log records the actual major self-improvement steps that were planned, implemented, validated, or deliberately deferred.

## Append-Only Rules

- Append every new record at the bottom of this file.
- Do not rewrite, reorder, or delete previous records.
- If a prior record needs correction, append a new correction record with `corrects_record_id`.
- If sensitive material was accidentally written, redact the minimum required text and append a redaction record explaining what category was removed.
- Before starting a major self-improvement step, read the latest relevant records and state what is different about the current step.

## Record Schema

Use this Markdown shape for each record:

```markdown
### YYYY-MM-DDTHH:MM:SSZ - Short Title

- `record_id`: kebab-case-date-title
- `actor`: codex | human | automated-loop | mixed
- `scope`: skills | docs | pipeline | routing | observability | validation | agent-work | storage | other
- `status`: planned | implemented | validated | deferred | failed | superseded
- `artifacts_changed`: paths or run directories
- `evidence`: commands, run ids, receipts, tests, logs, screenshots, or links
- `checked_prior_records`: record ids consulted before the change
- `corrects_record_id`: optional record id if this is a correction

#### Trigger

The operator request, incident, scheduled loop, or observation that caused the step.

#### What Changed

Concrete behavior, code, docs, routing, skill, or process changes.

#### What Worked

Evidence-backed observations about successful decisions, tools, or implementation paths.

#### What Did Not Work

Friction, failed assumptions, confusing loops, missing evidence, or validation gaps.

#### Next Steps

Specific follow-up work that should happen after this record.

#### Suggestions

Optional product, workflow, or automation ideas that are not yet committed work.

#### Tags

Comma-separated tags such as `cento-native`, `self-improvement`, `routing`, `factory`, `workset`.
```

## Records

### 2026-05-05T21:30:40Z - Self-Improvement Log Started After Parallel Train Promotion E2E

- `record_id`: 2026-05-05-self-improvement-log-started-parallel-train-promotion-e2e
- `actor`: codex
- `scope`: skills, docs, pipeline, routing, validation
- `status`: implemented
- `artifacts_changed`: `.codex/skills/cento-native/SKILL.md`, `skills/codex/cento-native/SKILL.md`, `docs/ai-self-improvement-log.md`, `docs/nav.html`
- `evidence`: `train-e2e-promotion-20260505T2135Z`, `workspace/runs/parallel-delivery/train/train-e2e-promotion-20260505T2135Z`, `workspace/runs/factory/parallel-train-train-e2e-promotion-20260505T2135Z`, `python3 -m pytest tests/test_parallel_integration_train.py -q`, `python3 -m pytest tests/test_parallel_integration_train.py tests/test_dev_pipeline_delivery.py tests/test_self_improvement_loop.py -q`, `make check`
- `checked_prior_records`: none, this is the first record
- `corrects_record_id`: none

#### Trigger

The operator asked Cento Native to maintain and check against an append-only self-improvement log, document every major self-improvement step, create the Markdown schema, and start the log with a first record.

The immediate context was a completed parallel-integration-train self-improvement step. The operator had correctly noticed that the process felt circular: Workset execution already existed, but the missing end-to-end piece was promotion from a completed parallel Workset train into the Factory Safe Integrator path.

#### What Changed

- Added a `Self-Improvement Log` rule to the active installed `cento-native` skill.
- Added the same rule to the repo copy of the `cento-native` skill without overwriting existing differences between the two copies.
- Created this human-facing Docs log with append-only rules, a reusable Markdown schema, and the first record.
- Linked the log from `docs/nav.html` so it is discoverable alongside the other human Docs.
- Documented the already-completed parallel train bridge as the first self-improvement record because it is the motivating example for avoiding repeated loops.

The parallel train work completed immediately before this log added:

- `cento parallel-delivery train run --workset-execute` for real Workset execution through the train.
- `cento parallel-delivery train promote` for handing accepted Workset patch bundles to Factory/Safe Integrator.
- `cento parallel-delivery train e2e` for one-command plan, execute, validate, and promote flow.
- Docs, tests, tool registry, completion, and generated tool index updates for the new command surface.

#### What Worked

- The existing Workset executor was already a useful parallel work substrate. The right fix was to bridge it into promotion rather than invent another worker system.
- Factory/Safe Integrator remained the integration authority. Promotion reuses that path instead of creating a second apply gate.
- The real fixture e2e run produced a `ready_for_apply` promotion decision and a valid Factory handoff in dry-run mode.
- Focused tests plus `make check` passed after the parallel train work.
- The new log gives future agents a stable place to check what was already done before planning another self-improvement pass.

#### What Did Not Work

- Before this record, the distinction between "Workset execution exists" and "promotion bridge is missing" was only implicit in the conversation and code state.
- That missing durable memory made the work feel like it was circling back to the same plan instead of naming the exact remaining gap.
- Promotion initially treated task-level Workset failures too strictly. The implementation had to be adjusted so task-level failures can be handed to Factory for classification while accepted patch bundles still promote.
- The repo already had many unrelated dirty files. The skill and Docs updates had to stay narrowly scoped and avoid normalizing unrelated generated or in-progress changes.

#### Next Steps

- Future major self-improvement work should start by reading the latest relevant records in this file.
- Every major step should append a new record before final reporting.
- Add a lightweight validator later that can check whether a self-improvement change touched routing, skills, autonomy, or pipeline code without a corresponding log record.
- Consider teaching the nightly self-improvement loop to include the latest records in its planning context and to propose the next log entry as part of its evidence handoff.
- Periodically review whether the active installed skill and repo skill copy have intentional differences, then decide whether to add a sync/check command instead of relying on manual awareness.

#### Suggestions

- Keep this log human-readable and short enough to scan, but evidence-rich enough for agents to make decisions from it.
- Prefer concrete run ids, receipt paths, and command outputs over broad summaries.
- When a user says a pipeline feels circular, add a record that separates "already done", "missing bridge", "validated now", and "next unresolved gap".
- Add tags consistently so future tools can index this Markdown without requiring a new database.

#### Tags

`cento-native`, `self-improvement`, `append-only-log`, `parallel-delivery`, `workset`, `factory`, `safe-integrator`, `docs`, `routing`, `validation`

### 2026-05-05T22:08:25Z - Tool Foundry MVP Implemented

- `record_id`: 2026-05-05-tool-foundry-mvp-implemented
- `actor`: codex
- `scope`: pipeline, routing, validation, docs, storage, agent-work
- `status`: implemented
- `artifacts_changed`: `scripts/tool_foundry.py`, `tests/test_tool_foundry.py`, `data/tools.json`, `scripts/completion/_cento`, `Makefile`, `docs/tool-foundry.md`, `docs/nav.html`, `docs/tool-index.md`, `docs/platform-support.md`, `.codex/skills/cento-native/SKILL.md`, `skills/codex/cento-native/SKILL.md`, `docs/ai-self-improvement-log.md`
- `evidence`: `./scripts/cento.sh foundry e2e --fixture client-intake-hub --dry-run --run-id foundry-cli-e2e-20260505 --max-parallel 6 --json`, `python3 -m pytest tests/test_tool_foundry.py -q`, `python3 -m pytest tests/test_tool_foundry.py tests/test_parallel_integration_train.py tests/test_object_storage.py -q`, `make check`, `./scripts/cento.sh docs foundry`, `./scripts/cento.sh tools`
- `checked_prior_records`: `2026-05-05-self-improvement-log-started-parallel-train-promotion-e2e`
- `corrects_record_id`: none

#### Trigger

The operator accepted the Tool Foundry plan and asked to implement it. The strategic goal was to make Cento more scalable, cheaper, and ready to create tools for a career consulting business, starting with a reusable pipeline rather than one bespoke CRM feature.

#### What Changed

- Added the registered `cento foundry` tool.
- Implemented `create`, `plan`, `execute`, `promote`, `status`, `validate`, and `e2e` commands.
- Made the first fixture tool `client-intake-hub` for career consulting.
- Routed Foundry through existing Factory planning, Workset manifests, parallel-delivery train e2e, train-to-Factory promotion, storage policy, cost receipts, and demo evidence.
- Added live `api-openai` budget gates requiring both `--budget-usd` and `--max-budget-usd`.
- Added a v1 hard-cap guard rejecting live caps above `$20`.
- Added human Docs, registry entries, zsh completion, platform/tool indexes, and Cento Native skill routing hints.

#### What Worked

- The existing parallel train promotion bridge was enough to make Foundry e2e real instead of simulated.
- Dry-run Foundry e2e now produces a passing run with zero AI cost and concrete receipts under `workspace/runs/foundry/<run-id>/`.
- `cento docs foundry` and `cento tools` now expose the command through normal Cento discovery.
- The budget guard rejected uncapped live execution before creating a run.
- The adjacent test slice passed across Foundry, parallel train promotion, and Object Storage.

#### What Did Not Work

- The first Workset design used run-scoped generated files as fixture worker write paths. That passed Workset shape validation but failed inside isolated worker worktrees because those generated files are not tracked in git.
- The fix was to keep generated product artifacts run-scoped while using existing tracked docs/standards files as fixture worker write targets for the dry-run proof path.
- Factory validation returns `blocked` before live patch collection, which is expected for a planning handoff. Foundry now records that as acceptable planning evidence and relies on Workset/train execution plus Foundry validation for the final e2e gate.

#### Next Steps

- Extend Foundry from fixture-only Client Intake Hub to an actual CRM-backed generated tool surface.
- Add a Foundry dashboard view showing runs, receipts, costs, validation, and generated tool previews.
- Add optional OCI artifact upload for non-sensitive generated evidence after explicit operator approval.
- Add a self-improvement validator that checks major pipeline/routing changes include a new log record.
- Teach Foundry to generate Worksets that target newly created files through API/artifact materialization instead of only tracked fixture targets.

#### Suggestions

- Keep `cento foundry e2e --dry-run` as the release gate for every future Foundry improvement.
- Treat live Foundry execution as an acceleration lane, not the baseline path.
- Use Client Intake Hub as the business-facing seed, then add Deliverable Generator and Foundry Dashboard as the next two fixtures.
- Add a small cost dashboard before raising any live cap beyond `$20`.

#### Tags

`cento-native`, `self-improvement`, `tool-foundry`, `career-consulting`, `client-intake-hub`, `factory`, `workset`, `parallel-delivery`, `cost-guard`, `storage-policy`, `docs`, `validation`

### 2026-05-05T23:15:31Z - Tool Foundry Real-File Materialization V2

- `record_id`: 2026-05-05-tool-foundry-real-file-materialization-v2
- `actor`: codex
- `scope`: pipeline, routing, validation, docs, crm, ui, self-improvement
- `status`: implemented
- `artifacts_changed`: `scripts/tool_foundry.py`, `tests/test_tool_foundry.py`, `scripts/crm_module.py`, `templates/crm/app.js`, `templates/crm/styles.css`, `templates/foundry/client-intake-hub/*`, `docs/client-intake-hub.md`, `docs/tool-foundry.md`, `data/tools.json`, `scripts/completion/_cento`, `docs/tool-index.md`, `docs/platform-support.md`, `docs/nav.html`, `docs/ai-self-improvement-log.md`
- `evidence`: `./scripts/cento.sh foundry e2e --fixture client-intake-hub --dry-run --real-files --target-root templates/foundry/client-intake-hub --run-id foundry-real-files-e2e-json-20260505 --max-parallel 6 --json`, `./scripts/cento.sh foundry materialize foundry-real-files-e2e-json-20260505 --target-root templates/foundry/client-intake-hub --apply --json`, `./scripts/cento.sh foundry validate foundry-real-files-e2e-json-20260505 --json`, `python3 -m pytest tests/test_tool_foundry.py -q`, `python3 -m pytest tests/test_tool_foundry.py tests/test_parallel_integration_train.py tests/test_object_storage.py -q`, `make check`, `curl http://127.0.0.1:47865/api/foundry/tools`, `workspace/tmp/crm-foundry-studio.png`, `workspace/tmp/client-intake-hub-preview.png`
- `checked_prior_records`: `2026-05-05-self-improvement-log-started-parallel-train-promotion-e2e`, `2026-05-05-tool-foundry-mvp-implemented`
- `corrects_record_id`: none

#### Trigger

The operator accepted the plan to move Foundry beyond demo fixture edits and asked to implement real-file materialization for the Client Intake Hub.

The prior Tool Foundry MVP proved Factory, Workset, train promotion, cost receipts, storage policy, and validation, but it still used existing docs/standards fixture files as worker write targets because isolated worktrees could not see run-scoped generated files.

#### What Changed

- Added `cento foundry materialize RUN_ID` with `--dry-run`, `--apply`, and `--target-root`.
- Added `cento foundry e2e --real-files` so real-file planning runs after the fixture train validates.
- Added real-file artifacts: `real_file_manifest.json`, `materialization_plan.json`, and `materialization_receipt.json`.
- Materialized the first repo-ready Client Intake Hub bundle under `templates/foundry/client-intake-hub/`.
- Added `docs/client-intake-hub.md` as the human-facing Docs entry for the materialized MVP.
- Wired `cento crm serve` to expose Foundry metadata at `/api/foundry/tools` and serve the preview under `/foundry/client-intake-hub/client-intake-hub.html`.
- Added a CRM Studio card for materialized Foundry tools.
- Updated command registry, completion, generated tool index/platform docs, and docs nav.

#### What Worked

- The dry-run e2e stayed deterministic and zero-cost while producing a real-file materialization plan.
- Applying materialization wrote only the approved target root and the approved human Docs page.
- Re-running materialization after apply is idempotent: all files resolve to `skip_identical`.
- The CRM API reports the Client Intake Hub as `materialized`.
- Browser screenshots confirmed both the CRM Studio card and the standalone preview render visibly.
- Focused tests, adjacent pipeline/storage tests, and `make check` passed.

#### What Did Not Work

- The first test pass exposed that copied run-scoped command and validation artifacts still contained run-specific ids and paths.
- That would have made every later run look like an overwrite conflict.
- The fix was to keep run-scoped evidence under `workspace/runs/foundry/...` while making the repo-ready command map and validation plan stable.
- A nested materialize call initially printed a human status line before outer e2e JSON. The command now supports quiet nested execution.

#### Next Steps

- Add a Foundry dashboard that lists runs, costs, materialization receipts, validation state, and preview links.
- Add a safe CRM action that can launch a new Client Intake Hub run from the Studio card.
- Run a tiny live `api-openai` rehearsal with a `$1-$2` cap after the deterministic path stays stable.
- Add optional OCI upload for non-sensitive generated evidence only after explicit operator approval.
- Add a validator that flags major pipeline/routing changes without a new self-improvement log record.

#### Suggestions

- Keep real-file materialization as the bridge between generated run artifacts and durable product files.
- Avoid putting run ids into repo-ready templates unless the file is explicitly a receipt.
- Treat CRM discovery as metadata-first until the generated tools need deeper state integration.
- Make the next business tool use this same dry-run, materialize, preview, validate contract before adding live model spend.

#### Tags

`cento-native`, `self-improvement`, `tool-foundry`, `real-files`, `materialization`, `client-intake-hub`, `crm`, `docs`, `workset`, `factory`, `validation`, `ui`

### 2026-05-06T00:15:41Z - Patch Swarm MVP Implemented

- `record_id`: 2026-05-06-patch-swarm-mvp-implemented
- `actor`: codex
- `scope`: pipeline, routing, validation, docs, ui, observability, cost, autopilot
- `status`: implemented
- `artifacts_changed`: `scripts/parallel_delivery.py`, `.cento/runtimes.yaml`, `scripts/agent_work_app.py`, `scripts/walk_autopilot.py`, `tests/test_patch_swarm.py`, `data/tools.json`, `scripts/completion/_cento`, `docs/patch-swarm.md`, `docs/parallel-ai-delivery-roadmap.md`, `docs/agent-work-runtimes.md`, `docs/tool-index.md`, `docs/platform-support.md`, `docs/nav.html`, `docs/ai-self-improvement-log.md`
- `evidence`: `./scripts/cento.sh parallel-delivery patch-swarm e2e --run-id patch-swarm-e2e-20260505 --candidate-target 100 --max-parallel-agents 5 --providers codex-exec,claude-code,api-openai --fixture --json`, `./scripts/cento.sh parallel-delivery patch-swarm validate patch-swarm-e2e-20260505 --json`, `./scripts/cento.sh walk-autopilot patch-swarm run --run-id patch-swarm-autopilot-20260505 --candidate-target 100 --max-parallel-agents 5 --json`, `./scripts/cento.sh walk-autopilot patch-swarm status --json`, `./scripts/cento.sh runtime check claude-code-fast --json`, `python3 -m py_compile scripts/parallel_delivery.py scripts/agent_work_app.py scripts/walk_autopilot.py`, `python3 -m pytest tests/test_patch_swarm.py -q`, `python3 -m pytest tests/test_patch_swarm.py tests/test_parallel_integration_train.py tests/test_dev_pipeline_delivery.py tests/test_walk_autopilot.py -q`, `python3 -m json.tool data/tools.json`, `./scripts/cento.sh docs parallel-delivery`, `make check`
- `checked_prior_records`: `2026-05-05-self-improvement-log-started-parallel-train-promotion-e2e`, `2026-05-05-tool-foundry-mvp-implemented`, `2026-05-05-tool-foundry-real-file-materialization-v2`
- `corrects_record_id`: none

#### Trigger

The operator accepted the Patch Swarm plan and asked to implement it end to end. The requested direction was aggressive AI cost effectiveness and massively parallel AI development: five or more agents, one hundred or more patch proposals, provider compatibility for `codex exec`, Claude Code, and OpenAI API patch proposals, integration with the existing Cento parallel execution UI, ten ProReq pipeline executions, and one dedicated integration execution.

#### What Changed

- Added `cento parallel-delivery patch-swarm` with `plan`, `execute`, `integrate`, `validate`, `status`, and `e2e`.
- Added ten ProReq execution lanes: request decomposition, Codex Exec adapter, Claude Code adapter, OpenAI patch proposal adapter, candidate normalization, dedupe clustering, deterministic validator fanout, cost/latency ledger, Dev Pipeline Studio UI, and autopilot coordinator hooks.
- Added one dedicated serialized integrator execution that selects one validated candidate per ProReq lane and writes a Safe Integrator handoff instead of mutating the main worktree.
- Added provider-normalized `candidate_patch.v1` receipts and fixture patch files for `codex-exec`, `claude-code`, and `api-openai`.
- Added Patch Swarm run artifacts: manifest, ProReq execution manifest, candidate index, dedupe clusters, ranking, cost ledger, patch swarm receipt, integration receipts, validation summary, UI state, decision report, and Safe Integrator handoff.
- Added the `claude-code-fast` runtime profile in `.cento/runtimes.yaml` for future Claude Code command execution.
- Added a Patch Swarm Dev Pipeline Studio blueprint and execution bridge so the existing pipeline UI can seed, run, finish, and display Patch Swarm state.
- Added Walk Autopilot hooks: optional loop stage flags plus `cento walk-autopilot patch-swarm run/status` for one-shot autopilot-compatible coordination.
- Updated command registry, zsh completion, human Docs, tool index, platform support docs, and runtime docs.

#### What Worked

- The deterministic Patch Swarm e2e produced `100` candidate patches, `10` ProReq executions, `10` selected winners, all three requested providers, one dedicated integrator, passing validation, and an estimated fixture cost ledger of `$0.412500`.
- The main proof run lives at `workspace/runs/parallel-delivery/patch-swarm/patch-swarm-e2e-20260505/`.
- The autopilot wrapper produced a separate passing run at `workspace/runs/parallel-delivery/patch-swarm/patch-swarm-autopilot-20260505/` and summary artifacts under `workspace/runs/walk-autopilot/patch-swarm/patch-swarm-autopilot-20260505/`.
- `ui_state.json` mirrors to `workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/patch-swarm/latest_ui_state.json`, giving the existing UI one stable source for candidate counts, provider mix, costs, validation, winners, and integration state.
- The Claude Code runtime profile validated with the installed `claude` executable.
- Focused Patch Swarm tests, adjacent parallel train/Dev Pipeline/Walk Autopilot tests, JSON registry validation, docs lookup, and `make check` passed.

#### What Did Not Work

- Live provider dispatch is intentionally not enabled by default. The MVP normalizes provider contracts and proves the high-parallel artifact flow through fixture-safe candidate generation.
- The Safe Integrator handoff is artifact-only. It does not apply selected patches to the repo yet.
- The Dev Pipeline Studio integration exposes Patch Swarm state through backend run payloads and mirrored UI state, but richer frontend views such as a candidate matrix, provider comparison table, and dedupe cluster explorer remain future work.
- Cost numbers are deterministic estimates for provider comparison and budget gating rehearsals, not invoices from live Codex/Claude/OpenAI execution.

#### Next Steps

- Add explicit live candidate dispatch gates for `codex exec`, Claude Code, and OpenAI API providers with per-provider budget caps, duplicate saturation stopping, and hard fail-closed cost ceilings.
- Teach the dedicated integrator to materialize selected candidates into Safe Integrator patch bundles and dry-run apply plans.
- Add candidate applyability checks: patch parse, target ownership, protected path rejection, dependency lockfile policy, and test impact hints.
- Add a Dev Pipeline Studio candidate matrix showing provider, lane, score, estimated cost, duplicate cluster, validation status, and selected winner.
- Run a tiny live trial with a strict dollar cap after the fixture path stays stable across repeated autopilot loops.

#### Suggestions

- Track cost per accepted patch, duplicate saturation by provider, validator pass rate, and integrator rejection reason as first-class metrics before scaling beyond `100` proposals.
- Use Patch Swarm as the high-volume proposal engine and keep Factory/Safe Integrator as the only mutation path.
- Prefer many cheap proposal candidates followed by deterministic pruning over expensive long-context builders for every lane.
- Add provider A/B reporting before deciding whether Codex Exec, Claude Code, or OpenAI API should own each lane by default.

#### Tags

`cento-native`, `self-improvement`, `patch-swarm`, `parallel-delivery`, `proreq`, `workset`, `dev-pipeline-studio`, `walk-autopilot`, `cost-effectiveness`, `codex-exec`, `claude-code`, `openai-api`, `safe-integrator`, `docs`, `validation`

### 2026-05-06T00:27:29Z - Factory Scale Final Test Implemented

- `record_id`: 2026-05-06-factory-scale-final-test-implemented
- `actor`: codex
- `scope`: factory, walk-autopilot, proreq-light, patch-swarm, cron, validation, docs, self-improvement
- `status`: implemented
- `artifacts_changed`: `scripts/walk_autopilot.py`, `scripts/dev_pipeline_hard_proreq.py`, `tests/test_walk_autopilot.py`, `docs/factory-1000-patch-swarm-roadmap.md`, `data/tools.json`, `scripts/completion/_cento`, `docs/nav.html`, `docs/tool-index.md`, `docs/platform-support.md`, `docs/ai-self-improvement-log.md`
- `evidence`: `python3 -m py_compile scripts/walk_autopilot.py scripts/dev_pipeline_hard_proreq.py scripts/proreq_light.py scripts/parallel_delivery.py`, `python3 -m pytest tests/test_walk_autopilot.py -q`, `python3 -m pytest tests/test_walk_autopilot.py tests/test_patch_swarm.py tests/test_dev_pipeline_delivery.py -q`, `python3 -m json.tool data/tools.json`, `python3 -m json.tool data/cento-cli.json`, `./scripts/cento.sh docs walk-autopilot`, `./scripts/cento.sh walk-autopilot factory-scale start --run-id factory-scale-validation-20260506T002606Z --duration-hours 0.1 --proreq-executions 2 --crontab-file /tmp/cento-factory-scale-crontab-factory-scale-validation-20260506T002606Z.txt --json`, `./scripts/cento.sh walk-autopilot factory-scale tick --run-id factory-scale-validation-20260506T002606Z --json`, `./scripts/cento.sh walk-autopilot factory-scale status --run-id factory-scale-validation-20260506T002606Z --json`, `./scripts/cento.sh walk-autopilot factory-scale start --run-id factory-scale-patch-validation-20260506T002642Z --duration-hours 0.1 --proreq-executions 3 --min-proreq-calls 30 --patch-swarm --crontab-file /tmp/cento-factory-scale-crontab-factory-scale-patch-validation-20260506T002642Z.txt --json`, `./scripts/cento.sh walk-autopilot factory-scale tick --run-id factory-scale-patch-validation-20260506T002642Z --json` x3, `./scripts/cento.sh parallel-delivery patch-swarm e2e --candidate-target 100 --max-parallel-agents 5 --fixture --json`, `make check`
- `checked_prior_records`: `2026-05-06-patch-swarm-mvp-implemented`, `2026-05-05-tool-foundry-real-file-materialization-v2`, `2026-05-05-tool-foundry-mvp-implemented`
- `corrects_record_id`: none

#### Trigger

The operator provided the six-hour Factory scale final test plan and asked for implementation in a fresh context. The goal was to connect Walk Autopilot, ProReq-light, Patch Swarm, cron scheduling, append-only ledgers, and Factory/Safe Integrator safety boundaries into one repeatable final test.

#### What Changed

- Added `cento walk-autopilot factory-scale` with `start`, `tick`, `status`, `install-cron`, and `uninstall-cron`.
- Added the managed cron block marker `# BEGIN CENTO FACTORY SCALE FINAL TEST` with a 12-minute schedule, `flock`, and a run-deadline check.
- Added log-derived run artifacts under `workspace/runs/walk-autopilot/factory-scale-<timestamp>/`: roadmap, config, execution manifest, events, thoughts, ProReq-light call ledger, metrics, spend ledger, handoff, cron docs, isolated ProReq-light roots, and Patch Swarm milestone folders.
- Added a 30-execution manifest that derives ten Patch Swarm milestone groups and expects 300 ProReq-light command-call records plus 1,000 Patch Swarm candidate receipts.
- Added one-execution-per-tick selection. Each execution appends the ten required ProReq-light command calls: intake, context, screenshot, pro-request, codex-plan, backend-work, integration-plan, validation-plan, deliver `--no-full-check --json`, and evidence.
- Added a ProReq-light pipeline-root environment override through `CENTO_DEV_PIPELINE_STUDIO_ROOT` so batch execution can avoid mutating Dev Pipeline Studio's active `execution_run.json`.
- Added roadmap docs, registry entries, completion, tool index/platform docs, and a Docs nav link.

#### What Worked

- Focused tests cover cron install/uninstall idempotence, one pending ProReq-light execution per tick, append-only call-ledger behavior, the 100-call minimum after ten simulated executions, 30-to-10 Patch Swarm grouping, status derived from call logs, and isolated ProReq-light roots.
- The short start/tick/status validation run used a temporary crontab and produced one completed ProReq-light execution with ten call records.
- The 3-tick factory-scale validation run completed one Patch Swarm milestone: 3 ProReq-light executions, 30 calls, 1 Patch Swarm run, and 100 candidate receipts.
- Patch Swarm fixture e2e still produced 100 candidates, 10 selected winners, passing validation, and a Safe Integrator handoff.
- `make check` passed after the command and docs updates.

#### What Did Not Work

- The full six-hour, 30-tick cron run was not executed during implementation. Validation used temporary crontab files and short runs to avoid mutating the real crontab or waiting six hours.
- Default factory-scale ProReq-light mode is ledger-only and API-safe. Running the actual ProReq-light commands is available behind `--execute-proreq`, but that heavier local Codex path was not exercised in this implementation pass.
- Patch Swarm remains fixture/candidate-receipt first. Live Codex/Claude/OpenAI provider dispatch and Safe Integrator apply are still later milestones behind explicit budget and validation gates.

#### Next Steps

- Run the full six-hour factory-scale schedule when the operator wants the final soak, then inspect `handoff.md`, `metrics.jsonl`, and milestone handoffs.
- Add optional status mirroring for factory-scale runs into Dev Pipeline Studio UI state.
- Add a tiny `--execute-proreq` rehearsal with one execution after confirming local Codex runtime availability and acceptable wall-clock time.
- Teach Factory/Safe Integrator to consume selected Patch Swarm candidate receipts as dry-run apply plans.

#### Suggestions

- Keep factory-scale status derived from JSONL ledgers; do not add mutable counters.
- Use temporary crontab files for tests and real crontab only for operator-started soak runs.
- Promote live provider fanout only after cost/latency admission and duplicate saturation metrics are visible.
- Treat the 1,000-candidate target as a receipt-generation and pruning proof until Safe Integrator apply plans are deterministic.

#### Tags

`cento-native`, `self-improvement`, `factory-scale`, `walk-autopilot`, `proreq-light`, `patch-swarm`, `cron`, `append-only`, `safe-integrator`, `cost-effectiveness`, `validation`, `docs`

### 2026-05-06T05:30:00Z - Factory Scale No-Overlap Advance Implemented

- `record_id`: 2026-05-06-factory-scale-no-overlap-advance
- `actor`: codex
- `scope`: walk-autopilot, factory-scale, patch-swarm, safe-integrator, spend-guard, docs, validation
- `status`: implemented
- `artifacts_changed`: `scripts/walk_autopilot.py`, `tests/test_walk_autopilot.py`, `data/tools.json`, `scripts/completion/_cento`, `docs/tool-index.md`, `docs/ai-self-improvement-log.md`
- `evidence`: `python3 -m py_compile scripts/walk_autopilot.py`, `python3 -m pytest tests/test_walk_autopilot.py -q`, `python3 -m pytest tests/test_walk_autopilot.py tests/test_patch_swarm.py tests/test_dev_pipeline_delivery.py -q`, `python3 -m json.tool data/tools.json`, `python3 -m json.tool data/cento-cli.json`, `./scripts/cento.sh docs walk-autopilot`, `./scripts/cento.sh walk-autopilot factory-scale preflight --run-id factory-scale-sleep-20260506T051332Z --json`, `./scripts/cento.sh walk-autopilot factory-scale advance --run-id factory-scale-sleep-20260506T051332Z --promotion-limit 25 --json`, `./scripts/cento.sh parallel-delivery patch-swarm e2e --candidate-target 100 --max-parallel-agents 5 --fixture --json`, `make check`
- `checked_prior_records`: `2026-05-06-factory-scale-final-test-implemented`, `2026-05-06-patch-swarm-mvp-implemented`
- `corrects_record_id`: none

#### Trigger

The operator confirmed that budget was available but asked not to overlap the existing autopilot and not to waste spend through accidental tight ChatGPT Pro/API loops. The completed `factory-scale-sleep-20260506T051332Z` run needed to become actionable Factory input rather than another manifest.

#### What Changed

- Added `cento walk-autopilot factory-scale preflight` to detect existing factory-scale cron, run status, and active factory-scale, ProReq-light, or Patch Swarm processes before starting or advancing.
- Added `cento walk-autopilot factory-scale advance` to reuse a completed factory-scale run, index Patch Swarm candidate receipts, write a candidate matrix, generate Safe Integrator promotion plans, and produce a morning report.
- Added a live OpenAI/API guard for the advance lane: dashboard-total hard-cap gating, hourly call limits, minimum spacing, global lock path, and fail-closed behavior when live API is not requested or usage cannot be trusted.
- Changed latest factory-scale run selection from lexical ordering to mtime ordering so older validation runs do not mask the real newest run.
- Stopped completed factory-scale ticks from appending repeated `run_complete` metrics/events after the completion event already exists.

#### What Worked

- Preflight against `factory-scale-sleep-20260506T051332Z` returned `reuse_completed_run`, no cron marker, and no active overlap.
- Advance wrote `workspace/runs/walk-autopilot/factory-scale-sleep-20260506T051332Z/advance/` with `candidate-matrix.json`, `safe-integrator-promotion-plan.json`, `live-api-guard.json`, `no-overlap-preflight.json`, and `morning-report.md`.
- The candidate matrix indexed `1,000` validated candidate receipts, `100` selected candidates, provider counts `codex-exec=340`, `claude-code=330`, `api-openai=330`, and no validation errors.
- The promotion plan selected `25` dry-run Safe Integrator candidates and kept `apply=false`.
- Live OpenAI/API stayed disabled because it was not requested; the guard recorded fail-closed status rather than guessing usage.

#### What Did Not Work

- No direct OpenAI usage API polling was added in this pass. The implemented guard relies on the existing dashboard-total snapshot route plus local append-only spend/rate ledgers.
- The promotion plan is still dry-run and artifact-only. It does not apply candidate patches or mutate the main worktree.
- The candidate matrix is a derived JSON artifact, not yet a full Dev Pipeline Studio interactive view.

#### Next Steps

- Teach Factory/Safe Integrator to consume `safe-integrator-promotion-plan.json` and create isolated apply/validation worktrees for the top candidates.
- Add a Dev Pipeline Studio candidate matrix view backed by the new `candidate-matrix.json`.
- Add optional official OpenAI usage polling only after verifying the current official API surface and keeping fail-closed behavior.
- Run one tiny live API review only after a dashboard-total baseline is supplied and the hard cap/rate limiter are active.

#### Suggestions

- Keep completed-run advance as the default path after large candidate-generation runs; do not rerun factory-scale unless the old run is stale or incomplete.
- Prefer Codex/Claude/local execution for broad implementation work and reserve live OpenAI API for compact, high-leverage structured review.
- Keep promotion limits small until deterministic applyability validation is reliable.

#### Tags

`cento-native`, `self-improvement`, `factory-scale`, `walk-autopilot`, `patch-swarm`, `safe-integrator`, `no-overlap`, `spend-guard`, `cost-effectiveness`, `validation`

### 2026-05-06T14:11:00Z - Factory Scale Day Autopilot Started

#### Trigger

The operator asked for a full day of more aggressive autopilot after the overnight Factory scale final test completed. The target was to scale from 300 logged ProReq-light calls to 1,000+ today, with a primary goal around 3,000 calls and a hard ceiling of 10,000 calls, while avoiding overlap and accidental metered OpenAI/API loops.

#### What Changed

- Added `cento walk-autopilot factory-scale start-day` for day-scale runs that derive execution count from a target ProReq-light command-call count.
- Added `--batch-size` support to `factory-scale tick`, so cron can advance multiple ProReq-light executions per guarded tick.
- Extended factory-scale config, cron, status, and handoff artifacts with run mode, batch size, target calls, max calls, remaining calls, configurable schedule, and configurable lock name.
- Kept day mode API-safe by default: ProReq-light remains ledger/local execution, Patch Swarm remains fixture candidate-receipt generation, and live OpenAI/API remains disabled unless explicit budget gates are passed.
- Updated tests, tool registry examples, docs output, and shell completions for day-scale operation.

#### What Worked

- Validation passed:
  - `python3 -m py_compile scripts/walk_autopilot.py`
  - `python3 -m pytest tests/test_walk_autopilot.py -q`
  - `python3 -m pytest tests/test_walk_autopilot.py tests/test_patch_swarm.py tests/test_dev_pipeline_delivery.py -q`
  - `python3 -m json.tool data/tools.json`
  - `./scripts/cento.sh docs walk-autopilot`
  - `./scripts/cento.sh parallel-delivery patch-swarm e2e --candidate-target 100 --max-parallel-agents 5 --fixture --json`
  - `make check`
- No-overlap preflight returned `safe_to_start`; the prior overnight run was completed and no factory-scale cron or active process was present.
- Started `factory-scale-day-20260506` with:
  - `300` ProReq-light executions.
  - `3,000` expected ProReq-light command-call records.
  - `10,000` max allowed ProReq-light command-call records.
  - `100` Patch Swarm fixture milestones.
  - `10,000` expected candidate patch receipts.
  - `5` executions per tick on a `*/10 * * * *` cron cadence.
- Seeded the first batch immediately: `5` executions complete, `50` ProReq-light call records, `1` Patch Swarm milestone, and `100` candidate patch receipts.

#### What Did Not Work

- Day-scale still generates fixture candidate receipts and handoffs first; it does not yet apply candidate patches through Safe Integrator.
- Direct OpenAI usage API polling remains deferred. The current guard keeps metered API share at `0` and fails closed unless live API is explicitly enabled with budget evidence.

#### Next Steps

- Let the installed day-scale cron continue advancing `factory-scale-day-20260506` without overlapping ticks.
- Consume the generated Safe Integrator handoffs from the best milestones in isolated worktrees once applyability validation is ready.
- Add usage polling only behind a fail-closed budget gate and only after checking the official OpenAI usage API surface.

#### Tags

`cento-native`, `self-improvement`, `factory-scale`, `walk-autopilot`, `day-scale`, `patch-swarm`, `no-overlap`, `spend-guard`, `cost-effectiveness`, `validation`

### 2026-05-06T14:31:00Z - Factory Scale Day Lane Accelerated With Spark And Claude

#### Trigger

The operator asked to continue scaling and explicitly asked to use Spark and Claude Code in addition to the active Factory scale lane.

#### What Changed

- Tuned `factory-scale-day-20260506` from `5` executions every `10` minutes to `10` executions every `5` minutes, preserving the same `3,000` ProReq-light command-call target and `10,000` hard ceiling.
- Reinstalled the managed Factory scale cron block with the same `factory-scale-day.lock` flock guard.
- Created and dispatched two bounded Taskstream side lanes:
  - `#1000232` on Codex Spark (`gpt-5.3-codex-spark`) to build a candidate selector.
  - `#1000231` on Claude Code (`claude-sonnet-4-6`) to build an integration risk audit.
- Kept side-lane ownership disjoint:
  - Spark writes only `workspace/runs/walk-autopilot/factory-scale-day-20260506/scaleout/spark-selector/`.
  - Claude writes only `workspace/runs/walk-autopilot/factory-scale-day-20260506/scaleout/claude-audit/`.

#### What Worked

- The accelerated cron tick advanced the run to:
  - `30/300` ProReq-light executions.
  - `300/3000` logged ProReq-light command calls.
  - `10/100` Patch Swarm fixture milestones.
  - `1000/10000` candidate patch receipts.
- Spark generated:
  - `workspace/runs/walk-autopilot/factory-scale-day-20260506/scaleout/spark-selector/selection.json`
  - `workspace/runs/walk-autopilot/factory-scale-day-20260506/scaleout/spark-selector/selection.md`
  - Validated with `agent-work validate-run 1000232`, result `pass`.
- Claude generated:
  - `workspace/runs/walk-autopilot/factory-scale-day-20260506/scaleout/claude-audit/audit.json`
  - `workspace/runs/walk-autopilot/factory-scale-day-20260506/scaleout/claude-audit/audit.md`
  - Validated with `agent-work validate-run 1000231`, result `pass`.
- Claude identified two hard blockers before live Claude/API fanout:
  - Budget gates have only run in ledger-only mode.
  - Patch Swarm candidates remain fixture-generated; no real Claude receipt has been schema-validated yet.

#### What Did Not Work

- Spark initially wrote its handoff to the draft `{run_dir}` path. The handoff was copied into the canonical issue directory and validation passed there.
- The run still does not apply candidate patches. Safe Integrator worktree apply remains the next gated step.
- Live API remains intentionally disabled; no direct OpenAI usage polling was added in this step.

#### Next Steps

- Let the accelerated cron continue toward the `3,000` call / `10,000` receipt target.
- Use Spark selection output to seed Safe Integrator worktree batches after duplicate and touched-path checks.
- Use Claude's blockers as gating criteria before enabling any real Claude/provider fanout.
- Add a small live-provider sandbox only after the budget gate can enforce a hard cap and record usage evidence.

#### Tags

`cento-native`, `self-improvement`, `factory-scale`, `walk-autopilot`, `day-scale`, `spark`, `claude-code`, `patch-swarm`, `safe-integrator`, `spend-guard`, `validation`

### 2026-05-06T18:06:35Z - Parallel Code Delivery Rollout Gates Implemented

- `record_id`: 2026-05-06-parallel-code-delivery-rollout-gates-implemented
- `actor`: codex
- `scope`: pipeline, validation, routing, factory, patch-swarm
- `status`: implemented
- `artifacts_changed`: `scripts/factory.py`, `scripts/factory_integrator_core.py`, `scripts/parallel_delivery.py`, `tests/test_patch_swarm.py`, `tests/test_factory_parallel_rollout.py`, `docs/factory.md`, `docs/patch-swarm.md`, `data/tools.json`, `scripts/completion/_cento`, `docs/ai-self-improvement-log.md`
- `evidence`: `python3 -m pytest tests/test_patch_swarm.py tests/test_factory_parallel_rollout.py -q`, `python3 -m py_compile scripts/factory.py scripts/factory_integrator_core.py scripts/parallel_delivery.py`
- `checked_prior_records`: `2026-05-05-self-improvement-log-started-parallel-train-promotion-e2e`, `2026-05-06-factory-scale-day-autopilot-started`, `2026-05-06-factory-scale-day-lane-accelerated-with-spark-and-claude`
- `corrects_record_id`: none

#### Trigger

The operator accepted the four-day rollout plan and asked to implement the path from fixture Patch Swarm runs toward real parallel code delivery, with no single-threaded retesting and with auto-merge/push allowed only behind hard gates.

#### What Changed

- Added Factory `validate-fanout` for parallel, cacheable candidate validation keyed by base SHA, patch hash, and validation suite.
- Made Factory Safe Integrator apply logs append-only instead of deleting a prior `apply-log.jsonl`.
- Added Factory `merge --auto-merge-main` with optional `--push`, local clean-worktree checks, release/rollback/fanout gates, pre/post validation, and merge/push receipts.
- Added Patch Swarm live budget guard artifacts: `usage_guard.json`, `provider_usage.jsonl`, and `candidate_spend_ledger.jsonl`.
- Made Patch Swarm live execution fail closed unless the plan is live-enabled, a budget cap is supplied, estimated spend is within cap, and `CENTO_PATCH_SWARM_LIVE_ADAPTERS=1` is set.
- Added Patch Swarm promotion from selected `candidate_patch.v1` receipts into Factory patch bundles, Factory apply plans, and Factory validation fanout when `integrate --apply` or `--factory-run` is used.

#### What Worked

- Existing fixture Patch Swarm behavior stayed compatible while gaining schema checks and optional Factory promotion.
- Factory fanout validation caches repeated candidate checks and avoids rerunning the same deterministic gate work.
- The auto-merge command is present but blocks in unsafe conditions such as missing integration worktree, dirty main worktree, wrong branch, missing rollback plan, or failed validation.

#### What Did Not Work

- Live provider commands are still not launched by default. The implementation intentionally blocks until provider adapter configuration is explicitly enabled.
- Fixture Patch Swarm diffs are useful for receipt scale tests but are not guaranteed to apply cleanly as real patches; Factory fanout now exposes that before apply.
- Full `make check` was not run before this record; focused tests and py_compile were run first.

#### Next Steps

- Add provider-command adapter configuration for Codex Spark and Claude Code candidate generation.
- Run a tiny live-provider sandbox with a very low cap and verify real candidate receipts before raising parallelism.
- Use `validate-fanout` output to select only applyable candidates for Safe Integrator batches.
- After a clean low-risk release branch passes, exercise `factory merge --auto-merge-main --push` in a clean main worktree.

#### Suggestions

- Keep fixture scale as the load-test lane and live provider scale as a capped ramp, not a sudden jump.
- Prefer Codex Spark and Claude Code subscription lanes for broad candidate generation; reserve metered API calls for small structured review or schema-normalization gaps.

#### Tags

`cento-native`, `self-improvement`, `parallel-delivery`, `patch-swarm`, `factory`, `safe-integrator`, `validate-fanout`, `auto-merge`, `spend-guard`, `validation`

### 2026-05-06T18:34:02Z - Factory Scale Promotion Bridge And Applyable Fixture Ramp

- `record_id`: 2026-05-06-factory-scale-promotion-bridge-applyable-ramp
- `actor`: codex
- `scope`: pipeline, validation, factory-scale, patch-swarm, safe-integrator
- `status`: implemented
- `artifacts_changed`: `scripts/walk_autopilot.py`, `scripts/parallel_delivery.py`, `tests/test_walk_autopilot.py`, `tests/test_patch_swarm.py`, `data/tools.json`, `scripts/completion/_cento`, `docs/tool-index.md`, `docs/ai-self-improvement-log.md`
- `evidence`: `python3 -m py_compile scripts/walk_autopilot.py scripts/parallel_delivery.py`, `python3 -m pytest tests/test_walk_autopilot.py tests/test_patch_swarm.py tests/test_factory_parallel_rollout.py -q`, `./scripts/cento.sh parallel-delivery patch-swarm e2e --run-id patch-swarm-applyable-validation-20260506 --candidate-target 100 --max-parallel-agents 5 --fixture --factory-run workspace/runs/factory/patch-swarm-applyable-validation-20260506 --json`, `./scripts/cento.sh walk-autopilot factory-scale start-day --run-id factory-scale-aggressive-applyable-20260506 --target-proreq-calls 1000 --max-proreq-calls 10000 --duration-hours 12 --batch-size 100 --patch-swarm-candidate-target 100 --patch-swarm-max-parallel-agents 5 --no-install-cron --json`, `./scripts/cento.sh walk-autopilot factory-scale tick --run-id factory-scale-aggressive-applyable-20260506 --batch-size 100 --json`, `./scripts/cento.sh walk-autopilot factory-scale advance --run-id factory-scale-aggressive-applyable-20260506 --promotion-limit 330 --json`, `./scripts/cento.sh walk-autopilot factory-scale promote --run-id factory-scale-aggressive-applyable-20260506 --limit 330 --factory-run workspace/runs/factory/factory-scale-aggressive-applyable-20260506-promotion-exclusive-330 --json`
- `checked_prior_records`: `2026-05-06-factory-scale-no-overlap-advance`, `2026-05-06-factory-scale-day-lane-accelerated-with-spark-and-claude`, `2026-05-06-parallel-code-delivery-rollout-gates-implemented`
- `corrects_record_id`: `2026-05-06-parallel-code-delivery-rollout-gates-implemented`

#### Trigger

The operator asked for a more aggressive autopilot push while preserving no-overlap and spend controls.

#### What Changed

- Added `cento walk-autopilot factory-scale promote`, which consumes `advance/safe-integrator-promotion-plan.json`, normalizes entries into `candidate_patch.v1`, and promotes them into Factory patch bundles, apply plans, and parallel validation fanout.
- Made factory-scale promotion exclusive-path by default so repeated milestone candidates do not reach Factory as overlapping owned scopes.
- Fixed Patch Swarm fixture generation to emit syntactically applyable unified diffs and to mark candidates validated only when `git apply --check` passes.
- Fixed factory-scale `advance` for partial final milestones, where a manifest milestone can exist without a Patch Swarm summary.

#### What Worked

- The completed 10,000-receipt day run was promoted far enough to expose the old fixture-patch flaw: Factory rejected overlapping paths first, then fanout caught corrupt patch syntax.
- A fresh 100-candidate Patch Swarm run promoted into Factory with `fanout_status=passed`.
- A new no-cron, no-live-API factory-scale run completed 100 ProReq-light executions, 1,000 command-call records, 33 Patch Swarm milestones, and 3,300 candidate receipts in one guarded local batch.
- The new run advanced 3,300 receipts, selected 330 candidates, promoted 10 exclusive-path winners, and produced `ready_for_apply` Factory evidence with 6 fanout-passed candidates and 4 docs/registry-gate rejections.

#### What Did Not Work

- The older 10,000-receipt fixture run remains useful for scale and selection evidence, but its historical candidate diffs are not safe apply inputs.
- Four promoted command-surface candidates remain blocked by the existing docs/registry gate because their patches do not include the required registry/docs companion updates.
- No live Codex/Claude/API candidate generation was launched in this step; spend stayed local/fixture.

#### Next Steps

- Add a small provider-command sandbox for Codex Spark and Claude Code candidate receipts behind a hard budget/use gate.
- Teach Factory/Patch Swarm selection to prefer docs/registry-complete candidates for command-surface paths.
- Run Safe Integrator `--apply` only on fanout-passed, semantically useful candidates, not fixture comments.

#### Tags

`cento-native`, `self-improvement`, `factory-scale`, `walk-autopilot`, `patch-swarm`, `safe-integrator`, `validate-fanout`, `spend-guard`, `no-overlap`, `validation`

### 2026-05-06T18:43:00Z - Industrial OS Hero Pane Routed Through Live Cento State

- `record_id`: 2026-05-06-industrial-os-hero-mission-router
- `actor`: codex
- `scope`: industrial-os, terminal-ui, taskstream, agent-runs, cluster, operator-workflow
- `status`: implemented
- `artifacts_changed`: `scripts/industrial_mission.py`, `scripts/industrial_panel.py`, `scripts/industrial_panel_e2e.sh`, `scripts/industrial_mission_contract_check.py`, `scripts/fixtures/industrial_panel/mission-busy.json`, `scripts/fixtures/industrial_panel/mission-clean.json`, `scripts/fixtures/industrial_panel/mission-degraded-data-source.json`, `scripts/fixtures/industrial_panel/mission-action-model.json`, `scripts/fixtures/industrial_panel/mission-sources/busy.json`, `scripts/fixtures/industrial_panel/mission-sources/clean.json`, `scripts/fixtures/industrial_panel/mission-sources/degraded-data-source.json`, `docs/ai-self-improvement-log.md`
- `evidence`: `python3 -m py_compile scripts/industrial_mission.py scripts/industrial_panel.py scripts/industrial_mission_contract_check.py`, `python3 -m json.tool scripts/fixtures/industrial_panel/mission-busy.json`, `python3 scripts/industrial_mission_contract_check.py`, `./scripts/industrial_panel_e2e.sh`, live render captured with `python3 scripts/industrial_panel.py hero --once --plain`
- `checked_prior_records`: `2026-05-06-parallel-code-delivery-rollout-gates-implemented`, `2026-05-06-factory-scale-applyable-promotion-implemented`
- `corrects_record_id`: none

#### Trigger

The operator asked to replace the fake Industrial OS hero pane with a Cento-native mission router derived from real Taskstream, agent-run, cluster, git, jobs, and quick-action state.

#### What Changed

- Added `scripts/industrial_mission.py`, a read-only adapter that builds a render-ready mission model from `agent-work list --json`, `agent-work runs --json --active`, cluster snapshots, `git status --short`, jobs state, and registered industrial actions.
- Replaced the hardcoded hero queue, fake action count, mission brief, static context engine, and fake hub keys with the live mission model.
- Added deterministic mission fixture support through `CENTO_INDUSTRIAL_MISSION_FIXTURE`.
- Added hero handlers for dry-run, selected context, status-note drafting, refresh, help, and safe command execution.
- Added per-action JSON receipts under `workspace/runs/industrial-os/action-runs/` for hero actions, including dry-run status, selected item, source, command, cwd, exit code, output tail, and timestamp.
- Kept the hero command surface conservative: review-ready work uses `review-drain --dry-run`, queued work uses `dispatch --dry-run`, cluster work prefers diagnostic commands, and shell wrappers are blocked.

#### What Worked

- The busy fixture orders Review-ready, Review-gated, Blocked, Queued dry-run, manual/untracked shell, cluster, and git items in the requested priority.
- The compact and 120-column hero renders fit within terminal width without the old fake strings or unimplemented capture/block actions.
- The contract check verifies selected context, dry-run execution, unsafe shell blocking, and receipt creation.
- A live unfixtured render now shows real Taskstream counts, manual Codex/Claude shells, cluster degradation, and dirty worktree state.

#### What Did Not Work

- The live render still depends on synchronous `agent-work` commands, so a slow Taskstream backend can delay hero refresh.
- The hero currently displays the first nine mission items; deeper queues remain summarized rather than scroll-windowed across all live items.

#### Next Steps

- Add a short-lived mission-model cache if synchronous Taskstream calls make the live pane feel sluggish.
- Add a scroll window for large Review queues so selection can move past the first nine items without losing the keyboard contract.
- Consider showing receipt paths in a small history strip after repeated hero actions.

#### Tags

`cento-native`, `self-improvement`, `industrial-os`, `taskstream`, `agent-work`, `cluster`, `terminal-ui`, `safe-actions`, `validation`

### 2026-05-06T18:53:30Z - Self-Improvement Autopilot E2E Wired Through Patch Swarm And Factory

- `record_id`: 2026-05-06-self-improvement-autopilot-e2e-patch-swarm-factory
- `actor`: codex
- `scope`: self-improvement, patch-swarm, api-sandbox, factory, safe-integrator, auto-merge, docs
- `status`: implemented
- `artifacts_changed`: `scripts/parallel_delivery.py`, `.cento/api_workers.yaml`, `tests/test_patch_swarm.py`, `tests/test_self_improvement_loop.py`, `tests/test_factory_parallel_rollout.py`, `docs/ai-self-improvement-autopilot.md`, `docs/ai-self-improvement-nightly.md`, `docs/patch-swarm.md`, `docs/factory.md`, `docs/nav.html`, `data/tools.json`, `docs/tool-index.md`, `scripts/completion/_cento`, `docs/ai-self-improvement-log.md`
- `evidence`: `python3 -m py_compile scripts/parallel_delivery.py scripts/cento_openai_worker.py scripts/factory.py scripts/factory_integrator_core.py`, `python3 -m pytest tests/test_patch_swarm.py tests/test_self_improvement_loop.py tests/test_factory_parallel_rollout.py -q`, `./scripts/cento.sh parallel-delivery self-improve e2e --run-id self-improve-e2e-fixture-final --fixture-only --candidate-target 10 --max-parallel-agents 2 --apply --validate-each --auto-merge-gate --json`, `python3 -m json.tool data/tools.json`, `python3 scripts/tool_index.py --registry data/tools.json --output docs/tool-index.md`, `./scripts/cento.sh docs parallel-delivery`, `./scripts/cento.sh docs factory`, `make check`
- `checked_prior_records`: `2026-05-06-parallel-code-delivery-rollout-gates-implemented`, `2026-05-06-factory-scale-promotion-bridge-applyable-ramp`
- `corrects_record_id`: none

#### Trigger

The operator asked to implement the accepted self-improvement autopilot e2e plan in a fresh context.

#### What Changed

- Added `cento parallel-delivery self-improve e2e` as a durable orchestration command.
- The command consumes latest `self-improve` `next_cycle_request.json`; fixture mode uses the deterministic seed fallback, while non-fixture mode can run the existing planning loop when latest is absent.
- Added the `api-patch-proposal` OpenAI worker profile and Patch Swarm conversion from completed `patch_proposal.v1` API worker artifacts into `candidate_patch.v1` receipts.
- Reworked Patch Swarm live API gating to block on `OPENAI_API_KEY`, `--budget-cap-usd`, `--max-budget-usd`, and estimated metered sandbox spend before dispatch.
- Allowed small Patch Swarm candidate targets for sandbox e2e runs.
- The self-improvement e2e retargets candidates to a run-scoped sandbox, promotes winners into Factory, runs `validate-fanout`, applies at most one candidate through the Safe Integrator worktree when requested, and runs `factory merge --auto-merge-main --dry-run --json` without `--push`.
- Added e2e artifacts and latest mirror under `workspace/runs/ai-self-improvement-e2e/`.

#### What Worked

- Fixture e2e reached `auto_merge_blocked_by_environment` with one Safe Integrator-applied sandbox candidate, passing Factory fanout and writing a dry-run auto-merge receipt with `push_requested=false`.
- Missing API key and over-cap live API sandbox paths block before API worker dispatch.
- The API worker artifact conversion test produces a valid `candidate_patch.v1` receipt and apply-checkable unified diff.

#### What Did Not Work

- The first fixture smoke showed that dirty/untracked source-path fixture patches could validate in the operator worktree but fail inside a clean integration worktree. The e2e now retargets to a sandbox path before candidate generation.
- Factory per-patch validation commands were initially relative to the integration worktree cwd; Patch Swarm promotion now writes absolute validation artifact paths.
- Live API e2e was not run because this validation path intentionally avoided metered calls.

#### Next Steps

- Run the optional live e2e with `CENTO_RUN_LIVE_API_E2E=1` and `OPENAI_API_KEY` after confirming the operator wants metered spend.
- Add Codex Spark and Claude Code real provider-command adapters behind separate hard gates.
- Keep auto-merge as dry-run evidence until the main worktree is clean and the operator explicitly asks for a push-enabled release gate.

#### Tags

`cento-native`, `self-improvement`, `parallel-delivery`, `patch-swarm`, `api-openai`, `safe-integrator`, `factory`, `auto-merge`, `spend-guard`, `validation`

### 2026-05-06T19:05:00Z - Agent Processes Pane Shows Doing Signal

- `record_id`: 2026-05-06-agent-processes-doing-signal
- `actor`: codex
- `scope`: industrial-os, agent-processes, agent-work, terminal-ui, operator-workflow
- `status`: implemented
- `artifacts_changed`: `scripts/agent_work.py`, `scripts/industrial_aux_tui.go`, `scripts/agent_processes_tui.go`, `docs/ai-self-improvement-log.md`
- `evidence`: `python3 -m py_compile scripts/agent_work.py`, `go build -o /tmp/cento-industrial-aux-check ./scripts/industrial_aux_tui.go`, `go build -o /tmp/cento-agent-processes-check ./scripts/agent_processes_tui.go`, `./scripts/industrial_aux_tui.sh agents --once`, `./scripts/agent_processes_tui.sh --once`, width check for both rendered outputs
- `checked_prior_records`: `2026-05-06-industrial-os-hero-mission-router`, `2026-05-06-self-improvement-autopilot-e2e-patch-swarm-factory`
- `corrects_record_id`: none

#### Trigger

The operator showed the Industrial OS Agent Processes pane and asked to add what the live agents are doing, with the result still fitting in the fixed pane.

#### What Changed

- Added process cwd capture for untracked interactive Codex/Claude shells in `agent-work runs --json --active`.
- Enriched Agent Processes run rows with issue subjects from the live Taskstream list when a run has an issue id but the run ledger lacks a subject.
- Changed the Industrial OS aux Agent Processes pane to render a compact first line plus a clipped `doing:` line for each live process.
- Updated the standalone `cento agent-processes --once` dashboard to rename the active-runs subject column to `DOING` and use issue subject, package, or command/cwd fallback.

#### What Worked

- The aux pane now shows manual shells as `doing: claude @ ~` or `doing: codex @ ~` instead of only `manual -> shell`.
- Managed runs can show their Taskstream issue subject inline when present.
- The aux render stayed within 58 columns and 20 lines; the standalone dashboard stayed within 100 columns.

#### What Did Not Work

- Manual shells still cannot expose a real task unless they are attached to a Taskstream issue or ledger. The pane now shows the honest command/cwd signal rather than inventing a task.

#### Next Steps

- Encourage launching agent work through the ledger wrapper or Taskstream dispatch so the pane can show exact issue subjects instead of only command/cwd for manual sessions.
- Consider adding a voluntary session note field for manual shells if operators want richer labels without forcing dispatch.

#### Tags

`cento-native`, `self-improvement`, `industrial-os`, `agent-processes`, `agent-work`, `terminal-ui`, `manual-shells`, `validation`

### 2026-05-11T18:11:37Z - Patch Swarm Product Module MVP

- `record_id`: 2026-05-11-patch-swarm-product-module-mvp
- `actor`: codex
- `scope`: patch-swarm, cento-web-app, parallel-delivery, safe-integrator, local-repos
- `status`: implemented
- `artifacts_changed`: `scripts/agent_work_app.py`, `scripts/parallel_delivery.py`, `templates/agent-work-app/index.html`, `templates/agent-work-app/app.js`, `templates/agent-work-app/styles.css`, `tests/test_patch_swarm.py`, `docs/patch-swarm.md`, `docs/cento-web-app.md`, `docs/ai-self-improvement-log.md`
- `evidence`: `python3 -m py_compile scripts/parallel_delivery.py scripts/agent_work_app.py`, `node --check templates/agent-work-app/app.js`, `python3 -m pytest tests/test_patch_swarm.py -q`, `curl -fsS http://127.0.0.1:47911/api/patch-swarm/repos`, `curl -fsS http://127.0.0.1:47911/api/patch-swarm/runs`, `playwright screenshot --viewport-size=1440,1100 --wait-for-selector='#patchSwarmView:not(.hidden)' --wait-for-timeout=1000 http://127.0.0.1:47911/patch-swarm workspace/tmp/patch-swarm-desktop.png`, `playwright screenshot --full-page --viewport-size=390,900 --wait-for-selector='#patchSwarmView:not(.hidden)' --wait-for-timeout=1000 http://127.0.0.1:47911/patch-swarm workspace/tmp/patch-swarm-mobile-full.png`, `workspace/tmp/patch-swarm-candidate-review.png`
- `checked_prior_records`: `2026-05-06-patch-swarm-mvp-implemented`, `2026-05-06-self-improvement-autopilot-e2e-patch-swarm-factory`
- `corrects_record_id`: none

#### Trigger

The operator provided the Patch Swarm product roadmap and asked for implementation in a fresh context.

#### What Changed

- Added standalone Cento Console routes for `/patch-swarm` and `/patch-swarm/runs/:run_id`.
- Added Patch Swarm product APIs for repo discovery, run creation, run detail, approval, rejection, and supervised apply.
- Repo discovery now surfaces branch, head, dirty paths, protected dirty paths, and likely test commands for local Git repositories.
- Product run creation stores selected repo, task brief, provider preset, validation profile, and UI metadata while retargeting generated candidate patch receipts to run-scoped paths in the selected repo.
- Approval and rejection write product receipts before apply; apply is blocked until approval exists.
- Non-Cento repos apply through a dedicated product worktree receipt; Cento repo applies can still hand off through Factory/Safe Integrator.
- Added a product-grade Patch Swarm UI with repo picker, task composer, run history, candidate ranking, diff preview, approval gate, rejection, and worktree apply actions.
- Updated Patch Swarm docs and the Cento web app section list to make Patch Swarm a first-class module.

#### What Worked

- The new API discovered local Git repos and reported protected dirty worktree state.
- Focused Patch Swarm tests covered local repo selection, run lifecycle metadata, approval/rejection, supervised external worktree apply, protected dirty path blocking, and app-shell routing.
- Browser validation confirmed the product route, mobile stacking, run-detail route, ranked candidate list, and diff preview render without runtime errors.

#### What Did Not Work

- An older Cento Console process was already serving port `47910`, so visual validation used a fresh instance on `47911`.
- Local Codex and Claude live candidate adapters are still future work; the product route records provider/runtime metadata and uses the existing Patch Swarm engine defaults unless hard-gated live API mode is explicitly requested.

#### Next Steps

- Add hard-gated local Codex/Claude provider command adapters that produce real `candidate_patch.v1` receipts.
- Add first-class Playwright regression tests for the new product UI flow instead of relying only on scripted screenshot validation.
- Dogfood one apply-disabled live run on Cento, then one supervised Safe Integrator apply on a separate clean local repo.

#### Tags

`cento-native`, `patch-swarm`, `cento-console`, `parallel-delivery`, `factory`, `safe-integrator`, `local-first`, `ui`, `validation`

### 2026-05-11T19:09:58Z - Patch Swarm First-Run Clarity UI

- `record_id`: 2026-05-11-patch-swarm-first-run-clarity-ui
- `actor`: codex
- `scope`: patch-swarm, cento-web-app, operator-workflow, ui
- `status`: implemented
- `artifacts_changed`: `templates/agent-work-app/app.js`, `templates/agent-work-app/index.html`, `templates/agent-work-app/styles.css`, `docs/ai-self-improvement-log.md`
- `evidence`: `node --check templates/agent-work-app/app.js`, `python3 -m pytest tests/test_patch_swarm.py -q`, `curl -fsS http://127.0.0.1:47912/api/patch-swarm/repos`, `curl -fsS http://127.0.0.1:47912/api/patch-swarm/runs`, `npx playwright screenshot --viewport-size=1365,1000 --wait-for-selector='#patchSwarmView:not(.hidden)' --wait-for-timeout=1000 http://127.0.0.1:47912/patch-swarm workspace/tmp/patch-swarm-after-1365.png`, `npx playwright screenshot --viewport-size=390,900 --wait-for-selector='#patchSwarmView:not(.hidden)' --wait-for-timeout=1000 http://127.0.0.1:47912/patch-swarm workspace/tmp/patch-swarm-after-mobile.png`, `npx playwright screenshot --viewport-size=2048,1000 --wait-for-selector='#patchSwarmView:not(.hidden)' --wait-for-timeout=1000 http://127.0.0.1:47912/patch-swarm workspace/tmp/patch-swarm-after-2048.png`, Playwright DOM checks for default startable repo selection, blocked Cento gating, empty-task gating, disabled review actions, mobile no-overflow, and no console/page errors
- `checked_prior_records`: `2026-05-11-patch-swarm-product-module-mvp`
- `corrects_record_id`: none

#### Trigger

The operator provided a 180-minute implementation plan to improve Patch Swarm first-run clarity without changing backend run semantics.

#### What Changed

- Sorted repository options so startable repos appear first, labeled blocked repos in-place, and defaulted to the first `can_start=true` repo instead of selecting blocked Cento.
- Added explicit composer states for Ready, Blocked, Task required, Starting, Run created, and Failed.
- Kept Fixture mode presented as the safe/no-spend default and added reassurance that generation does not mutate the selected repo.
- Reworked empty run detail state so "No run selected" shows the next action and hides zero-value stats.
- Made legacy engine-only runs visually distinct from product runs and added repo, status, candidate, approval, and apply facts to history rows.
- Gated Approve, Apply, and Reject actions from selected/validated candidate, supervised approval, and selected-candidate state.
- Tightened responsive Patch Swarm and Software Delivery Hub rail layout so the mobile viewport reaches the Patch Swarm composer without horizontal overflow.

#### What Worked

- Existing repo and run APIs already exposed the state needed for first-run clarity, so this remained a UI-only pass.
- The blocked Cento checkout stayed visible with its protected dirty path, while the default repo changed to a startable repository.
- Browser checks confirmed empty-task and blocked-repo gates, disabled review actions before a run is selected, no page errors, and no mobile horizontal overflow.

#### What Did Not Work

- The live local run list currently contains only legacy engine-only runs, so visual validation confirmed the legacy styling path; product-row styling is covered by the same renderer but was not backed by an existing local product run.
- The shared console topbar is still tall on narrow mobile viewports; the Patch Swarm rail now compresses enough to expose the composer, but broader topbar redesign was out of scope.

#### Next Steps

- Add a lightweight Playwright regression around `/patch-swarm` first-run controls once the repo has a browser-test harness.
- Dogfood one fixture product run in a clean non-Cento repo, then capture a product-history screenshot and candidate-review state.

#### Tags

`cento-native`, `self-improvement`, `patch-swarm`, `cento-console`, `operator-workflow`, `ui`, `validation`
