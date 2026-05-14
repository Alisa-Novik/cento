# Agent Work Live Dispatch Incident

Use this runbook when `walk-autopilot` or `agent-pool-kick` reports a live worker launch failure. The default response is incident handling with bounded repair and retry, not switching the loop back to proof-only work.

## Incident Class

The common class is `missing_canonical_manifest`:

- `agent-pool-kick --dry-run` shows queued live candidates.
- `agent-work dispatch` blocks preflight with a missing canonical `story.json`.
- The affected issue may be moved to `Blocked` by the failed dispatch before repair runs.

Other classes are `dispatch_preflight_blocked`, `agent_pool_live_timeout`, or a reason from `agent-pool-kick` such as `agent_pool_runtime_missing`.

## Immediate Response

Run the repair with preflight still enabled:

```bash
./scripts/cento.sh agent-pool-kick \
  --repair-missing-manifests \
  --repair-apply \
  --repair-lanes all \
  --repair-limit 3 \
  --max-launch 0 \
  --dry-run
```

If the failure already changed a candidate to `Blocked`, force the specific issue id:

```bash
./scripts/cento.sh agent-pool-kick \
  --repair-missing-manifests \
  --repair-apply \
  --repair-lanes all \
  --repair-issue ISSUE_ID \
  --repair-limit 3 \
  --max-launch 0 \
  --dry-run
```

Then retry the live launch with the same bound:

```bash
./scripts/cento.sh agent-pool-kick --max-launch 3
```

Do not add `--skip-preflight`; repair the manifest contract instead.

## Walk Autopilot Behavior

When live dispatch fails, `walk-autopilot` writes an incident bundle under:

```text
workspace/runs/walk-autopilot/<run-id>/incidents/
```

Each bundle contains:

- `incident.json` with classification, candidate issue ids, manifest gaps, and resolution status.
- `attempts.jsonl` with the original live launch, repair command, post-repair dry-run, retry, and recovery-plan command when needed.
- `notes.md` for operator handoff.

If the same unresolved class repeats in consecutive loops, the run creates or records a guarded self-improvement follow-up instead of silently cycling.

## Validation

After repair, validate the restored contract before broad dispatch:

```bash
python3 -m json.tool data/tools.json
python3 -m pytest tests/test_agent_pool_kick.py tests/test_walk_autopilot.py
./scripts/cento.sh agent-pool-kick --max-launch 3 --dry-run
```

The incident is recovered when the bounded live retry exits `0` or a new, more specific blocker is recorded in the incident bundle.
