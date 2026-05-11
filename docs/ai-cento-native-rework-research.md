# AI and Cento-Native Rework Research

Date: 2026-05-04

Scope: inspect the live Dev Pipeline Studio Execution Flow, research Cento's current agent/skill/tool surfaces end to end, compare against adjacent local AI and pipeline projects, and propose how to make AI work more effective by making Cento the native execution and evidence substrate.

Primary live surface checked:

- URL: `http://127.0.0.1:47910/dev-pipeline-studio#pipeline-flow`
- Screenshot artifact: `workspace/runs/ai-cento-native-rework/dev-pipeline-flow-20260504.png`
- API state inspected: `GET /api/dev-pipeline-studio`
- Latest visible run at inspection time: `hard-proreq-task-hard-proreq-project-20260504T065328911797Z`

## Executive Summary

Cento already has the most important building blocks for a stronger AI operating model: registered tools, MCP, Taskstream, story manifests, worksets, structured OpenAI workers, deterministic validation, evidence bundles, and a live Dev Pipeline Studio. The missing piece is not another general "agent prompt". The missing piece is a unified Cento-native AI loop where every AI request is converted into a typed contract, routed through Cento tools/MCP first, executed in bounded lanes, validated deterministically, and handed back through Taskstream/evidence artifacts.

The current hard-proreq Execution Flow is a good prototype of that direction. It captures operator input, generates Cento context, keeps the frontend screenshot lane muted, prepares a schema-backed GPT Pro backend request, materializes backend work, writes integration and validation plans, and leaves evidence artifacts. The page proves that Cento can become the AI control plane rather than just a wrapper around models.

However, the current system is still split across too many partially overlapping surfaces:

- Skills tell Codex to route through Cento, but MCP does not yet expose the full Dev Pipeline / Build / Workset / Factory contract surface.
- Dev Pipeline Studio has structured artifacts, but the validator/proof UI is not fully aligned with the underlying receipts.
- `scripts/agent_work_app.py` owns server routes, pipeline defaults, UI state shaping, hard-proreq execution, artifact mapping, and API handlers in one large module.
- The AI lifecycle has multiple schema families (`story.json`, `validation.json`, `execution_run.json`, workset manifests, OpenAI artifacts, evidence bundles) without one top-level run envelope.
- The strongest existing pattern, "deterministic-first validation", exists in docs and tooling but should become the default mechanical gate for every AI run.

The recommendation is to rework AI around a Cento AI Runtime made of five layers:

1. Intent router: classify the user request and choose the registered Cento path.
2. Context builder: gather Cento context, code ownership, dirty state, route/API targets, and validation candidates.
3. Contract planner: create a typed story/workset/pipeline contract before model work.
4. Execution lanes: run model/tool workers only inside declared ownership, budget, and runtime constraints.
5. Evidence gate: validate with deterministic receipts, screenshots, logs, and Taskstream handoff.

Skills should become short routing adapters into this runtime, not the runtime itself.

## Research Method

Commands and surfaces used:

- `cento gather-context --no-remote`
- `cento tools`
- `cento docs agent-work`
- `cento docs build`
- `cento docs factory`
- `cento docs cento-mcp`
- `cento runtime list --json`
- `python3 scripts/cento_mcp_server.py --list-tools`
- `cento scan --query "agent-work" --no-open`
- `npx --yes playwright screenshot --browser=firefox --full-page http://127.0.0.1:47910/dev-pipeline-studio#pipeline-flow /tmp/dev-pipeline-flow.png`
- Direct API checks against `GET /api/dev-pipeline-studio`
- Direct artifact reads under `workspace/runs/dev-pipeline-studio/docs-pages/latest/`

The `cento scan --query "agent-work"` run scanned 1514 Cento source files, found 223 matched files and 1286 matches, and wrote the latest scan artifact at `workspace/runs/scan-onepager/latest/summary.json`.

## Code Places Inspected

The request asked for at least five code places in different projects. I inspected six project/surface families:

1. Cento core:
   - `scripts/agent_work_app.py`
   - `scripts/dev_pipeline_hard_proreq.py`
   - `scripts/cento_workset.py`
   - `scripts/cento_openai_worker.py`
   - `scripts/cento_mcp_server.py`
   - `scripts/agent_work.py`
   - `scripts/story_manifest.py`
   - `data/tools.json`
   - `docs/agent-work.md`
   - `docs/agent-work-story-manifest.md`
   - `docs/agent-work-validator-lane.md`
   - `docs/dev-pipeline-run-contracts.md`
   - `tests/test_dev_pipeline_delivery.py`

