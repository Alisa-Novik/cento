# Cento Build

`cento build` is the local, deterministic build-package primitive for future parallel workers. It is a safe work-package contract and patch acceptance layer. It does not launch cloud workers, call model APIs, create PRs, or schedule worker pools.

The v1.2 local-builder flow is:

```text
operator task -> manifest -> owned paths -> builder prompt -> local worker -> patch bundle -> integration dry-run -> apply -> validation -> evidence
```

## Commands

Create a manifest and Builder prompt:

```bash
cento build init \
  --task "Fixture docs page patch" \
  --mode fast \
  --write tests/fixtures/cento_build/app_page.html \
  --route /fixture
```

This writes:

```text
.cento/builds/<build_id>/manifest.json
.cento/builds/<build_id>/builder.prompt.md
```

Validate a manifest:

```bash
cento build check .cento/builds/<build_id>/manifest.json
```

Print or rewrite the Builder prompt:

```bash
cento build prompt .cento/builds/<build_id>/manifest.json
cento build prompt .cento/builds/<build_id>/manifest.json --write
```

Dry-run integrate a worker patch:

```bash
cento build bundle synthesize \
  --manifest .cento/builds/<build_id>/manifest.json \
  --patch .cento/builds/<build_id>/workers/builder_1/patch.diff

cento build integrate .cento/builds/<build_id>/manifest.json \
  --bundle .cento/builds/<build_id>/integration/patch_bundle.json \
  --dry-run
```

Check a worker artifact explicitly:

```bash
cento build artifact check .cento/builds/<build_id>/workers/builder_1/worker_artifact.json
```

Run one local worker and collect its patch bundle:

```bash
cento build worker run .cento/builds/<build_id>/manifest.json \
  --worker builder_1 \
  --runtime fixture \
  --fixture-case valid \
  --worktree \
  --timeout 180
```

Fixture cases are `valid`, `unowned`, `protected`, `delete`, `lockfile`, and `binary`. `valid` writes only the first owned path; unsafe cases must be rejected by the build guard.

Runtime profiles are the preferred command-worker path:

```bash
cento runtime check codex-fast

cento build worker run .cento/builds/<build_id>/manifest.json \
  --worker builder_1 \
  --runtime-profile codex-fast \
  --worktree
```

Profiles live in `.cento/runtimes.yaml`. Command profiles use argv arrays, scrubbed environment allowlists, explicit timeouts, isolated worktrees, and post-run path guards. Missing command executables are warnings from `cento runtime check` unless `--require-executable` is passed.

Raw command strings are available only as an explicit local escape hatch:

```bash
cento build worker run .cento/builds/<build_id>/manifest.json \
  --worker builder_1 \
  --runtime command \
  --command "codex exec --prompt-file {prompt}" \
  --allow-unsafe-command \
  --worktree \
  --timeout 180
```

Command placeholders are `{manifest}`, `{prompt}`, `{build_dir}`, `{worker_dir}`, `{worktree}`, `{worker}`, and `{artifact_dir}`.

This writes:

```text
.cento/builds/<build_id>/workers/builder_1/worker_artifact.json
.cento/builds/<build_id>/workers/builder_1/patch_bundle.json
.cento/builds/<build_id>/workers/builder_1/patch.diff
.cento/builds/<build_id>/workers/builder_1/handoff.md
```

Rejected workers still write `worker_artifact.json`, `patch.diff` when available, and rejection details. Safe output uses worker artifact status `completed`; unsafe output uses `rejected`; runtime failure uses `failed`.

Run the integration dry-run in an isolated clean worktree:

```bash
cento build integrate .cento/builds/<build_id>/manifest.json \
  --bundle .cento/builds/<build_id>/workers/builder_1/patch_bundle.json \
  --worktree \
  --dry-run
```

Apply a previously accepted integration receipt to the operator worktree:

```bash
cento build apply .cento/builds/<build_id>/manifest.json \
  --bundle .cento/builds/<build_id>/workers/builder_1/patch_bundle.json \
  --from-receipt .cento/builds/<build_id>/integration_receipt.json
```

Print the latest receipt:

```bash
cento build receipt .cento/builds/<build_id>
```

## Manifest Contract

The manifest is JSON first. It declares:

- `schema_version`: `cento.build.v1`
- `id`: stable build id
- `task`: title and description
- `mode`: execution mode from `.cento/modes.yaml`
- `scope.routes`: affected routes
- `scope.read_paths`: non-exclusive read paths
- `scope.write_paths`: exclusive owned write paths
- `scope.protected_paths`: paths that cannot be edited
- `policies`: ask, dirty repo, commit, push, and change policies
- `validation`: validation tier and commands
- `workers`: local worker artifact directories

`cento build init --mode fast` copies the mode policy into the manifest. `standard` and `thorough` produce different policy metadata.

## Integration Rules

`cento build integrate` accepts a patch only when:

- the manifest is valid
- a patch bundle is supplied, unless `--dev-raw-patch` is explicitly used for fixture/dev work
- all touched paths are owned
- no protected paths are touched
- no binary, traversal, absolute-path, symlink, submodule, undeclared delete, or unowned-rename patch is present
- lockfile changes are explicitly owned
- dirty owned paths are absent unless `--allow-dirty-owned` is passed
- `git apply --check` passes
- validation commands pass

