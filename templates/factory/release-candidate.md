# Factory Integration Release Candidate

- Run: `{{ run_id }}`
- Branch: `{{ branch }}`
- Worktree: `{{ worktree }}`
- Merge readiness: `{{ merge_readiness }}`
- Applied patches: `{{ applied_count }}`
- Rejected patches: `{{ rejected_count }}`
- AI calls used: `0`

## Applied Patches

{{ applied_patches }}

## Rejected Patches

{{ rejected_patches }}

## Human Merge Checklist

- Review applied patch bundle summaries.
- Inspect `rollback-plan.json`.
- Run any manual checks required by the module owner.
- Merge the integration branch only after human approval.
