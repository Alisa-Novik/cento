# OCI Image Migration

Readable HTML guide: [`docs/oci-image-migration.html`](./oci-image-migration.html).

This document is the operator and agent handoff for Cento's mirror-only image migration to Oracle Cloud Infrastructure Object Storage.

The current migration copies Cento run images to OCI Standard Object Storage, verifies restore samples by SHA-256, and leaves all local files unchanged. It is not a disk-reclaim flow yet.

## Current Cloud State

- Bucket: `cento-images-standard`
- Namespace: `id4bktw2wcnn`
- Region: `us-ashburn-1`
- Storage tier: `Standard`
- Public access: `NoPublicAccess`
- Versioning: `Disabled`
- Replication: `Disabled`
- Object events: `Disabled`
- Object prefix: `cento/images/v1/objects/sha256/`

Current live mirror evidence:

```text
workspace/runs/object-storage/image-migration-20260505T051846Z/
  manifest.json
  summary.md
  upload-receipt.json
  upload-summary.md
  verify-receipt.json
```

The completed run planned `452` image rows under `workspace/runs`, deduped them to `352` unique OCI objects, uploaded `361,679,317` bytes, and verified a 10-object download sample. Estimated Standard storage cost for the unique object bodies is about `$0.0086/month`.

## Command Surface

Verify OCI auth and namespace in the working region:

```bash
cento object-storage status --probe --region us-ashburn-1 --json
```

Create or verify the private Standard image bucket:

```bash
cento object-storage ensure-bucket \
  --name cento-images-standard \
  --namespace id4bktw2wcnn \
  --region us-ashburn-1 \
  --json
```

Plan a mirror-only image migration:

```bash
cento object-storage plan-images \
  --root workspace/runs \
  --bucket cento-images-standard \
  --namespace id4bktw2wcnn \
  --region us-ashburn-1 \
  --json
```

Upload the planned unique image objects:

```bash
cento object-storage upload-images \
  --manifest workspace/runs/object-storage/<run-id>/manifest.json \
  --bucket cento-images-standard \
  --namespace id4bktw2wcnn \
  --region us-ashburn-1 \
  --live \
  --json
```

Verify uploaded objects by downloading a sample and checking SHA-256:

```bash
cento object-storage verify-images \
  --manifest workspace/runs/object-storage/<run-id>/upload-receipt.json \
  --sample 10 \
  --json
```

## Migration Contract

The image mirror is intentionally conservative.

- It scans only image-like files under the selected root.
- Supported suffixes are `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.svg`, and `.xwd`.
- It skips `.git`, `.venv`, `venv`, `__pycache__`, and `node_modules`.
- It blocks sensitive-looking paths containing `token`, `secret`, `.env`, `.pem`, or `key4.db`.
- It dedupes by SHA-256 before upload.
- It uploads content-addressed object bodies.
- It never deletes, truncates, rewrites, or replaces local files.

Object names are deterministic:

```text
cento/images/v1/objects/sha256/<first2>/<sha256>/<filename>
```

The manifest keeps one row per source image path. Duplicate local files point at the same content-addressed object body but remain distinct manifest rows.

## Receipts

`manifest.json` is the planned work:

- source path
- size
- SHA-256
- extension
- content type
- artifact class
- sensitivity
- object name and URI
- planned upload role: `primary`, `duplicate`, or `blocked`

`upload-receipt.json` records the executed upload:

- source manifest
- bucket, namespace, and region
- uploaded object count
- failed object count
- dedupe count
- blocked row count
- per-row upload status

`verify-receipt.json` records restore validation:

- source upload receipt
- verification sample size
- downloaded file paths
- OCI return codes
- expected SHA-256
- per-object verification result

## Safety And Risk

The current bucket posture is private and low-cost:

- Standard Object Storage, not Archive.
- No public bucket access.
- No pre-authenticated requests are required.
- No versioning, so accidental duplicate version growth is not enabled.
- No replication, so writes are not copied to another region.

Bill explosion risk is low at current size. The main risks are future unbounded uploads, public access changes, broad pre-authenticated URLs, enabling versioning without lifecycle controls, or adding a disk-reclaim command before restore testing is mature.

Data leak risk is controlled by private bucket access plus filename/path filtering, but the filter is not a substitute for review. Do not upload secrets, browser profile credential stores, `.env` files, private keys, API tokens, or client-sensitive records.

## Validation Checklist

Run this before claiming the migration path is healthy:

```bash
python3 -m pytest tests/test_object_storage.py -q
python3 -m py_compile scripts/object_storage.py
python3 -m json.tool data/tools.json >/tmp/cento-tools-json-check.txt
python3 -m json.tool data/cento-cli.json >/tmp/cento-cli-json-check.txt
zsh -n scripts/completion/_cento
make check
```

Run this against OCI after an upload:

```bash
oci os bucket get \
  --region us-ashburn-1 \
  --namespace-name id4bktw2wcnn \
  --bucket-name cento-images-standard \
  --query 'data.{name:name,storageTier:"storage-tier",publicAccessType:"public-access-type",versioning:versioning,replicationEnabled:"replication-enabled"}' \
  --output json

oci os object list \
  --region us-ashburn-1 \
  --namespace-name id4bktw2wcnn \
  --bucket-name cento-images-standard \
  --prefix cento/images/v1/objects/sha256/ \
  --all \
  --output json
```

Expected bucket posture:

```json
{
  "name": "cento-images-standard",
  "publicAccessType": "NoPublicAccess",
  "replicationEnabled": false,
  "storageTier": "Standard",
  "versioning": "Disabled"
}
```

## Next Implementation Steps

### 1. Resume-Safe Uploads

Add incremental receipts so a long upload can resume safely:

- write `upload-receipt.partial.json` after every object upload
- add `upload-images --resume`
- skip objects already marked `uploaded` with matching SHA
- keep the final `upload-receipt.json` format stable

Acceptance criteria:

- killing an upload mid-run leaves a readable partial receipt
- rerunning with `--resume` completes without re-uploading successful objects
- duplicate SHA rows still point to the same primary object

### 2. Remote Object Metadata

Write OCI object metadata during upload:

- `cento-sha256`
- `cento-source-path`
- `cento-artifact-class`
- `cento-migration-run-id`

Add metadata-aware verification:

- `verify-images --metadata-first`
- compare remote metadata before downloading
- keep download verification available as the strongest restore proof

Acceptance criteria:

- uploaded objects expose the expected metadata through OCI CLI
- metadata mismatch fails verification
- sample download still SHA-verifies

### 3. Idempotent Re-Runs

Before uploading a primary object, check whether the target object already exists.

Desired behavior:

- if object exists with matching metadata, mark `already_uploaded`
- if object exists without metadata, require download verification or overwrite only with `--force`
- if object exists with mismatched hash metadata, fail closed

Acceptance criteria:

- rerunning upload on the same manifest produces zero failed objects
- no accidental duplicate object keys are created
- no existing object is overwritten unless explicitly forced

### 4. Storage Catalog Integration

Connect OCI locations back into `workspace/storage/catalog.sqlite`.

Use the existing `artifact_locations` table:

```text
artifact_id
location_type = oci_object
uri = oci://id4bktw2wcnn/cento-images-standard/...
verified_at
restore_tested_at
```

Update `scripts/storage.py report` to show:

- local-only image bytes
- OCI-mirrored image bytes
- verified mirrored image count
- restore-tested image count
- unmirrored large images

Acceptance criteria:

- `storage.py report` includes OCI mirror status
- mirrored artifacts can be queried by location type
- catalog integrity remains `ok`

### 5. Restore Commands

Add explicit restore commands before any disk reclaim work:

```bash
cento object-storage restore-image \
  --source-path workspace/runs/.../image.png \
  --manifest workspace/runs/object-storage/<run-id>/upload-receipt.json \
  --out workspace/restores/image-restore-<timestamp>

cento object-storage restore-images \
  --manifest workspace/runs/object-storage/<run-id>/upload-receipt.json \
  --sample 10 \
  --out workspace/restores/image-restore-<timestamp>
```

Restore must:

- download from OCI
- verify SHA-256
- write `restore-receipt.json`
- avoid overwriting existing files unless `--overwrite` is passed

Acceptance criteria:

- one image can be restored by original source path
- a sample batch restore passes SHA verification
- existing local files are protected by default

### 6. Reclaim Planning Only

Do not delete local images yet. Add only a future planning command:

```bash
cento object-storage plan-reclaim-images \
  --manifest workspace/runs/object-storage/<run-id>/upload-receipt.json \
  --json
```

Eligibility should require:

- object uploaded
- object verified
- restore test passed
- local source path still has the same SHA
- run is not active
- path is not sensitive

The first reclaimable action should be a restore stub, not deletion:

```text
image.png.oci.json
```

Stub fields:

- original path
- original size
- SHA-256
- object URI
- migration receipt
- restore command
- migrated timestamp

Acceptance criteria:

- unverified objects are never reclaim candidates
- changed local files are rejected
- command writes a plan only and does not remove local files

## AI Handoff Prompt

Use this prompt for the next implementation agent:

```text
You are working in /home/alice/projects/cento.

Goal: continue the OCI image migration implementation safely.

Read first:
- docs/oci-image-migration.md
- scripts/object_storage.py
- tests/test_object_storage.py
- workspace/runs/object-storage/image-migration-20260505T051846Z/upload-receipt.json
- workspace/runs/object-storage/image-migration-20260505T051846Z/verify-receipt.json

Constraints:
- mirror-only remains the default
- never delete or replace local images
- keep the bucket private Standard storage
- use explicit region us-ashburn-1 and namespace id4bktw2wcnn
- update data/tools.json, data/cento-cli.json, docs/tool-index.md, docs/platform-support.md, README.md, and completion if the command surface changes

Recommended next task:
Implement upload-images --resume with partial receipts and tests.

Validation:
- python3 -m pytest tests/test_object_storage.py -q
- python3 -m py_compile scripts/object_storage.py
- zsh -n scripts/completion/_cento
- make check
```