2. Codex/Cento skills:
   - `/home/alice/.codex/skills/cento-native/SKILL.md`
   - `/home/alice/.codex/skills/cento-native/references/routing.md`
   - `/home/alice/.codex/skills/cento-requirements-manifest/SKILL.md`
   - `/home/alice/.codex/skills/.system/skill-creator/SKILL.md`

3. GitHub plugin skills:
   - `/home/alice/.codex/plugins/cache/openai-curated/github/3c463363/skills/gh-address-comments/SKILL.md`
   - `/home/alice/.codex/plugins/cache/openai-curated/github/3c463363/skills/yeet/SKILL.md`

4. OpenCode:
   - `/home/alice/projects/opencode/packages/opencode/src/tool/tool.ts`
   - `/home/alice/projects/opencode/packages/opencode/src/tool/task.ts`
   - `/home/alice/projects/opencode/packages/opencode/src/session/system.ts`
   - `/home/alice/projects/opencode/packages/opencode/src/session/mode.ts`
   - `/home/alice/projects/opencode/packages/opencode/src/config/config.ts`

5. Docmgmt RAG project:
   - `/home/alice/projects/docmgmt/build_index.py`
   - `/home/alice/projects/docmgmt/generate_letter.py`

6. AIPOC pipeline project:
   - `/home/alice/projects/aipoc/airflow/dags/ml_training_pipeline.py`

## Live Dev Pipeline Studio Observations

The live page is already close to the desired mental model. It shows:

- Product shell: Cento Console -> Software Delivery Hub -> Dev Pipeline Studio -> Execution Flow.
- Active route: hard-proreq route.
- Run status: completed.
- Source: `cento-hard-proreq-pro`.
- Runtime: `cento-native + GPT pro request`.
- Run mode: `backend-plan-first`.
- Stage count: 4 displayed high-level cards in the UI, backed by 6 stage records in the API.
- Step count: 9 execution steps.
- Artifact count: 23 in API state, with 13 existing hard-proreq artifacts in the run payload summary.
- Run history: 9 hard-proreq runs shown in the API.

The latest run artifacts include:

- `operator_intake.json`
- `mini_cento_context.json`
- `ui_screenshot_request.json`
- `existing_ui_reference.png`
- `image_generation_request.json`
- `image_generation_response.json`
- `pro_output_schema.json`
- `pro_backend_request.json`
- `pro_backend_plan.json`
- `backend_work_manifest.json`
- `integration_plan.json`
- `validation_plan.json`
- `hard_proreq_evidence.json`

The hard-proreq run path proves a useful E2E concept:

1. Capture the operator prompt and questionnaire answer.
2. Build a mini Cento context artifact.
3. Split frontend screenshot work into a muted lane.
4. Prepare a strict schema-backed backend planning request.
5. Dispatch or simulate GPT Pro planning.
6. Convert the backend plan into Cento-native workstreams.
7. Write integration and validation plans.
8. Collect a hard-proreq evidence artifact.
9. Render the whole thing in Execution Flow.

## Current Strengths

### Cento Already Has A Native Tool Contract

`cento gather-context --no-remote` reports 45 registered tools and explicitly says `data/tools.json`, `cento tools`, `cento platforms`, and `cento docs` are the source of truth. This is exactly the right foundation for AI routing. An AI should not invent shell commands when Cento already knows the durable tool contract.

Important registered surfaces:

- `agent-work`: Taskstream-backed task creation, splitting, dispatch, prompt, runs, and validation.
- `build`: manifest-owned local build primitive with owned path checks, worker prompts, patch bundles, dry-run integration, and safe apply.
- `factory`: deterministic planning, dispatch dry-runs, patch collection, Safe Integrator, release evidence, and Autopilot.
- `workset`: N-worker runner with exclusive write paths, dependencies, structured API workers, and sequential integration.
- `cento-mcp`: structured MCP surface for context, agent-work, story, cluster, bridge, and platform operations.
- `scan`: archived local source scan one-pagers.
- `runtime`: validation of local builder runtime profiles.

### Skills Already Point In The Correct Direction

The `cento-native` skill says to treat Cento as the source of truth before inventing scripts, tools, registries, workflows, or cross-node commands. Its routing order is also correct:

1. MCP tools when structured Cento MCP exists.
2. Registered CLI tools from `cento tools` / `data/tools.json`.
3. Existing aliases.
4. Existing scripts only after confirming the registered entrypoint.
5. New code only when discovery shows no existing path fits.

