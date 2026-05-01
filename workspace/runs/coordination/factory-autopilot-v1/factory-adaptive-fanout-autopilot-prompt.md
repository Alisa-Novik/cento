# Prompt For ChatGPT Pro / Codex: Build Factory Adaptive Fanout Autopilot For Cento

Saved from operator context on 2026-05-01.

## Package

```text
factory-autopilot-v1
```

Working title:

```text
Factory Adaptive Fanout Autopilot
```

This is part of the original "solve Factorio" strategy for Cento: use AI and automation to scale AI and automation while lowering cost and increasing reliability.

The Autopilot layer should move the human operator out of the critical path without turning Cento into an uncontrolled agent launcher.

Core loop:

```text
scan -> decide -> act once -> record evidence -> adjust fanout -> repeat
```

Core rule:

```text
Fanout may increase only when validation and integration are keeping up.
```

Do not build reckless high-fanout. Build adaptive fanout with hard brakes.

## Role

Operate as:

```text
- principal AI systems architect
- senior dev-platform engineer
- Cento Factory coordinator
- safety-oriented automation designer
```

Output should be directly usable by Codex or by `cento agent-work split`.

Be concrete. Avoid strategy fluff. Produce implementation-ready architecture, commands, artifacts, schemas, tasks, acceptance criteria, validation commands, and rollout plan.

## Background

Cento is intended to become a self-improving development factory.

Desired end state:

```text
I say: "develop me a career consulting module."

Cento:
  - interprets the request
  - creates a factory plan
  - creates Taskstream epics/tasks
  - generates story.json and validation.json
  - dispatches bounded workers
  - validates mostly without model calls
  - collects patches
  - integrates safely
  - updates docs/tool registries
  - generates screenshots/evidence
  - renders release packet
  - learns from the run
```

The point is not "many agents." The point is:

```text
more throughput with less chaos
```

Strategic policy:

```text
If shell can answer it, shell answers it.
If a manifest can preserve it, write the manifest.
If Tier 0 can validate it, do not ask AI to review it.
If AI is needed, give it only the narrow failing artifact.
```

## Intended Factory Sequence

Assume these packages either exist or are being built before Autopilot:

```text
factory-planning-v1
factory-dispatch-v1
factory-integration-v1
factory-autopilot-v1
```

Planning purpose:

```text
request -> factory-plan.json -> story.json -> validation.json -> evidence hub
```

Dispatch purpose:

```text
factory-plan.json -> queue -> leases -> worktrees -> worker prompt bundles -> patch bundles -> integration dry-run
```

Integration purpose:

```text
patch bundles -> integration worktree/branch -> ordered patch application -> validation after each patch -> rollback -> release candidate
```

Autopilot purpose:

```text
Repeatedly decide whether to dispatch, collect, validate, integrate, render, pause, escalate, or stop.
```

Autopilot does not replace Dispatch or Integration. Autopilot orchestrates them.

## Cento Context

Repo:

```text
/home/alice/projects/cento
```

Cento conventions:

```text
scripts/                 executable tools and canonical automation home
scripts/lib/             shared shell helpers
data/tools.json          central registry of available tools
data/cento-cli.json      canonical JSON docs for root cento CLI built-ins
mcp/                     repo-root MCP setup and tool-call guidance
templates/               app/report/project templates
standards/               implementation and UX standards
workflows/               operating playbooks
workspace/runs/          generated run artifacts, reports, evidence, prompts, logs
docs/                    generated or maintained reference docs
```

Keep these aligned when tool surfaces change:

```text
README.md
Makefile
data/tools.json
data/cento-cli.json
docs/tool-index.md
docs/platform-support.md
```

Implementation preferences:

```text
- Prefer shell for orchestration/glue.
- Prefer Python for structured parsing/reporting.
- Avoid mandatory external dependencies where standard tools suffice.
- Every new tool should be standalone and registered.
- Generated artifacts should live under workspace/runs/.
- Do not silently mutate Taskstream or main branch.
- Use dry-run by default.
```

## Existing Relevant Tool Surfaces

Assume Cento has or is building these command families:

```text
cento
cento cluster
cento agent-work
cento agent-work-app
cento agent-manager
cento agent-pool-kick
cento story-manifest
cento validation-manifest
cento validator-tier0
cento no-model-validation-e2e
cento story-screenshot-runner
cento mcp
cento crm
cento funnel
cento gather-context
cento notify
cento scan
cento factory
```

