# Cento AI Native Execution Plan

Generated: 2026-05-05T05:13:19Z

Source research: `docs/ai-cento-native-rework-research.md`.

Run directory: `workspace/runs/ai-cento-native-execution-plan/20260505T051319Z`.

This document is the canonical execution plan produced by the controlled Spark coordination run. It validates the older research plan against the live Cento repo, preserves current/proposed/outdated distinctions, expands the architecture into implementation contracts, and defines how future Spark lanes should execute and validate the work.

## Integration Summary

- Execution mode: controlled live Spark drafting with `gpt-5.3-codex-spark` section workers plus coordinator integration.
- Canonical output: `docs/ai-cento-native-execution-plan.md`.
- Worker outputs: `workspace/runs/ai-cento-native-execution-plan/20260505T051319Z/sections/*.md`.
- Taskstream records: coordinator `1000178`; lane records `1000179`, `1000180`, `1000181`, `1000182`, `1000183`, `1000184`, `1000185`, `1000187`.
- Current-state facts are valid only as of 2026-05-05 and must be refreshed with the commands in the validation checklist before implementation decisions.

## Important Current Corrections

- The original research doc is useful but stale in several places: tool count is now 50, latest hard-proreq run is `hard-proreq-task-hard-proreq-project-20260505T050416185358Z`, and stored hard-proreq run history is larger than the older observation.
- `parallel-delivery` exists and the latest status reports `completed`, `validation: passed`, `demo: completed`, and `pass_count: 12`.
- `cento runtime list --json` currently reports `codex-fast`, `fixture-valid`, and `python-fixture` as passing.
- MCP remains narrow: context/platform/cluster/bridge/agent-work/story tools exist, while Dev Pipeline/build/workset/factory/runtime/scan/evidence MCP tools are proposed future work.
- `agent-work` does not expose a pool-dispatch subcommand; use `agent-work dispatch` for direct issue dispatch and `agent-pool-kick --dry-run` for pool planning. `agent-pool-kick --json` is also not accepted, although dry-run output is JSON-shaped.
- Hard-proreq Pro planning is still gated/fallback unless `CENTO_HARD_PROREQ_DISPATCH_PRO=1` and credentials are configured; do not describe deterministic fallback artifacts as live Pro output.

## Section Index

- Validation Matrix: `workspace/runs/ai-cento-native-execution-plan/20260505T051319Z/sections/validation_matrix.md` (10423 bytes), Taskstream `1000179`
- Current State: `workspace/runs/ai-cento-native-execution-plan/20260505T051319Z/sections/current_state.md` (14540 bytes), Taskstream `1000180`
- Target Architecture: `workspace/runs/ai-cento-native-execution-plan/20260505T051319Z/sections/target_architecture.md` (18178 bytes), Taskstream `1000181`
- Proposed Interfaces: `workspace/runs/ai-cento-native-execution-plan/20260505T051319Z/sections/interfaces.md` (16226 bytes), Taskstream `1000182`
- Dev Pipeline Gaps And Fixes: `workspace/runs/ai-cento-native-execution-plan/20260505T051319Z/sections/dev_pipeline_gaps.md` (7579 bytes), Taskstream `1000184`
- Skills And Runtime Policy: `workspace/runs/ai-cento-native-execution-plan/20260505T051319Z/sections/skills_runtime.md` (15962 bytes), Taskstream `1000185`
- Spark Coordination Runbook: `workspace/runs/ai-cento-native-execution-plan/20260505T051319Z/sections/spark_coordination.md` (6297 bytes), Taskstream `1000183`
- Validator Checklist: `workspace/runs/ai-cento-native-execution-plan/20260505T051319Z/sections/validator_review.md` (9955 bytes), Taskstream `1000187`

---

## Validation Matrix

_Integrated from `workspace/runs/ai-cento-native-execution-plan/20260505T051319Z/sections/validation_matrix.md`._

# Validation Matrix: `docs/ai-cento-native-rework-research.md` (as of 2026-05-05)

Scope: validate claims in the research document against the live Cento repo at `/home/alice/projects/cento`.

## Status Legend

- `true` = verified against current state
- `partially true` = validated core idea but implementation/details differ
- `outdated` = claim is no longer current (stale counts, dates, paths, etc.)
- `false` = explicit claim is contradicted by current state
- `unknown` = future-state/recommendation with insufficient runtime verification

## Matrix

| ID | Claim | Status | Evidence |
| --- | --- | --- | --- |
| C01 | `cento gather-context --no-remote` reports 45 registered tools. | `outdated` | `cento gather-context --no-remote` now reports `total tools: 50`, `Linux tools: 47`, `both: ...`. `data/tools.json` also contains `len 50` tool entries. |
| C02 | `cento tools` / `cento gather-context` indicate `data/tools.json` + `cento tools` + `cento platforms` + `cento docs` are source-of-truth. | `true` | `cento gather-context --no-remote` prints source-of-truth note; `data/tools.json` is present and loaded; docs list these command families. |
| C03 | Runtime list contains `codex-fast`, `fixture-valid`, `python-fixture` with passing validation. | `true` | `cento runtime list --json` returns exactly these three profiles, each `status: "passed"` with executables and limits. |
| C04 | MCP surface is narrow: agent-work/cluster/bridge/context/story only; no dev pipeline/build/workset/factory/runtime/scan/evidence start tools. | `true` | `CENTO_MCP_READ_ONLY=1 python3 scripts/cento_mcp_server.py --list-tools` returns only 11 tool entries (`cento_agent_work_*`, `cento_cluster_status`, `cento_bridge_mesh_status`, `cento_context`, `cento_platforms`, `cento_story_manifest_*`). |
| C05 | MCP README/docs reflect the same narrow scope. | `true` | `docs/cento-mcp-server.md` lists the same 11 tool families and labels MCP as a small allowlist wrapper without full CLI exposure. |
| C06 | MCP tooling includes command entry points for `dev-pipeline state`, `scan`, `runtime` and `evidence` checks. | `false` | No such tool names appear in MCP list output (only story/agent-work/cluster/context/platform). |
| C07 | Dev Pipeline hard-proreq latest run in repo is `hard-proreq-task-hard-proreq-project-20260504T065328911797Z`. | `outdated` | Latest hard-proreq directory under `workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/latest` points to `hard-proreq-task-hard-proreq-project-20260505T050416185358Z` (from `execution_run.run_id`). |
| C08 | Latest hard-proreq execution status is `completed` with source `cento-hard-proreq-pro`. | `true` | `workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/execution_run.json` has `status: "completed"` and `source: "cento-hard-proreq-pro"`. |
| C09 | Hard-proreq execution exposes 4-stage UI cards backed by 6 stage records and 9 steps. | `partially true` | `execution_run.json` has `6` stages and `9` steps. Stage IDs: `input`, `repo`, `blueprint`, `factory`, `validation`, `handoff`. |
| C10 | Latest run artifact count was `23` in API with `13` existing artifacts in payload summary. | `outdated` | Current `execution_run.json` has `20` artifacts. |
| C11 | Latest hard-proreq run has artifacts for the same end-to-end chain (intake, context, screenshot lane, schema, plan, workstreams, evidence). | `true` | `workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/latest` contains: `operator_intake.json`, `mini_cento_context.json`, `ui_screenshot_request.json`, `existing_ui_reference*.png`, `image_generation*.json`, `pro_output_schema.json`, `pro_backend_*.json`, `backend_work_manifest.json`, `integration_plan.json`, `validation_plan.json`, `hard_proreq_evidence.json`, etc. |
| C12 | `execution_run.json` carries proof/validation status fields to drive UI trust. | `partially true` | `execution_run.json` has keys `proof` and `validation`, currently both `None`; so the payload is explicit but no status is populated. |
| C13 | Hard-proreq evidence artifact is `completed`. | `true` | `workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/latest/hard_proreq_evidence.json` contains `"status": "completed"`. |
| C14 | Pro backend run is gated and falls back when `CENTO_HARD_PROREQ_DISPATCH_PRO` is not enabled. | `true` | `pro_backend_plan.json` summary: `"GPT pro request is schema-ready; backend work uses deterministic fallback until CENTO_HARD_PROREQ_DISPATCH_PRO=1 is enabled."`; `pro_backend_error.json` reason: `"Pro API dispatch is gated..."`. |
| C15 | Hard-proreq validation should show template validators as `passed, passed, muted` in execution summary. | `partially true` | In latest run, `validation_plan.json` has `validators: []` and `status: null` for top-level validation state. |
| C16 | Dev Pipeline hard-proreq history in the live run view is around 9 runs. | `outdated` | `workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq` currently contains `37` non-`latest` run directories; UI claim of 9 is stale against stored run set. |
| C17 | `cento scan --query "agent-work" --no-open` produced 1514 scanned files, 223 matched files, 1286 matches. | `outdated` | Latest scan summary file `workspace/runs/scan-onepager/latest/summary.json` now reports `matched_files: 616`, `total_matches: 3320`. |
| C18 | `cento agent-work` exposes a pool-dispatch subcommand in help and runtime flow. | `false` | `cento agent-work --help` includes `dispatch` but no pool-dispatch subcommand. |
| C19 | `cento-agent-work docs` are aligned with current CLI (the removed pool subcommand is documented as usable). | `outdated` | Stale examples with `--execute` and `--json` flags appeared in `docs/agent-work.md` and `docs/agent-work-runtimes.md`, but those subcommands do not exist in help output; references have been removed. |
| C20 | `cento agent-pool-kick --help` exposes `--json` for machine output mode. | `false` | `cento agent-pool-kick --help` flags: `--builder-target`, `--validator-target`, `--small-target`, `--coordinator-target`, `--max-launch`, `--dry-run` only; no `--json`. |
| C21 | `agent-pool-kick` does not return machine-readable output by default. | `false` | `cento agent-pool-kick --dry-run` returns full JSON with fields like `generated_at`, `active_counts`, `targets`, `launched`, etc., even without any `--json` flag. |
| C22 | Docs/mcp claims match the CLI runtime around Spark lane planning. | `partially true` | The documented Spark workflow is partially present via `agent-pool-kick --dry-run`, but stale pool planning references in docs (removed subcommand and `--json` flag) are incorrect per actual help. |
| C23 | `data/tools.json` includes build/factory/workset/scan/runtime as registered tool families. | `true` | `python3 - <<'PY'` read of `data/tools.json` confirms 50 tools including `build`, `workset`, `factory`, `runtime`, `scan`, etc.; CLI `cento tools` output also lists these families. |
| C24 | `cento docs build` and `cento docs factory` resolve correctly and are discoverable. | `true` | `cento docs build` and `cento docs factory` execute successfully (exit 0) and print canonical command examples; this can be reproduced from the recorded command output. |
| C25 | `scripts/agent_work_app.py` is split (small bootstrap + route modules). | `false` | `rg` hits in `scripts/agent_work_app.py` show constants, schema handlers, task/DB sync, and dev pipeline execution/evidence logic in one file. |
| C26 | `scripts/cento_openai_worker.py` defines schema-backed outputs and validation gates, and does not mutate repository state. | `partially true` | `rg` confirms schemas for `patch_proposal.v1`, `validation_review.v1`, `hard_proreq_plan.v1`, `workset_plan.v1`; the repository currently also has non-worker integration paths, but the file itself is schema-driven and no direct mutation was asserted from schema constants alone. |
| C27 | `parallel-delivery` run for the run directory in question is complete with passing validation and demo completed. | `true` | `cento parallel-delivery status --json` currently reports `status: "completed"`, `pass_count: 12`, `validation: "passed"`, `demo: "completed"`, `run_dir: workspace/runs/parallel-delivery/vp-e2e-20260505T0230Z`. |
| C28 | `parallel-delivery` evidence/implementation is validated by passing tests. | `partially true` | Existing tests around hard-proreq delivery were run: `python3 -m pytest tests/test_dev_pipeline_delivery.py -q` reports `15 passed`. No dedicated `tests/test_parallel_delivery.py` exists in this repo snapshot. |
| C29 | The latest hard-proreq plan includes exactly the documented 10 workstreams. | `true` | `pro_backend_plan.json` from latest hard-proreq run has `len(backend_workstreams) == 10`. |
| C30 | `cento-native` skills are already comprehensive for routing, run envelopes, and evidence handoff. | `partially true` | Installed skills under `/home/alice/.codex/skills` are `cento-native`, `cento-requirements-manifest`, `navigate-skills`, `ui-verify-and-report` only. |
| C31 | Proposed `cento-ai-run`, `cento-validator`, `cento-evidence-handoff` already exist. | `false` | Only currently available Cento skills are as listed above; those proposed names are not present in `/home/alice/.codex/skills` and no dedicated command surfaces are present. |
| C32 | MCP read/write extension should include `cento_runtime_list`, `cento_dev_pipeline_*`, `cento_evidence_check` as part of rework. | `unknown` | This is a proposed target in the research; implementation is not currently present, so it is not yet verifiable as true/false in current runtime. |
| C33 | UI proof and validation currently can still be considered fully aligned to source-of-truth receipts. | `partially true` | Evidence mismatch risk exists: top-level `execution_run.proof` is `None` while artifacts + `hard_proreq_evidence.json` exist, which supports the documented concern in findings. |
| C34 | Latest hard-proreq evidence artifacts are fully integrated into execution_run artifact list. | `true` | `execution_run.json` artifact list explicitly includes `execution/hard-proreq/latest/...` paths and both `validation_plan.json` and `hard_proreq_evidence.json`. |
| C35 | Scan and hard-proreq tooling are still discoverable via docs. | `true` | `docs/cento-mcp-server.md`, `docs/agent-work.md`, `scripts/dev_pipeline_hard_proreq.py` and the command outputs above confirm scan + hard-proreq paths remain present and operational. |

