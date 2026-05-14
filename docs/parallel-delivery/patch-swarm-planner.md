# Patch Swarm Request Splitter and 100-Task Planner

## Overview

The Patch Swarm planner turns one high-level request into durable planning artifacts: `split-plan.json`, `task-graph.json`, and per-task contract drafts under `task-contracts/`. It is a planning and validation surface only. It does not dispatch workers, apply patches, call live Pro by default, or mutate Taskstream/Redmine/story state.

## Planner Modes

- `fixture` writes deterministic tasks for tests and demos.
- `no-model` uses request text and safe Cento surface hints to produce a conservative local plan.
- `proreq` writes ChatGPT Pro planning manifest and prompt artifacts without a live Pro call unless explicitly enabled in a future safe backend.
- `manual-import` validates and normalizes a Pro-generated split plan into Cento artifacts.

## Candidate Target vs Candidate Count

`--candidate-target` is the requested upper bound. In fixture mode it can produce exactly 5, 20, or 100 tasks for validation. In no-model mode it is a cap, not a promise.

## Why 100 Tasks Is a Cap, Not a Goal

Patch Swarm maximizes safe parallelism, not raw task count. Small requests should stay small. Broad requests can approach 100 only when task boundaries, path ownership, dependencies, and validation evidence remain clear.

## Coarse Product Lanes

The planner decomposes into coarse product lanes before smaller tasks: coordination, builder work, validation, docs/evidence, integration sequencing, and human handoff.

## Task Lanes

- `builder`: bounded source changes.
- `validator`: tests, fixtures, validation harnesses, and checks.
- `docs-evidence`: docs, runbooks, evidence summaries, and operator packets.
- `coordinator`: metadata, manifests, CLI routing, or cross-surface coordination.
- `integrator`: integration sequencing plans, not arbitrary patch application.
- `human-handoff`: subjective, device-bound, credential-bound, or unsafe-to-automate work.

## Risk Tiers

- `low`: docs, fixtures, read-only validation, isolated helpers.
- `medium`: bounded code changes with clear tests and ownership.
- `high`: CLI/registry/integration logic or cross-cutting behavior.
- `human`: subjective, credential-bound, production-operation, or device-only decisions.

## Worker Profile Suggestions

Profiles are suggestions only: `python-builder`, `cli-builder`, `schema-validator`, `test-writer`, `docs-evidence-writer`, `safe-integrator`, `factory-planner`, `workset-lease-planner`, and `human-operator`.

## Path Ownership Rules

Owned paths must be relative, slash-separated, deduplicated, and non-overlapping. Absolute paths, `..`, `.env.mcp`, and secret-like paths are rejected. When safe ownership cannot be inferred, the planner should keep owned paths empty and raise risk or human handoff instead of guessing.

## Human Handoff Rules

Requests involving visual polish, device-only checks, production credentials, real customers, manual approval, secrets, tokens, or `.env` values must create or mark a human-handoff task.

## Split Plan Schema

`split-plan.json` includes common schema metadata, request metadata, `candidate_target`, `candidate_count`, `max_parallel_agents`, `planner_mode`, planning policy, lane names, and task records. Every task includes ID, title, story, lane, risk tier, human handoff flag, worker profile, owned/read-only paths, dependencies, acceptance contract, validation commands, expected artifacts, integration notes, rejection triggers, and evidence pointers.

## Task Graph Schema

`task-graph.json` records every task as a node, `depends_on` / `blocks` / `shares_context` / `conflicts_with` edges, a topological order, and parallel groups bounded by `max_parallel_agents`. `depends_on` edges must be acyclic.

## ProReq Planning Flow

ProReq mode writes:

```text
proreq/planning-manifest.json
proreq/chatgpt-pro-planner-prompt.md
proreq/manual-import-instructions.md
```

The prompt instructs ChatGPT Pro to produce a plan matching the schema, avoid overlapping paths, use coarse lanes first, mark human handoff tasks, and cap candidates at 100.

## Manual Import Flow

Manual import accepts a JSON split plan with `--import-plan`. It rejects invalid JSON, more than 100 candidates, duplicate IDs, unknown lanes, unknown dependencies, overlapping paths, unsafe paths, and missing acceptance or validation contracts for automated tasks.

## CLI Examples

```bash
cento parallel-delivery patch-swarm split \
  --request-file REQUEST.md \
  --candidate-target 20 \
  --max-parallel-agents 5 \
  --mode no-model \
  --run-dir workspace/runs/parallel-delivery/planner-run \
  --json
```

```bash
cento parallel-delivery patch-swarm split \
  --candidate-target 100 \
  --max-parallel-agents 5 \
  --fixture \
  --run-id planner-fixture \
  --run-dir workspace/runs/parallel-delivery/planner-fixture \
  --json
```

```bash
cento parallel-delivery patch-swarm split \
  --mode manual-import \
  --import-plan pro-plan.json \
  --run-dir workspace/runs/parallel-delivery/imported-plan \
  --json
```

## Validation Commands

```bash
python3 -m json.tool data/tools.json >/dev/null
python3 -m json.tool data/cento-cli.json >/dev/null
cento parallel-delivery patch-swarm split --help
pytest -q tests/test_parallel_delivery_planner.py
```

## Fixture Run

The deterministic fixture run lives at `workspace/runs/parallel-delivery/planner-fixture/` and includes `request.md`, `split-plan.json`, `task-graph.json`, `task-contracts/`, `proreq/`, `planner-report.md`, and `start-here.md`.

## Unsafe Planning Rules

- Do not include secrets.
- Do not copy `.env.mcp`.
- Do not store OpenAI keys or local secret values.
- Do not store absolute secret paths.
- Do not directly mutate Taskstream/Redmine/story state.
- Do not claim validation passed without validation evidence.
- Do not write generated run artifacts outside `workspace/runs/` unless the operator explicitly supplies a run directory for validation.
