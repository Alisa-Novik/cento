# Agent Work Docs/Evidence Lane

The Docs/Evidence lane owns manager-facing deliverables and evidence preservation. Implementation agents do not own final proof.

## Lane Contract

The Docs/Evidence lane is responsible for:

- Generating and updating `start-here.html` hubs from story manifests.
- Maintaining `deliverables.json` with current artifact links.
- Writing and publishing validation logs and screenshot indexes.
- Keeping captain's notes append-only (no history rewrites).
- Composing Redmine review notes with the required four sections.
- Preserving old evidence rather than overwriting it.

The Docs/Evidence lane does **not**:

- Write product code or implement features.
- Run the Validator pass (`validate --result pass`) — that belongs to the Validator lane.
- Move issues to Review — that is gated by the Validator lane.
- Delete or overwrite prior evidence files.

## Required Inputs from story.json

| Field | Purpose |
|---|---|
| `issue.id`, `issue.title`, `issue.status` | Hub header and Redmine link |
| `issue.url` | Direct link to the Redmine story |
| `lane.owner`, `lane.agent`, `lane.node` | Attribution in the hub |
| `paths.run_dir` | Root for all output files |
| `scope.goal` | Hub subtitle |
| `scope.acceptance` | Review checklist items |
| `expected_outputs[]` | Files to link from the hub; `owner` field used to group by lane |
| `validation.required_evidence[]` | Evidence paths to verify and list |
| `deliverables.manifest` | Source for `deliverables_hub.py` generation |
| `deliverables.hub` | Target hub path |
| `screenshots[]` | Names, descriptions, and output paths for screenshot index |
| `handoff.notes` | Appended to captain's notes |
| `review_gate.required_sections` | Sections to include in the Redmine review note |
| `review_gate.residual_risk_required` | Whether the review note must include a non-empty Residual risk section |
| `routes[]` | App/UI links for the hub |

## Required Outputs

Every story worked by this lane must produce:

| File | Description |
|---|---|
| `<run_dir>/start-here.html` | Manager-facing hub with links to app, docs, screenshots, validation log, and Redmine status |
| `<run_dir>/deliverables.json` | Structured manifest consumed by `scripts/deliverables_hub.py` or `scripts/story_manifest.py render-hub` |
| `<run_dir>/validation.md` | Append-only evidence log: commands run, results, screenshot paths |
| `<run_dir>/screenshots/` | Visual evidence directory; each screenshot indexed in the hub |

Optional but standard:

| File | When present |
|---|---|
| `<run_dir>/captain-notes.md` | Append-only narrative across all runs on the story |
| `<run_dir>/screenshots/index.html` | Standalone screenshot browser when there are more than a few images |

## Generating the Hub

From a story manifest:

```bash
python3 scripts/story_manifest.py render-hub workspace/runs/agent-work/<id>/story.json --check-links
```

From a deliverables manifest:

```bash
python3 scripts/deliverables_hub.py workspace/runs/agent-work/<id>/deliverables.json --check-links
```

Run either command again to regenerate — it must not destroy prior evidence.

## Redmine Review-Note Sections

Every Redmine review note posted by this lane must include all four sections below. The `review_gate.required_sections` field in `story.json` is the machine-readable version of this requirement.

### Delivered

Bullet list of what was built or shipped this story. Each item names a concrete artifact or change, not a task status.

```
*Delivered*
* docs/agent-work-docs-evidence-lane.md — Docs/Evidence lane contract
* workspace/runs/agent-work/49/start-here.html — evidence hub
```

### Validation

Bullet list of checks run and their results. State the command or check name, then pass or fail. If a check was skipped, say so and why.

```
*Validation*
* python3 scripts/story_manifest.py validate workspace/runs/agent-work/49/story.json — pass
* required evidence files present — pass
```

### Evidence

Paths to durable artifacts a reviewer can open. At minimum: hub, validation log or report. Include screenshots when they exist.

```
*Evidence*
* @workspace/runs/agent-work/49/start-here.html@
* @workspace/runs/agent-work/49/validation.md@
* @docs/agent-work-docs-evidence-lane.md@
```

### Residual risk

Explicit statement of what could still go wrong. If there is no risk, state "None" — the section must be present and non-empty. Silence is not a risk statement.

```
*Residual risk*
* None — contract is documentation only; no production code changed.
```

Or when risk exists:

```
*Residual risk*
* Hub links to screenshots that are not yet captured; validator must confirm before closing.
```

## review_gate in story.json

The `review_gate` field enforces the four-section requirement at the manifest level:

```json
"review_gate": {
  "required_sections": [
    "Delivered",
    "Validation",
    "Evidence",
    "Residual risk"
  ],
  "residual_risk_required": true
}
```

`residual_risk_required: true` means the Residual risk section must be present and non-empty. The Docs/Evidence lane is responsible for writing this field into new story manifests it creates, and for including all four sections in every Redmine review note.

## Evidence Preservation Rules

1. Never delete or overwrite existing screenshots, validation logs, or hub snapshots.
2. Append to `captain-notes.md` and `validation.md`; do not truncate.
3. When regenerating a hub, write to the same path — the script must be idempotent.
4. Archive old hubs as `start-here-<timestamp>.html` before replacing if the story has been through Review once already.

## Minimal story.json Shape for This Lane

```json
{
  "schema_version": "1.0",
  "issue": { "id": 49, "title": "...", "package": "spark-docs-evidence-lane" },
  "lane": { "owner": "docs-evidence", "role": "builder", "node": "linux", "agent": "docs-claude" },
  "paths": { "run_dir": "workspace/runs/agent-work/49" },
  "scope": {
    "goal": "Define Docs/Evidence lane contract.",
    "acceptance": [
      "docs/agent-work-docs-evidence-lane.md exists and covers contract, inputs, outputs, and review-note sections.",
      "story.json for #49 present with review_gate field."
    ]
  },
  "expected_outputs": [
    {
      "path": "docs/agent-work-docs-evidence-lane.md",
      "owner": "docs-evidence",
      "description": "Docs/Evidence lane contract",
      "required": true
    }
  ],
  "review_gate": {
    "required_sections": ["Delivered", "Validation", "Evidence", "Residual risk"],
    "residual_risk_required": true
  }
}
```