Autopilot should call or coordinate existing Factory surfaces. Do not duplicate their core logic unless needed for fixture isolation.

## Mission

Build a safe adaptive fanout loop for Cento Factory.

Autopilot should repeatedly:

```text
1. scan current Factory run state
2. scan Agent Manager state
3. inspect queue, leases, patch backlog, integration backlog, validation backlog, and cost budget
4. decide whether to dispatch more work, collect existing work, validate, integrate, render, pause, escalate, or stop
5. execute at most one bounded control action per cycle
6. write a machine-readable iteration summary
7. render operator-facing evidence
8. stop after max cycles, budget limits, no-progress limits, or safety gates
```

Autopilot should prevent:

```text
- runaway workers
- duplicate workers
- stale ledgers
- too many patches waiting for integration
- validation backlog explosion
- cost blowups
- protected shared-path conflicts
- false confidence from weak checks
- automatic merge to main
- hidden manual review
```

## Non-Negotiable Constraints

Do not propose or implement:

```text
- abusing ChatGPT Pro
- credential sharing
- UI scraping
- consumer ChatGPT as unattended backend
- unbounded worker spawning
- thousands of agents
- automatic merge to main
- unattended production release
- semantic conflict resolution pretending to be deterministic
- hidden strong-model review
- bypassing existing no-model validation
```

Default posture:

```text
dry-run first
explicit --execute required for live action
one bounded action per cycle
every decision recorded
every stop reason recorded
zero-AI E2E required
```

## Operating Principle

Autopilot is not a "do everything" agent.

It is a deterministic control loop.

Core invariant:

```text
Autopilot can dispatch more workers only when downstream systems are healthy.
```

If integration falls behind, Autopilot should stop dispatching and integrate.

If validation falls behind, Autopilot should stop dispatching and validate.

If Agent Manager sees stale/duplicate runs, Autopilot should pause or reconcile.

If patch rejection rate rises, Autopilot should reduce fanout.

If cost budget is low, Autopilot should reduce fanout or stop.

## Desired Operator Flow

Dry-run:

```bash
cento factory autopilot RUN_ID --dry-run --cycles 3
```

Controlled execution:

```bash
cento factory autopilot RUN_ID \
  --execute \
  --cycles 5 \
  --max-builders 4 \
  --max-validators 3 \
  --max-integrators 1 \
  --budget-usd 2.00
```

Status:

```bash
cento factory autopilot-status RUN_ID --json
```

Render:

```bash
cento factory autopilot-render RUN_ID
```

A single Autopilot run should answer:

```text
What did Cento inspect?
What action did it choose?
Why?
What command did it run?
What happened?
What changed?
Did fanout increase, decrease, or hold?
What should happen next?
Why did it stop?
```

## Artifact Layout

For each Factory run:

```text
workspace/runs/factory/<run-id>/autopilot/
├── autopilot-state.json
├── policy.json
├── cycles/
│   ├── 0001/
│   │   ├── scan.json
│   │   ├── pressure.json
│   │   ├── safety-gates.json
│   │   ├── decision.json
│   │   ├── action.json
│   │   ├── result.json
│   │   └── summary.md
│   └── ...
├── events.jsonl
├── metrics.json
├── fanout-history.json
├── budget.json
├── stop-reason.json
├── autopilot-summary.md
└── autopilot-panel.html
```

## Core Schema Direction

Required schemas:

```text
factory-autopilot-state/v1
factory-autopilot-policy/v1
factory-autopilot-scan/v1
factory-autopilot-pressure/v1
factory-autopilot-safety-gates/v1
factory-autopilot-decision/v1
factory-autopilot-action/v1
factory-autopilot-result/v1
factory-autopilot-metrics/v1
factory-autopilot-stop-reason/v1
```

Every cycle must record:

```text
duration
command run
exit code
outputs
decision
reason
AI calls used
estimated cost
progress made
next recommended action
```

## Cycle Algorithm

Each cycle must:

```text
1. Acquire Autopilot lock.
2. Load policy.
3. Load run state.
4. Scan Factory state.
5. Scan Agent Manager state.
6. Scan git/cluster/Taskstream state if available.
7. Compute pressure metrics.
8. Evaluate safety gates.
9. Decide exactly one action.
10. Execute exactly one action.
11. Record result.
12. Update metrics.
13. Update fanout policy.
14. Append event log.
15. Release lock.
16. Stop or continue.
```

