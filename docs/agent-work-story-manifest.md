# Agent Work Story Manifest

`story.json` is the shared contract for one Cento Taskstream story. It sits above the existing validation and deliverables manifests so every agent lane can start from the same source instead of chat history.

Recommended path:

```bash
workspace/runs/agent-work/<issue-id>/story.json
```

Validate a story manifest:

```bash
python3 scripts/story_manifest.py validate workspace/runs/agent-work/<issue-id>/story.json
```

Generate a manager-facing hub from a story manifest:

```bash
python3 scripts/story_manifest.py render-hub workspace/runs/agent-work/<issue-id>/story.json --check-links
```

Use it in a Builder handoff:

```bash
cento agent-work handoff <issue-id> --manifest workspace/runs/agent-work/<issue-id>/story.json --summary "..."
```

## Required Fields

- `schema_version`: current value is `1.0`.
- `issue`: story identity: `id`, `title`, `package`, and optional `url`.
- `lane`: owner lane metadata: `owner`, `role`, `node`, and `agent`.
- `paths.run_dir`: durable run directory for the story.
- `scope.acceptance`: non-empty acceptance checklist.
- `expected_outputs`: files or artifacts the story should produce.

## Optional But Standard Fields

- `routes`: UI routes or pages the story changes or validates.
- `api_endpoints`: HTTP/API checks relevant to the story.
- `validation.manifest`: existing `validation.json` path for `cento agent-work validate-run`.
- `validation.commands`: focused local checks a Builder or Validator can run.
- `deliverables.manifest`: `deliverables.json` path for `scripts/deliverables_hub.py`.
- `screenshots`: required screenshot names, URLs, viewports, and output paths.
- `handoff`: human/device handoff steps and notes.
- `review_gate`: required review-note sections and residual-risk policy.
- `review_gate.required_evidence_categories`: optional list of evidence classes to enforce (`syntax-test`, `api-check`, `screenshot`, `visual-inspection`).

Screenshot support:

- `screenshots[]` supports optional `auth` and `auth_note` metadata for protected targets.
- `cento story-screenshot-runner` reads screenshot entries, generates deterministic screenshot paths, captures both desktop/mobile viewports, and writes metadata/index evidence for Docs/Evidence and Validator lanes.

Example:

```bash
cento story-screenshot-runner workspace/runs/agent-work/59/story.json --force
```

## Agent Lane Usage

Builder:

- Reads `scope`, `routes`, `api_endpoints`, and `expected_outputs`.
- Implements the smallest code path that satisfies `scope.acceptance`.
- Runs `validation.commands` that are safe before handoff.
- Uses `cento agent-work handoff --manifest story.json`.

Validator:

- Starts from `validation.manifest`.
- Runs `cento agent-work validate-run ISSUE --manifest validation.json --story-manifest story.json`.
- Checks screenshots and evidence listed in `story.json`.
- Moves the story to Review only after required checks and evidence pass.

Docs/Evidence:

- Maintains `deliverables.manifest`, `start-here.html`, screenshot index, and manager-facing summaries.
- Preserves old evidence instead of rewriting history.
- Links `story.json`, `validation.json`, validation reports, screenshots, and current story status.

Coordinator:

- Creates or updates `story.json` before dispatch.
- Splits stories when `routes`, `api_endpoints`, `screenshots[]`, or `handoff` requirements differ.
- Combines stories only when they can share the same acceptance contract, validation commands, evidence files, and review gate.
- Routes work explicitly to Builder, Validator, and Docs/Evidence lanes instead of overloading a single owner.
- Keeps Taskstream statuses aligned with the active owner and the current blocker state.
- Escalates missing device access or human handoff requirements early.
- Follow the operating checklist in `docs/agent-work-coordinator-lane.md` for intake, acceptance contracts, shared evidence, notifications, and handoff escalation.

## Minimal Shape

```json
{
  "schema_version": "1.0",
  "issue": {
    "id": 56,
    "title": "Process Scaling: Story manifest format",
    "package": "improve-dev-process"
  },
  "lane": {
    "owner": "builder",
    "role": "builder",
    "node": "linux",
    "agent": "alice"
  },
  "paths": {
    "run_dir": "workspace/runs/agent-work/56"
  },
  "scope": {
    "goal": "Create a standard story manifest format.",
    "acceptance": [
      "A manifest example exists.",
      "Docs explain required vs optional fields."
    ]
  },
  "expected_outputs": [
    {
      "path": "docs/agent-work-story-manifest.md",
      "owner": "docs-evidence",
      "description": "Story manifest contract documentation"
    }
  ]
}
```

If used for strict gate checks, extend the manifest with `review_gate`:

```json
{
  "review_gate": {
    "required_sections": ["Delivered", "Validation", "Evidence", "Residual risk"],
    "residual_risk_required": true,
    "required_evidence_categories": ["syntax-test", "screenshot", "visual-inspection", "api-check"]
  }
}
```

## Relationship To Existing Manifests

`story.json` does not replace `validation.json` or `deliverables.json`.

- `validation.json` remains the executable validation contract for `validate-run`.
- `deliverables.json` remains the source for `start-here.html`.
- `story.json` links those files and adds ownership, routes, handoff, and review-gate context.

## Hub Generation

`render-hub` derives a `deliverables.json` and `start-here.html` from `story.json`.

Default outputs:

- `workspace/runs/agent-work/<issue-id>/deliverables.json`
- `workspace/runs/agent-work/<issue-id>/start-here.html`

The command is repeatable and does not delete older evidence. It rewrites only the generated deliverables manifest and HTML hub for the selected story.

Use `--check-links` to fail when local links in the generated hub are missing.