---

## Current State

_Integrated from `workspace/runs/ai-cento-native-execution-plan/20260505T051319Z/sections/current_state.md`._

# Current-State Map (Cento) — 2026-05-05

Scope: `/home/alice/projects/cento` runtime and docs as observed on **2026-05-05**.

## 0) Anchors and evidence collection

- Canonical state refresh:
  - `cd /home/alice/projects/cento && python3 scripts/gather_context.py --no-remote`
  - `cd /home/alice/projects/cento && python3 scripts/cento_runtime.py list --json`
  - `cd /home/alice/projects/cento && python3 scripts/agent_work.py list --json`
  - `cd /home/alice/projects/cento && python3 scripts/agent_work.py recovery-plan --json`
  - `cd /home/alice/projects/cento && python3 scripts/agent_pool_kick.py --dry-run`
  - `cd /home/alice/projects/cento && python3 scripts/cento_mcp_server.py --list-tools`
  - `cd /home/alice/projects/cento && python3 scripts/parallel_delivery.py status --json`
- Rundir for this execution slice:
  - `workspace/runs/ai-cento-native-execution-plan/20260505T051319Z`
  - `workspace/runs/ai-cento-native-execution-plan/20260505T051319Z/sections/current_state.md` (this file)

## 1) Registered tools

### 1.1 Tool registry state

- Source-of-truth JSON: `data/tools.json` (top-level object `tools`)
  - `jq '.tools | length' data/tools.json` → `50` tools.
- `cento gather-context --no-remote` confirms:
  - total tools: `50`
  - linux tools: `47`
  - macOS tools: `37`
  - both: `37`

### 1.2 Registered IDs (50 total)

- `agent-pool-kick`
- `agent-processes`
- `agent-work`
- `agent-work-hygiene`
- `audio-quick-connect`
- `batch-exec`
- `bluetooth-audio-doctor`
- `bridge`
- `build`
- `burp`
- `cento-cli`
- `cento-mcp`
- `cluster`
- `crm`
- `daily`
- `dashboard`
- `demo-evidence`
- `discord`
- `display-layout-fix`
- `factory`
- `gather-context`
- `i3reorg`
- `incident`
- `install-linux`
- `install-macos`
- `kitty-theme-manager`
- `mcp`
- `mobile`
- `mozilla-vpn`
- `network-tui`
- `notify`
- `object-storage`
- `opencode`
- `parallel-delivery`
- `platform-report`
- `preset`
- `project-scaffold`
- `quick-help`
- `quick-help-fzf`
- `rd`
- `repo-snapshot`
- `runtime`
- `scan`
- `search-report`
- `system-inventory`
- `temp`
- `tool-index`
- `tui`
- `wallpaper-manager`
- `workset`

### 1.3 Platform-availability quick map

- linux-only (subset): `audio-quick-connect`, `bluetooth-audio-doctor`, `burp`, `dashboard`, `i3reorg`, `preset`, `quick-help`, `discord`, `rd`, `wallpaper-manager`, `install-linux`
- macOS-only: `incident`, `install-macos`, `mobile`, plus mobile tooling lane
- both: `cento-cli`, `agent-work`, `build`, `factory`, `runtime`, `workset`, `parallel-delivery`, `cento-mcp`, etc.

### 1.4 Relevant docs for tool contract

- `data/tools.json` (registry payload)
- `data/cento-cli.json` (root CLI metadata)
- `docs/tool-index.md` (command index)
- `docs/cento-cli.md`
- `docs/agent-work.md`
- `docs/agent-work-runtimes.md`
- `docs/cento-mcp-server.md`
- `docs/factory.md`
- `docs/cento-workset.md`
- `docs/cento-build.md`
- `docs/dev-pipeline-run-contracts.md`

### 1.5 Relevant schema definitions

- JSON schemas:
  - `docs/schemas/cento.build.v1.json`
  - `docs/schemas/cento.validation_receipt.v1.json`
  - `docs/schemas/cento.apply_receipt.v1.json`
  - `docs/schemas/cento.integration_receipt.v1.json`
  - `docs/schemas/cento.worker_artifact.v1.json`
  - `docs/schemas/cento.patch_bundle.v1.json`
  - `docs/schemas/cento.taskstream_evidence.v1.json`
- Runtime/API schema contracts (embedded constants rather than standalone JSON files):
  - `scripts/cento_openai_worker.py`
  - `scripts/cento_workset.py`
  - `scripts/agent_work_app.py`
  - `scripts/dev_pipeline_hard_proreq.py`

## 2) Runtime profiles and AI routing

### 2.1 Command/runtime layer

Command and live results:
- `python3 scripts/cento_runtime.py list --json`
- `python3 scripts/agent_work.py runtimes --json`
- `.cento/runtimes.yaml`
- `.cento/modes.yaml`
- `data/agent-runtimes.json`
- `.cento/api_workers.yaml`

### 2.2 Registered runtime profiles (live)

`python3 scripts/cento_runtime.py list --json` currently returns:
- `codex-fast` (type `command`) — status `passed`
- `fixture-valid` (type `fixture`) — status `passed`
- `python-fixture` (type `command`) — status `passed`

### 2.3 Runtime contract files

- `.cento/runtimes.yaml`
  - profiles: `codex-fast`, `fixture-valid`, `python-fixture`
  - both command profiles allowlist `PATH`, `HOME`, etc. and enforce patch/file budget caps
- `.cento/modes.yaml`
  - `fast`, `standard`, `thorough` mode semantics
- `.cento/api_workers.yaml`
  - request model profiles: `api-planner`, `api-section-worker`, `api-reviewer`, `api-mini-integrator`, `api-proreq-planner`
- `data/agent-runtimes.json` / `agent_work.py runtimes --json`
  - `codex` `weight: 0`, `budget_note`: temporarily disabled for dispatch
  - `claude-code` `weight: 100`, `preferred: true`
  - sample counts from output: `claude-code: 100` for a 100-size routing sample

## 3) MCP surface and current gaps

### 3.1 MCP config and tool listing

- MCP config file: `.mcp.json`
  - servers present: `cento`, `filesystem`, `fetch`, `github`
- `python3 scripts/cento_mcp_server.py --list-tools` returns 11 tools:
  - `cento_agent_work_list`
  - `cento_agent_work_show`
  - `cento_agent_work_create`
  - `cento_agent_work_update`
  - `cento_agent_work_claim`
  - `cento_agent_work_validate_run`
  - `cento_agent_work_handoff`
  - `cento_context`
  - `cento_platforms`
  - `cento_cluster_status`
  - `cento_bridge_mesh_status`
  - `cento_story_manifest_validate`
  - `cento_story_manifest_render_hub`
- Read-only mode exists via `CENTO_MCP_READ_ONLY` in server docs and wrapper logic.

### 3.2 MCP vs CLI surface gap (confirmed)

- MCP remains narrow and does not expose:
  - `workset`
  - `build`
  - `factory`
  - `scan`
  - `runtime`
  - `parallel-delivery`
  - `agent-pool-kick` (no direct wrapper)
  - `dev_pipeline_hard_proreq` and hard-proreq pipeline controls
- This is already documented as a deliberate narrow allowlist in `docs/cento-mcp-server.md`.

## 4) Dev Pipeline state (hard-proreq, live artifacts)

### 4.1 Run selection and status

- Latest hard-proreq run ID (known): `hard-proreq-task-hard-proreq-project-20260505T050416185358Z`
- Execution run object:
  - `workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/execution_run.json`
  - status: `completed`
  - pipeline: `hard-proreq-task-hard-proreq-project`
  - source: `cento-hard-proreq-pro`
  - run_id: `hard-proreq-task-hard-proreq-project-20260505T050416185358Z`
  - stages: `input,repo,blueprint,factory,validation,handoff`
  - artifact count: `20`

### 4.2 Artifact snapshots

- Canonical latest run path:
  - `workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/latest/`
- Latest run mirror path:
  - `workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/hard-proreq-task-hard-proreq-project-20260505T050416185358Z/`
- Representative files present under latest:
  - `operator_intake.json`
  - `mini_cento_context.json`
  - `ui_screenshot_request.json`
  - `pro_backend_request.json`
  - `image_generation_request.json`
  - `image_generation_response.json`
  - `pro_output_schema.json`
  - `parallel_patch_workset.json`
  - `story_index.json`
  - `stories/*.json` + `stories/*.validation.json`
  - `backend_work_manifest.json`
  - `manifest_integration_policy.json`
  - `integration_plan.json`
  - `validation_plan.json`
  - `hard_proreq_evidence.json`
  - screenshot files: `existing_ui_reference.png`, `existing_ui_reference_square.png`, `generated_integrator_screenshot.png`

### 4.3 Command references for pipeline contracts

- `cd /home/alice/projects/cento && sed -n ... docs/dev-pipeline-run-contracts.md`
- `cd /home/alice/projects/cento && python3 scripts/dev_pipeline_hard_proreq.py --help`
- `cd /home/alice/projects/cento && python3 scripts/dev_pipeline_hard_proreq.py all`
- `cd /home/alice/projects/cento && python3 scripts/agent_work_app.py` (dev-pipeline route wiring lives here)

### 4.4 Recent hard-proreq history

- `workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/` currently contains `37` historical run folders (plus `latest`), showing continuous execution cadence across previous timestamps.

## 5) Parallel-delivery lane

- Status command: `cd /home/alice/projects/cento && python3 scripts/parallel_delivery.py status --json`
- Current status (as of run):
  - `run_dir`: `workspace/runs/parallel-delivery/vp-e2e-20260505T0230Z`
  - `status`: `completed`
  - `pass_count`: `12`
  - `validation`: `passed`
  - `demo`: `completed`
- Validation summary path:
  - `workspace/runs/parallel-delivery/vp-e2e-20260505T0230Z/validation_summary.json`
  - checks include `proreq.pass_count 12/12`, `proreq.completed 12/12`, `proreq.workset_checks 12/12`, `demo.status completed`
- Execution manifest path:
  - `workspace/runs/parallel-delivery/vp-e2e-20260505T0230Z/execution_manifest.json`
- Implementation manifest path:
  - `workspace/runs/parallel-delivery/vp-e2e-20260505T0230Z/implementation_manifest.json`
  - target: `workers=10`
  - integrator policy: `only-if-needed`, reviewer profile `api-mini-integrator`
- Receipt paths:
  - `workspace/runs/parallel-delivery/vp-e2e-20260505T0230Z/proreq_receipt.json`
  - `workspace/runs/parallel-delivery/vp-e2e-20260505T0230Z/proreq_receipt.partial.json`
- Demo paths:
  - `workspace/runs/parallel-delivery/vp-e2e-20260505T0230Z/demo/demo_receipt.json`
  - `workspace/runs/parallel-delivery/vp-e2e-20260505T0230Z/demo/workset.json`
  - `.cento/worksets/parallel_delivery_demo_vp_e2e_20260505t0230z_20260505023500154341/workset_receipt.json`

## 6) Build/workset/factory surfaces

### 6.1 Build

- Script: `scripts/cento_build.py`
- Command surfaces: `docs/cento-build.md`, `cento build ...`
- Key outputs under `.cento/builds/<build_id>/`:
  - `manifest.json`
  - `workers/<worker-id>/...` (`worker_artifact.json`, `patch_bundle.json`, `patch.diff`, `handoff.md`)
  - `integration_receipt.json`
  - `validation_receipt.json`
  - `apply_receipt.json`
  - `taskstream_evidence.json`
  - `events.ndjson`

### 6.2 Workset

- Script: `scripts/cento_workset.py`
- Command surfaces: `docs/cento-workset.md`, `cento workset ...`
- Live workset run directories:
  - `.cento/worksets/<workset_id>/`
  - Includes `workset.json`, `leases.json`, `workset_receipt.json`, `workset_evidence.json`, `events.ndjson`, `workers/*/`
- Build artifacts produced for workset tasks:
  - `.cento/builds/workset_<run_id>_<task_id>/...` (manifest, workers, integration/validation/apply receipts)

### 6.3 Factory