Use filesystem locking with atomic mkdir:

```text
workspace/runs/factory/<run-id>/autopilot/autopilot.lock/
```

Default lock TTL:

```text
10 minutes
```

## Action Decision Policy

Priority order:

```text
1. If safety gate fails -> pause or escalate.
2. If stale/duplicate workers exist -> collect/reconcile before dispatch.
3. If patch backlog exists -> integrate before dispatching more builders.
4. If validation backlog exists -> validate before dispatching more builders.
5. If integration backlog exceeds threshold -> integrate before dispatching more builders.
6. If all backlogs are healthy and queue has runnable work -> dispatch small batch.
7. If no runnable work exists -> render summary and stop.
```

Allowed actions:

```text
dispatch
collect
validate
integrate
render
pause
escalate
stop
```

Dispatch only if:

```text
- Agent Manager healthy
- queue valid
- leases valid
- no protected path conflict
- validation backlog below threshold
- integration backlog below threshold
- patch backlog below threshold
- cost budget remains
- previous cycle made progress
```

## Adaptive Fanout Policy

Start conservative:

```json
{
  "initial_builders": 2,
  "initial_validators": 2,
  "initial_integrators": 1,
  "max_builders": 4,
  "max_validators": 3,
  "max_integrators": 1,
  "max_cycles": 5,
  "max_ai_calls_per_task": 1,
  "max_run_budget_usd": 2.0
}
```

Increase fanout only if previous cycle has:

```text
- zero critical Agent Manager issues
- zero duplicate active runs
- stale_run_count <= threshold
- patch_rejection_rate <= 20%
- integration_backlog_count <= 4
- validation_backlog_count <= 6
- validation_pass_rate >= 80%
- no protected path conflicts
- cost budget remaining
- progress_made = true
```

Decrease fanout if:

```text
- patch rejection rate increases
- validation backlog grows
- integration backlog grows
- stale workers appear
- duplicate workers appear
- cost rises faster than accepted patches
- docs/tool registry gates fail
- no progress in previous cycle
```

Hard stop if:

```text
- Agent Manager critical issue exists
- duplicate active worker exists
- protected shared path conflict exists
- integration branch becomes invalid
- rollback metadata missing
- budget exhausted
- same task fails twice
- no progress for two cycles
```

Fanout must never exceed configured max values.

## Safety Gates

Implement:

```text
agent_manager_critical
duplicate_active_worker
stale_run_threshold
protected_path_conflict
queue_valid
leases_valid
validation_manifest_present
integration_state_valid
rollback_metadata_present_when_applying
budget_remaining
same_task_failed_twice
no_progress_limit
dirty_git_owned_path_conflict
docs_registry_gate
```

## Cost and Budget Policy

Default:

```json
{
  "max_run_budget_usd": 2.0,
  "max_ai_calls_per_task": 1,
  "max_strong_model_calls_per_run": 0,
  "budget_warning_threshold_usd": 0.5
}
```

Autopilot should track:

```text
ai_calls_used
estimated_cost_usd
budget_remaining_usd
cost_per_collected_patch
cost_per_validated_patch
cost_per_integrated_patch
```

Autopilot should reduce fanout or stop if:

```text
- budget remaining is below warning threshold
- budget exhausted
- cost per accepted patch worsens sharply
- repeated retries consume budget without progress
```

## Worker Quality Feedback

Compute:

```text
patch_rejection_rate
validation_pass_rate
unowned_path_violation_count
docs_registry_gate_failure_count
same_task_retry_count
stale_worker_count
time_to_collected_patch
time_to_validated_patch
time_to_integrated_patch
```

Use deterministic counters first.

## Required Commands

Add or extend:

```bash
cento factory autopilot RUN_ID --dry-run
cento factory autopilot RUN_ID --execute
cento factory autopilot RUN_ID --cycles 5
cento factory autopilot RUN_ID --max-builders 4
cento factory autopilot RUN_ID --max-validators 3
cento factory autopilot RUN_ID --max-integrators 1
cento factory autopilot RUN_ID --budget-usd 2.00
cento factory autopilot-status RUN_ID --json
cento factory autopilot-render RUN_ID
```

Dry-run default:

```text
If neither --dry-run nor --execute is supplied, use --dry-run.
```

