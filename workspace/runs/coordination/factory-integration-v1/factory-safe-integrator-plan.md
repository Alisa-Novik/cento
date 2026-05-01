# Factory Safe Integrator v1

Saved from operator context on 2026-05-01.

## Next Move

After `factory-dispatch-v1`, the next move should be:

```text
factory-integration-v1
```

Working title:

```text
Factory Safe Integrator
```

This package turns Cento from "can safely prepare/dispatch work" into "can safely deliver a coherent module." It is the next real Factorio unlock from the original prompt:

```text
user request -> task graph -> workers -> patches -> validation -> integration -> docs/release evidence
```

## Why This, Not Live High-Fanout Yet

Do not build high-fanout worker execution next.

After `factory-dispatch-v1`, Cento will be able to create queues, leases, worktrees, prompt bundles, patch bundles, and integration dry-runs. The bottleneck then becomes:

```text
Can Cento safely combine many worker outputs into one validated module?
```

If workers scale before integration is solved, the result is more patches, more conflicts, more stale runs, more review burden, and more chaos.

The next leverage layer is therefore:

```text
patch bundles -> integration branch -> per-patch validation -> rollback -> release candidate
```

That is the control plane that lets Cento safely increase worker count later.

## Epic

```text
EPIC: Factory Safe Integrator v1
Package: factory-integration-v1
```

Epic description:

```text
Build the safe integration layer for Cento Factory. Given a validated factory run with patch bundles, create an isolated integration worktree/branch, apply candidate patches in dependency order, validate after each patch, quarantine failures, enforce owned-path and docs/tool registry gates, generate rollback metadata, sync Taskstream status previews, and render a release candidate packet. Do not merge to main automatically.
```

## What This Unlocks

Before:

```text
Cento can plan and prepare work.
```

After:

```text
Cento can produce a validated release candidate from multiple bounded workers.
```

That is the moment Cento starts behaving like a real development factory instead of a task generator.

## Operator Flow

Target operator flow:

```bash
cento factory integrate RUN_ID --plan

cento factory integrate RUN_ID \
  --prepare-branch \
  --branch factory/RUN_ID/integration

cento factory integrate RUN_ID \
  --apply \
  --validate-each \
  --limit 3

cento factory validate-integrated RUN_ID

cento factory release-candidate RUN_ID

cento factory sync-taskstream RUN_ID --dry-run

cento factory render-hub RUN_ID
```

Important defaults:

```text
No automatic merge to main.
No silent Taskstream Done transition.
No high-fanout execution increase yet.
```

## Core Artifacts

Add:

```text
workspace/runs/factory/<run-id>/integration/
├── integration-state.json
├── integration-branch.json
├── apply-plan.json
├── apply-log.jsonl
├── applied-patches.json
├── rejected-patches.json
├── validation-after-each-patch.json
├── quarantine/
│   └── <task-id>/
├── rollback-plan.json
├── merge-readiness.json
├── taskstream-sync-preview.json
├── release-candidate.md
└── residual-risks.md
```

Most important artifact:

```text
integration-state.json
```

It should answer:

- Which patches were applied?
- Which were rejected?
- Why?
- What validation passed after each patch?
- What branch/worktree contains the release candidate?
- What remains risky?
- What can be merged by a human/operator?

## First Implementation Slice

The smallest useful version:

```text
Given fixture patch bundles, create an integration worktree, apply patches in planned order, run validation after each patch, reject/quarantine bad patches, and produce release-candidate.md.
```

This can be zero-AI.

No models. No live dispatch. No remote complexity.

## Package Boundaries

In scope:

- integration worktree creation
- integration branch metadata
- patch apply ordering
- git apply checks
- actual patch application inside isolated worktree
- per-patch validation
- rollback plan
- failed patch quarantine
- docs/tool registry gate
- release candidate rendering
- merge readiness report
- Taskstream sync dry-run
- Console integration status

Out of scope:

- automatic merge to main
- large-scale live worker dispatch
- Batch/API worker execution
- full cross-node build farm
- semantic conflict resolution
- automatic strong-model review
- production deployment