- Script: `scripts/factory.py` plus integrations under `scripts/factory_*`
- Command surfaces: `docs/factory.md`, `docs/factory-integration.md`, `docs/factory-autopilot.md`
- Run state under `workspace/runs/factory/<run-id>/`
- Contract outputs include:
  - `intake.json`
  - `constraints.json`
  - `context-pack.json`
  - `factory-plan.json`
  - `tasks/<task-id>/story.json`
  - `tasks/<task-id>/validation.json`
  - `tasks/<task-id>/dispatch.json`
  - `dispatch-plan.json`
  - `integration/*`
  - `release-packet.md`, `project-delivery.md`, `summary.md`
- Factory also depends on runtime adapters under `factory/runtime/*`

## 7) Agent-work board and dispatch state

### 7.1 Live board summary

- `cd /home/alice/projects/cento && python3 scripts/agent_work.py list --json | jq`:
  - total issues: `30`
  - status: `Blocked 2`, `Queued 25`, `Running 2`, `Validating 1`
  - role: `builder 24`, `validator 3`, `coordinator 3`
  - package: `agent-ops 14`, `default 12`, `kanji-a-day-watch-mvp 2`, `kanji-a-day 1`, `redmine-retirement-e2e-v1 1`
  - source: `local 16`, `taskstream 14`
  - nodes: `linux 13`, `macos 2`, blank `15` (legacy/unknown node fields)
- `cd /home/alice/projects/cento && python3 scripts/agent_work.py runs --json --active --no-untracked`
  - `runs: []`, `count: 0` (tracked active=0 at snapshot time)

### 7.2 Recovery and stale-state

- `cd /home/alice/projects/cento && python3 scripts/agent_work.py recovery-plan --json`
  - board after snapshot: `Queued 27`, `Running 2`, `Validating 1`, `Blocked 2`
- Reported manual/interactive sessions: 4 untracked interactive `node=linux` sessions.
- Reported stale runs: 5 (`stale_no_process`) from mixed agent roles with prior codex/claude sessions.
- Candidate safe follow-ups were generated for internal artifact gaps:
  - issue `1000175`
  - issue `1000173`

### 7.3 Pool dispatch planning

- `cd /home/alice/projects/cento && python3 scripts/agent_pool_kick.py --dry-run`
  - active counts: builder/validator/small/coordinator = `0/0/0/0`
  - targets: builder `4`, validator `3`, small `3`, coordinator `1`
  - run mode: `dry_run=true`
  - planned launches included queued issues in validator and builder lanes (8 total planned records in sample)
  - no launches actually started because dry-run mode
- `cd /home/alice/projects/cento && python3 scripts/agent_pool_kick.py --help`
  - flags: `--builder-target`, `--validator-target`, `--small-target`, `--coordinator-target`, `--max-launch`, `--dry-run`
  - confirmed **no `--json` flag** on this script

### 7.4 CLI vs docs mismatch (resolved)

- `docs/agent-work-runtimes.md` and `docs/agent-work.md` previously described the pool-dispatch subcommand with `--limit` / `--execute` / `--json`; those references have been removed and the docs now direct to `agent-pool-kick` and `agent-work dispatch`.
- `python3 scripts/agent_work.py --help` includes subcommands:
  - `dispatch`, but not a pool-dispatch subcommand
  - the docs/CLI mismatch has been resolved.

### 7.5 Cluster/MCP for dispatch checks

- MCP tool check:
  - `python3 scripts/cento_mcp_server.py --call-tool cento_cluster_status --arguments '{}'`
  - mesh/socket state observed:
    - linux: `connected`
    - macos: `connected`
    - iphone: `disconnected`
- CLI check:
  - `python3 scripts/cento.sh cluster status`
  - confirms same topology and local socket locations:
    - `/tmp/cento-linux.sock`
    - `/tmp/cento-mac.sock`

## 8) Current canonical risks and immediate action items

1. **MCP narrowness**: MCP remains intentionally limited; board and task work is only partially bridged, and many execution domains are CLI-only.
2. **pool-dispatch drift** *(resolved)*: stale pool-dispatch subcommand references in `docs/agent-work.md` and `docs/agent-work-runtimes.md` have been removed; the current surface is `agent-pool-kick` or per-issue `agent-work dispatch`.
3. **proof/status cohesion**: hard-proreq `execution_run.json` is complete but `proof`/`validation` top-level fields are not always materialized with one canonical status object, while receipts exist and are present in artifacts.
4. **agent-work runtime posture**: automated dispatch is effectively Claude-only due to `codex` weight set to `0`, so run planning is not the originally mixed profile.

---

## Target Architecture

_Integrated from `workspace/runs/ai-cento-native-execution-plan/20260505T051319Z/sections/target_architecture.md`._

# Cento AI Native Target Architecture

_Reference source: `docs/ai-cento-native-rework-research.md` (2026-05-04). This section is a canonical target design derived from observed Cento behavior and run artifacts, not a claim that all items are already implemented.

## Objective

Define a single Cento-native execution model where every AI request is converted into deterministic contracts, routed through MCP/CLI surfaces, executed in bounded lanes, and judged by evidence artifacts before handoff.

This section is intentionally “AI-readable”:

- strict named layers,
- explicit ownership and budgets,
- deterministic state transitions,
- source/receipt-driven evidence.

## 1) Core layers

### 1.1 Intent Route

**Purpose:** classify inbound work into a concrete route and execution template before any planning/model call.

**Inputs:** raw prompt, issue context, screenshots, route hints.

**Observed evidence from current behavior:** hard-proreq and parallel-pipeline template routing already happen from API run posts and `schema_version` enforcement in existing run contracts.

**Canonical output (`cento.intent_route.v1`):**

```json
{
  "schema_version": "cento.intent_route.v1",
  "request_id": "string",
  "timestamp": "2026-05-05T05:13:19Z",
  "source": {
    "kind": "chat_prompt|issue|ui_run|cli",
    "origin_url": "",
    "issue_id": ""
  },
  "routing": {
    "project_id": "hard-proreq-project|parallel-pipeline-project|...",
    "template_id": "hard-proreq-task|parallel-task|...",
    "mode_hint": "planner-only|executor|evidence-only|handoff-only",
    "requires_taskstream": false,
    "requires_model": true,
    "requires_human_review": false
  },
  "runtime_constraints": {
    "planner_model": "required|optional|forbidden",
    "builder_model": "codex-fast|codex-medium|none",
    "validator_tier": "deterministic-first|model-assisted|manual",
    "muted_frontend_lane": true
  },
  "required_context": [
    "project-manifest",
    "templates",
    "owned-paths",
    "tool-surface"
  ],
  "next_action": "intent-route"
}
```

**Routing invariants (must-haves):**

- If a matching MCP/CLI route exists, pick it before ad-hoc shell actions.
- If no durable route exists, return `blocked` with explicit evidence (`route_missing`), then fail before model mutation.
- Routes that require model calls must still produce this object before model invocation.

---

### 1.2 Context Bundle

**Purpose:** provide the planner and execution lanes with short-circuit evidence and bounded context.

Current implementation currently writes a hard-proreq `mini_cento_context.json`; this design treats that as a subset of a generalized bundle.

**Canonical object (`cento.context_bundle.v1`):**

```json
{
  "schema_version": "cento.context_bundle.v1",
  "source": "cento-intent-route",
  "run_id": "ai-run-20260505T051319Z",
  "inputs": ["prompt", "issue", "screenshot"],
  "facts": {
    "gather_context": {"status": "passed", "artifact": "workspace/runs/.../context_bundle/gather-context.json"},
    "dirty_state": {"status": "passed", "dirty_files": []},
    "tool_surface": {
      "cento_tools_count": 45,
      "mcp_tools_available": true
    },
    "repo_health": {
      "git_head": "",
      "protected_paths_detected": [".git", ".env", "node_modules"]
    }
  },
  "path_contract": {
    "owned_candidates": [],
    "read_scope": ["docs/", "scripts/", "src/"],
    "write_forbidden": [".git", ".env", "node_modules"]
  },
  "evidence": {
    "tool_snapshots": [],
    "search_hits": [],
    "recent_failures": []
  },
  "expires_at": "2026-05-05T05:43:19Z"
}
```

**Context rules:**

- No writes in this layer.
- Should include evidence-bearing outputs rather than narrative claims.
- Expiry is required to avoid stale preflight.

---

### 1.3 AI Run Envelope

**Purpose:** one durable top-level contract that normalizes all current run families into a single inspectable object.

Current codebase already has multiple manifest families (`story`, `validation`, `execution_run`, `workset`, various `hard_proreq` and `workset_receipt` artifacts). The envelope is missing today; this is the missing normalization point.

**Canonical object (`cento.ai_run.v1`) (portable, source-agnostic):**

```json
{
  "schema_version": "cento.ai_run.v1",
  "run_id": "ai-run-20260505T051319Z",
  "created_at": "2026-05-05T05:13:19Z",
  "source": {
    "kind": "chat_prompt|taskstream|issue|ui",
    "origin": "https://.../dev-pipeline-studio#pipeline-flow",
    "requester": "operator-id"
  },
  "state": {
    "lifecycle": "queued|running|completed|blocked|failed|accepted",
    "validation": "pending|deterministic|model-review|manual-review",
    "proof": "missing|partial|passed|failed"
  },
  "route": "cento.intent_route.v1 reference",
  "context": "cento.context_bundle.v1 reference",
  "contracts": {
    "story": "workspace/.../story.json",
    "validation": "workspace/.../validation.json",
    "workset": "workspace/.../workset.json",
    "pipeline_manifest": "workspace/.../pipeline_manifest.json",
    "execution_run": "workspace/.../execution/execution_run.json"
  },
  "execution": {
    "runtime": "cento-native|cento-workset|cento-build|cento-factory|api-openai-pro",
    "lane_status": {
      "planner": "running",
      "builder": "queued",
      "validator": "queued",
      "integrator": "queued",
      "evidence": "queued"
    },
    "cost_usd": 0.0,
    "budget_usd_cap": 20.0,
    "budget_usd_soft": 10.0
  },
  "artifacts": {
    "current": [],
    "received": [],
    "required": [
      "hard_proreq_evidence.json",
      "validation_plan.json",
      "workset_receipt.json",
      "taskstream_evidence.json"
    ]
  },
  "receipts": [],
  "handoff": {
    "status": "review|blocked|ready|delivered",
    "next_action": "run-validator|promote-workset|open-taskstream-issue|re-run"
  }
}
```

---

### 1.4 Contract Planner

**Purpose:** split execution into enforceable artifacts before any code mutation.

Current pattern: hard-proreq emits schema-backed plan + ten story manifests + workset/integration/validation manifests. That behavior should be preserved but normalized by `ai_run`.

**Inputs:** `intent_route`, `context_bundle`, operator objective.

**Outputs:** one of: `story.json`, `workset.json`, `pipeline_manifest`, `validation_plan`, `integration_policy`.

**Contract invariants:**

- `execution_model` must be explicit (`deterministic`, `api-openai`, `api-openai-parallel`, `local-builder`, `factory`, `noop`).
- Every writing lane must declare `owned_paths` (non-empty unless `planning-only`).
- Every mutation lane must declare `read_paths`, `forbidden_paths`, and `runtime`.
- Validation plan must be generated before model-lane output is accepted.
- Planner output is only accepted when JSON schema matches and no unknown manifest references exist.

**Ownership rules in planner output:**

- Planner lane owns only planning artifacts, no repository writes.
- Builder lane may mutate only `owned_paths` after conflict checks.
- Integrator lane owns merge/apply decisions and final acceptance.

---

### 1.5 Execution Lanes

Execution is always decomposed into lane graph (can run serially/parallel). The graph below is canonical for this architecture.

```text
Intent Route -> Context Bundle -> Contract Planner
      -> Planner Lane (no writes)
      -> Builder Lane (bounded writes)
      -> Validator Lane (evidence-first)
      -> Integrator Lane (serialized if multiple workers)
      -> Evidence Lane (proof + handoff)
```

#### Planner Lane

- **Function:** plan and decompose work.
- **Allowed runtime:** no-model or model, but no writes.
- **Inputs:** route + context + prior failures.
- **Outputs:** signed planner artifacts and lane assignments.
- **Failure:** schema mismatch, missing required context, unknown template, invalid route.

#### Builder/Producer Lanes

- **Function:** create patch proposals or worker artifacts.
- **Allowed runtime:** bounded workset/build/runtime profile (`codex-fast` and similar).
- **Path policy:** explicit owned-write paths only.
- **Evidence required:** request/response artifacts, worker outputs, command receipts.
- **Muting:** non-critical optional lanes (e.g. screenshot) can be muted and marked non-blocking.

#### Validator Lane

- **Function:** deterministic-first check of artifacts.
- **Allowed runtime:** command/file/url/screenshot validation by default; model review only if validation manifest requests escalation.
- **Mandatory:** produce evidence artifacts before marking validation passed.
- **Rule:** subjective interpretation is not a replacement for evidence.

#### Integrator Lane

- **Function:** converge worker outputs through a single, serial apply path.
- **Failure model:** any failed worker integration halts downstream gates unless `degrade` policy is explicit.
- **Receipts required:** integration receipt + evidence references.

