# Patch Swarm Patch Bundle Collection and Safety Validation

## Overview

Patch bundle collection is the local-first handoff between worker outputs and later integration. Workers submit either a `cento.patch_bundle.v1` manifest with a local diff reference or an evidence-only result. Cento validates those outputs against the authoritative lease manifest, writes one receipt per bundle, and writes an aggregate report. This slice does not apply, stage, commit, reset, clean, or integrate patches.

The implementation lives in `scripts/parallel_delivery_patch_bundles.py` and is exposed through:

```bash
cento parallel-delivery patch-bundles validate --bundle PATH --lease-manifest PATH --out DIR --base-commit COMMIT --json
cento parallel-delivery patch-bundles collect --bundles-dir DIR --lease-manifest PATH --out DIR --run-id RUN_ID --base-commit COMMIT --json
```

## Bundle Schema

Patch bundles use `schema: cento.patch_bundle.v1` and include `bundle_id`, `task_id`, `worker_id`, `run_id`, `base_commit`, `touched_paths`, `diff_path` or a local `patch_content_ref`, `changed_file_summary`, `validation_commands`, `evidence_files`, `result_status`, and `risk_flags`.

Evidence-only bundles set `result_status: evidence_only`, leave `touched_paths` empty, and provide safe local evidence file references. They are receipted without requiring a diff.

## Authoritative Leases

Worker-provided ownership data is not trusted. The validator reads the task lease from a local lease manifest. The v1 fixture schema is `cento.patch_bundle_leases.v1` with one `tasks` entry per task. Each task declares `allowed_paths`, `protected_paths`, allowed deletes/renames/lockfiles, binary/symlink/submodule policy, and lockfile line limits.

## Safety Checks

The validator reuses `cento build` path matching and lockfile helpers where those policies already exist. It validates manifest paths and parsed diff paths and rejects absolute paths, traversal, NUL bytes, Windows drive paths, remote patch refs, edits outside the lease, protected path edits, `.env.mcp` and local secret-looking paths, prohibited symlink/submodule/binary patches, undeclared deletes, unowned renames, broad lockfile changes, secret-looking added patch content, missing or unsafe evidence refs, and base commit mismatches.

Secret scanning only inspects added patch lines and receipts store redacted detector details, not matched values.

## Receipts and Reports

Each bundle writes a deterministic JSON receipt under `receipts/`. Accepted receipts set `validation_status: accepted`; rejected receipts include stable `reason_codes` and redacted `issues`.

The collector writes:

- `patch-bundle-report.json`
- `patch-bundle-report.md`
- `validation-summary.txt`
- `receipts/receipt-*.json`

The report includes accepted/rejected/evidence-only counts, rejection reason counts, receipt paths, run id, base commit, and validator version.

## Fixture Run

The deterministic fixture input writer is:

```bash
python3 scripts/parallel_delivery/patch_bundle_fixture.py \
  --out workspace/runs/parallel-delivery/patch-bundle-fixture \
  --base-commit "$(git rev-parse HEAD)"
```

Then collect:

```bash
cento parallel-delivery patch-bundles collect \
  --run-id patch-bundle-fixture \
  --bundles-dir workspace/runs/parallel-delivery/patch-bundle-fixture/input/bundles \
  --lease-manifest workspace/runs/parallel-delivery/patch-bundle-fixture/input/leases.json \
  --out workspace/runs/parallel-delivery/patch-bundle-fixture \
  --base-commit "$(git rev-parse HEAD)" \
  --json
```

The fixture includes one safe patch bundle, one evidence-only bundle, and rejected bundles for outside lease, protected path, `.env.mcp`, traversal, absolute path, symlink, submodule, binary patch, undeclared delete, unowned rename, broad lockfile change, and fake secret-looking added content.

## Rejection Codes

Stable reason codes include `missing_required_field`, `invalid_bundle_schema`, `run_id_mismatch`, `base_commit_mismatch`, `missing_task_lease`, `unsafe_path_traversal`, `absolute_path`, `path_outside_lease`, `diff_path_not_declared`, `declared_path_not_in_diff`, `protected_path_edit`, `local_secret_path_edit`, `symlink_patch_prohibited`, `submodule_patch_prohibited`, `binary_patch_prohibited`, `undeclared_delete`, `unowned_rename`, `broad_lockfile_change`, `secret_like_content`, `unsafe_evidence_path`, `missing_evidence_file`, `unsupported_patch_ref`, `worker_validation_missing`, and `worker_validation_failed`.

## Unsafe Rules

- Do not copy secrets or `.env.mcp`.
- Do not store OpenAI keys or local secret values.
- Do not trust worker-provided lease data.
- Do not support remote patch refs in this slice.
- Do not claim a bundle is accepted without a receipt.
- Do not apply patches in collection or validation.
- Do not write generated run artifacts outside `workspace/runs/` unless an operator explicitly provides another output directory.
