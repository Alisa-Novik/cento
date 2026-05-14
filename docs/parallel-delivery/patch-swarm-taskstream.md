# Patch Swarm Taskstream Handoff

Patch Swarm can emit Cento `agent-work` handoff manifests from a validated split plan without creating live Taskstream stories. This is the bridge between high-fanout Patch Swarm planning and the existing Taskstream operating model.

The adapter is dry-run by default. It writes local work-package directories containing:

- `story.json`
- `validation.json`
- `handoff.md`
- `agent-work-command.txt`

Live creation is gated behind `cento parallel-delivery taskstream apply --apply` and uses the existing `cento agent-work create --manifest ...` command path. It does not write Taskstream, Redmine, story, board, or cluster state directly.

## Commands

Generate handoff manifests:

```bash
cento parallel-delivery taskstream emit \
  --split-plan workspace/runs/parallel-delivery/taskstream-fixture/input/split-plan.json \
  --out workspace/runs/parallel-delivery/taskstream-fixture \
  --transport manifest-only \
  --run-preflight
```

Run preflight over generated packages:

```bash
cento parallel-delivery taskstream preflight \
  --manifest-dir workspace/runs/parallel-delivery/taskstream-fixture/work-packages \
  --out workspace/runs/parallel-delivery/taskstream-fixture/preflight
```

Refuse live creation unless explicitly applied:

```bash
cento parallel-delivery taskstream apply \
  --manifest-dir workspace/runs/parallel-delivery/taskstream-fixture/work-packages \
  --out workspace/runs/parallel-delivery/taskstream-fixture/live-refusal \
  --transport agent-work
```

The final command must fail because `--apply` is absent. A live create run must be explicit:

```bash
cento parallel-delivery taskstream apply \
  --manifest-dir workspace/runs/parallel-delivery/taskstream-fixture/work-packages \
  --out workspace/runs/parallel-delivery/taskstream-fixture/apply \
  --transport agent-work \
  --apply
```

## Artifact Contract

`taskstream emit` accepts existing Patch Swarm `split-plan.json` artifacts and the fallback fixture schema `cento.parallel_delivery.split_plan.v1`.

Each generated `story.json` uses the existing agent-work story format:

- `schema_version: "1.0"`
- `issue.id: 0` for create-time draft manifests
- `issue.title` and `issue.package`
- `lane.owner`, `lane.role`, `lane.node`, and `lane.agent`
- `paths.run_dir`
- `scope.acceptance`
- `expected_outputs`
- `validation.manifest`, `validation.mode`, `validation.commands`

The adapter also adds Patch Swarm metadata such as `source`, `run_id`, `request_id`, `task_id`, `owned_paths`, `touched_path_candidates`, `acceptance_contract`, and `evidence_links`.

Each generated `validation.json` uses the existing `cento.validation-manifest.v1` checks format so `cento agent-work preflight story.json --validation-manifest validation.json` can validate it. Patch Swarm metadata is included as supplemental fields.

## Routing

Routing is deterministic:

- Tasks with implementation scope, acceptance criteria, and validation commands route to `agent-work`.
- Evidence-only, planning-only, blocked, or explicitly `manifest-only` tasks remain local manifests.

`agent-work-command.txt` is only a command preview in dry-run mode. The command uses the approved `cento agent-work create --manifest ...` surface.

## Guards

The adapter rejects unsafe manifest inputs:

- absolute paths
- traversal paths
- Windows drive paths
- NUL bytes
- `.env`, `.env.*`, `.env.mcp`
- local secret-looking paths
- secret-looking inline values

Generated evidence stays under `workspace/runs/parallel-delivery/taskstream-fixture/` for the fixture path. Tests never create live Taskstream issues.

## Fixture

Run:

```bash
make test-taskstream-handoff
make taskstream-fixture
```

The fixture writes:

- `workspace/runs/parallel-delivery/taskstream-fixture/input/split-plan.json`
- `workspace/runs/parallel-delivery/taskstream-fixture/work-packages/*/story.json`
- `workspace/runs/parallel-delivery/taskstream-fixture/work-packages/*/validation.json`
- `workspace/runs/parallel-delivery/taskstream-fixture/work-packages/*/handoff.md`
- `workspace/runs/parallel-delivery/taskstream-fixture/taskstream-handoff-report.json`
- `workspace/runs/parallel-delivery/taskstream-fixture/taskstream-handoff-report.md`
- `workspace/runs/parallel-delivery/taskstream-fixture/validation-summary.txt`
