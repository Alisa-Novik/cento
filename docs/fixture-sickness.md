# Fixture Sickness

## Definition

Fixture Sickness is the Cento failure mode where an agent repeatedly creates new fixtures, schemas, manifests, contracts, dashboards, or evidence bundles instead of using existing Cento surfaces and previously produced evidence to execute real work.

It looks productive because it produces files.

It is dangerous because it avoids integration.

In Patch Swarm terms, Fixture Sickness is what happens when the system proves it can coordinate delivery, then the next plan restarts from zero with another runtime contract, another schema family, another fixture E2E, and another evidence stack instead of consuming the closeout evidence and running one real task through the existing surfaces.

## Symptoms

- Planning another runtime contract after a runtime contract already exists.
- Creating another schema instead of consuming `factory`, `build`, `workset`, or `parallel-delivery` artifacts.
- Creating another fixture E2E instead of running a real non-fixture pilot.
- Treating evidence production as delivery.
- Repeating recon and gap maps every phase without using the prior map.
- Adding new `workspace/runs/...` families that nobody consumes.
- Rebuilding task graphs, leases, queues, inboxes, and release candidates while Factory, Build, Workset, Parallel Delivery, and Agent Work already have them.
- Proposing new tools before checking `cento tools`, `cento docs`, `data/tools.json`, and prior evidence.
- Confusing "we can generate a demo" with "the system can do work."
- Designing the next phase from scratch instead of asking how to use the closeout artifacts.

## Why It Happens

- Agents optimize for producing visible artifacts.
- Fixtures are safer than real execution.
- Contracts feel like progress.
- New schemas avoid the harder work of adapter and integration.
- Long multi-call plans drift toward scaffolding.
- Evidence becomes an end in itself.
- Lack of a reuse gate allows every phase to restart at zero.

## Why It Is Harmful

- It destroys trust.
- It burns Pro and Codex calls.
- It duplicates workflows.
- It increases maintenance burden.
- It hides the fact that real execution is not improving.
- It makes Cento look like a museum of receipts instead of a delivery system.
- It violates Cento's routing rule: prefer existing surfaces first.
- It prevents the system from using its own outputs.

## Existing Surfaces That Must Be Reused First

- `cento parallel-delivery`: Patch Swarm coordinator for plan, execute, demo, validate, status, and patch-swarm E2E.
- `cento factory`: intake, no-model planning, queues, prompt bundles, patch collection, validation, integration dry-runs, release candidates, and evidence hubs.
- `cento build`: owned-path build packages, builder prompts, patch bundles, dry-run integration, safe apply, and receipts.
- `cento workset`: exclusive-path local N-worker execution and sequential integration.
- `cento agent-work`: Taskstream story and validation manifests plus task lifecycle.
- `cento agent-pool-kick`: bounded worker launch, with dry-run behavior before live launch.
- `cento agent-processes`: process and worker visibility.
- `cento temp`: short-lived operator command and clipboard bridge.
- `cento demo-evidence`: low-memory demo video receipts.

These are not references to admire. They are surfaces to consume before creating anything new.

## The Reuse Gate

Before proposing a new fixture, schema, manifest, contract, tool, command, evidence family, or 10+ call plan, an agent must answer:

1. What existing command already does this?
2. What existing artifact already represents this state?
3. What existing evidence proves it already worked?
4. What existing tool should consume this next?
5. Can this be done by connecting Factory, Build, Workset, Parallel Delivery, or Agent Work?
6. Is this new thing actually needed, or are we avoiding a real run?
7. What is the smallest adapter that would let us use the existing result?
8. What prior run directory should this continue from?
9. What exact command will consume the previous output?
10. What user-visible outcome happens after reuse?

If the answers are missing, the proposal is rejected as Fixture Sickness.

## Patch Swarm Reuse Gate

