# Builder Agent Guidelines

Builders work inside a Cento build manifest. Owned write paths are exclusive. Read paths are non-exclusive. Protected paths are never editable.

## Builder May

- inspect read paths
- edit only owned write paths
- create a patch artifact
- run allowed validation commands
- summarize assumptions
- report blockers
- report files touched

## Builder Must Output

Each Builder writes these files under its manifest artifact directory:

```text
patch.diff
patch_bundle.json
worker_artifact.json
handoff.md
```

`worker_artifact.json` uses `cento.worker_artifact.v1` and records worker id, role, status, manifest id, base ref, owned paths, touched paths, patch path, assumptions, validation, blockers, and risks.

`patch_bundle.json` uses `cento.patch_bundle.v1` and records touched paths, owned paths, unowned paths, protected paths touched, summary, base ref, and whether integration is required.

`handoff.md` stays short:

```markdown
# Builder Handoff

## Changed
- Updated the owned page.

## Touched files
- tests/fixtures/cento_build/app_page.html

## Assumptions
- Used static fixture content.

## Validation
- Diff check: passed

## Risks
- No live data source is connected.
```

## Builder Must Never

- edit unowned paths
- stage unrelated files
- commit unless explicitly allowed
- push unless explicitly allowed
- modify protected files
- change lockfiles unless explicitly owned and allowed
- touch `.env` or credentials
- silently expand scope
- overwrite dirty owned files
- hide validation failures

## Dirty Repo Rules

Dirty unrelated files are preserved and ignored. Dirty owned files block or warn according to the manifest policy. Staged unrelated files must not be touched.

## Patch Requirements

Generate patches against the current base:

```bash
git diff -- <owned_paths> > patch.diff
```

The patch must not include unowned paths, protected paths, binary blobs, or lockfiles unless the manifest explicitly owns and allows them.