#### Evidence Lane

- **Function:** collect and normalize proof, cost, and residual risk.
- **Artifacts:** evidence bundle, budget receipts, proof statuses, handoff notes.
- **Output:** review-ready summary with Delivered/Validation/Evidence/Residual Risk structure (current validator lane guidance already follows this format).

---

### 2) Lifecycle state model

Use one canonical lifecycle for each run and normalize source-layer states into it.

#### 2.1 Run lifecycle (high-level)

1. `created`
2. `routed`
3. `context_bundled`
4. `contract_ready`
5. `queued`
6. `running`
7. `validated`
8. `evidence_ready`
9. `handoff_ready`
10. `accepted`

Allowed terminal states: `blocked`, `rejected`, `failed`.

#### 2.2 Lane state set

- `accepted`
- `completed`
- `running`
- `queued`
- `blocked`
- `failed`
- `muted`
- `separate-flow`

#### 2.3 Source normalization map (canonical)

- Existing accepted/merged/passed -> `accepted`.
- Completed/running statuses from execution steps -> `running`.
- blocked/dependency-blocked/budget-blocked/budget-exceeded -> `blocked`.
- failed -> `failed`.
- muted/separate-flow/deferred -> `muted` (non-blocking lane).

#### 2.4 State transitions (contract)

- `created -> routed -> context_bundled` is automatic when route and context are persisted.
- `contract_ready -> queued` requires planner manifest success and path ownership checks.
- `queued -> running` after lane dispatch confirmation.
- `running -> validated` only after validator returns evidence-backed pass/fail.
- `validated -> evidence_ready` requires evidence bundle existence and integrity.
- `evidence_ready -> handoff_ready` requires review constraints met (e.g., deterministic check pass, required evidence refs).
- `handoff_ready -> accepted` only via review/action lane.

Failure transitions:

- Any stage can transition to `blocked` if prerequisites missing.
- Any hard runtime failure -> `failed` and no downstream mutation.

---

### 3) Data flow

```text
Operator / Taskstream / API
  -> route.id decision
  -> context artifacts + git/tool snapshot
  -> ai_run envelope creation
  -> contracts: story / workset / validation / pipeline manifest
  -> dispatch lanes
    -> model planner output
    -> workset/build output artifacts
    -> integration receipts
    -> validator receipts + costs
  -> evidence bundle
  -> Taskstream or UI handoff
```

**Mandatory envelope linkage for every artifact path:**

- Every artifact includes `run_id` and `run_manifest` backlink where supported.
- Evidence cards must carry run references to avoid UI/run ambiguity.
- Lane-specific receipts must be retrievable by both MCP and UI with the same path convention.

---

### 4) Ownership, budget, and runtime rules

#### 4.1 Ownership

- **Owner of contract:** `cento_intent_route` + Planner lane.
- **Owner of repo changes:** Builder/Workset lanes only.
- **Owner of evidence claims:** Evidence lane and Validator lane.
- **Owner of release/status handoff:** Integrator/Validator gate path.

#### 4.2 Budget rules

- Hard-cap and soft-cap are explicit in run execution config (observed defaults in current hard-proreq planning: soft 10.00 USD, hard 20.00 USD target).
- All runs must track:
  - `budget_usd_soft`
  - `budget_usd_cap`
  - `budget_spent`
  - `budget_breaches`
- If runtime costs are not measurable, run is blocked as `evidence_missing` rather than silently accepted.
- A blocked-lane rule for cost: any hard-cap exceed transitions to `blocked` and records `budget_exceeded`.

#### 4.3 Runtime rules

- No-model-first for context/route/validation command lane.
- Planner may be model-backed but cannot write repo.
- Builder mutations require explicit runtime profile and path ownership.
- Validator uses deterministic commands first; model review is explicit escalation only.
- Proof/muted lanes cannot block unless explicitly configured as `blocking`.

---

### 5) Evidence gate

Evidence gate is the control boundary before any handoff.

#### 5.1 Evidence inputs

- Schema checks for each referenced manifest.
- Required artifact existence.
- Deterministic command/test results.
- Optional screenshot/file capture.
- Budget and receipt consistency.

#### 5.2 Source-dependent proof resolver

The gate resolves proof by run source:

- hard-proreq source -> `hard_proreq_evidence.json` + `validation_plan.json` + validator outputs
- workset source -> `workset_receipt`
- build source -> build/apply/evidence receipts
- factory source -> factory integration/release receipts

#### 5.3 Gate outputs

- `proof_status = passed` only when required evidence references resolve.
- `proof_status = failed` when any required item is missing/invalid.
- `proof_status = partial` when optional lanes are missing but not required.
- `proof_status = missing` when evidence lane has no artifacts.

---

### 6) Evaluation loop

To keep the runtime self-correcting, every run must write evaluation metrics tied to `ai_run`.

Required metrics:

- route accuracy (classification confidence, re-route count)
- time-to-contract (prompt to planner complete)
- time-to-proof (prompt to evidence_ready)
- contracts complete rate
- validator deterministic pass rate
- failed/blocked causes by class
- percentage of direct shell calls bypassing Cento/MCP
- residual human risk categories and review comments
- cost per accepted run

Loop behavior:

1. append metric row at each state transition,
2. aggregate nightly into a run-quality report,
3. expose regression alerts if any threshold drifts (e.g., blocked rate, missed evidence).

---

### 7) Failure modes and controls

| Failure mode | Typical detection | Control action |
| --- | --- | --- |
| Route mismatch | route schema invalid / no template match | `blocked` with `route_not_supported`, request user reroute |
| Stale context | context artifact expired or missing | `blocked` + rebuild context bundle |
| Unowned path write | ownership overlap or forbidden prefix write | `blocked`; auto-rewrite planner contracts |
| Model fallback ambiguity | plan generated from cached/fallback source but source not recorded | fail evidence gate; require explicit `source_note` |
| Validation mismatch | UI proof says complete but receipts missing | fail evidence gate and sync status normalizer |
| Validation command failure | required command exits !=0 or file empty | mark `failed`, keep artifacts and return recovery guidance |
| Budget breach | `budget_spent > budget_usd_cap` | `blocked`, freeze execution, escalate to operator |
| Receipt desync | step status not reflected in run envelope | reject status publish, re-run proof resolver |
| Human-review drift | missing residual-risk section | reject handoff gate |

---

## 8) Parallel Spark lane split for execution

Use Spark lanes as independent contributors with strict artifact contracts.

- **Lane A – Routing + Context Extraction**
  - owns: intent route, context bundle generation, preflight checks
  - outputs: `intent_route`, `context_bundle`, preflight status
  - success criteria: route complete and context valid

- **Lane B – Contract and Planner Fabrication**
  - owns: story/workset/validation contract generation and manifest normalization
  - outputs: `story`, `validation`, `workset`, contract artifacts linked to `ai_run`
  - success criteria: explicit ownership, paths, runtime, and budget fields

- **Lane C – Execution & Evidence (build + validation + gate)**
  - owns: model/Builder lanes, workset dispatch, validator execution, evidence collection, proof resolution
  - outputs: lane receipts, evidence bundle, cost receipts, review-ready handoff
  - success criteria: evidence completeness and deterministic checks

- **Lane D – Runtime/Compliance and Recovery (coordination lane)**
  - owns: state normalization, status harmonization, escalation routing, failure taxonomy, and post-run metrics update
  - outputs: stable status map and evaluation records
  - success criteria: no blocked/failed silent transitions

### Coordination contracts

- Contracts between lanes are file-backed and JSON schema checked.
- No lane may mutate artifacts owned by another lane except through approved handoff.
- All lanes must write append-only event records (`events.ndjson` style) with `run_id`, `lane`, `status_before`, `status_after`, `artifact`, `error_code`.

---

### Minimal coordination checklist (for any lane)

- `[ ]` route + context artifacts are present and valid
- `[ ]` ownership is explicit for every writable path
- `[ ]` budgets are loaded (`soft`, `cap`, currency)
- `[ ]` runtime profile is explicit (`local`, `api`, `noop`, `fixture`)
- `[ ]` evidence IDs map to real files/commands
- `[ ]` proof gate can calculate PASS/FAIL/PARTIAL
- `[ ]` state transitions are deterministic and recorded

---

## 9) Status of source evidence vs targets

- **Already observed today:** hard-proreq lane decomposition, muted screenshot lane, schema-backed planning requests, workset manifests, deterministic validation orientation, and dedicated evidence artifacts.
- **Target gap to implement:** universal `cento.ai_run.v1`, normalized proof source resolver, and unified UI proof/validation status mapping across pipeline and workset routes.
- **Risk note:** this architecture is implementation-ready, but execution of every section above depends on explicit coding and schema/test coverage.

---

## Proposed Interfaces

_Integrated from `workspace/runs/ai-cento-native-execution-plan/20260505T051319Z/sections/interfaces.md`._

# AI Native Interface Draft (Proposed)

## Scope and status

This is a **proposed**, future-only interface contract for Spark coordination. It is intentionally canonical, machine-readable-first, and narrow.

All fields marked `proposed: true` are new and not current in the repo.

## Cross-lane split (for execution planning)

- Lane 1 (schemas): own the contract IDs and JSON field contracts.
- Lane 2 (Dev Pipeline): implement API/MCP read/start/show/proof and evidence resolution.
- Lane 3 (runtimes/scan): implement `scan` and runtime surface, then wire to AI handoff.
- Lane 4 (this lane): define complete proposed interfaces, coordinate signatures, and keep CLI/MCP behavior aligned.

## Proposed schema: `cento.intent_route.v1`

```json
{
  "schema_version": "cento.intent_route.v1",
  "proposed": true,
  "route_id": "route-hard-proreq-2026-05-05-01",
  "request_id": "chat-2026-05-05-0513",
  "input": {
    "raw_text": "...",
    "screenshot": "optional/path.png",
    "issue_id": "optional",
    "source": "chat|ui|api|issue|file",
    "tenant": "cento-local",
    "cwd": "."
  },
  "policy": {
    "prefer_mcp": true,
    "allow_model_fallback": true,
    "risk_hint": "low|medium|high",
    "max_budget_usd": 20.0
  },
  "decision": {
    "route": "hard-proreq|generic-task|workset|build|factory|scan|runtime-list|docs-evidence|unknown",
    "requires_taskstream": false,
    "requires_model": true,
    "requires_human": false,
    "validation_mode": "no-model|model|human-review",
    "next_command": "cento ai-run plan --route hard-proreq",
    "confidence": 0.0
  },
  "selected_inputs": ["project_id", "template_id", "runtime_profile"],
  "generated_at": "2026-05-05T05:13:19Z"
}
```

`cento intent-route` (proposed CLI) and `cento_intent_route` (proposed MCP) map free-form requests into the above object.

CLI behavior (proposed):

- `cento ai-route <text> --source ui|chat|issue|file --request-id ...`
- `cento ai-route --json --dry-run ...`
- Deterministic fields: same input plus route classification and suggested next command.

MCP behavior:

- Tool: `cento_intent_route`
- Input: `{ "raw_text": string, "source": "chat|ui|issue|file", "request_id": string, "risk_hint": "low|medium|high" }`
- Output: command/CLI-like payload plus full `cento.intent_route.v1` object.

## Proposed schema: `cento.context_bundle.v1`

```json
{
  "schema_version": "cento.context_bundle.v1",
  "proposed": true,
  "bundle_id": "context-hard-proreq-20260505T051319Z",
  "run_dir": "workspace/runs/ai-cento-native-execution-plan/20260505T051319Z/contexts/..",
  "source_route": "route-id",
  "collected_at": "2026-05-05T05:13:19Z",
  "gather": {
    "tools": ["cento tools", "cento platforms", "cento runtime list --json", "cento scan --query"],
    "dirty_repo": true,
    "dirty_paths": ["scripts/foo.py"],
    "protected_paths_touched": [".cento/config"],
    "context_files": ["workspace/runs/.../mini_cento_context.json"]
  },
  "constraints": {
    "blocked_actions": ["openai:network-call", "cross-repo-edit"],
    "allow_creates": false,
    "allow_unowned_paths": false
  },
  "evidence_refs": [
    {
      "type": "json",
      "path": "workspace/runs/.../context_scan.json",
      "source": "scan/cento_scan"
    }
  ]
}
```

CLI behavior (proposed):

- `cento ai-context --route-id ... --json --collect`
- Emits a persisted bundle path and prints JSON when `--json`.
- Uses existing `cento gather-context --no-remote` and deterministic local scans.

MCP behavior:

- Tool: `cento_context_bundle`
- Output fields: includes `schema_version`, bundle path, collected constraints, tool registry summary, scan counters, and artifact refs.

## Proposed schema: `cento.ai_run.v1` (new top-level envelope)