That should become the default AI posture across all Cento tasks.

### Deterministic-First Validation Is Explicit

The Agent Work docs say validation is no-model by default. Builders leave durable artifacts, validators prefer files, commands, URLs, screenshots, generated reports, and review summaries over model judgment. Story manifests carry `validation.mode`, `risk`, `no_model_eligible`, `escalation_triggers`, and commands.

This is important: it prevents "the model says it is done" from becoming the validation boundary.

### Workset And OpenAI Workers Are Well-Bounded

`scripts/cento_workset.py` rejects overlapping write paths and requires explicit write paths. It supports dependencies, structured API workers, budgeted execution, patch materialization, and sequential integration. This is the right mechanical substrate for AI code work.

`scripts/cento_openai_worker.py` is also directionally strong:

- It produces structured artifacts only.
- It never mutates repository files.
- It defines explicit output schemas such as `patch_proposal.v1`, `validation_review.v1`, `workset_plan.v1`, and `hard_proreq_plan.v1`.
- It validates structured outputs before producing receipts.

### MCP Exists, But Needs A Wider Surface

`scripts/cento_mcp_server.py` exposes context, platforms, cluster status, bridge status, agent-work list/show/create/claim/update/handoff/validate, and story manifest validate/render. It constrains file paths to the Cento repo and supports read-only mode through `CENTO_MCP_READ_ONLY`.

This should be the AI's first structured interface. The gap is that Dev Pipeline Studio, Build, Workset, Factory, runtime profiles, scan, and evidence queries are not yet first-class MCP tools.

### OpenCode Shows Useful Agent Mode Patterns

OpenCode's source separates:

- Tool definitions via typed `Tool.define(...)`.
- A `task` tool that starts a subordinate session with restricted tools.
- System prompt context that loads project instructions from `AGENTS.md`, `CLAUDE.md`, and configured instruction globs.
- Modes that can disable write/edit/patch tools for planning.
- MCP configuration as typed local/remote schemas.

Cento can adopt the same idea at a higher level: separate `plan`, `build`, `validate`, `handoff`, and `review` modes as runtime policies, not just prompt instructions.

### The Docmgmt RAG Project Shows The Need For Safer Retrieval

The docmgmt project has a simple RAG loop: build a FAISS index from local documents, retrieve relevant chunks, and generate a letter with a prompt template. The pattern is useful because Cento also needs local context retrieval, but the implementation shows risks Cento should avoid:

- Retrieval is not tied to durable citations.
- There is no output schema.
- FAISS loading uses `allow_dangerous_deserialization=True`.
- The final output is written directly without validation or evidence receipts.

Cento should take the good part, local retrieval, and wrap it in safe indexes, citations, schemas, and validation.

### The Airflow DAG Shows A Clear Pipeline Mental Model

The AIPOC DAG is simple but useful as a comparison: `load_data -> train_and_validate`, with MLflow metrics. Cento should make every AI pipeline similarly explicit:

- Named task nodes.
- Declared dependencies.
- Durable outputs.
- Metrics and receipts.
- A visible run graph.

Dev Pipeline Studio is already moving in that direction.

## Key Findings

### Finding 1: The Hard-Proreq Route Is The Right Strategic Direction

The hard-proreq route is the first place where Cento behaves like an AI-native platform:

- User input becomes a typed input manifest.
- Cento context is generated before model planning.
- Frontend visual work is explicitly separated and muted.
- GPT Pro planning is schema-backed.
- Backend work becomes Cento workstreams with owned paths, dependencies, validation commands, and handoff artifacts.
- Evidence is collected as files, not just as chat.

This is the pattern to generalize.

### Finding 2: Skills Are Currently Guidance, Not Execution Contracts

Skills are useful for steering Codex, but they should not be the final source of truth for AI execution. A skill can be ignored, partially remembered, or overloaded by conversation context. Cento tools and MCP calls are more reliable because they return structured state and write durable artifacts.

Recommended posture:

- Skills route the agent to Cento.
- Cento creates and validates the execution contract.
- The agent follows the contract.
- Evidence decides whether work is done.

### Finding 3: MCP Is Too Narrow For The Desired AI Loop

Current MCP is strong for agent-work and story manifests, but the desired E2E loop also needs structured tools for:

- Dev Pipeline Studio state.
- Starting a pipeline run.
- Reading execution run artifacts.
- Running `cento scan`.
- Checking runtime profiles.
- Creating build manifests.
- Executing worksets.
- Reading Factory plan/status/evidence.
- Querying evidence completeness.

