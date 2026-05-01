# Cento Storage

Cento Storage is the no-delete artifact catalog and retention control plane for high-fanout Factory work.

It answers:

- what artifacts exist
- which run, task, package, or issue produced them
- which artifacts are high-value evidence
- which files are duplicate, bulky, private, or reproducible
- which files are candidates for future compression, normalization, archive, or prune gates

The first slice is intentionally conservative. It catalogs and plans lifecycle actions, but it does not delete artifacts and does not upload anything to cloud storage.

## Commands

```bash
cento storage scan --root workspace/runs --db workspace/storage/catalog.sqlite
cento storage plan --dry-run
cento storage query --largest --limit 20
cento storage query --class screenshot_raw
cento storage pressure --json
cento storage normalize screenshots --dry-run
cento storage compress logs --dry-run
cento storage snapshot-db --path workspace/storage/catalog.sqlite --out workspace/storage/db-snapshots/catalog-snapshot.db
cento storage restore-test --sample 10
cento storage verify --all
cento storage report --out workspace/storage/reports/storage-summary.md
```

## Artifact Classes

The scanner classifies common Cento run artifacts:

- `manifest`: `factory-plan.json`, `story.json`, queue state, integration state, Autopilot state
- `ledger`: run ledgers and JSONL event streams
- `patch`: patch bundles, changed-files lists, diffstats, handoffs
- `validation`: validation summaries and evidence
- `release_packet`: release candidates, delivery packets, static hubs
- `screenshot_raw`: raw `.xwd` screenshots
- `screenshot_normalized`: normalized PNG/WebP/JPEG screenshots
- `prompt`: worker prompts and prompt records
- `log`: Codex logs, validator logs, shell transcripts
- `sqlite_db` and `sqlite_wal`: database files and WAL/SHM companions
- `build_intermediate`: reproducible build outputs
- `research_source` and `research_map`: research artifacts and implementation maps
- `client_data`: business or client-sensitive data

## Safety Rules

Storage v1 has a no-delete posture.

- `cento storage plan` writes a dry-run plan only.
- Raw screenshots are only marked for normalization/compression until derivatives are verified.
- SQLite DB/WAL files require controlled snapshots and integrity checks before movement.
- Build intermediates can be reported as deletion candidates, but v1 will not prune them.
- Cloud upload is out of scope for v1.

SQLite snapshots use SQLite backup semantics and write metadata next to the snapshot. The command does not delete active WAL/SHM files:

```bash
cento storage snapshot-db --path workspace/storage/catalog.sqlite --out workspace/storage/db-snapshots/catalog-snapshot.db
```

Future pruning should require a verified catalog, backup location, restore test, deletion manifest, and quarantine TTL.

## External Vault

The planned 8TB disk is treated as a vault target:

```text
/mnt/cento-vault
```

It does not need to be connected for Storage v1. When the mount is absent, `cento storage plan` marks the vault as `mocked_unmounted` and keeps all vault movement as plan-only metadata.

After the disk is plugged in, the expected layout is:

```text
/mnt/cento-vault/
├── snapshots/
├── cas/
├── cold-runs/
├── db-snapshots/
├── screenshots/
├── logs-compressed/
└── restore-tests/
```

Storage v1 still will not write there automatically. Future vault execution should require explicit enable flags plus hash verification.

## Factory Relationship

Factory, Safe Integrator, and Autopilot produce durable artifacts under `workspace/runs/`. High fanout will increase artifact volume, so Autopilot should eventually read storage pressure before increasing dispatch.

Useful future Autopilot gates:

- uncataloged artifact count
- raw screenshots without derivatives
- unverified cold moves
- catalog integrity failures
- storage pressure from largest artifacts

`cento storage pressure --json` emits the first Autopilot-friendly pressure packet. It does not mutate anything. The first version reports catalog integrity, artifact bytes, raw XWD count/bytes, private artifact count, SQLite artifact count, and whether fanout should increase, hold, or pause.

## Validation

```bash
python3 scripts/storage_e2e.py --fixture mixed-artifacts --out workspace/runs/storage/cento-storage-v1
grep -q "AI calls used: 0" workspace/runs/storage/cento-storage-v1/e2e-summary.md
sqlite3 workspace/runs/storage/cento-storage-v1/catalog.sqlite "PRAGMA integrity_check;"
python3 -m json.tool workspace/runs/storage/cento-storage-v1/storage-pressure.json
python3 scripts/no_model_validation_e2e.py
make check
```