It rejects patches that touch unowned files, protected files, lockfiles not explicitly owned, mismatched manifest or worker artifacts, or patches that do not apply cleanly. Every integration attempt writes:

```text
.cento/builds/<build_id>/integration_receipt.json
.cento/builds/<build_id>/validation_receipt.json
```

`cento build apply` applies only after the integration receipt is accepted. It rejects when the manifest id, bundle id/path, base ref, dirty-owned state, bundle contract, or patch apply check fails. A successful apply writes:

```text
.cento/builds/<build_id>/apply_receipt.json
.cento/builds/<build_id>/taskstream_evidence.json
```

The fixture checks are:

```bash
cento build check tests/fixtures/cento_build/manifest.valid.json
cento build artifact check tests/fixtures/cento_build/worker_artifact.valid.json
cento build artifact check tests/fixtures/cento_build/worker_artifact.unowned.json
cento build bundle synthesize --manifest tests/fixtures/cento_build/manifest.valid.json --patch tests/fixtures/cento_build/patch.valid.diff
cento build integrate tests/fixtures/cento_build/manifest.valid.json --bundle .cento/builds/build_fixture_docs_page_001/integration/patch_bundle.json --dry-run
cento build bundle synthesize --manifest tests/fixtures/cento_build/manifest.valid.json --patch tests/fixtures/cento_build/patch.unowned.diff
cento build bundle synthesize --manifest tests/fixtures/cento_build/manifest.valid.json --patch tests/fixtures/cento_build/patch.protected.diff
cento build bundle synthesize --manifest tests/fixtures/cento_build/manifest.valid.json --patch tests/fixtures/cento_build/patch.traversal.diff
cento build bundle synthesize --manifest tests/fixtures/cento_build/manifest.valid.json --patch tests/fixtures/cento_build/patch.binary.diff
cento build worker run .cento/builds/<build_id>/manifest.json --worker builder_1 --runtime fixture --fixture-case valid --worktree --timeout 180
cento build apply .cento/builds/<build_id>/manifest.json --bundle .cento/builds/<build_id>/workers/builder_1/patch_bundle.json --from-receipt .cento/builds/<build_id>/integration_receipt.json
```

The valid bundle is accepted when the owned path is clean or `--allow-dirty-owned` is explicit. The raw patch integration path rejects by default. The unowned artifact, unowned patch, protected patch, traversal patch, and binary patch are rejected.

## Run Fast

`cento run fast` now creates an implicit build package for owned-path tasks:

```bash
cento run fast \
  --task "Patch docs page title" \
  --write apps/watch/KanjiADay/Preview/index.html \
  --route /docs/apps/kanji-a-day
```

With `--local-builder fixture --fixture-case valid --apply`, `cento run fast` runs one isolated local builder, dry-runs the collected patch bundle, applies it if accepted, runs smoke validation, and writes evidence:

```bash
cento run fast \
  --task "Patch docs page title" \
  --write apps/watch/KanjiADay/Preview/index.html \
  --route /docs/apps/kanji-a-day \
  --local-builder fixture \
  --fixture-case valid \
  --apply \
  --validation smoke \
  --commit none
```

The same fast path can use a real local runtime profile:

```bash
cento run fast \
  --task "Patch docs page title" \
  --write apps/watch/KanjiADay/Preview/index.html \
  --route /docs/apps/kanji-a-day \
  --runtime-profile codex-fast \
  --apply \
  --validation smoke \
  --commit none
```

This writes:

```text
.cento/builds/<build_id>/manifest.json
.cento/builds/<build_id>/builder.prompt.md
.cento/builds/<build_id>/workers/builder_1/worker_artifact.json
.cento/builds/<build_id>/workers/builder_1/patch_bundle.json
.cento/builds/<build_id>/integration_receipt.json
.cento/builds/<build_id>/apply_receipt.json
.cento/builds/<build_id>/validation_receipt.json
.cento/builds/<build_id>/taskstream_evidence.json
```

Without `--local-builder`, the integration receipt remains `pending` and records that no worker patch was collected.

## Factory And Taskstream

`cento build` is the concrete local slice that Factory can call before real worker scheduling exists. It covers materialize, local lease shape, collect, validate, and dry-run integrate for one manifest-owned patch package.

Each generated build writes `.cento/builds/<build_id>/events.ndjson`. Current event names are:

```text
build_manifest_created
builder_prompt_created
worker_started
worker_artifact_written
worker_artifact_received
validation_receipt_written
integration_dry_run_passed
integration_dry_run_rejected
integration_receipt_pending
patch_applied
patch_apply_rejected
taskstream_evidence_attached
build_completed
```

Taskstream should treat a build as a work unit only when the integration and validation receipts provide evidence. `cento workset` is the thin local orchestrator above this one-worker contract: it runs exclusive-path tasks in parallel worktrees, then feeds each patch back through `cento build` sequential integration and apply. Factory remains responsible for future materialization and release candidate flow.
