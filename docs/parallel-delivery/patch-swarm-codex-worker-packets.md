# Patch Swarm Codex Worker Packets

## Overview

Patch Swarm Codex worker packets are local Markdown instructions for copy/paste Codex execution. They are generated from `split-plan.json`, `task-graph.json`, and `path-leases.json`; they do not call Codex, OpenAI APIs, ChatGPT Pro, MCP, Taskstream, Redmine, worker pools, or patch application paths.

## Operator Copy/Paste Flow

Generate the packet bundle, open `codex-packet-index.md`, and copy exactly one packet into one Codex thread. Each worker leaves a patch bundle, diff, handoff note, and evidence under the run directory. Integration remains a later Safe Integrator step.

## Inputs

- `request.md`
- `split-plan.json`
- `task-graph.json`
- `path-leases.json`

`path-leases.json` is the source of truth for owned write paths, read-only paths, guarded paths, protected paths, dirty owned paths, manual review flags, dependency gates, and parallel groups.

## Outputs

- `codex-packet-bundle.json`
- `codex-packet-index.json`
- `codex-packet-index.md`
- `packets/` for fixture runs or `codex-packets/` for real runs
- `patch-bundles/README.md`
- `handoffs/README.md`
- `packet-validation.json`
- `packet-validation-report.md`
- `start-here.md`

## Packet Bundle Layout

Fixture evidence is written under `workspace/runs/parallel-delivery/codex-packets-fixture/`. Real run packets stay in the selected run directory and use the same index and validation artifacts.

## Worker Packet Required Sections

Every packet includes:

- `## Thread Title`
- `## Task ID`
- `## Mission`
- `## Discovery Commands`
- `## Owned Write Paths`
- `## Read-Only Paths`
- `## Prohibited Paths`
- `## Implementation Steps`
- `## Expected Files Changed`
- `## Tests And Validation`
- `## Evidence Path`
- `## Patch Bundle Output Instructions`
- `## Handoff Note Format`
- `## Failure / Blocker Protocol`
- `## Safety Rules`
- `## Acceptance Criteria`

## Lane-Specific Guidance

Builder packets emphasize small bounded implementation and patch bundles. Validator packets emphasize tests, fixtures, negative cases, and evidence. Docs-evidence packets emphasize operator-facing docs and run evidence. Coordinator packets emphasize manifest, schema, CLI, registry, and docs consistency without broad rewrites. Integrator packets emphasize planning or validation only unless a lease explicitly permits a safe apply action. Human-handoff packets are non-mutating.

## Path Lease Enforcement

Packets instruct workers to edit only Owned Write Paths and inspect Read-Only Paths without modification. If a required change appears outside the lease, the worker must stop and write `workers/<task_id>/handoff.md`.

## Prohibited Paths

Every packet includes secret and lease guards including `.env`, `.env.*`, `.env.mcp`, `.git/**`, key/certificate patterns, read-only paths, other tasks' owned paths, and paths outside the task lease.

## Patch Bundle Output

Every worker writes:

```text
workers/<task_id>/handoff.md
workers/<task_id>/evidence/
patch-bundles/<task_id>.patch-bundle.json
patch-bundles/<task_id>.diff
```

The patch bundle records run ID, task ID, base ref, worker ID, claimed paths, changed paths, diff path, summary, tests run, evidence files, handoff note, risks, and manual review status.

## Handoff Note Format

Handoff notes use:

```markdown
# Codex Worker Handoff

## Task ID
## Status
## Summary
## Files Changed
## Validation Run
## Evidence Files
## Blockers
## Risks
## Suggested Next Action
```

## Failure and Blocker Protocol

Workers stop and write a handoff when required edits are outside owned paths, dirty work would be overwritten, validation needs missing secrets or external services, direct Taskstream/Redmine database writes are required, acceptance criteria conflict, dependencies are missing, or protected paths need changes.

## CLI Examples

```bash
cento parallel-delivery patch-swarm worker-packets \
  --run-dir workspace/runs/parallel-delivery/codex-packets-fixture \
  --run-id codex-packets-fixture \
  --fixture \
  --count 10 \
  --json
```

Script fallback:

```bash
python3 scripts/parallel_delivery_codex_packets.py write-fixture --run-dir workspace/runs/parallel-delivery/codex-packets-fixture --run-id codex-packets-fixture --count 10 --json
python3 scripts/parallel_delivery_codex_packets.py generate --run-dir workspace/runs/parallel-delivery/codex-packets-fixture --count 10 --json
python3 scripts/parallel_delivery_codex_packets.py validate-bundle --run-dir workspace/runs/parallel-delivery/codex-packets-fixture --json
python3 scripts/parallel_delivery_codex_packets.py print-policy --json
```

## Fixture Run

The deterministic fixture creates 10 tasks: two builder, two validator, two docs-evidence, two coordinator, and two integrator packets with non-overlapping owned paths and shared read-only context.

## Validation Commands

```bash
python3 scripts/parallel_delivery_codex_packets.py validate-bundle --run-dir workspace/runs/parallel-delivery/codex-packets-fixture --json
pytest -q tests/test_parallel_delivery_codex_worker_packets.py
```

## Unsafe Packet Rules

Packets are unsafe if they omit path leases, encourage edits outside owned paths, contain secret-like values, require live services, require direct Taskstream/Redmine database writes, claim validation without evidence, or apply patches in this generation slice.