- [ ] Did I inspect `cento tools`?
- [ ] Did I inspect `cento docs parallel-delivery`?
- [ ] Did I inspect `cento docs factory`?
- [ ] Did I inspect `cento docs build`?
- [ ] Did I inspect `cento docs workset`?
- [ ] Did I inspect prior evidence under `workspace/runs/parallel-delivery`?
- [ ] Did I identify the previous run directory I am continuing from?
- [ ] Did I identify the exact existing artifact I am consuming?
- [ ] Did I identify the exact existing command that consumes it?
- [ ] Did I try an existing command before proposing a new one?
- [ ] Did I prefer adapter over schema?
- [ ] Did I prefer real pilot over fixture?
- [ ] Did I avoid creating a new durable workflow?
- [ ] Did I avoid creating a new fixture unless it protects a real command?
- [ ] Did I avoid changing registry, docs, or Makefile unless a durable user-facing surface changed?
- [ ] Did I preserve dirty work?
- [ ] Did I keep secrets local?
- [ ] Did I define the user-visible next action?

If any required item is unchecked, stop and explain why.

## Forbidden Planning Patterns

Bad:

> Create a new runtime schema for worker queues.

Better:

> Inspect existing Factory queue and Patch Swarm worker-packet artifacts; add an adapter only if no existing field supports the next command.

Bad:

> Create a new E2E fixture proving 100 agents.

Better:

> Use the existing 100-candidate fixture only as a regression gate, then run one real non-fixture pilot with live workers disabled or dry-run.

Bad:

> Create a new release-candidate packet.

Better:

> Use existing Factory or Patch Swarm release-candidate artifacts; add a missing evidence pointer if needed.

Bad:

> Create a new task manifest format.

Better:

> Use the existing Agent Work story/validation manifest format or Factory task artifacts.

Bad:

> Create another 30-call foundation.

Better:

> Start from the 20-call closeout evidence and ask what command consumes it next.

## Correct Next-Phase Principle

The next phase after the 20-call Patch Swarm closeout should be:

USE THE SYSTEM ON ITSELF.

Not:

- another fixture suite
- another schema family
- another runtime plan
- another one-pager

But:

- select one real low-risk Cento task
- use existing `parallel-delivery`, `factory`, `build`, `workset`, or `agent-work` surfaces
- generate or reuse work packages
- run one or two real Codex workers manually if needed
- collect actual patches
- validate through existing safety gates
- dry-run integration
- produce release evidence
- write a postmortem of missing reuse gaps

## The Use Before Build Rule

Before creating anything new:

1. Try to run an existing command.
2. Try to consume an existing artifact.
3. Try to adapt an existing format.
4. Try to add a thin bridge.
5. Only then create a new durable artifact or tool.

## What Future ChatGPT Pro Calls Must Do

Future Pro calls must not default to "create a new implementation packet."

They must start with:

- Which previous run are we continuing?
- Which existing artifact is the input?
- Which existing command consumes it?
- What is the smallest next action?
- What will be real, not fixture?

## Examples For Patch Swarm

Instead of:

> Call 1: runtime contract.

Do:

> Call 1: consume the 20-call closeout and identify the first real task to run through existing `parallel-delivery` or `factory`.

Instead of:

> Call 2: runtime schema.

Do:

> Call 2: map existing Factory, Build, and Workset artifacts to the Patch Swarm closeout artifacts and identify only missing adapters.

Instead of:

> Call 3: fixture E2E.

Do:

> Call 3: run the existing fixture E2E once as a regression gate, then run a real non-fixture dry-run plan.

## Required AI Behavior

Future agents must:

- read this document before planning Patch Swarm, Factory, Build, or Workset expansions
- cite or mention the Reuse Gate in their plan
- reject duplicate fixture proposals
- prefer adapters over new formats
- prefer real pilot runs over new proof fixtures
- treat evidence as an input to the next command, not as a terminal artifact
- preserve dirty work
- keep secrets local
- avoid direct Taskstream database mutation

## Closeout

Cento is not allowed to become a museum of beautiful receipts. Evidence must drive the next action.
