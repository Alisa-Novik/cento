# Agent Work Coordinator Lane

The Coordinator lane owns intake triage, story splitting, lane routing, acceptance contract hygiene, shared evidence decisions, replacement state changes, and early escalation when a story needs human/device access.

The lane does not implement product code or validate final evidence. It keeps the work queue coherent and makes the next action explicit.

## Coordinator Contract

Use the Coordinator lane to make the work graph smaller and clearer before a Builder starts.

Split a story when any of the following differ:

- route coverage or page surface
- API coverage or request shape
- screenshot outputs, viewport sizes, or device targets
- human/device/environment access requirements
- review-note or evidence requirements

Combine related work only when the stories can share the same acceptance contract, validation commands, evidence files, review gate, and durable outputs. If the evidence is shared but the story boundaries are still fuzzy, keep the stories separate and point them at the same artifact set instead of forcing a merge.

Every split task must declare owned files, modules, or responsibility boundaries. Use `cento agent-work create --owns PATH_OR_SCOPE` or `cento agent-work split --owns PATH_OR_SCOPE` so builder and validator prompts show the ownership boundary. Do not dispatch two builders with overlapping owned paths unless one is explicitly a read-only validator or docs/evidence worker.

Every created task must start from a generated story manifest. For `cento agent-work create`, interpret the request first, write a draft `story.json` with `issue.id: 0`, then pass it with `--manifest`. Taskstream creation without a manifest is intentionally blocked.

Assign lanes by responsibility:

- Builder: smallest coherent implementation slice, changed files, and implementation notes.
- Validator: independent checks, screenshots, review evidence, and pass/fail judgment.
- Docs/Evidence: `story.json`, `deliverables.json`, `start-here.html`, validation logs, screenshot indexes, and review-note wording.
- Coordinator: triage, split/combine decisions, routing, blocker escalation, and replacement status hygiene.

Keep replacement statuses accurate:

- `Queued` before claim.
- `Running` only while the active owner is actually working.
- `Blocked` as soon as a missing dependency is known.
- `Validating` when the implementation is ready for the next owner or the coordinator has finished triage and written the handoff.
- `Review` only after a Validator pass.
- `Done` only after review close-out.

If a status note does not change ownership, blockers, or the next owner, do not send another status update.

## Operating Commands

Use these commands as the default coordinator toolkit:

```bash
cento agent-work claim ISSUE_ID --node "$(uname -s)" --agent "$USER" --role coordinator
cento agent-work show ISSUE_ID
cento agent-work list --json
cento agent-work runs --json --active
cento agent-work run-status RUN_ID --json
cento agent-work review-drain --package <package> --dry-run
python3 scripts/story_manifest.py validate workspace/runs/agent-work/<issue-id>/story.json --check-links
python3 scripts/story_manifest.py render-hub workspace/runs/agent-work/<issue-id>/story.json --check-links
cento agent-work update ISSUE_ID --status running --role coordinator --note "..."
cento agent-work update ISSUE_ID --status blocked --role coordinator --note "blocked because ..."
cento agent-work update ISSUE_ID --status validating --role coordinator --note "..."
cento notify status
cento notify iphone "ISSUE_ID moved to Review"
cento notify all "ISSUE_ID blocked: ..."
```

## Pool Kick Diagnostics

The automatic pool launcher writes the latest machine-readable summary to `~/.local/state/cento/agent-pool-kick-latest.json`. The coordinator run bundle mirrors the same payload under `workspace/runs/agent-work/<run-id>/actions.json`.

When the pool starts zero workers, read these fields first:

- `reason_summary.primary_reason`
- `reason_summary.summary`
- `reason_summary.next_action`
- `reason_summary.lanes[]`
- `reason_summary.validation_modes`
- `reason_summary.dispatch_failures[]`

Typical next actions:

- `active_target_already_met`: wait for active workers to finish or raise the target.
- `no_candidates`: queue or split a matching issue for the lane.
- `all_candidates_blocked_review`: unblock or finish the blocked or Review issues.
- `version_skew`: requeue the stale-model work or align the runtime/model mapping.
- `validation_failed`: inspect the local no-model validation report, fix the missing evidence or failing checks, and rerun the pool.
- `runtime_missing`: fix the runtime registry or missing binary on the launch node.
- `dispatch_failures`: inspect the dispatch failure records and fix the underlying error.

Validator routing now follows a three-way planning table:

- `no-model`: a story manifest exists, `validation.no_model_eligible` is true, `validation.risk` is not high, and the manifest is explicit enough to run `validate-run` locally.
- `cheap-model`: a manifest exists and the story still needs validator judgment, but the story is not high risk and does not require a stronger escalation.
- `strong-model`: the manifest is missing, the risk is high, the story is ambiguous, `validation.mode` is manual-planning, or the work needs human/device judgment.