```json
{
  "schema_version": "cento.ai_run.v1",
  "proposed": true,
  "id": "ai-run-hard-proreq-2026-05-05T051319Z",
  "status": "planned|running|blocked|complete|failed",
  "route_id": "route-hard-proreq-...",
  "created_at": "2026-05-05T05:13:19Z",
  "source": {
    "kind": "chat_prompt|issue|pipeline|scan",
    "value": "..."
  },
  "route": {
    "decision_id": "route-id",
    "kind": "hard-proreq",
    "requires_model": true,
    "requires_human": false,
    "validation_mode": "no-model|model|human-review"
  },
  "context": {
    "bundle": "workspace/runs/.../context_bundle.json",
    "commands": ["cento context --bundle ...", "cento scan --query ..."]
  },
  "contracts": {
    "pipeline_manifest": "workspace/runs/dev-pipeline-studio/docs-pages/latest/pipeline_manifest.json",
    "workset": "workspace/runs/.../workset.json",
    "build_manifest": "workspace/runs/.../manifest.json",
    "story": "workspace/runs/.../story.json",
    "validation": "workspace/runs/.../validation.json"
  },
  "execution": {
    "kind": "dev_pipeline|workset|build|factory",
    "runtime": "cento-native + GPT-pro",
    "model": "gpt-5.x",
    "run_id": "hard-proreq-task-hard-proreq-project-...",
    "artifacts_root": "workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/..."
  },
  "receipts": [
    {
      "kind": "validation|integration|apply|proof",
      "path": ".../validation_receipt.json",
      "status": "passed|failed|muted|missing"
    }
  ],
  "proof": {
    "status": "passed|failed|missing",
    "missing": ["..."],
    "next_action": "run validator|re-collect artifact|blocked-by-policy",
    "score": 0.0
  },
  "metrics": {
    "cost_usd": 0.12,
    "duration_ms": 12000,
    "validation_hits": 3,
    "missing_inputs": 0
  }
}
```

CLI behavior (proposed):

- `cento ai-run create --route-id ... --context-bundle ... --json`
- `cento ai-run show <run-id> --json`
- `cento ai-run check <run-id> --require-proof` validates envelope and evidence.

MCP behavior:

- `cento_ai_run_create`: creates envelope and links contracts.
- `cento_ai_run_show`: reads envelope, contracts, run state, receipts, and proof summary.
- `cento_ai_run_check`: verifies contract/receipt consistency and emits canonical missing/error list.

## Proposed evidence check contract

### `cento.evidence_check.v1`

```json
{
  "schema_version": "cento.evidence_check.v1",
  "proposed": true,
  "subject": {
    "kind": "ai_run|dev_pipeline_run|build|workset|factory",
    "id": "ai-run-hard-proreq-..."
  },
  "status": "ok|warn|fail",
  "checks": [
    {
      "name": "schema",
      "status": "ok",
      "details": "schema_version present and valid"
    }
  ],
  "artifacts": {
    "required": ["pipeline_manifest.json", "validation_receipt.json"],
    "found": ["pipeline_manifest.json"],
    "missing": ["validation_receipt.json"]
  },
  "receipts": {
    "validation": "workspace/runs/.../validation_receipt.json",
    "proof": "workspace/runs/.../evidence_bundle.json",
    "model": "cento.openai-worker"
  },
  "recommended_next": ["run cento_ai_run_check", "re-run validator", "attach evidence bundle"],
  "checked_at": "2026-05-05T05:13:19Z"
}
```

CLI behavior:

- `cento evidence check <ai-run|run-dir|dev-run-id> --json`
- Option `--require-proof` exits non-zero unless proof and minimum deterministic checks pass.

MCP behavior:

- Tool: `cento_evidence_check`
- Input: `{"subject_kind":"ai_run|workset|build|factory", "subject_id":"...", "strict":false, "require_proof":true}`
- Output: status + missing/mismatch matrix + command replay bundle.

## Dev Pipeline interfaces (read/start/show/proof)

### Shared run object (proposed `cento.dev_pipeline_run.v1`)

```json
{
  "schema_version": "cento.dev_pipeline_run.v1",
  "proposed": true,
  "run_id": "hard-proreq-task-hard-proreq-project-2026...",
  "pipeline": {
    "project_id": "hard-proreq-project",
    "template_id": "hard-proreq-task",
    "status": "queued|running|completed|failed",
    "source": "api|ui|cli",
    "started_at": "2026-05-05T05:13:19Z",
    "elapsed_ms": 8400
  },
  "inputs": [
    { "id": "operator-thoughts", "kind": "questionnaire", "source": "user", "status": "ok" }
  ],
  "proof": { "status": "pending|passed|failed", "source": "run-kind" },
  "artifacts_root": "workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/...",
  "artifact_count": 12,
  "links": {
    "state": "/api/dev-pipeline-studio?project=...&template=...",
    "manifest": "pipeline_manifest.json"
  }
}
```

API behavior (existing endpoints, behavior alignment target):

- `GET /api/dev-pipeline-studio?project=...&template=...` -> studio state + selected template metadata.
- `POST /api/pipeline-runs` accepts a proposal-shaped request and returns run envelope.
- `GET /api/pipeline-runs/<run-id>` (proposed new, if not present): return `cento.dev_pipeline_run.v1` for a single run.
- `GET /api/pipeline-runs/<run-id>/proof` (proposed): source-dependent proof object.

MCP tools (proposed):

- `cento_dev_pipeline_state`: read state + templates.

  - Input: `{ "project_id":"", "template_id":"", "run_id":"", "include_artifacts":true }`
  - Output: state object plus curated `proposed`/`current` proof fields.

- `cento_dev_pipeline_run_start`: start a pipeline run.

  - Input: `{ "project_id":"...", "template_id":"...", "inputs":[{ "id":"...", "kind":"questionnaire", "value":... }], "request_id":"...", "dry_run":false, "schema_version":"cento.pipeline_run_request.v1" }`
  - Output: `{ "run_id": "...", "run": "cento.dev_pipeline_run.v1", "queued_artifacts": [...] }`

- `cento_dev_pipeline_run_show`: fetch per-run payload.

  - Input: `{ "run_id":"...", "artifact_paths":true }`
  - Output: `cento.dev_pipeline_run.v1`.

- `cento_dev_pipeline_run_proof`: source-aware proof resolver.

  - Input: `{ "run_id":"...", "check_mode":"minimum|strict" }`
  - Output: `cento.evidence_check.v1`-compatible proof section.

CLI behavior (proposed):

- `cento dev-pipeline state --project ... --template ... --json`
- `cento dev-pipeline run start --project ... --template ... --input-file ... --json`
- `cento dev-pipeline run show <run-id> --json`
- `cento dev-pipeline run proof <run-id> --strict --json`

## Runtime list interface

Existing CLI target behavior to align:

- `cento runtime list --json` returns profile list with status + executable availability.

Proposed MCP tool:

### `cento_runtime_list`

Input:

```json
{ "json": true, "name": "", "require_executable": false, "include_errors": false }
```

Output shape (minimal):

```json
{
  "schema_version": "cento.runtime_list.v1",
  "proposed": true,
  "profiles": [
    {
      "name": "codex-fast",
      "type": "command|fixture",
      "status": "passed|failed|warning",
      "timeout_seconds": 180,
      "max_changed_files": 80,
      "executable": "codex",
      "executable_available": true,
      "errors": [],
      "warnings": ["..."]
    }
  ]
}
```

CLI/GUI behavior:

- `cento runtime list --json` accepted in machine mode.
- `cento runtime check <name> --json --require-executable` for single profile.
- MCP returns same shape, and write tools must reference it for deterministic runtime choice.

## Scan interface

CLI behavior (existing + proposed additions):

- Existing: `cento scan --query <expr> [--no-open|--regex|--case-sensitive|--limit]`
- Proposed extension: `--json` to print machine payload directly (without HTML lookup dependency).

Proposed MCP tool: `cento_scan`

Input:

```json
{ "schema_version": "cento.scan_request.v1", "proposed": true, "query": "agent_work", "root": ".", "regex": false, "case_sensitive": false, "limit": 12, "open_browser": false, "json": true }
```


Output:

```json
{
  "schema_version": "cento.scan_result.v1",
  "proposed": true,
  "query": "agent_work",
  "root": "/home/alice/projects/cento",
  "matched_files": 31,
  "total_matches": 188,
  "scanned_files": 900,
  "top_files": [ { "relative_path": "scripts/agent_work_app.py", "count": 12 } ],
  "summary_path": "workspace/runs/scan-onepager/latest/summary.json",
  "html_path": "workspace/runs/scan-onepager/latest/index.html"
}
```

## Build tool interfaces (proposed MCP wrappers)

Each MCP write tool is read-only-safe by default unless explicitly invoked.

Proposed canonical request envelope:

```json
{
  "schema_version": "cento.build_command_request.v1",
  "proposed": true,
  "command": "init|check|worker_run|integrate|apply|artifact_check|bundle_synthesize|receipt",
  "args": {},
  "json": true,
  "require_ok": false,
  "timeout_seconds": 120
}
```

Standard MCP response:

```json
{ "ok": true, "exit_code": 0, "command": ["cento", "build", "..."], "stdout": "...", "stderr": "...", "artifacts": [".cento/builds/..."] }
```
Commands to expose:

- `cento_build_init`: map to `cento build init`.
- `cento_build_artifact_check`: map to `cento build artifact check`.
- `cento_build_worker_run`: map to `cento build worker run`.
- `cento_build_integrate`: map to `cento build integrate`.
- `cento_build_apply`: map to `cento build apply`.
- `cento_build_receipt`: map to `cento build receipt`.

## Workset tool interfaces (proposed MCP wrappers)

Canonical `cento.workset` command envelope:

```json
{
  "schema_version": "cento.workset_command_request.v1",
  "proposed": true,
  "command": "check|run|execute|materialize_artifact",
  "workset": ".cento/worksets/<run-id>/workset.json",
  "max_parallel": 3,
  "runtime": "api-openai|fixture|local-command",
  "runtime_profile": "codex-fast",
  "budget_usd": 3.0,
  "max_budget_usd": 5.0,
  "apply": false,
  "json": true
}
```

Core MCP tools:

- `cento_workset_check`: calls `cento workset check`, returns validation summary.
- `cento_workset_run`: calls `cento workset run`, returns `.cento/worksets/<run_id>/workset_receipt.json`.
- `cento_workset_execute`: calls `cento workset execute`, returns task status + `workset_receipt` + `workset_evidence`.
- `cento_workset_materialize_artifact`: calls `cento workset materialize-artifact`.

CLI behavior:

- keep existing behavior and ensure JSON prints include artifact paths when `--json`.

## Factory tool interfaces (proposed MCP wrappers)

Canonical request payload:

```json
{
  "schema_version": "cento.factory_command_request.v1",
  "proposed": true,
  "command": "intake|plan|materialize|queue|lease|dispatch|collect|validate|integrate|release|runtime_list|runtime_show",
  "run_dir": "workspace/runs/factory/<run-id>",
  "request": "plan and deliver feature",
  "risk": "low|medium|high",
  "lane": "builder|validator|coordinator",
  "json": true
}
```

Proposed MCP tools:

- `cento_factory_intake`: wraps `cento factory intake`.
- `cento_factory_plan`: wraps `cento factory plan`.
- `cento_factory_materialize`: wraps `cento factory materialize`.
- `cento_factory_queue`: wraps `cento factory queue`.
- `cento_factory_lease`: wraps `cento factory lease`.
- `cento_factory_dispatch`: wraps `cento factory dispatch`.
- `cento_factory_collect`: wraps `cento factory collect`.
- `cento_factory_validate`: wraps `cento factory validate`.
- `cento_factory_integrate`: wraps `cento factory integrate`.
- `cento_factory_status`: wraps `cento factory status`.
- `cento_factory_release`: wraps `cento factory release`.
- `cento_factory_runtime_list` and `cento_factory_runtime_status`: wraps `cento factory runtime` subcommands.

Each factory MCP call returns the same wrapped command envelope (`ok/exit_code/command/stdout/stderr`) plus resolved artifact pointers:

- `workspace/runs/factory/<run>/factory-plan.json`
- `workspace/runs/factory/<run>/queue/queue.json`
- `workspace/runs/factory/<run>/integration/integration-state.json`
- `workspace/runs/factory/<run>/delivery-status.json`

## Validation and proof mapping by run kind

Recommended source mapping in the proof resolver:

- `cento-workset` -> `.cento/worksets/<id>/workset_receipt.json`
- `cento-build` -> `.cento/builds/<id>/integration_receipt.json` + `.cento/builds/<id>/apply_receipt.json` + `.cento/builds/<id>/taskstream_evidence.json`
- `cento-hard-proreq` -> hard-proreq evidence + `validation_plan.json` + validator receipts
- `factory` -> `integration/integration-state.json` + `delivery-status.json`

Status rule:

- `passed` if at least one required receipt exists and no failed required checks.
- `warn` if optional receipts missing.
- `fail` if required receipts missing/failed.

## Alignment note

These are proposed interfaces only. No existing behavior is changed by this file; it is the canonical plan for Spark Lane implementation.

---

## Dev Pipeline Gaps And Fixes

