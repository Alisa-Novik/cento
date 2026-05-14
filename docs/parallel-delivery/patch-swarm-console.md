# Patch Swarm Console Status

Patch Swarm console status is an artifact-backed operator view for an existing run. It does not create a database. It reads the run directory, writes stable `console-data.json`, and can export a no-build static `start-here.html` hub with relative evidence links.

## Render A Console Hub

```bash
cento parallel-delivery patch-swarm status \
  --run-dir workspace/runs/parallel-delivery/e2e-fixture/fixture-100-agents \
  --write-html \
  --json
```

The command writes:

```text
<run-dir>/console-data.json
<run-dir>/start-here.html
<run-dir>/link-check.json
```

`--json` prints a compact machine-readable summary with the run id, result, candidate count, workers, bundle buckets, integration, validation, release candidate, next action, and generated artifact paths.

## Generate A Fixture Run

```bash
cento parallel-delivery patch-swarm e2e \
  --candidate-target 25 \
  --max-parallel-agents 5 \
  --fixture \
  --run-id fixture-console-25 \
  --output-dir workspace/runs/parallel-delivery/console-fixture/fixture-console-25 \
  --json
```

Then render the hub:

```bash
cento parallel-delivery patch-swarm status \
  --run-dir workspace/runs/parallel-delivery/console-fixture/fixture-console-25 \
  --write-html \
  --json
```

Open `workspace/runs/parallel-delivery/console-fixture/fixture-console-25/start-here.html` in a browser, or use the Cento Console route:

```text
/patch-swarm/console?run_dir=workspace/runs/parallel-delivery/console-fixture/fixture-console-25
```

Existing product Patch Swarm runs also expose a `Status console` link from the run detail evidence row.

## Source Artifacts

The console reads whichever supported artifact shape exists in the run:

- `validation-summary.json` or `validation_summary.json`
- `validation-report.md`
- `split-plan.json` and `task-graph.json`
- `path-leases.json`
- `worker-packets/codex-packet-index.json`
- `validation/patch-bundle-validation.json`
- `integration/integration-plan.json`
- `integration/integration-receipt.json`
- `integration/rejected-patches.json`
- `release-candidate/release-candidate.json`
- `release-candidate/demo-evidence.md` or `release-candidate/release-notes.md`

The generated HTML links only to relative files inside the run directory. Missing optional artifacts are shown as missing text, not clickable links, so link validation can fail closed on broken or escaping links.

## Next Action Rules

The operator next action is deterministic:

- Missing validation summary: `Generate or repair fixture validation summary`
- Failed validation: `Inspect validation-report.md and failing stage`
- Rejected bundles: `Review rejected bundles before release candidate`
- Human-review conflicts: `Resolve conflicts in conflict-report.md`
- Failed dry-run integration: `Run rebase or dry-run repair for affected bundles`
- Missing release candidate: `Create release candidate evidence`
- Passed validation with release candidate: `Ready for operator demo/release review`