`--execute` must still obey hard safety gates.

## Suggested Files

Add:

```text
scripts/factory_autopilot.py
scripts/factory_autopilot_state.py
scripts/factory_autopilot_scan.py
scripts/factory_autopilot_policy.py
scripts/factory_autopilot_fanout.py
scripts/factory_autopilot_budget.py
scripts/factory_autopilot_render.py
scripts/factory_autopilot_e2e.py
scripts/fixtures/factory-autopilot/
scripts/fixtures/factory-autopilot-state/
scripts/fixtures/factory-autopilot-scan/
scripts/fixtures/factory-autopilot-policy/
scripts/fixtures/factory-autopilot-fanout/
scripts/fixtures/factory-autopilot-budget/
scripts/fixtures/factory-autopilot-loop/
templates/factory/autopilot-summary.md
templates/factory/autopilot-panel.html
docs/factory-autopilot.md
```

Update:

```text
scripts/factory.py
scripts/cento
data/tools.json
data/cento-cli.json
docs/factory.md
docs/tool-index.md
docs/platform-support.md
README.md
```

## Console UI Requirements

Add a Factory Autopilot panel to Cento Console.

Required sections:

```text
Autopilot Overview
Cycle Timeline
Current Decision
Fanout / Backpressure
Safety Gates
Cost Budget
Throughput
Quality
Stop Reason
Next Recommended Action
```

Use Cento dark theme:

```text
dark charcoal background
orange accents
green = pass/implemented
yellow = partial/warning
red = blocked/fail
blue = info/planned
```

## Implementation Tasks

Create Taskstream tasks using package:

```text
factory-autopilot-v1
```

Task titles:

```text
EPIC: Factory Adaptive Fanout Autopilot v1
Autopilot state schema and validator
Autopilot scan aggregator
Autopilot safety gate evaluator
Autopilot pressure calculator
Autopilot policy engine
Adaptive fanout and backpressure controller
Autopilot cost and budget gate
Autopilot action executor
Autopilot iteration loop
Autopilot CLI facade and command registration
Autopilot zero-AI E2E
Autopilot evidence renderer
Autopilot Console panel
Autopilot screenshot evidence
Autopilot docs and operator rollout
Autopilot release evidence packet
```

## Acceptance Commands

Primary zero-AI E2E:

```bash
python3 scripts/factory_autopilot_e2e.py \
  --fixture career-consulting \
  --out workspace/runs/factory/factory-autopilot-e2e
```

Autopilot dry-run:

```bash
cento factory autopilot factory-autopilot-e2e \
  --dry-run \
  --cycles 3
```

Status:

```bash
cento factory autopilot-status factory-autopilot-e2e --json
```

Render:

```bash
cento factory autopilot-render factory-autopilot-e2e
```

Verify artifacts:

```bash
test -f workspace/runs/factory/factory-autopilot-e2e/autopilot/autopilot-state.json
test -f workspace/runs/factory/factory-autopilot-e2e/autopilot/policy.json
test -f workspace/runs/factory/factory-autopilot-e2e/autopilot/metrics.json
test -f workspace/runs/factory/factory-autopilot-e2e/autopilot/stop-reason.json
test -f workspace/runs/factory/factory-autopilot-e2e/autopilot/autopilot-summary.md
test -f workspace/runs/factory/factory-autopilot-e2e/autopilot/autopilot-panel.html
```

Verify cycle artifacts:

```bash
test -f workspace/runs/factory/factory-autopilot-e2e/autopilot/cycles/0001/scan.json
test -f workspace/runs/factory/factory-autopilot-e2e/autopilot/cycles/0001/decision.json
test -f workspace/runs/factory/factory-autopilot-e2e/autopilot/cycles/0001/action.json
test -f workspace/runs/factory/factory-autopilot-e2e/autopilot/cycles/0001/result.json
```

Verify zero AI:

```bash
grep -q "AI calls used: 0" \
  workspace/runs/factory/factory-autopilot-e2e/e2e-summary.md
```

No-model regression:

```bash
python3 scripts/no_model_validation_e2e.py
```

Tool/docs registry:

```bash
cento factory --help
python3 -m json.tool data/tools.json
python3 -m json.tool data/cento-cli.json
grep -R "factory autopilot" docs README.md
grep -R "adaptive fanout" docs/factory-autopilot.md
```