_Integrated from `workspace/runs/ai-cento-native-execution-plan/20260505T051319Z/sections/dev_pipeline_gaps.md`._

# Dev Pipeline Gaps: Proof, Validation, Run Selection, and UI Trust

This section records proof/validation/selection gaps in the Dev Pipeline Studio execution path, with concrete fixes and test additions. It is scoped to:
- `scripts/agent_work_app.py`
- `scripts/dev_pipeline_hard_proreq.py`
- `tests/test_dev_pipeline_delivery.py`
- `docs/dev-pipeline-run-contracts.md`

## 1) Proof / receipt resolution is fragmented

Observed behavior:
- Hard-proreq run payload starts with `source: "cento-hard-proreq-pro"` and `artifacts` from `dev_pipeline_hard_proreq_artifacts(...)`.
- Hard-proreq finish path rewrites `run_payload["artifacts"]` from that same helper and emits only the list for events.
- Workset/delivery runs compute artifacts from `dev_pipeline_delivery_artifacts` using execution run + receipt data.
- Evidence cards are assembled from default cards and per-template config in `dev_pipeline_base_evidence_cards`.

Gap:
- There is no canonical proof resolver object that indicates which artifact set is the authoritative proof for a run. UI and status logic can therefore read different proof sources for the same run.

Fix:
- Introduce `dev_pipeline_resolve_proof(...)` (single function) that returns:
  - `proof_source`: `hard-proreq|workset|factory|manifest`
  - `proof_provider`: `run_payload|run_receipt|history`
  - `required_artifacts`
  - `observed_artifacts`
  - `missing_artifacts`
  - `proof_status` (canonical)
  - `proof_confidence` (numeric)
- Persist it as `execution_run["proof_summary"]`.
- In `dev_pipeline_execution_flow`, derive `execution_flow["proof"]` only from this summary so UI evidence/status cards align with an explicit resolver.


## 2) Validation status normalization is incomplete

Observed behavior:
- `dev_pipeline_validation_status` supports `passed|configured|queued|warning|failed|manual-review`.
- Aggregate validator receipt status in `dev_pipeline_write_validation_outputs` is only: `failed` > `passed` > `configured`.
- Stage/status mappers flatten values across contexts:
  - `dev_pipeline_execution_status_label` maps accepted/applied/passed/merged to `completed`.
  - mutes map to `muted`.
  - stage reducer treats `muted`, `separate-flow`, `deferred` as completed.
- `validation_results.passed` in execution flow counts `passed|completed` only.

Gap:
- `warning` and `manual-review` lose semantic precision and can be downgraded via aggregation or stage mapping.
- Status vocabularies differ across validator config, execution stages, evidence cards, and UI labels.

Fix:
- Define one canonical status layer:
  - `proof_status`: `passed|warning|manual-review|failed|blocked|muted|running|queued|configured|missing`
  - `pipeline_status`: `running|queued|completed|blocked|failed`
- Route all status text through one normalizer (validation, execution, evidence, cards, stage reducers).
- Update aggregate validation to return `warning` when any validator yields warning/manual-review, not `configured`.
- Update validation UI counts to treat non-`passed` states as non-success.


## 3) Live/fallback/cached provenance is implicit

Observed behavior:
- `dev_pipeline_execution_flow` resolves runs by:
  1. `execution/execution_run.json`
  2. optional `selected_run_id` history run
  3. first matching history row
- `dev_pipeline_execution_history` only stores `status`, `started`, `finished`, `path`, `active`.

Gap:
- UI cannot trust if a row is live, explicitly selected, stale fallback, or historical cache.

Fix:
- Extend history row schema with:
  - `provenance`: `live|selected|fallback|cached`
  - `resolved_from`: resolved file path
  - `selection_reason`: short machine reason
- Extend execution flow output with:
  - `run_selection`: `{ requested_run_id, resolved_run_id, resolved_from, resolved_as, is_live, selection_reason }`
- Make fallback-to-history behavior explicit in resolver logic and persisted metadata.


## 4) Latest-run behavior can drift from authoritative source

Observed behavior:
- If no active run is found, flow reconstructs a synthetic `run_id` from timestamps.
- If manifest active id is stale or wrong pipeline, it is blanked.
- History injection can synthesize rows even when `execution/execution_run.json` is stale.

Gap:
- Determinism is mostly incidental; status shown to operators can represent an older run when newer history exists.

Fix:
- Add `dev_pipeline_resolve_active_execution_run(root, expected_pipeline, selected_run_id)` returning:
  - chosen `run_payload`
  - provenance
  - `is_live`
  - `is_stale`
- Use this same resolver from:
  - `dev_pipeline_execution_flow`
  - `dev_pipeline_studio_state`
  - finish/append event paths when needed.


## 5) Evidence artifacts are assembled but weakly trusted

Observed behavior:
- Hard-proreq evidence artifact is generated by `command_evidence` as `hard_proreq_evidence.json`, with per-artifact `exists` flags.
- Base evidence cards default statuses from static strings or presence heuristics (`title_status`), not proof checks.
- Execution summary artifacts are built by appending fallback paths such as `evidence/pipeline_receipt.json`, `validation/validation_receipt.json`, `execution/execution_run.json`.

Gap:
- A missing required artifact can still render non-error card states when status text is optimistic.
- Evidence trust is not represented as a single computed state.

Fix:
- Require explicit evidence contract per run:
  - `evidence_bundle.json` contains required proof artifact names + checks performed.
  - `evidence_bundle_manifest.json` tracks present/missing + severity per item.
- Render evidence/integration/validation cards from this manifest, not from static template status fallbacks.
- Surface `evidence_trust` (`high|medium|low`) in execution_flow and UI so trust level is explicit.


## 6) UI status trust currently depends on template/card-level text

Observed behavior:
- Integration/validator/evidence cards frequently derive from string labels (`title_status`) with fallback values, not proof-level outcome.
- Stage status is often inferred from step status buckets; this can diverge from proof receipt status.

Gap:
- The UI can show “passed/completed” even if validators produce `warning` or required evidence is missing.

Fix:
- Add `pipeline_ui_state` block to studio response:
  - `proof.status`
  - `execution.status`
  - `validation.status`
  - `evidence.status`
  - `confidence`
- Bind pipeline cards to these normalized status fields only.
- Require evidence status gating before transition to handoff-complete UI state.


## 7) Tests to add now

Current tests validate inputs, seeds, parallel paths, and optional image handling, but do not cover proof/resolution status contracts.

Add these test classes in `tests/test_dev_pipeline_delivery.py`:
- `test_proof_resolver_unifies_hard_proreq_and_workset_sources`
- `test_status_normalizer_maps_all_variants_to_canonical`
- `test_history_rows_expose_live_selected_fallback_cached`
- `test_execution_flow_prefers_latest_authoritative_run_when_live_stale`
- `test_evidence_manifest_blocks_when_required_artifact_missing`
- `test_validation_warning_manual_review_not_counted_as_passed`
- `test_ui_execution_flow_status_matches_proof_summary`


## 8) Implementation sequence (smallest safe increments)

1) Add canonical status normalizers and shared proof status constants.
2) Add explicit `resolve_execution_run` + `resolve_proof` helpers.
3) Wire execution flow and studio response to resolved proof status + provenance.
4) Add evidence manifest validation + trust score output.
5) Update tests with table-driven and synthetic run fixtures.

---

## Skills And Runtime Policy

_Integrated from `workspace/runs/ai-cento-native-execution-plan/20260505T051319Z/sections/skills_runtime.md`._

# AI Native Skills and Runtime Policy (Canonical Draft)

## Scope and issue link

This is the canonical, machine-facing policy draft for **Taskstream issue 1000185**.

It converts `docs/ai-cento-native-rework-research.md` into a concrete execution policy:

- current skill guidance,
- proposed thin skills,
- runtime and model-selection policy,
- deterministic-first validation with explicit escalation,
- strong-model planning constraints,
- Spark/Codex bounded builders,
- no-model-only paths,
- API/image/Pro gating,
- and skill authoring rules.

Status: **current and future sections mixed; explicit `proposed` flags mark non-implemented behavior.**

## Policy data shape

```json
{
  "schema_version": "cento.skill_runtime_policy.v1",
  "issue_id": 1000185,
  "run_dir": "workspace/runs/ai-cento-native-execution-plan/20260505T051319Z",
  "proposed": false,
  "created_for": "ai-cento-native-rework",
  "timestamp": "2026-05-05T05:13:19Z",
  "components": {
    "current_skills": [
      "cento-native",
      "cento-requirements-manifest"
    ],
    "proposed_skills": [
      "cento-ai-run",
      "cento-validator",
      "cento-evidence-handoff"
    ],
    "current_mcp_surface": [
      "agent-work",
      "cluster",
      "bridge",
      "story",
      "context",
      "platforms"
    ],
    "proposed_mcp_extensions": [
      "cento_ai_run_*",
      "cento_dev_pipeline_*",
      "cento_scan",
      "cento_runtime_list",
      "cento_evidence_check",
      "cento_build_init",
      "cento_workset_execute",
      "cento_factory_plan"
    ],
    "runtime_profiles_observed": [
      "codex-fast",
      "fixture-valid",
      "python-fixture"
    ]
  }
}
```

## 1) Current skill guidance baseline

### 1.1 `cento-native` (installed, active)

Observed behavior in the current repository and skill guidance:

- starts with Cento discovery and repo/tool reality,
- prefers MCP/CLI over free-form scripting,
- routes Cento feature work through Taskstream,
- uses temp/cluster/one-off command paths for one-off tasks,
- preserves dirty repo state when operating on user workspaces,
- and keeps implementation instructions thin.

This is the right base layer because it forces tool-first operation before agent improvisation.

### 1.2 `cento-requirements-manifest` (installed, active)

- turns screenshots/mockups/notes into structured requirements artifacts,
- emits `cento.requirements_manifest.v1` style outputs,
- optionally scaffolds a draft `story.json`,
- should not dispatch worker execution itself.

### 1.3 Gap from validation against current run

From validation evidence:
- only current installed skills are `cento-native`, `cento-requirements-manifest`, plus generic helpers,
- proposed skills `cento-ai-run`, `cento-validator`, and `cento-evidence-handoff` are not installed yet.

This gap is intentional in phase-0 but must close before the run model becomes durable across all routes.

## 2) Proposed thin skill set (no business logic)

Each new skill must be an adapter: map task -> command/tool -> schema artifact, not a planner/executor of long logic.

### 2.1 `cento-ai-run` (proposed)

**Use case:** launch or continue any AI execution flow from an intent.

Inputs:
- route decision (existing `cento.intent_route.v1`),
- context bundle,
- optional workset/manifest hints.

Actions:
- run `cento_intent_route`,
- run `cento_context_bundle`,
- create `cento.ai_run.v1` via `cento_ai_run_create`,
- route to Dev Pipeline Studio/build/workset/factory based on template and validation mode.

Outputs:
- run id (`id`),
- selected runtime profile (`runtime_profile`),
- acceptance handoff target (`handoff_target`),
- evidence manifest pointer.

No direct file mutation except explicit run artifacts it owns by contract.

### 2.2 `cento-validator` (proposed)

**Use case:** independent and reproducible validation lane.

Inputs:
- `story.json`,
- `validation.json`,
- `run_dir`.

Actions:
- run deterministic commands from validation manifest first,
- capture screenshot evidence when declared,
- emit validator evidence and receipts,
- mark unresolved/subjective checks as manual-review or warning.

Constraints:
- no repo mutation unless explicitly declared in task and owned path policy,
- model use must be explicit and only for escalation (never first response),
- should not be used as the only judge for completion.

### 2.3 `cento-evidence-handoff` (proposed)

**Use case:** package manager-facing proof and lane transition.

Inputs:
- run/envelope identifier,
- validation outputs,
- mandatory artifact refs.

Actions:
- produce evidence hub index,
- emit Delivered/Validation/Evidence/Risk summaries,
- draft Taskstream handoff/notes,
- verify every required artifact link resolves.

Gate:
- cannot mark as “ready” if proof obligations remain unresolved.

## 3) Runtime and model policy

### 3.1 Runtime classes

| Runtime | Purpose | Typical actor | Default gate |
|---|---|---|---|
| `no-model` | deterministic checks + read-only planning | validator/planner preflight | mandatory baseline |
| `cheap-model` | low-risk synthesis / summarization | small/fast model workers | optional and auditable |
| `strong-model` | decomposition + architecture planning | planner lane only | allowed only when no-model lacks completion |
| `codex-fast` | bounded repository edits | bounded builders in workset/worktree | must have owned paths + validator |
| `fixture-valid` | deterministic fixtures + dry-run checks | validator/test scaffolding | must pass command contracts |
| `api-openai` | local/non-vision model-assisted calls | explicit API-needed tasks | requires provider/env |
| `api-openai-parallel` | parallel API calls for expensive workloads | optional worker fanout | same gates + cost caps |
| `api-openai-image` | image lane (muted by default for frontends) | screenshot/asset operations | explicit file + screenshot references |
| `api-openai-pro` | GPT Pro fallback path | backend-heavy worksets and hard-proreq | hard-gated and opt-in |

