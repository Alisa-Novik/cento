# Cento Tool Foundry

`cento foundry` creates Cento-native business tools through the existing delivery pipeline.

Foundry is a facade over Factory, Workset, parallel train promotion, storage policy, cost receipts, and demo evidence. It does not replace those systems. The first v1 fixture is the career consulting **Client Intake Hub**.

## Commands

```bash
cento foundry create "client intake hub" --domain career-consulting --max-parallel 6 --budget-usd 10 --max-budget-usd 20 --json
cento foundry plan RUN_ID --json
cento foundry execute RUN_ID --runtime fixture --json
cento foundry execute RUN_ID --runtime api-openai --budget-usd 10 --max-budget-usd 20 --json
cento foundry promote RUN_ID --dry-run --json
cento foundry materialize RUN_ID --target-root templates/foundry/client-intake-hub --dry-run --json
cento foundry materialize RUN_ID --target-root templates/foundry/client-intake-hub --apply --json
cento foundry status RUN_ID --json
cento foundry validate RUN_ID --json
cento foundry e2e --fixture client-intake-hub --dry-run --json
cento foundry e2e --fixture client-intake-hub --dry-run --real-files --target-root templates/foundry/client-intake-hub --json
cento foundry e2e --fixture client-intake-hub --live --budget-usd 10 --max-budget-usd 20 --json
```

Use the dry-run fixture path for repeatable validation. Add `--real-files` when you want Foundry to produce a create-file materialization plan after the fixture train passes. Live `api-openai` execution requires both budget flags and v1 rejects hard caps above `$20`.

## Artifacts

Foundry runs write under:

```text
workspace/runs/foundry/<run-id>/
```

The stable artifact set is:

- `foundry-spec.json`
- `factory_handoff.json`
- `workset.json`
- `workset_check.json`
- `plan_receipt.json`
- `train_e2e_result.json`
- `execution_receipt.json`
- `cost_receipt.json`
- `storage-policy.json`
- `demo-evidence.json`
- `real_file_manifest.json`
- `materialization_plan.json`
- `materialization_receipt.json`
- `validation_summary.json`
- `summary.md`
- `tool/client-intake-hub/*`

Train promotion writes under:

```text
workspace/runs/parallel-delivery/train/foundry-<run-id>-train/
workspace/runs/factory/parallel-train-foundry-<run-id>-train/
```

## Behavior

- `create` writes the Foundry spec, Client Intake Hub fixture bundle, private-by-default storage policy, demo evidence manifest, and initial cost receipt.
- `plan` runs deterministic Factory planning/materialization/queue evidence and writes a Workset manifest with six exclusive work slices.
- `execute` routes the Workset through `cento parallel-delivery train e2e`.
- `promote` can re-run the train-to-Factory promotion for the generated train run.
- `validate` requires the Foundry spec, Factory handoff, Workset check, execution receipt, train validation, promotion readiness, cost receipt, storage policy, and demo evidence.
- Fixture execution writes zero AI cost and is the required safe validation path.
- Live execution is explicit and capped.

## Client Intake Hub Fixture

The v1 fixture proves the pipeline for a career consulting tool without using real client data.

The generated run bundle includes:

- client profile schema
- command/API map routed through existing `cento crm` and `cento foundry`
- no-build HTML preview
- operator notes
- storage/leak policy
- validation plan

Workset execution uses existing tracked fixture targets so isolated worker worktrees can produce patch bundles without mutating the main checkout. The generated product bundle and evidence remain run-scoped under `workspace/runs/foundry/<run-id>/`.

## Real-File Materialization

Real-file mode turns the run-scoped Client Intake Hub bundle into repo-ready files without asking isolated workers to edit paths they cannot see.

The default target is:

```text
templates/foundry/client-intake-hub/
```

The materialized MVP writes:

- `templates/foundry/client-intake-hub/client-intake-hub.html`
- `templates/foundry/client-intake-hub/client-profile.schema.json`
- `templates/foundry/client-intake-hub/command-api.json`
- `templates/foundry/client-intake-hub/storage-leak-policy.json`
- `templates/foundry/client-intake-hub/validation-plan.json`
- `templates/foundry/client-intake-hub/README.md`
- `docs/client-intake-hub.md`

`materialize` defaults to planning unless `--apply` is passed. Apply writes only under `templates/foundry/...` plus the approved `docs/client-intake-hub.md` page. Existing files with identical content are skipped; changed existing files block instead of being overwritten.

`cento crm serve` discovers the materialized Client Intake Hub and exposes a preview through the CRM Studio view.

## Safety

- Real resumes, LinkedIn exports, client notes, private job-search notes, secrets, and raw PII are blocked from cloud upload by default.
- OCI storage, when later used, must be private Standard tier with no public access.
- Foundry records cost receipts even when no AI calls occur.
- Foundry does not merge to main; promotion stops at Factory/Safe Integrator dry-run unless `--apply` is explicitly passed.
- Real-file materialization is local-only and does not upload to OCI.