Console screenshot validation:

```bash
python3 scripts/factory_autopilot_console_e2e.py \
  --run workspace/runs/factory/factory-autopilot-e2e

test -f workspace/runs/factory/factory-autopilot-e2e/screenshots/autopilot-overview.png
```

## Definition Of Done

`factory-autopilot-v1` is done when:

```text
- Autopilot can scan a Factory run.
- Autopilot can compute pressure metrics.
- Autopilot can evaluate safety gates.
- Autopilot can decide exactly one safe action per cycle.
- Autopilot can run multiple dry-run cycles.
- Autopilot can increase, decrease, or hold fanout based on metrics.
- Autopilot blocks dispatch when validation/integration backlogs grow.
- Autopilot records every decision with reasons.
- Autopilot records cost, AI calls, safety gates, throughput, and quality metrics.
- Autopilot writes stop-reason.json.
- Autopilot renders operator evidence.
- Console shows Autopilot state.
- Full E2E uses zero AI calls.
- Existing no-model validation E2E still passes.
- No automatic merge to main exists.
- No unbounded worker spawning exists.
```

Hard success metric:

```text
An operator can run `cento factory autopilot RUN_ID --dry-run --cycles 3` and see exactly why Cento chose dispatch, collect, validate, integrate, pause, or stop.
```

## First Real-World Trial After E2E

After the zero-AI fixture passes, run Autopilot against a small real Factory package:

```text
career-consulting-module-v1
```

Initial live limits:

```json
{
  "cycles": 3,
  "max_builders": 2,
  "max_validators": 2,
  "max_integrators": 1,
  "budget_usd": 1.0,
  "execute_dispatch": false,
  "execute_integration": false
}
```

Dry-run command:

```bash
cento factory autopilot career-consulting-module-v1 \
  --dry-run \
  --cycles 3 \
  --max-builders 2 \
  --max-validators 2 \
  --max-integrators 1 \
  --budget-usd 1.00
```

Even in execute mode:

```text
Integration application should remain isolated to integration worktree/branch.
No automatic merge to main.
```

## Residual Risks

Track:

```text
- Real Codex/Claude dispatch may still need runtime-specific hardening.
- Factory Integration must be mature before execute-mode fanout increases.
- Console may initially be read-only.
- Agent Manager stale-run signals may need tuning.
- Cost accounting may be approximate until factory-cost-v1.
- Cross-node validation remains deferred to build-farm.
- Strong-model escalation remains manual.
```

Render these in:

```text
workspace/runs/factory/<run-id>/autopilot/residual-risks.md
```

## Deferred Work

Defer to `factory-runtime-v1`:

```text
- runtime-specific Codex/Claude adapters
- live local/open model routing
- Batch/API worker adapters
- model call cache replay
- prompt execution history by provider
```

Defer to `factory-buildfarm-v1`:

```text
- Linux/macOS/VM validation matrix
- remote test execution
- cross-platform artifact collection
- build farm dashboard
```

Defer to `factory-research-map-v1`:

```text
- automatic PDF/spec section extraction
- research-to-task coverage inference
- implementation map status suggestions
- evidence linking from patches back to research sections
```

Defer to `factory-cost-v1`:

```text
- precise token accounting
- cost-per-validated-patch dashboard
- cached prompt savings dashboard
- worker quality scoring by runtime/model
```

Defer to `factory-release-v1`:

```text
- human approval workflow
- final merge command
- release note publishing
- changelog integration
```

## Output Format For ChatGPT Pro / Codex Planning

Produce:

```text
1. Executive summary.
2. Autopilot architecture.
3. Artifact/schema design.
4. Cycle algorithm.
5. Fanout/backpressure policy.
6. Safety gates.
7. Cost/budget policy.
8. Command surface.
9. Implementation file plan.
10. Taskstream task list.
11. Acceptance commands.
12. Definition of done.
13. Residual risks.
14. Immediate Codex implementation instructions.
```

Be direct. Optimize for implementation this week.

Do not hand-wave. Do not say "thousands of agents." Do not rely on a model judge where deterministic checks suffice.

The result should make Cento feel like this:

```text
I give Cento a goal.
Cento plans work.
Cento starts only safe work.
Cento validates finished work.
Cento integrates only coherent patches.
Cento slows down when quality drops.
Cento produces evidence every cycle.
```

That is the high-fanout path.