### 3.2 Model-mode matrix

For each request, select one primary mode and one fallback mode:

- `no-model`: default for route discovery, schema check, manifest validation, command/screenshot evidence checks.
- `cheap-model`: only when no-model can’t complete non-subjective parsing (`validation.summary` text, acceptance normalization, short command notes).
- `strong-model`: only for planning and tradeoff decisions.
- `api-openai` / `api-openai-image` / `api-openai-pro`: only when work explicitly requires external model features and gates permit.

### 3.3 Prohibited behavior

- strong-model workers must not write into shared repo without a task-bounded lane contract.
- bounded builders may not escape `owned_paths`.
- no-model mode must not invoke model APIs as a required dependency.
- all API model use must produce command/receipt logs and completion evidence.
- model mode cannot hide evidence debt; unresolved checks must remain explicit in `manual_review`.

## 4) Deterministic-first validation policy

### 4.1 Principle

Validation has strict order:

1. deterministic command checks and structural schema checks,
2. evidence checks for files/URLs/screenshot paths,
3. model-assisted review only if required and explicitly escalated.

Any unresolved subjective condition is kept as `manual_review`.

### 4.2 Deterministic checks required by policy

For each `story.json` + `validation.json` pair:

- manifest schema fields exist and are valid,
- required command list exists and uses allow-listed commands,
- expected outputs exist by path,
- API fields (when declared) are present and non-empty,
- screenshot entries have deterministic output targets,
- escalation triggers are explicit and machine-readable.

Validation status mapping:
- `passed`: all deterministic checks pass and required artifacts present.
- `warn`: deterministic checks pass but one or more non-blocking policy constraints missing (e.g., optional screenshot reference missing and lane is muted).
- `manual-review`: ambiguity, high risk, missing manifest references, failed deterministic command.
- `blocked`: hard gate failure with unresolved no-recoverable blockers.

### 4.3 Escalation criteria to model review

- `missing_manifest`,
- `high_risk`,
- `failed_deterministic_command`,
- `ambiguous_acceptance`,
- `ux_judgment_required`.

These must be persisted in `story.validation.escalation_triggers`.

## 5) Strong-model planning policy

Strong model is used for:

- decomposition,
- architecture trade-offing,
- complex plan synthesis,
- risk discovery,
- schema-backed proposal of workstreams.

Strong-model outputs must follow:

- no code writes in planning pass,
- produce a plan artifact with bounded scope,
- explicitly name:
  - read/write paths,
  - validation plan,
  - runtime profile,
  - run budgets,
  - expected artifacts,
  - risk and escalation triggers,
- handoff to Codex/validator only after deterministic prechecks are represented.

If a plan claims write intent, it must include `owned_paths` and `forbidden_paths`.

## 6) Spark lane split and bounded builders

### 6.1 Lane contract

Execution is decomposed and can run in parallel:

- `planner` lane (strong-model + no-mutate),
- `builder` lanes (codex runtimes + bounded edits),
- `validator` lanes (deterministic-first + screenshot capture),
- `handoff` lane (evidence/package transition).

Each lane receives a deterministic envelope entry:
- `lane_id`,
- `mode`,
- `runtime_profile`,
- `owned_paths`,
- `read_paths`,
- `max_files`,
- `max_lines`,
- `validator_contract`,
- `cost_usd_hard_cap`.

### 6.2 Spark/Codex bounded builder constraints

For every Codex builder task:

- `read_paths` must be explicit and subset of context,
- `owned_paths` must be explicit and non-empty,
- edits are restricted to owned paths plus task-specific allow-list,
- patch size and file-count bounds apply,
- execution must emit:
  - command output,
  - modified files list,
  - artifact manifests,
  - validation artifacts,
  - receipt status.

Failure behavior:
- if bounds are violated, builder fails fast and routes to manual review,
- if evidence artifacts are missing, handoff is blocked with a clear blocker code.

### 6.3 Lane routing example

```text
Request -> intent_route -> context_bundle -> strong-model plan (planner)
        -> workset/build/factory (builder lane, Codex-fast/isolated, bounded writes)
        -> validator lane (deterministic-first)
        -> evidence-handoff lane (proof + taskstream)
```

## 7) No-model paths

No-model is the default mode and must remain dominant for these:

- command and tool discovery (`cento tools`, `cento docs`, `cento runtime list`, `cento scan`),
- registry/tool availability checks,
- schema validation (`story/validation/workset/build/factory schemas`),
- file existence and hash checks,
- API smoke checks where credentials are not required,
- deterministic screenshot capture and evidence indexing,
- dirty-work checks and worktree reconciliation,
- run provenance checks (`live/selected/fallback/cached` provenance where available).

No-model mode is considered complete only when required outputs are machine-verified, not merely summarized in prose.

## 8) API, image, and Pro gating policy

### 8.1 API gating

Any API runtime lane is only authorized when the command contract explicitly requires it and the feature can be reproduced from manifest.

- If API keys are missing, fail deterministically with `blocked: missing_env`.
- If required API endpoint schema is absent, fail with `blocked: missing_api_contract`.
- Any API path must emit request/response metadata and status in receipts.

### 8.2 Image lane gating

Image operations are supported only when:

- source asset/reference exists,
- image task is declared in manifest as muted-required or required,
- provider environment is present,
- generated filenames and outputs are deterministic.

Failure to meet this is either:

- `muted` when optional and non-blocking,
- `blocked` when the requirement is explicit and non-optional.

### 8.3 Pro lane gating

GPT Pro-capable paths are **opt-in** and use hard env gating.

- `CENTO_HARD_PROREQ_DISPATCH_PRO=1` must be set for hard Pro routing.
- if not enabled, route deterministically to deterministic fallback artifacts with clear `pro-disabled` reason.
- Pro usage must include:
  - explicit reason code,
  - intended endpoint target,
  - fallback plan.

## 9) Skill authoring rules for Cento runtime

All skills must follow these invariants:

1. **Trigger precision**
   Frontmatter and description define exact trigger conditions; avoid broad or fuzzy prompts.

2. **Tiny control surface**
   A skill outputs: which tool to call, which artifact to read/write, and where to hand off.

3. **No duplicate tool catalogs**
   Never re-list full `cento tools` contracts inside skill text.

4. **No in-skill executable logic**
   If a Cento command or MCP tool exists, call it; do not reimplement behavior in the skill body.

5. **Machine evidence first**
   Prefer artifact links, paths, and status fields over prose summaries.

6. **Reference-heavy design**
   Move long rationale to `references/*.md`; keep `SKILL.md` minimal and action-driven.

7. **Explicit proof boundaries**
   Each skill defines what counts as success and which checks are `manual_review`.

8. **Model discipline**
   State the required model/runtime mode and include hard limits (`max_cost_usd`, `max_runtime_ms`, `max_patches`, `max_files`).

9. **Recovery semantics**
   Include deterministic fallback path when model/API is unavailable.

## 10) Canonical acceptance criteria for this lane

- `cento-native` remains short and discovery-first.
- proposed skills are thin wrappers around CLI/MCP surfaces.
- deterministic checks remain the first gate and are explicit in schema.
- strong models are allowed only for planning and synthesis, never as silent mutation.
- bounded builders require explicit owned paths and receipts.
- API/image/Pro gates are hard and auditable.
- no-model gets default preference for validation and evidence checks.

## Delivered

- Captured a complete canonical policy model linking current implementation state and proposed futures.
- Added a concrete skill taxonomy with `cento-native`, `cento-requirements-manifest`, `cento-ai-run`, `cento-validator`, `cento-evidence-handoff`.
- Added runtime policy including deterministic-first validation ordering and no-model-first mode selection.
- Defined Spark/Codex builder boundaries with hard constraints and lane contracts.
- Defined API/image/Pro gating and explicit fallback semantics.
- Added skill authoring standards that keep skills thin and tool-driven.

## Validation

- Non-model validation mode for this lane remains file-surface limited.
- Required section exists in this file only:
  - `current skill guidance`,
  - `proposed thin skills`,
  - `model/runtime policy`,
  - `deterministic-first validation`,
  - `strong-model planning`,
  - `Spark/Codex bounded builders`,
  - `no-model paths`,
  - `API/image/Pro gating`,
  - `skill authoring rules`.
- No direct command execution was required to produce this draft beyond file reads.

## Evidence

- Backed by:
  - run-level validation findings in this execution set (existing matrix and lane artifacts),
  - current lane story metadata for expected outputs,
  - `docs/ai-cento-native-rework-research.md` assertions (both current state and proposed target),
  - existing installed-skill evidence from local environment.

## Residual risk

- The proposed MCP tool set and three thin skills are not yet installed in the environment.
- Some policy constants (`CENTO_HARD_PROREQ_DISPATCH_PRO` semantics, API contract IDs, and exact openai-runtime names) must be normalized in implementation.
- Validation of evidence-handoff fields depends on downstream Taskstream conventions still being finalized.
- The runtime policy references explicit cost and patch budgets; those may need calibration after first bounded pilot run.

---

## Spark Coordination Runbook

_Integrated from `workspace/runs/ai-cento-native-execution-plan/20260505T051319Z/sections/spark_coordination.md`._

# Spark Lane 5 Coordination Runbook

This runbook is the operational control playbook for Spark Lane 5 in the execution plan run.
It uses the live Cento CLI surfaces only; the removed pool-dispatch subcommand is not used.

## Scope and runtime contract

- Taskstream issues must be created from a valid `story.json` where `issue.id = 0`.
- Spark live dispatch must use `gpt-5.3-codex-spark` for Codex-based runs.
- Live worker fan-out is bounded to **4 active workers** per dispatch batch.
- `agent_pool_kick.py` is used for batch dispatch; it supports `--dry-run` but has **no** `--json` mode.

## 1) Taskstream issue creation and intake

Create each issue first, then validate and gate before dispatch.

```bash
cd /home/alice/projects/cento
python3 scripts/agent_work.py create \
  --title "Spark Lane 5: ... concise scope ... " \
  --manifest workspace/runs/agent-work/<issue-id>/story.json \
  --role coordinator \
  --package <package-name> \
  --owns "<owned-path-or-scope>" \
  --json
```

Notes:
- `create` fails unless `story.json` validates and has `issue.id = 0` (it is rewritten to real issue id automatically).
- For a multi-task package, prefer `agent-work split` for explicit bounded tasks before dispatch.

## 2) Pre-dispatch validation on the issue

Preflight every candidate story before queueing it.

```bash
python3 scripts/agent_work.py preflight \
  workspace/runs/agent-work/<issue-id>/story.json \
  --validation-manifest workspace/runs/agent-work/<issue-id>/validation.json \
  --write-validation-draft \
  --json
```

- If preflight fails, block the item and write the blocker reason on issue before any dispatch.

```bash
python3 scripts/agent_work.py update <issue-id> \
  --status blocked \
  --role coordinator \
  --note "Preflight failed: ... exact reason ..."
```

## 3) Controlled dry-run dispatch plan

Use this before every live Spark wave. It must pass first.

```bash
cd /home/alice/projects/cento
CENTO_AGENT_RUNTIME=codex \
CENTO_POOL_CODEX_MODEL=gpt-5.3-codex-spark \
CENTO_POOL_STRONG_VALIDATOR_MODEL=gpt-5.3-codex-spark \
python3 scripts/agent_pool_kick.py \
  --dry-run \
  --max-launch 4 \
  --validator-target 3 \
  --builder-target 4 \
  --small-target 3 \
  --coordinator-target 1
```

- `--max-launch 4` enforces the live cap for this pass.
- Review stdout and `~/.local/state/cento/agent-pool-kick-latest.json` for:
  - `reason_summary.primary_reason`
  - `reason_summary.summary`
  - `reason_summary.next_action`
  - `reason_summary.lanes[].lane`
  - `reason_summary.lanes[].queued`
  - `reason_summary.lanes[].reason`
- If `launched` is empty or blockers exist, resolve blockers first and rerun dry-run.

## 4) Live dispatch

Run the live wave only after dry-run is accepted.

```bash
cd /home/alice/projects/cento
CENTO_AGENT_RUNTIME=codex \
CENTO_POOL_CODEX_MODEL=gpt-5.3-codex-spark \
CENTO_POOL_STRONG_VALIDATOR_MODEL=gpt-5.3-codex-spark \
python3 scripts/agent_pool_kick.py \
  --max-launch 4 \
  --validator-target 3 \
  --builder-target 4 \
  --small-target 3 \
  --coordinator-target 1
```

For a single issue manual override, dispatch directly:

```bash
python3 scripts/agent_work.py dispatch <issue-id> \
  --role builder \
  --runtime codex \
  --model gpt-5.3-codex-spark
```

You may dry-run the same single-item dispatch with `--dry-run` before executing.

## 5) Monitoring loop

Use this sequence while the wave is active.

```bash
python3 scripts/agent_work.py runs --json --active --reconcile --no-untracked
python3 scripts/agent_work.py list --json
python3 scripts/agent_work.py show <issue-id>
```