Without these MCP tools, Codex falls back to shell and ad hoc API calls. That works for a power user, but it is less reliable as an AI substrate.

### Finding 4: Execution Flow Proof And Validation Are Not Fully Aligned

The live page showed "Receipt pending" in the Proof panel even though the hard-proreq run had completed and written `hard_proreq_evidence.json`. The Validation Results panel showed `0 / 3 validators passed` and listed validators as configured, while the template-level hard-proreq validators in the manifest are `passed`, `passed`, and `muted`.

This is not just a UI polish issue. It means the AI operator cannot fully trust the visual control plane as the source of truth. The Execution Flow should derive proof status from the correct receipt type for each run source:

- Workset runs: `workset_receipt`.
- Hard-proreq runs: `hard_proreq_evidence.json`, `validation_plan.json`, and validator receipts.
- Factory runs: Factory integration/release receipts.
- Build runs: integration/apply/evidence receipts.

### Finding 5: The Code Has One Monolithic Control-Plane Module

`scripts/agent_work_app.py` currently handles static serving, Taskstream API handlers, Dev Pipeline Studio state, hard-proreq defaults, pipeline run validation, execution threading, artifact mapping, UI state shaping, and route handling. That makes it harder to evolve AI runtime behavior safely.

This is manageable now but will become a bottleneck if Dev Pipeline Studio becomes the main AI run surface.

### Finding 6: Cento Has Multiple Manifest Families Without One Run Envelope

There are strong schemas, but they live in parallel:

- `story.json`
- `validation.json`
- `deliverables.json`
- `pipeline_manifest.json`
- `execution_run.json`
- `workset.json`
- `cento.api_worker_artifact.v1`
- `cento.workset_receipt.v1`
- `hard_proreq_evidence.json`

The missing abstraction is a top-level `cento.ai_run.v1` envelope that links all of them and normalizes status, owner, scope, model usage, artifacts, receipts, validation, and next action.

### Finding 7: Runtime Profiles Are Promising But Underused

The current runtime registry has `codex-fast`, `fixture-valid`, and `python-fixture`. `codex-fast` is a command runtime using `codex exec --prompt-file {prompt}`, with timeout, patch size, changed-file limits, and network disabled.

That is the right shape. The AI rework should make runtime profile selection an explicit part of every contract:

- `planner`: cheap or strong model, no writes.
- `builder`: Codex runtime in worktree, write-limited.
- `validator`: deterministic commands first, model only if story requires it.
- `docs-evidence`: no product writes except evidence/hub paths.

### Finding 8: Existing GitHub Plugin Skills Model Good Connector Discipline

The GitHub plugin skills choose a structured connector first, then use `gh` for gaps such as thread-aware review state. That is the right precedent for Cento:

- Use Cento MCP for structured state.
- Use Cento CLI for registered durable operations.
- Use raw shell only for local coding/tests/file reads.
- Avoid pretending a flat or incomplete surface is complete.

### Finding 9: Current Hard-Proreq Pro Dispatch May Be A Deterministic Fallback

The inspected `pro_backend_plan.json` says: "GPT pro request is schema-ready; backend work uses deterministic fallback until CENTO_HARD_PROREQ_DISPATCH_PRO=1 is enabled." That is a sensible development mode, but the UI language should make clear whether the plan came from live Pro, a deterministic fallback, or a cached prior artifact.

This matters for trust, cost, and evaluation.

### Finding 10: AI Effectiveness Needs Evaluation Metrics, Not Just Better Prompts

The platform should measure:

- Time from prompt to typed contract.
- Percent of runs with complete story/validation/evidence links.
- Percent of AI runs blocked by missing context, dirty paths, or missing credentials.
- Percent of validations passing without model judgment.
- Rework rate after human review.
- Cost per accepted change.
- Number of runs with ambiguous status or missing receipts.
- Number of direct shell commands used where a Cento/MCP route existed.

## Proposed AI Architecture

### Principle

Make Cento the operating system for AI work. Models should be workers inside Cento contracts, not independent actors that happen to call Cento sometimes.

### Target Layers

#### 1. Intent Router

Input: raw user request, route, screenshot, issue, or code question.

Output: a typed routing decision.

Responsibilities:

- Classify request type: status, research, docs, UI, code change, pipeline run, Taskstream task, validation, release, cluster operation.
- Check whether an existing Cento MCP tool or registered CLI tool handles it.
- Choose whether the request needs Taskstream work or can be executed directly.
- Decide whether model work is needed at all.
- Choose a pipeline template: hard-proreq, generic-task, doc-page, UI screenshot, validation-only, release-evidence, Factory integration.

