# Walk Autopilot Spend Cap Incident

Date: 2026-05-05

## Summary

The Walk Autopilot run `walk-autopilot-20260505T152507Z` was stopped after the OpenAI usage dashboard showed spend above the intended `$20` total cap.

Dashboard evidence from the operator showed:

- May spend: `$45.82`
- Selected-range total spend: `$48.21`
- May 5 charges dominated by `gpt-5.4-pro-2026-03-05` input/output plus `gpt-image-1` image charges.

The local run ledger had reported only `$0.33742`. That number was incomplete: it counted completed image receipts but did not include completed Pro response receipts for several `gpt-5.4-pro` calls. The dashboard is the source of truth for budget enforcement.

## What Happened

The run was started with a `$20` hard cap, and the operator intended that cap to mean total OpenAI dashboard/project spend. The coordinator interpreted it as local run-ledger spend.

That distinction mattered because the run ledger was receipt based. It only counted records that Cento had successfully written locally. The dashboard still counted OpenAI work that had been accepted and billed even when Cento did not receive or persist a completed response receipt.

The visible mismatch was:

- Operator dashboard total: `$48.21`
- Operator May spend: `$45.82`
- Cento local run ledger before reconciliation: `$0.33742`

The `$0.33742` report was therefore not a real cap state. It was only "locally receipted image spend so far."

## Timeline

| Time (UTC) | Event |
|---|---|
| 2026-05-05 15:25 | Walk Autopilot run `walk-autopilot-20260505T152507Z` started with live workers and live API lanes enabled. |
| 2026-05-05 16:05 to 17:15 | Multiple Hard ProReq runs wrote `gpt-5.4-pro` started records and request artifacts. |
| 2026-05-05 17:25 | Loop 7 status still showed local spend `$0.33742`, because Pro completions were not receipted locally. |
| 2026-05-05 17:38 | Operator reported dashboard spend above cap and clarified the `$20` cap was total dashboard/project spend. |
| 2026-05-05 17:38 | Coordinator was stopped, active tracked workers were checked, and a spend incident was opened. |
| 2026-05-05 17:49 | Run ledger was reconciled to the stricter selected-range dashboard total `$48.21`. |
| 2026-05-05 17:52 | Dashboard-total budget gates were validated to block live API starts before a tmux session or network call is created. |

## Why The Ledger Was Wrong

The old budget check trusted `workspace/runs/walk-autopilot/<run-id>/spend-ledger.jsonl` as the hard-cap source. That file was not complete enough for live Pro/image control.

Known Pro runs had `pro_backend_request.json` plus local spend records with `status=started`, but no matching local completion or timeout receipt with final usage/cost:

- `hard-proreq-task-hard-proreq-project-20260505T160522071163Z`
- `hard-proreq-task-hard-proreq-project-20260505T161522143806Z`
- `hard-proreq-task-hard-proreq-project-20260505T170546743595Z`
- `hard-proreq-task-hard-proreq-project-20260505T171546814172Z`

This left the local ledger below reality while the OpenAI dashboard had the actual charges.

## Impact

- The intended `$20` OpenAI dashboard/project cap was exceeded.
- The local coordinator kept operating based on an undercounted run ledger.
- Live worker progress itself was not the main cost driver; the dashboard evidence points to explicit Pro/image lanes.
- The run artifacts are still useful for traceability, but the pre-incident local ledger cannot be used as a source of truth.

## Immediate Response

- Stopped the tmux coordinator for `walk-autopilot-20260505T152507Z`.
- Confirmed no tracked active Agent Work runs remained.
- Sent an iPhone incident notification.
- Reconciled the run spend ledger to the stricter selected-range dashboard total `$48.21`.
- Added a dashboard-total budget gate before any future live API Pro/image lane can launch.

## Root Cause

The original cap enforcement used the local append-only run ledger as the hard-cap source. That was insufficient because Pro calls can incur dashboard spend even when local coordination times out or fails before writing a completed response receipt with usage.

The intended cap was total OpenAI dashboard/project spend, not run-local delta.

## New Guardrail

Any future Walk Autopilot run with `--allow-live-api` must include `--dashboard-total-spend-usd` or `CENTO_OPENAI_DASHBOARD_TOTAL_SPEND_USD`.

If the supplied dashboard total is already greater than or equal to `--hard-cap-usd`, the coordinator exits before starting. Hard ProReq Pro/image dispatch also checks `CENTO_REQUIRE_DASHBOARD_TOTAL_BUDGET=1` and blocks network calls when the dashboard total is missing or over cap.

Example blocked restart while total is over cap:

```bash
./scripts/cento.sh walk-autopilot start-tmux \
  --loops 12 \
  --cadence-seconds 1200 \
  --hard-cap-usd 20 \
  --allow-live-api \
  --dashboard-total-spend-usd 48.21
```

Expected behavior:

- Exit code `2`
- No tmux session is created
- No Pro/image network call is attempted
- Error payload explains the dashboard total and hard cap comparison

## Verification

The fix was validated with:

```bash
python3 -m pytest tests/test_walk_autopilot.py tests/test_dev_pipeline_delivery.py -q
make check
python3 -m json.tool data/tools.json
./scripts/cento.sh walk-autopilot start-tmux --allow-live-api --hard-cap-usd 20 --dashboard-total-spend-usd 48.21
```

The over-cap `start-tmux` command exited before creating a session. The focused tests cover:

- response-ID dedupe in the spend ledger
- dashboard total baseline accounting
- live API gate failure when dashboard total is missing
- live API gate failure when dashboard total exceeds the hard cap
- Hard ProReq Pro dispatch blocked before network calls
- Hard ProReq image dispatch blocked before network calls

## Operating Rule Going Forward

For any metered OpenAI API work, budget gates must use the OpenAI dashboard/project total when the operator states a total cap. Local ledgers are useful for attribution and reconciliation, but they cannot be the sole stop condition for Pro/image lanes.

Allowed without a dashboard spend snapshot:

- local validation
- no-model checks
- dry-run planning
- Codex/Claude agent lanes that do not call metered OpenAI API

Blocked without a dashboard spend snapshot:

- `walk-autopilot --allow-live-api`
- Hard ProReq `gpt-5.4-pro` dispatch
- OpenAI image generation
- `parallel-delivery self-improve` when it enables Pro/image lanes

## Incident Artifacts

- `workspace/runs/walk-autopilot/walk-autopilot-20260505T152507Z/incidents/spend-cap-dashboard-20260505T173800Z/incident.md`
- `workspace/runs/walk-autopilot/walk-autopilot-20260505T152507Z/handoff.md`
- `workspace/runs/walk-autopilot/walk-autopilot-20260505T152507Z/spend-ledger.jsonl`