## Taskstream Tasks

```yaml
- title: "EPIC: Factory Safe Integrator v1"
  package: "factory-integration-v1"
  lane: "coordinator"
  node: "linux"
  owned_scope:
    - "workspace/runs/factory/factory-integration-e2e/"
  goal: "Coordinate safe integration of Factory patch bundles into isolated release candidates."
  expected_outputs:
    - "Factory integration epic"
    - "Child tasks with story.json and validation.json"
    - "Release evidence packet"
  validation_commands:
    - "cento agent-work list --json"
    - "cento factory status factory-integration-e2e --json"
  no_model_eligible: true
  risk: "low"
  dependencies: []
```

```yaml
- title: "Integration state schema and validator"
  package: "factory-integration-v1"
  lane: "builder"
  node: "linux"
  owned_scope:
    - "scripts/factory_integration_state.py"
    - "scripts/fixtures/factory-integration-state/"
  goal: "Define and validate integration-state.json, apply-plan.json, applied/rejected patch records, rollback metadata, and merge readiness."
  expected_outputs:
    - "integration-state schema"
    - "pass/fail fixtures"
    - "machine-readable validator output"
  validation_commands:
    - "python3 scripts/factory_integration_state.py validate scripts/fixtures/factory-integration-state/pass/integration-state.json"
    - "! python3 scripts/factory_integration_state.py validate scripts/fixtures/factory-integration-state/fail/missing-rollback.json"
  no_model_eligible: true
  risk: "low"
  dependencies: []
```

```yaml
- title: "Integration worktree and branch preparer"
  package: "factory-integration-v1"
  lane: "builder"
  node: "linux"
  owned_scope:
    - "scripts/factory_integrate.py"
    - "workspace/factory-integration-worktrees/.gitkeep"
  goal: "Create an isolated integration worktree and branch for a factory run without touching main."
  expected_outputs:
    - "integration worktree created"
    - "branch metadata recorded"
    - "base SHA recorded"
    - "dirty worktree preflight check"
  validation_commands:
    - "python3 scripts/factory_integrate.py prepare scripts/fixtures/factory-integration/pass-run --dry-run"
    - "python3 scripts/factory_integrate.py prepare scripts/fixtures/factory-integration/pass-run --worktree /tmp/cento-factory-integration-test"
  no_model_eligible: true
  risk: "medium"
  dependencies:
    - "Integration state schema and validator"
```

```yaml
- title: "Patch ordering and applicability checker"
  package: "factory-integration-v1"
  lane: "builder"
  node: "linux"
  owned_scope:
    - "scripts/factory_integrate.py"
    - "scripts/fixtures/factory-integration/"
  goal: "Read patch bundles, dependency order, owned paths, and validation status to create apply-plan.json."
  expected_outputs:
    - "apply-plan.json"
    - "accepted/rejected candidate lists"
    - "skip reasons"
    - "dependency-aware ordering"
  validation_commands:
    - "python3 scripts/factory_integrate.py plan scripts/fixtures/factory-integration/pass-run"
    - "python3 -m json.tool scripts/fixtures/factory-integration/pass-run/integration/apply-plan.json"
  no_model_eligible: true
  risk: "medium"
  dependencies:
    - "Integration state schema and validator"
```

```yaml
- title: "Sequential patch applier with checkpoints"
  package: "factory-integration-v1"
  lane: "builder"
  node: "linux"
  owned_scope:
    - "scripts/factory_integrate.py"
    - "scripts/fixtures/factory-integration-apply/"
  goal: "Apply candidate patches one at a time in the integration worktree, record checkpoints, and reject patches that fail git apply."
  expected_outputs:
    - "apply-log.jsonl"
    - "applied-patches.json"
    - "rejected-patches.json"
    - "per-patch checkpoint metadata"
  validation_commands:
    - "python3 scripts/factory_integrate.py apply scripts/fixtures/factory-integration-apply/pass-run --worktree /tmp/cento-factory-apply-test"
    - "! python3 scripts/factory_integrate.py apply scripts/fixtures/factory-integration-apply/fail-conflict --worktree /tmp/cento-factory-apply-fail-test"
  no_model_eligible: true
  risk: "medium"
  dependencies:
    - "Integration worktree and branch preparer"
    - "Patch ordering and applicability checker"
```