Implementation path:

- Add `cento_intent_route` as an MCP tool and CLI helper.
- Input schema should include `prompt`, `cwd`, `route`, `provided_paths`, `screenshots`, `risk_hint`, and `mode`.
- Output schema should include `route`, `required_context`, `pipeline_template`, `requires_taskstream`, `requires_model`, `requires_human`, `validation_mode`, and `next_command`.

#### 2. Context Builder

Input: routing decision.

Output: context bundle.

Responsibilities:

- Run `cento gather-context --no-remote` or full remote context when needed.
- Snapshot dirty work and protected paths.
- Identify registered tools and docs relevant to the route.
- Build code search hits with paths and line references.
- Inspect route/API/UI surface when present.
- Collect existing run artifacts and recent failures.

Implementation path:

- Generalize `mini_cento_context.json` into `cento.context_bundle.v1`.
- Add citations: every claim should point to a file path, command output artifact, API artifact, or screenshot.
- Store under `workspace/runs/ai/<run-id>/context_bundle.json`.

#### 3. Contract Planner

Input: context bundle and user request.

Output: execution contract.

Responsibilities:

- Create or update `story.json` for work that should enter Taskstream.
- Create `workset.json` for bounded code changes.
- Create `pipeline_manifest` selections for Dev Pipeline Studio.
- Create `validation.json` with deterministic commands and escalation triggers.
- Define ownership, write paths, read paths, routes, budgets, runtime profiles, and acceptance criteria.

Implementation path:

- Add a top-level `cento.ai_run.v1` manifest that links all other manifests.
- Require that every builder has explicit `owned_paths` or an explicit "planning only" mode.
- Require that every validation path declares whether it is no-model, cheap-model, strong-model, or human.

#### 4. Execution Lanes

Input: execution contract.

Output: artifacts and receipts.

Lane types:

- Context lane: deterministic.
- Planner lane: model allowed, no writes.
- Builder lane: Codex or other runtime in isolated worktree, bounded writes.
- Validator lane: deterministic first, model review only when explicitly required.
- Docs/evidence lane: durable summaries, screenshots, hubs, links.
- Integrator lane: applies only accepted bundles/receipts.

Implementation path:

- Route planner/model work through `cento_openai_worker.py` or Codex runtime profiles.
- Route code changes through `cento build` or `cento workset`.
- Route multi-task dispatch through `cento agent-work` or `cento factory`.
- Never let an AI worker both invent scope and mutate the shared worktree in one step.

#### 5. Evidence Gate

Input: execution outputs.

Output: pass/fail/block and handoff.

Responsibilities:

- Validate all declared JSON schemas.
- Run deterministic commands.
- Check artifacts exist.
- Check screenshots and UI captures when relevant.
- Produce a review summary.
- Update Taskstream only when the proper lane owns the status transition.

Implementation path:

- Make Execution Flow proof source-dependent.
- Use `story_manifest.py validate`, `agent-work validate-run`, and validation manifests for all Taskstream work.
- Add `cento evidence check <ai-run>` or MCP equivalent.

## Proposed E2E Flow

```text
User request
  -> cento_intent_route
  -> cento_context_bundle
  -> cento_ai_run manifest
  -> story/workset/pipeline contract
  -> preflight
      - dirty path check
      - protected path check
      - platform check
      - credential/model check
      - budget check
  -> model planning if needed
  -> bounded execution lane
      - build/workset/factory/agent-work
  -> deterministic validation
  -> evidence bundle
  -> Taskstream or direct handoff
  -> learning/evaluation record
```

This flow should exist whether the user starts from:

- Chat prompt.
- `/issues/new?prompt=...`.
- Dev Pipeline Studio Run Pipeline.
- Taskstream issue.
- GitHub PR feedback.
- Screenshot plus requirements.
- CLI command.

## Skill Rework Plan

### Current Skill Problem

Skills currently carry valuable instructions, but they do not create durable run state. A skill can guide the agent to do the right thing, but once the agent starts improvising, there is no guaranteed contract or evidence trail.

### Target Skill Role

Each Cento skill should answer only:

- When does this skill trigger?
- Which Cento route should be used?
- Which context/reference file should be loaded?
- Which hard stops apply?
- Which validation evidence is required?

Everything executable should move into Cento tools, MCP, or scripts.

### Recommended Skill Set

#### `cento-native`

Role: core routing and safety.