- `runs --active --reconcile --no-untracked` is the primary view of active/queued/stale session state.
- `~/.local/state/cento/agent-pool-kick-latest.json` is the authoritative last-wave dispatch transcript.
- For any abnormal run_id, drill into it:

```bash
python3 scripts/agent_work.py run-status <run-id> --json --reconcile
```

Repeat the dry-run/live pair when queued capacity remains and active count is below target:

```bash
python3 scripts/agent_work.py runs --json --active --no-untracked
```

Use `--max-launch 4` again on every live re-kick.

## 6) Stale run handling

Stale handling is lane-level only after reconciliation and confirmation.

```bash
python3 scripts/agent_work.py runs --json --active --reconcile --no-untracked
python3 scripts/agent_work.py recovery-plan --json
```

- Stale candidates usually appear under:
  - `status = stale`
  - or `health = stale_no_process` from `run-status`
- If stale dispatch is caused by old Spark dispatch metadata, re-queue only after the issue has no active live owner:

```bash
python3 scripts/agent_work.py update <issue-id> \
  --status queued \
  --role <builder|validator|coordinator> \
  --note "Old Spark dispatch can be requeued after stale reconciliation."
```

- For non-external blockers (`split-needed`, internal artifacts, evidence gaps), follow `recovery-plan` outputs and apply only bounded safe actions.

```bash
python3 scripts/agent_work.py recovery-plan --apply --json
```

- Use `review-drain --dry-run` before apply if a high-risk closure decision is pending.

## 7) Integration and review closure

Once per package, drain review-ready approvals before finalizing package closure.

```bash
python3 scripts/agent_work.py review-drain \
  --package <package-name> \
  --status review \
  --note "Spark lane review drain preflight." \
  --dry-run

python3 scripts/agent_work.py review-drain \
  --package <package-name> \
  --status review \
  --note "Spark lane review drain applied by coordinator." \
  --apply
```

For completed items, move to done explicitly:

```bash
python3 scripts/agent_work.py update <issue-id> \
  --status done \
  --role coordinator \
  --note "Spark lane complete and validated."
```

## 8) Closure conditions

- `python3 scripts/agent_work.py runs --json --active --no-untracked` returns zero active/stale items.
- `python3 scripts/agent_work.py list --json` shows no unexpected Review/Blocked in scope of this package.
- `python3 scripts/agent_work.py recovery-plan --json` reports no residual unsafe blockers.
- Final evidence references are linked in corresponding `story.json` and any handoff/review artifacts.
- Commit any coordination notes and close the Spark coordination issue only after the above checks are true.

---

## Validator Checklist

_Integrated from `workspace/runs/ai-cento-native-execution-plan/20260505T051319Z/sections/validator_review.md`._

# Validator Checklist for the Canonical AI-Centric Rework Plan

**Lane:** Spark 8 (validator)
**Issue:** 1000187
**Run directory:** `workspace/runs/ai-cento-native-execution-plan/20260505T051319Z`

## Delivered
- Independent, deterministic validation checklist for the final canonical Markdown merge.
- No edits to source canonical content; this file is a validator draft only.

## Validation Inputs
- Source research: `docs/ai-cento-native-rework-research.md`
- Section drafts in this run: `workspace/runs/ai-cento-native-execution-plan/20260505T051319Z/sections/*.md`
- Candidate canonical output path (set by coordinator): `CANONICAL_DOC`
- Runtime checks run from repo root: `/home/alice/projects/cento`

Set before validation:

```bash
export RUN_DIR=/home/alice/projects/cento/workspace/runs/ai-cento-native-execution-plan/20260505T051319Z
export CANONICAL_DOC=${CANONICAL_DOC:-/home/alice/projects/cento/docs/ai-cento-native-execution-plan.md}
cd /home/alice/projects/cento
mkdir -p "$RUN_DIR/validation"
```

## Required Facts to Verify

### A. Canonical document integrity and traceability
1. Canonical path is resolvable and non-empty.
2. Canonical doc includes explicit scope (research findings + proposed architecture + execution plan).
3. Canonical doc states that the baseline source is `docs/ai-cento-native-rework-research.md` with date/signature context.
4. Canonical doc is assembled from all lane outputs (or states replacements with rationale where one lane owned sections are intentionally merged/renamed).
5. Every non-empirical recommendation is tagged as proposal vs current-state fact.

### B. Claimable system facts (must be evidence-backed)
6. Tool registry facts (counts, families, source-of-truth references) match a live check at validation time.
7. MCP coverage facts match live tool set (`--list-tools`) and indicate exact parity/gap deltas vs desired surface.
8. Runtime/profile facts align to actual `cento runtime list --json`.
9. Dev Pipeline run facts align to `workspace/runs/dev-pipeline-studio/docs-pages/latest/...` artifacts and `execution_run.json`.
10. Validation/proof semantics are described as source-dependent and the canonical doc includes the mapping used for each run source.
11. Hard-proreq evidence/state claims are tied to artifact paths and are explicitly marked stale/history when not current.
12. Required residual risks and acceptance gates are included as executable criteria (not prose-only).

## Commands to Run (deterministic checks)

1. **Precondition checks**

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('$CANONICAL_DOC')
if not p.exists():
    raise SystemExit(f'CANONICAL_DOC missing: {p}')
print(f'CANONICAL_DOC={p}')
text = p.read_text()
print(f'bytes={p.stat().st_size}')
print(f'headings={sum(1 for line in text.splitlines() if line.startswith("#"))}')
PY

rg -n '^##|^###|^#' "$CANONICAL_DOC" | head
[ -f "$RUN_DIR/sections/validation_matrix.md" ]
[ -f "$RUN_DIR/sections/target_architecture.md" ]
[ -f "$RUN_DIR/sections/interfaces.md" ]
[ -f "$RUN_DIR/sections/dev_pipeline_gaps.md" ]
[ -f "$RUN_DIR/sections/spark_coordination.md" ]
```

2. **Section-to-doc traceability**

```bash
rg -n "^#|^##|^###" "$RUN_DIR/sections/validation_matrix.md" "$RUN_DIR/sections/target_architecture.md" "$RUN_DIR/sections/interfaces.md" "$RUN_DIR/sections/dev_pipeline_gaps.md" "$RUN_DIR/sections/spark_coordination.md" > "$RUN_DIR/validation/section_headings.txt"
wc -l "$RUN_DIR/validation/section_headings.txt"
```

3. **Current-state facts from live tools**

```bash
cento gather-context --no-remote > "$RUN_DIR/validation/gather_context_now.txt"
python3 - <<'PY'
from pathlib import Path
text = Path('$RUN_DIR/validation/gather_context_now.txt').read_text()
print('total_tools=', 'tools:' in text)
# Keep command output parseable and explicit; manual reviewer should confirm final values.
PY

cento tools > "$RUN_DIR/validation/cento_tools_now.txt"
cento runtime list --json > "$RUN_DIR/validation/runtime_profiles_now.json"
CENTO_MCP_READ_ONLY=1 python3 scripts/cento_mcp_server.py --list-tools > "$RUN_DIR/validation/mcp_tools_now.json"
```

4. **Dev Pipeline and hard-proreq evidence checks**

```bash
python3 - <<'PY'
import json
from pathlib import Path
base = Path('workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq')
latest = base / 'latest'
exec_run = json.loads((latest/'execution_run.json').read_text())
print('latest_run_id=', exec_run.get('run_id'))
print('artifact_count=', len(exec_run.get('artifacts', [])))
print('proof=', exec_run.get('proof'))
print('validation=', exec_run.get('validation'))
PY

[ -f workspace/runs/scan-onepager/latest/summary.json ] && cat workspace/runs/scan-onepager/latest/summary.json | jq .
```

5. **Static source checks tied to claims**

```bash
rg -n "C0[1-9]|C[1-9][0-9]" "$CANONICAL_DOC" "$RUN_DIR/sections/validation_matrix.md" > "$RUN_DIR/validation/claim_ids.txt"
rg -n "proposed|outdated|unknown|partially true|false" "$CANONICAL_DOC" > "$RUN_DIR/validation/claim_statuses.txt"
rg -n "latest run|run_id|artifacts|proof|validation|evidence" "$CANONICAL_DOC" > "$RUN_DIR/validation/primary_claim_lines.txt"
```

6. **Cross-check that canonical status transitions are normalized**

```bash
rg -n "queued|running|completed|failed|manual-review|warning|muted|proof|proof_status|status" "$CANONICAL_DOC" "$RUN_DIR/sections/target_architecture.md" "$RUN_DIR/sections/dev_pipeline_gaps.md"
```

## Stale/outdated-command and stale-fact checks

- Validate that any date-specific claim in the canonical doc is bounded with a timestamp.
- Check if the canonical date differs from run timestamp `2026-05-05T05:13:19Z` and is explicitly called “historical” when older.
- If a command appears in text, verify there is a corresponding captured output artifact timestamped no later than canonical run date.
- If command outputs include tool counts, run IDs, stage counts, validator counts, or artifact counts, verify against fresh outputs captured in this validation session.
- Mark as **STALE** if: no freshness marker, run id/path missing, output artifact absent, or numbers differ without rationale note.

```bash
rg -n "Date:|as of|as-of|last checked|latest|2026-05-" "$CANONICAL_DOC"
rg -n "1514|223|1286|45|50|23|13|9|37|4-stage|6 stage|runtime profiles" "$CANONICAL_DOC"
```

## Acceptance Criteria

1. **Coverage completeness**
   - Canonical doc includes all required domains: baseline state, evidence truth, architecture, lane split, interface changes, proof/validation model, roadmap, risks, and acceptance tests.
2. **Evidence sufficiency**
   - Every hard claim is linked to either command output, JSON artifact, source file, or test artifact.
3. **Freshness compliance**
   - All command-derived facts either point to fresh outputs from this run window or are explicitly marked as historical baselines.
4. **No ambiguous status semantics**
   - Proof/validation statuses are normalized and mapped consistently across claims (configured/queued/running/completed/passed/failed/manual-review/warning/muted/missing).
5. **Lane independence**
   - Validator section can reproduce checks without relying on another lane’s prose assumptions.
6. **Actionability**
   - Final section ends with machine-checkable pass/fail states and follow-up tasks.

## Residual Risk Categories

1. **Environment drift risk**: live tools differ between validation and authoring environments (e.g., tool counts, run IDs).
   - Mitigation: include exact command artifacts and re-run commands at handoff.
2. **Canonical-merging drift**: merged document silently drops or rephrases lane sections in a way that loses mandatory constraints.
   - Mitigation: preserve section-level source mapping and include one-to-one trace links in final doc.
3. **Stale-baseline leakage**: historical IDs/metrics copied without timestamp markers.
   - Mitigation: classify all dated data as `historical` unless revalidated.
4. **Status-canonical mismatch**: status labels not matching underlying execution payloads.
   - Mitigation: require one proof-source normalization reference in doc and runbook.
5. **Review bottleneck risk**: validation checks list only positive outcomes.
   - Mitigation: require explicit failed/blocked/uncertain examples to demonstrate error paths.

## Final Pass/Fail Rubric

- **PASS**
  - All required facts verified.
  - No stale commands without explicit historical labeling.
  - Traceability matrix complete for every factual statement.
  - No unresolved escalation triggers and risk list closed as mitigated.

- **CONDITIONAL PASS**
  - One or more claims are marked historical but justified with reproducible rationale and no critical gaps.
  - Some non-blocking unknowns remain with follow-up ticket IDs and owners.

- **FAIL**
  - Missing canonical file or required evidence artifacts.
  - Unsupported or unverifiable command-derived claims.
  - Contradictory proof/validation semantics.
  - Absence of lane-8 acceptance criteria or residual-risk closure notes.

## Evidence

- A canonical pass requires these files to exist, be non-empty, and be referenced by the final review log:

```bash
for p in \
  "$RUN_DIR/validation/section_headings.txt" \
  "$RUN_DIR/validation/gather_context_now.txt" \
  "$RUN_DIR/validation/cento_tools_now.txt" \
  "$RUN_DIR/validation/runtime_profiles_now.json" \
  "$RUN_DIR/validation/mcp_tools_now.json" \
  "$RUN_DIR/validation/claim_ids.txt" \
  "$RUN_DIR/validation/claim_statuses.txt" \
  "$RUN_DIR/validation/primary_claim_lines.txt" \
  "$RUN_DIR/validation/section_headings.txt"; do
  [ -s "$p" ] || (echo "missing-or-empty $p" && exit 1)
done
```

## Evidence Snapshot Bundle (this lane)

- `$RUN_DIR/validation/section_headings.txt`
- `$RUN_DIR/validation/gather_context_now.txt`
- `$RUN_DIR/validation/cento_tools_now.txt`
- `$RUN_DIR/validation/runtime_profiles_now.json`
- `$RUN_DIR/validation/mcp_tools_now.json`
- `$RUN_DIR/validation/claim_ids.txt`