```yaml
- title: "Per-patch validation runner"
  package: "factory-integration-v1"
  lane: "validator"
  node: "linux"
  owned_scope:
    - "scripts/factory_integrated_validate.py"
    - "scripts/fixtures/factory-integrated-validate/"
  goal: "Run validation commands after each applied patch and record validation-after-each-patch.json."
  expected_outputs:
    - "validation-after-each-patch.json"
    - "per-command duration"
    - "decision per patch"
    - "AI calls used: 0"
  validation_commands:
    - "python3 scripts/factory_integrated_validate.py scripts/fixtures/factory-integrated-validate/pass-run --json"
    - "python3 -m json.tool scripts/fixtures/factory-integrated-validate/pass-run/integration/validation-after-each-patch.json"
  no_model_eligible: true
  risk: "medium"
  dependencies:
    - "Sequential patch applier with checkpoints"
```

```yaml
- title: "Rollback and quarantine manager"
  package: "factory-integration-v1"
  lane: "builder"
  node: "linux"
  owned_scope:
    - "scripts/factory_rollback.py"
    - "scripts/fixtures/factory-rollback/"
  goal: "Generate rollback-plan.json and quarantine failed patches with reason, failed command, and recovery recommendation."
  expected_outputs:
    - "rollback-plan.json"
    - "quarantine/<task-id>/"
    - "failure reason metadata"
    - "reverse patch commands"
  validation_commands:
    - "python3 scripts/factory_rollback.py plan scripts/fixtures/factory-rollback/pass-run"
    - "test -f scripts/fixtures/factory-rollback/pass-run/integration/rollback-plan.json"
  no_model_eligible: true
  risk: "medium"
  dependencies:
    - "Per-patch validation runner"
```

```yaml
- title: "Docs and tool registry integration gate"
  package: "factory-integration-v1"
  lane: "validator"
  node: "linux"
  owned_scope:
    - "scripts/factory_registry_gate.py"
    - "scripts/fixtures/factory-registry-gate/"
  goal: "Reject integrated candidates that change command surfaces without matching registry and docs updates."
  expected_outputs:
    - "registry gate checker"
    - "docs/tool alignment report"
    - "pass/fail fixtures"
  validation_commands:
    - "python3 scripts/factory_registry_gate.py scripts/fixtures/factory-registry-gate/pass-run"
    - "! python3 scripts/factory_registry_gate.py scripts/fixtures/factory-registry-gate/fail-missing-tool-index"
  no_model_eligible: true
  risk: "low"
  dependencies:
    - "Sequential patch applier with checkpoints"
```

```yaml
- title: "Merge readiness report"
  package: "factory-integration-v1"
  lane: "validator"
  node: "linux"
  owned_scope:
    - "scripts/factory_merge_readiness.py"
    - "scripts/fixtures/factory-merge-readiness/"
  goal: "Produce merge-readiness.json summarizing applied patches, validation, registry gates, residual risk, and whether human merge review is ready."
  expected_outputs:
    - "merge-readiness.json"
    - "ready/not-ready decision"
    - "blocking reasons"
    - "residual risk list"
  validation_commands:
    - "python3 scripts/factory_merge_readiness.py scripts/fixtures/factory-merge-readiness/pass-run --json"
    - "python3 -m json.tool scripts/fixtures/factory-merge-readiness/pass-run/integration/merge-readiness.json"
  no_model_eligible: true
  risk: "low"
  dependencies:
    - "Docs and tool registry integration gate"
    - "Rollback and quarantine manager"
```

