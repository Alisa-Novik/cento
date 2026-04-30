# #83 Builder Report: Agent Pool Dispatch Visibility

Date: 2026-04-30

## Summary

The original concern was valid but incomplete. Mac's local-only run view showed only two untracked local Codex sessions, which made it look like no dispatched workers existed. Linux had its own run ledger with pool activity that Mac was not listing.

I updated `scripts/agent_work.py` so Mac-side `cento agent-work runs` appends Linux's own run ledger when remote lookup is enabled. This makes the default manager view cluster-aware instead of Mac-ledger-only.

## Evidence

Before/without remote lookup:

```text
cento agent-work runs --json --active --no-remote-reconcile
count: 2
statuses: untracked_interactive=2
nodes: macos=2
```

After remote-aware listing:

```text
cento agent-work runs --json --active
count: 14
statuses: running=1, stale=9, untracked_interactive=4
nodes: linux/Linux=12, macos=2
```

Linux pool-kick state also exists:

```text
~/.local/state/cento/agent-pool-kick-latest.json
active_counts: builder=1, validator=0, small=0, coordinator=0
targets: builder=4, validator=3, small=3, coordinator=1
launched: []
```

## Findings

- Mac main has `dispatch-pool`; Linux checkout does not because it is behind and dirty.
- Linux has new local pool tooling (`scripts/agent_pool_kick.py`, `scripts/agent_work_hygiene.sh`) not yet reconciled into Mac main.
- Some workers did launch from Linux, but several became stale quickly.
- Board state has been churned heavily into `Review` and `Blocked`; there are currently few or no clean queued candidates for Mac's `dispatch-pool`.
- The manager view was misleading because it did not aggregate Linux-local ledgers.

## Changed Files

- `scripts/agent_work.py`: append Linux run records to Mac-side run listings when remote lookup is enabled.
- `docs/agent-run-ledger.md`: document cluster-aware vs local-only run views.

## Recommended Next Work

1. Reconcile Linux pool tooling into Mac main without overwriting Linux dirty work.
2. Normalize node casing (`Linux` vs `linux`) so run grouping and filters are reliable.
3. Add a pool health command that reports why it launched zero workers.
4. Add a stale-worker recovery policy that unblocks or requeues safely instead of leaving a blocked board.
