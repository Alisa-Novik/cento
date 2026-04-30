# #93 Builder Report: Pool Zero-Launch Diagnostics

Date: 2026-04-30

## Summary

Added diagnostics to `cento agent-work dispatch-pool --json` so a zero-launch result explains why no workers were planned.

## Delivered

- `dispatch-pool` JSON now includes a `diagnostics` object.
- Diagnostics include open issue count, requested status, status matches, eligible count before limit, applied filters, skipped counts, and `zero_launch_reason`.
- Fixed `--limit 0` handling so it produces zero candidates and reports `limit_zero`.
- Normalized node filtering for `Linux` vs `linux`.

## Evidence

Current plan:

```bash
cento agent-work dispatch-pool --limit 5 --json
```

Evidence:

```text
workspace/runs/agent-work/93/dispatch-pool-current.json
```

Filtered-out plan:

```bash
cento agent-work dispatch-pool --status queued --package no-such-package --limit 5 --json
```

Evidence:

```text
workspace/runs/agent-work/93/dispatch-pool-filtered.json
```

Limit-zero plan:

```bash
cento agent-work dispatch-pool --limit 0 --json
```

Evidence:

```text
workspace/runs/agent-work/93/dispatch-pool-limit-zero.json
```

## Validation

```bash
python3 -m py_compile scripts/agent_work.py
python3 -m json.tool workspace/runs/agent-work/93/dispatch-pool-current.json
python3 -m json.tool workspace/runs/agent-work/93/dispatch-pool-filtered.json
python3 -m json.tool workspace/runs/agent-work/93/dispatch-pool-limit-zero.json
```

## Residual Risk

This improves Mac main's `dispatch-pool`; Linux still has dirty, behind local pool tooling that needs reconciliation under #94.