```yaml
- title: "Taskstream integration sync preview"
  package: "factory-integration-v1"
  lane: "builder"
  node: "linux"
  owned_scope:
    - "scripts/factory_taskstream_sync.py"
    - "scripts/fixtures/factory-taskstream-sync/"
  goal: "Preview Taskstream status updates based on integration results without mutating the board by default."
  expected_outputs:
    - "taskstream-sync-preview.json"
    - "Running to Validating preview"
    - "Validating to Review preview"
    - "Blocked transition preview for rejected patches"
  validation_commands:
    - "python3 scripts/factory_taskstream_sync.py scripts/fixtures/factory-taskstream-sync/pass-run --dry-run"
    - "python3 -m json.tool scripts/fixtures/factory-taskstream-sync/pass-run/integration/taskstream-sync-preview.json"
  no_model_eligible: true
  risk: "medium"
  dependencies:
    - "Merge readiness report"
```

```yaml
- title: "Release candidate renderer"
  package: "factory-integration-v1"
  lane: "docs-evidence"
  node: "macos"
  owned_scope:
    - "scripts/factory_release_candidate.py"
    - "templates/factory/release-candidate.md"
    - "templates/factory/integration-summary.html"
  goal: "Render a human-readable release candidate packet from integration state, validation, rollback, merge readiness, and Taskstream sync preview."
  expected_outputs:
    - "release-candidate.md"
    - "integration-summary.html"
    - "accepted/rejected patch summary"
    - "human merge checklist"
  validation_commands:
    - "python3 scripts/factory_release_candidate.py scripts/fixtures/factory-merge-readiness/pass-run"
    - "test -f scripts/fixtures/factory-merge-readiness/pass-run/integration/release-candidate.md"
    - "grep -q \"Merge readiness\" scripts/fixtures/factory-merge-readiness/pass-run/integration/release-candidate.md"
  no_model_eligible: true
  risk: "low"
  dependencies:
    - "Merge readiness report"
    - "Taskstream integration sync preview"
```

```yaml
- title: "Factory integration CLI facade"
  package: "factory-integration-v1"
  lane: "builder"
  node: "linux"
  owned_scope:
    - "scripts/factory.py"
    - "scripts/cento"
    - "data/tools.json"
    - "data/cento-cli.json"
  goal: "Wire integration commands into `cento factory integrate`, `validate-integrated`, `release-candidate`, and `sync-taskstream`."
  expected_outputs:
    - "`cento factory integrate RUN_ID --plan`"
    - "`cento factory integrate RUN_ID --prepare-branch`"
    - "`cento factory integrate RUN_ID --apply --validate-each`"
    - "`cento factory release-candidate RUN_ID`"
    - "registry updates"
  validation_commands:
    - "cento factory --help"
    - "cento factory integrate factory-integration-e2e --plan"
    - "python3 -m json.tool data/tools.json"
    - "python3 -m json.tool data/cento-cli.json"
  no_model_eligible: true
  risk: "medium"
  dependencies:
    - "Release candidate renderer"
```

```yaml
- title: "Factory integration zero-AI E2E"
  package: "factory-integration-v1"
  lane: "validator"
  node: "linux"
  owned_scope:
    - "scripts/factory_integration_e2e.py"
    - "scripts/fixtures/factory-integration-e2e/"
    - "workspace/runs/factory/factory-integration-e2e/"
  goal: "Create a complete no-model E2E from patch bundles to integration branch, sequential apply, validation, rollback metadata, merge readiness, and release candidate."
  expected_outputs:
    - "e2e-summary.md"
    - "integration-state.json"
    - "validation-after-each-patch.json"
    - "merge-readiness.json"
    - "release-candidate.md"
    - "AI calls used: 0"
  validation_commands:
    - "python3 scripts/factory_integration_e2e.py --fixture career-consulting --out workspace/runs/factory/factory-integration-e2e"
    - "grep -q \"AI calls used: 0\" workspace/runs/factory/factory-integration-e2e/e2e-summary.md"
  no_model_eligible: true
  risk: "low"
  dependencies:
    - "Factory integration CLI facade"
```