The dry-run lane diagnostics surface the planned mode as `reason_summary.lanes[].planned_validation_mode` and the mode histogram as `reason_summary.validation_modes`. When the no-model path is chosen, the pool runs the existing `cento agent-work validate-run` command locally instead of starting an AI validator session.

## Story Intake Checklist

1. Claim the issue as coordinator and record the current node and agent owner.
2. Read the replacement issue and any `story.json` or deliverables manifest attached to the run directory.
3. Check the live board and running ledger together. The board can show queued work that is not actually running, and the run ledger can show active work that has not yet been recorded on the board.
4. Record a short running note that names the intake decision, the package, and any immediate blocker.
5. If the issue is part of a package with multiple stories, compare the sibling stories before dispatching anything new and decide whether to split, combine, or leave them separate.

## Acceptance Contract Checklist

Before dispatching or combining work, verify that the story contract is explicit:

- `scope.acceptance` is non-empty and uses outcome language, not vague status language.
- `expected_outputs` lists the durable artifacts the reviewer should open.
- `validation.commands` names the checks that should run before handoff.
- `validation.required_evidence` matches the commands and the artifact paths.
- `handoff.human_steps` exists when a human must touch a device, simulator, account, or LAN-only environment.
- `review_gate.required_sections` includes `Delivered`, `Validation`, `Evidence`, and `Residual risk` when strict review notes are required.

## Deterministic-First Validation Checklist

Before dispatching validator work, verify that the story can be proven without a model judge:

- `validation.commands` is a deterministic command list, not a prompt to infer intent.
- `validation.required_evidence` points at durable local artifacts the validator can open later.
- Any subjective requirement is split, blocked, or routed to human/device handoff instead of being hidden inside validation.
- `review_gate.required_sections` stays on the standard four-section review-note shape.
- If the rollout genuinely needs a new CLI command, register it in `data/tools.json` and regenerate `docs/tool-index.md` and `docs/platform-support.md`.

If the acceptance contract is missing or incomplete, stop and either:

- mark the issue `blocked`, or
- split it into a narrower story with a tighter contract.

## Shared Evidence Detection

Combine stories only when they truly share evidence. Treat the following as the decision inputs:

- `routes`
- `api_endpoints`
- `screenshots[].output`
- `validation.required_evidence`
- `validation.commands`
- `expected_outputs`
- `review_gate`

Stories should usually stay separate when any of these differ:

- route coverage
- API coverage
- screenshot outputs or viewports
- device access requirements
- final review-note requirements

Stories can be combined when they reuse the same evidence files, the same validation commands, and the same review gate. If the evidence is shared but the story boundaries are still unclear, keep the stories separate and point them at the same durable artifact set.

Before closing a package with shared review evidence, dry-run:

```bash
cento agent-work review-drain --package <package> --dry-run
```

When the board is stalled with no queued work, start with:

```bash
cento agent-work recovery-plan
```

Use the report to decide whether the next safe move is:

- requeue stale blocked work that has no live run,
- drain review-ready items,
- or create at most one or two small follow-up tasks for internal Cento gaps or explicit split-needed blockers.

Do not create follow-up work for human, device, credential, or LAN blockers. If the recovery plan cannot point to a bounded internal gap, leave the blocked issue in place and record the blocker instead of spawning new tasks.

## State-Change Notifications

Notify only on state changes that matter:

- claim/start
- blocked
- validating / ready for validation
- review
- done
- human input needed

Keep the message short and factual. Include the issue id, the new state, the blocking dependency if there is one, and the next owner when it changes.

Recommended pattern:

```bash
cento agent-work update ISSUE_ID --status running --role coordinator --note "..."
cento notify iphone "ISSUE_ID now running"
```

Use `cento notify all` only for broad blockers or when more than one person needs the same update.

Do not send progress pings for every minor edit or inspection step.

## Human Handoff Escalation

Escalate immediately when a story needs something the current node cannot provide:

- physical device access
- simulator or emulator access
- LAN-only service access
- credentials or secrets the agent cannot mint
- a missing build machine, browser, or test host

Escalation checklist:

1. Mark the issue `blocked`.
2. State the exact missing dependency in the board note.
3. Include the human action needed to unblock the story.
4. Name the evidence path or device artifact that must be provided.
5. Send a short notification when a configured target exists.

For mobile and device-heavy stories, write the human handoff details into `story.json` so the next coordinator does not have to reconstruct them from chat history.

## Coordinator Exit Criteria

The coordinator job is complete when:

- the story contract is explicit,
- the queue decision is recorded,
- any follow-up dispatch recommendation is written down,
- blocker states are reflected on the board,
- and the next owner is obvious.

At that point, leave a concise report and move the issue to `validating` with the coordinator role.
