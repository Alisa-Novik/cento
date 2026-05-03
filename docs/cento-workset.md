# Cento Workset

`cento workset` is the first local parallelization layer above `cento build`.
It runs multiple exclusive-path build tasks, collects one patch bundle per task,
then integrates and applies accepted patches through one sequential lane.
`cento workset execute` adds structured API artifact workers while keeping repo
mutation inside the local materializer and build integration layer.

It does not run cloud workers, use OpenAI Batch API, create PRs, split
screenshots into epics, or attempt smart merging.

## Contract

Parallelization v1 constraints:

- each task owns exclusive `write_paths`
- no shared files
- no overlapping paths
- no glob write paths
- dependency gates are simple `depends_on` arrays
- a task dispatches only after dependencies are completed and applied
- integration and apply are always sequential
- conflicts block only the affected branch; independent tasks continue
- API workers write structured artifacts only; local materialization writes files
- `.cento/api_workers.yaml` defines the configured hard budget maximum; CLI
  `--max-budget-usd` cannot raise it
- budget caps reserve at least `minimum_cost_usd_estimate_per_request` for each
  API worker before dispatch
- API workers enforce `max_input_chars` before the OpenAI request and
  `max_output_tokens` on the Responses API request
- budget caps stop new API dispatch before the hard max is exceeded, and a
  real usage estimate above the hard max blocks integration for that task

Shared-file edits must be represented as a separate serialized integrator task.

## API Worker Config

`.cento/api_workers.yaml` controls API-worker safety defaults:

```yaml
openai:
  budget_usd_default: 3
  budget_usd_max: 5
  max_parallel_requests: 6
  timeout_seconds: 45
  retry_attempts: 1
  cost_usd_estimate_per_request: 0.10
  minimum_cost_usd_estimate_per_request: 0.10
  max_input_chars: 20000
  max_output_tokens: 2000
```

Profiles may lower or specialize per-request limits, but the configured
`budget_usd_max` remains the hard ceiling for `cento workset execute`.

## Workset Manifest

```json
{
  "schema_version": "cento.workset.v1",
  "id": "workset_kanji_docs",
  "mode": "fast",
  "max_parallel": 3,
  "tasks": [
    {
      "id": "hero",
      "task": "Update hero section",
      "write_paths": ["apps/docs/kanji/Hero.tsx"],
      "depends_on": []
    },
    {
      "id": "status",
      "task": "Update status cards",
      "write_paths": ["apps/docs/kanji/StatusCards.tsx"],
      "depends_on": []
    },
    {
      "id": "layout",
      "task": "Wire page layout after sections are ready",
      "write_paths": ["apps/docs/kanji/Page.tsx"],
      "depends_on": ["hero", "status"]
    }
  ]
}
```

## Commands

Validate exclusive paths and dependencies:

```bash
cento workset check tests/fixtures/cento_workset/workset.valid.json
cento workset check tests/fixtures/cento_workset/workset.overlap.json
```

Run two local fixture workers, then integrate and apply sequentially:

```bash
cento workset run tests/fixtures/cento_workset/workset.valid.json \
  --max-workers 2 \
  --runtime-profile fixture-valid \
  --apply sequential \
  --validation smoke
```

Run the same shape with a real local command profile:

```bash
cento workset run workset.json \
  --max-workers 3 \
  --runtime-profile codex-fast \
  --apply sequential \
  --validation smoke
```

Execute with the v1 command shape:

```bash
cento workset execute .cento/worksets/docs_page.json \
  --max-parallel 6 \
  --runtime api-openai \
  --budget-usd 3 \
  --max-budget-usd 5 \
  --integrate sequential \
  --apply \
  --validation smoke
```

Fixture and local command execution use the same dispatcher:

```bash
cento workset execute tests/fixtures/cento_workset/workset.execute.fixture.json \
  --max-parallel 3 \
  --runtime fixture \
  --integrate sequential \
  --validation smoke

cento workset execute workset.json \
  --max-parallel 3 \
  --runtime local-command \
  --runtime-profile codex-fast \
  --integrate sequential \
  --validation smoke
```

Materialize one API artifact into a local patch bundle:

```bash
cento workset materialize-artifact .cento/worksets/<run_id>/workers/<worker_id>/artifact.json
```

## Outputs

Each run writes:

```text
.cento/worksets/<run_id>/workset.json
.cento/worksets/<run_id>/leases.json
.cento/worksets/<run_id>/workset_receipt.json
.cento/worksets/<run_id>/workset_evidence.json
.cento/worksets/<run_id>/events.ndjson
.cento/worksets/<run_id>/workers/<worker_id>/request.json
.cento/worksets/<run_id>/workers/<worker_id>/response.json
.cento/worksets/<run_id>/workers/<worker_id>/artifact.json
.cento/worksets/<run_id>/workers/<worker_id>/cost_receipt.json
.cento/worksets/<run_id>/workers/<worker_id>/worker_receipt.json
```

Each task still writes a normal build package under:

```text
.cento/builds/workset_<run_id>_<task_id>/
```

Those build packages contain the normal manifest, builder prompt,
worker artifact, patch bundle, integration receipt, apply receipt, validation
receipt, taskstream evidence, and events.