```yaml
- title: "Factory Console integration panel"
  package: "factory-integration-v1"
  lane: "builder"
  node: "macos"
  owned_scope:
    - "Cento Console Factory route files only"
    - "Console fixture data for factory-integration-e2e"
  goal: "Show integration branch, applied patches, rejected patches, validation after each patch, rollback, merge readiness, and release candidate links."
  expected_outputs:
    - "Integration tab"
    - "Applied/rejected patch table"
    - "Merge readiness card"
    - "Rollback panel"
    - "Release candidate link"
  validation_commands:
    - "python3 scripts/factory_integration_e2e.py --fixture career-consulting --out workspace/runs/factory/factory-integration-e2e"
    - "cento agent-work-app --help"
  no_model_eligible: true
  risk: "medium"
  dependencies:
    - "Factory integration zero-AI E2E"
```

```yaml
- title: "Factory integration docs and rollout"
  package: "factory-integration-v1"
  lane: "docs-evidence"
  node: "macos"
  owned_scope:
    - "docs/factory-integration.md"
    - "docs/factory.md"
    - "docs/tool-index.md"
    - "docs/platform-support.md"
    - "README.md"
  goal: "Document the safe integration flow, branch policy, patch gates, rollback, Taskstream sync preview, and release candidate workflow."
  expected_outputs:
    - "docs/factory-integration.md"
    - "updated Factory docs"
    - "tool index updates"
    - "operator quickstart"
  validation_commands:
    - "grep -R \"factory integration\" docs README.md"
    - "grep -R \"release-candidate\" docs/factory-integration.md"
    - "grep -R \"rollback-plan\" docs/factory-integration.md"
  no_model_eligible: true
  risk: "low"
  dependencies:
    - "Factory integration CLI facade"
```

## Acceptance Commands

```bash
python3 scripts/factory_integration_e2e.py \
  --fixture career-consulting \
  --out workspace/runs/factory/factory-integration-e2e
```

```bash
cento factory integrate factory-integration-e2e --plan
```

```bash
cento factory integrate factory-integration-e2e \
  --prepare-branch \
  --branch factory/factory-integration-e2e/integration
```

```bash
cento factory integrate factory-integration-e2e \
  --apply \
  --validate-each \
  --limit 3
```

```bash
cento factory validate-integrated factory-integration-e2e
```

```bash
cento factory release-candidate factory-integration-e2e
```

```bash
cento factory sync-taskstream factory-integration-e2e --dry-run
```

```bash
test -f workspace/runs/factory/factory-integration-e2e/integration/integration-state.json
test -f workspace/runs/factory/factory-integration-e2e/integration/validation-after-each-patch.json
test -f workspace/runs/factory/factory-integration-e2e/integration/rollback-plan.json
test -f workspace/runs/factory/factory-integration-e2e/integration/merge-readiness.json
test -f workspace/runs/factory/factory-integration-e2e/integration/release-candidate.md
```

```bash
grep -q "AI calls used: 0" \
  workspace/runs/factory/factory-integration-e2e/e2e-summary.md
```

```bash
python3 scripts/no_model_validation_e2e.py
```

## Definition Of Done

`factory-integration-v1` is done when:

- Patch bundles can be read from a Factory run.
- Integration worktree/branch can be prepared without touching main.
- Patches are ordered by dependency and risk.
- Patches are applied one at a time.
- Validation runs after each patch.
- Failed patches are quarantined, not ignored.
- Rollback metadata is generated.
- Docs/tool registry gates are enforced.
- Merge readiness is machine-readable.
- Taskstream sync is previewed but not automatically finalized.
- Release candidate packet is rendered.
- Console shows integration status.
- Full E2E uses zero AI calls.

## What Comes After

Once this is done, the sequence should be:

```text
1. factory-runtime-v1
   Real Codex/Claude/local worker adapters with budgets and stop rules.

2. factory-buildfarm-v1
   Linux/macOS/VM validation matrix.

3. factory-research-map-v1
   Deep Research/spec sections mapped to implemented/partial/missing evidence.

4. career-consulting-module-v1
   First real generated module using the full Factory loop.

5. factory-cost-v1
   Cost-per-patch, cost-per-release-candidate, cached prompt savings, worker quality scoring.
```

The next move is Safe Integrator:

```text
We did not scale agents by trusting them more.
We scaled them by removing their authority to merge,
then built deterministic integration gates around their output.
```