Keep it short. It should say:

- Start with Cento discovery.
- Prefer MCP.
- Prefer registered tools.
- Use Taskstream for Cento feature/automation changes.
- Use temp/cluster/batch wrappers for one-off work.
- Preserve dirty user work.

Add references:

- `references/routing.md`: existing command routing.
- `references/dev-pipeline.md`: how to use Dev Pipeline Studio and `POST /api/pipeline-runs`.
- `references/evidence.md`: story/validation/evidence requirements.
- `references/runtime.md`: model/runtime selection rules.

#### `cento-requirements-manifest`

Role: convert screenshots/mockups/rough requirements into pickup-ready contracts.

Keep hard stops. This skill should not dispatch work. It should produce `cento.requirements_manifest.v1` and, when useful, a draft `story.json`.

#### `cento-ai-run`

New role: start a Cento AI run from a prompt.

This skill should route to:

- `cento_intent_route`
- `cento_context_bundle`
- `cento_ai_run create`
- Dev Pipeline Studio or workset/build/factory depending on the routing decision.

It should be thin and mostly point to MCP/CLI.

#### `cento-validator`

New role: independent validation lane.

This skill should:

- Read `story.json` and `validation.json`.
- Run deterministic checks.
- Capture screenshots when declared.
- Write validator evidence.
- Avoid product code edits unless explicitly asked.

#### `cento-evidence-handoff`

New role: package manager-facing outputs.

This skill should:

- Build start hubs.
- Summarize evidence.
- Verify artifact links.
- Produce review notes with Delivered, Validation, Evidence, and Residual risk.

### Skill Authoring Rules

Use the skill-creator guidance:

- Keep frontmatter descriptions precise, because descriptions are the trigger mechanism.
- Keep `SKILL.md` lean.
- Move detailed material into references.
- Put deterministic/repeated logic into scripts.
- Do not put broad README-style docs inside skills.

For Cento specifically:

- A skill should never duplicate the full `cento tools` contract.
- A skill should name the tool to call and the artifact expected.
- A skill should not carry long code snippets if a Cento command can generate them.

## MCP Rework Plan

Add these MCP tools:

### Read Tools

- `cento_dev_pipeline_state`
  - Inputs: `project_id`, `template_id`, `run_id`.
  - Wraps `GET /api/dev-pipeline-studio` or direct state builder.

- `cento_dev_pipeline_run_show`
  - Inputs: `run_id`.
  - Returns execution run, artifacts, logs, validation status, and proof status.

- `cento_scan`
  - Inputs: `query`, `case_sensitive`, `no_open`.
  - Returns scan summary and artifact path.

- `cento_runtime_list`
  - Returns runtime profiles and validation status.

- `cento_evidence_check`
  - Inputs: `ai_run`, `story`, or `run_dir`.
  - Returns missing evidence, stale receipts, failed checks, and next action.

### Explicit Write Tools

- `cento_dev_pipeline_run_start`
  - Inputs: `project_id`, `template_id`, typed `inputs`.
  - Wraps the existing pipeline run API.

- `cento_ai_run_create`
  - Inputs: route decision and context bundle.
  - Writes the top-level `cento.ai_run.v1` envelope.

- `cento_build_init`
  - Inputs: task, read paths, write paths, validation tier.
  - Writes build manifest and builder prompt.

- `cento_workset_execute`
  - Inputs: workset path, runtime profile, integration mode, validation mode, budget.
  - Executes a workset and returns receipt.

- `cento_factory_plan`
  - Inputs: intake text/run dir.
  - Creates deterministic Factory plan.

Write tools should obey the current MCP pattern:

- Explicit writes only.
- `CENTO_MCP_READ_ONLY=1` disables writes.
- Paths constrained to the Cento repo root.
- Return `ok`, `exit_code`, `command`, `stdout`, `stderr`, and structured artifact paths.

## Dev Pipeline Studio Rework

### Keep

- The hard-proreq route.
- Run-scoped artifacts.
- Strict input contract.
- Muted frontend screenshot lane.
- Schema-backed backend plan.
- Evidence panel.
- Previous run history.
- Per-stage details and logs.

### Fix

- Proof panel should understand non-workset receipts.
- Validation Results should use actual validator receipt state, not only configured state.
- The stage card count should match API stages or clearly separate "phases" from "stages".
- The UI should label fallback/cached/live model execution distinctly.
- Artifact list should group artifacts by contract stage.
- The "Run pipeline" button should expose the typed input contract clearly before start.

### Add

- "Open run manifest" link.
- "Open evidence bundle" link.
- "Create Taskstream work from this plan" action.
- "Run validator now" action.
- "Promote to workset/build/factory" action.
- "Replay run from artifacts" action.
- "Copy MCP call" and "Copy CLI command" actions for every run.

## Model And Runtime Strategy

### Use Strong Models For Planning, Not Unbounded Mutation

Strong models are valuable for:

- Ambiguous decomposition.
- Architecture choices.
- Risk discovery.
- Schema-backed planning.
- Review of complex tradeoffs.

Strong models should not directly mutate the shared worktree. They should produce typed plans, workstreams, prompts, and validation recommendations.

### Use Codex Runtime Profiles For Bounded Code Work

Use runtime profiles like `codex-fast` for:

- Small owned-path code changes.
- Isolated worktree work.
- Patch proposals.
- Tests and logs.

Every code worker should get:

- Owned write paths.
- Read paths.
- Acceptance criteria.
- Validation commands.
- Protected paths.
- Budget/time limits.
- Required output artifact schema.

### Use Cheap Models For Low-Risk Assistance

Cheap/small models can:

- Classify intent.
- Summarize context bundles.
- Draft story manifests.
- Draft evidence summaries.
- Suggest validation commands.

But their output should still be checked by deterministic gates.

### Use No Model When Possible

No-model paths should handle:

- Context gathering.
- Tool lookup.
- Registry checks.
- Schema validation.
- File existence checks.
- API smoke checks.
- Screenshot capture.
- Evidence link checking.
- Worktree dirty checks.

## Proposed `cento.ai_run.v1`

This envelope should sit above current manifests.

```json
{
  "schema_version": "cento.ai_run.v1",
  "id": "ai-run-20260504-001",
  "source": {
    "kind": "chat_prompt",
    "url": "http://127.0.0.1:47910/dev-pipeline-studio#pipeline-flow",
    "issue_id": "",
    "created_at": "2026-05-04T00:00:00Z"
  },
  "route": {
    "decision": "dev-pipeline-studio",
    "project_id": "hard-proreq-project",
    "template_id": "hard-proreq-task",
    "requires_taskstream": false,
    "requires_model": true,
    "validation_mode": "no-model"
  },
  "context": {
    "bundle": "workspace/runs/ai/ai-run-20260504-001/context_bundle.json",
    "commands": ["cento gather-context --no-remote", "cento tools"],
    "code_refs": []
  },
  "contracts": {
    "story": "",
    "validation": "",
    "pipeline_manifest": "workspace/runs/dev-pipeline-studio/docs-pages/latest/pipeline_manifest.json",
    "workset": ""
  },
  "execution": {
    "status": "completed",
    "runtime": "cento-native + GPT pro request",
    "model": "gpt-5.4-pro",
    "run_id": "hard-proreq-task-hard-proreq-project-20260504T065328911797Z",
    "started_at": "",
    "finished_at": "",
    "cost_usd": 0.0
  },
  "artifacts": [],
  "receipts": [],
  "validation": {
    "status": "passed",
    "deterministic_passed": true,
    "manual_review_required": false,
    "missing": []
  },
  "handoff": {
    "status": "ready",
    "taskstream_issue": "",
    "next_action": "review backend work manifest"
  }
}
```

Benefits:

- One run can be inspected by CLI, MCP, UI, and agents.
- Receipts become source-dependent but normalized.
- Taskstream can link to a single run envelope.
- Dev Pipeline Studio can render any AI route, not only hard-proreq and generic task.
- Evaluation metrics can aggregate across run types.

## Code Structure Improvement

This is intentionally small and pragmatic. The current code works, but the AI runtime should not keep growing inside one app script.

### Split `scripts/agent_work_app.py`

Proposed structure:

```text
scripts/
  agent_work_app.py                 # thin HTTP entrypoint and server bootstrap
  agent_work_api.py                 # Taskstream issue/review API handlers
  dev_pipeline/
    __init__.py
    state.py                        # dev_pipeline_studio_state and API payload shaping
    routes.py                       # pipeline API request/response handlers
    manifests.py                    # pipeline defaults and manifest normalization
    execution.py                    # seed/spawn/finish execution runs
    hard_proreq.py                  # hard-proreq route integration
    validation.py                   # validator/proof normalization
    artifacts.py                    # artifact URL/path/size logic
    schemas.py                      # schema constants and typed payload helpers
```

Keep backward-compatible imports initially so tests can migrate incrementally.

### Move Hard-Proreq Defaults To Data

Move hard-proreq project/template/default input definitions out of Python into versioned JSON:

```text
data/dev-pipeline/templates/hard-proreq-task.json
data/dev-pipeline/projects/hard-proreq-project.json
data/dev-pipeline/schemas/pipeline-run-request.json
```

Python should load, validate, and normalize them rather than own all defaults inline.

### Normalize Status In One Place

Create one backend status normalizer and export the mapping to frontend:

- `configured`
- `queued`
- `running`
- `completed`
- `passed`
- `failed`
- `blocked`
- `muted`
- `skipped`
- `accepted`

Avoid the current mismatch where validators are `passed` in one artifact but displayed as `configured` elsewhere.

### Make Proof Source-Dependent

Create a proof resolver:

```text
resolve_proof(execution_run) -> {
  status,
  receipt_kind,
  receipt_path,
  facts,
  missing
}
```

It should know:

- `cento-workset-api-openai` -> workset receipt.
- `cento-hard-proreq-pro` -> hard-proreq evidence and validation plan.
- `cento-build` -> build integration/apply/evidence receipts.
- `cento-factory` -> factory integration/release receipts.

### Add Thin Tests Per Module

Keep the existing focused tests and add:

- `test_dev_pipeline_proof_resolver.py`
- `test_dev_pipeline_validation_status.py`
- `test_cento_ai_run_manifest.py`
- `test_cento_mcp_dev_pipeline.py`

## Roadmap

### Phase 0: Align Current Execution Flow

Target: 1-2 days.

- Fix proof status for hard-proreq.
- Fix validation status mapping.
- Add "live/fallback/cached" model source label.
- Add tests around current hard-proreq latest run state.
- Add `cento_dev_pipeline_state` MCP read tool.

### Phase 1: Add AI Run Envelope

Target: 2-4 days.

- Define `cento.ai_run.v1`.
- Write `cento ai-run create/show/check` CLI.
- Link existing Dev Pipeline runs into the envelope.
- Add evidence completeness checks.
- Render AI run summaries in Dev Pipeline Studio.

### Phase 2: Widen MCP

Target: 3-5 days.

- Add Dev Pipeline read/start tools.
- Add scan/runtime read tools.
- Add evidence check tool.
- Add build/workset write tools with read-only protection.
- Add MCP docs and smoke tests.

### Phase 3: Rework Skills Around Cento Runtime

Target: 1-3 days.

- Keep `cento-native` small.
- Add `references/dev-pipeline.md`, `references/evidence.md`, and `references/runtime.md`.
- Add `cento-ai-run`, `cento-validator`, and `cento-evidence-handoff` skills.
- Ensure each skill points to MCP/CLI, not copied logic.

### Phase 4: Generalize Hard-Proreq

Target: 1-2 weeks.

- Extract hard-proreq into data templates.
- Support generic easy/medium work through the same envelope.
- Let users promote a hard-proreq backend plan into Taskstream/Factory/workset.
- Make screenshot lane optional but visible and auditable.

### Phase 5: Evaluation Loop

Target: ongoing.

- Record run metrics.
- Track validation pass/fail causes.
- Track cost and runtime by route.
- Track rework after human review.
- Track cases where agents bypassed Cento tool routing.

## Concrete Next Tasks

1. Add `cento_dev_pipeline_state` MCP read tool.
2. Add proof resolver for hard-proreq execution runs.
3. Fix Validation Results to read real validator receipt/status state.
4. Draft `data/schemas/cento-ai-run.v1.json`.
5. Add `cento ai-run create/show/check` commands.
6. Split Dev Pipeline Studio code out of `agent_work_app.py` behind compatibility wrappers.
7. Add `cento-native/references/dev-pipeline.md`.
8. Add `cento-validator` skill for independent validation lane.
9. Add Dev Pipeline "Create Taskstream work from plan" action.
10. Add evaluation metrics to `hard_proreq_evidence.json` or the new AI run envelope.

## Bottom Line

Cento-nativeness is the right direction. The strongest design is not "more skills" or "better prompts" by itself. The strongest design is:

- skills for lightweight intent routing,
- MCP for structured Cento operations,
- registered CLI tools as durable execution contracts,
- worksets/build/factory for bounded AI work,
- story and validation manifests for acceptance,
- deterministic receipts and screenshots for proof,
- Taskstream for human-visible lifecycle,
- Dev Pipeline Studio for live run observability.

The current hard-proreq Execution Flow already demonstrates this. The next step is to turn it from a specialized route into the standard Cento AI runtime.
