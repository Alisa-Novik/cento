# Patch Swarm Validation Matrix

This matrix defines the future runtime validation contract and the current Call 1 docs validation checks.

| Area | Scenario | Command / Check | Expected Result | Evidence |
| --- | --- | --- | --- | --- |
| Intake | Request file exists | `cento parallel-delivery init --request-file REQUEST.md` | Run directory created | `run.json` |
| Intake | Missing request file rejected | `cento parallel-delivery init --request-file missing.md` | Fails with no run mutation | `evidence/commands.log` or failure receipt |
| Intake | ProReq packet generated | Inspect `request/proreq.json` | Goal, acceptance, risks, budget, paths, and validation fields exist | `request/proreq.json` |
| Planning | Max 100 tasks | `cento parallel-delivery plan --run RUN_ID --max-tasks 100` | `decomposition.json` has `<= 100` tasks | `plan/decomposition.json` |
| Planning | Over-100 rejected | `cento parallel-delivery plan --run RUN_ID --max-tasks 101` | Fails closed or clamps only with explicit evidence | planner failure receipt |
| Planning | Task acceptance contract required | JSON check on task records | Every task has acceptance criteria | `plan/decomposition.json` |
| Planning | Dependency graph valid | Graph check | No dependency cycles | `plan/task_graph.json` |
| Leasing | Overlapping paths rejected | future fixture with two tasks writing same file | Conflicting leases fail | `leases/path_leases.json` |
| Leasing | Glob write paths rejected | future fixture with `docs/*.md` write path | Workset check fails | Workset check receipt |
| Leasing | Absolute paths rejected | future fixture with `/tmp/outside` write path | Workset check fails | Workset check receipt |
| Leasing | Shared edit serialized | future fixture with shared file pressure | Planner creates serialized integrator task or fails with reason | `plan/risks.json` |
| Prompts | Prompt includes lease | grep prompt for owned/read-only paths | Worker cannot miss path boundary | `prompts/task-0001.md` |
| Prompts | Prompt includes acceptance | grep prompt for acceptance contract | Task cannot dispatch without acceptance | prompt emission receipt |
| Collection | Bundle schema valid | JSON schema check | Patch bundle has task, base, paths, diff, evidence | `workers/task-0001/patch.bundle.json` |
| Collection | Diff exists | `test -f workers/task-0001/patch.diff` | Diff artifact present | `patch.diff` |
| Validation | Changed paths inside lease | diff path check | Patch passes only if all changed paths are leased | `validation/task-0001.validation.json` |
| Validation | Unsafe path rejected | fixture changes outside leased paths | Task becomes `rejected` with reason | rejection receipt |
| Validation | Secret leak rejected | fixture copies `.env.mcp` or API-key-like value | Task rejected and secret not copied into evidence | validation failure receipt |
| Validation | Direct DB writes rejected | fixture attempts Taskstream/Redmine/story DB mutation | Task rejected | validation failure receipt |
| Validation | Required tests evidenced | compare `validation_commands` and `tests_run` | Claimed tests have command output or are marked not run | validation matrix |
| Validation | Dirty work protected | fixture would overwrite unrelated dirty work | Integration blocked before apply | validation failure receipt |
| Integration | Queue recorded | `cento parallel-delivery integrate --run RUN_ID --strategy sequential` | `integration/queue.json` records order | `integration/queue.json` |
| Integration | Dependency order honored | dependency-order fixture | Dependents integrate after prerequisites | queue and integrated patch ledger |
| Integration | No unsafe git operations | inspect apply plan/commands | No required `git reset`, `git checkout`, `git clean`, or `git stash` | integration receipt |
| Integration | Failed task does not fail run when safe patch remains | mixed safe/unsafe fixture | Unsafe rejected, safe integrated | integrated/rejected ledgers |
| Integration | No safe patch fails run | all unsafe fixture | Run reaches `failed` with evidence | `evidence/summary.md` |
| Release candidate | RC written | `cento parallel-delivery rc --run RUN_ID` | `release-candidate.json`, build and validation logs exist | `rc/release-candidate.json` |
| Release candidate | RC requires integration or no-op | run with no integration evidence | RC command fails unless no-op is explicit | RC failure receipt |
| Evidence | Summary written | `cento parallel-delivery evidence --run RUN_ID` | `evidence/summary.md` exists | `evidence/summary.md` |
| Evidence | Artifact index complete | JSON check | Required artifacts are present or marked absent with reason | `evidence/artifacts.json` |
| Evidence | Secrets excluded | grep evidence for blocked secret paths/tokens | No `.env.mcp`, API keys, or local secret values | evidence scan receipt |
| Console | Status payload complete | `cento parallel-delivery status --run RUN_ID --json` | Summary includes run ID, state, counts, leases, validation, queue, RC, evidence path, next action | status receipt |
| Taskstream | Uses safe surfaces | inspect sync/agent-work command path | Status is published through MCP or `cento agent-work`, not direct DB writes | Taskstream sync preview |
| Demo | Bounded e2e | `cento parallel-delivery demo --request-file examples/parallel-delivery/simple-request.md --max-tasks 3` | Proves intake, planning, leases, prompts, collection, validation, rejection, integration, RC, evidence, status | demo evidence summary |
| Existing runtime | Current Patch Swarm fixture e2e | `cento parallel-delivery patch-swarm e2e --candidate-target 30 --max-parallel-agents 3 --fixture --json` | Current implementation proves candidate generation and Safe Integrator handoff without main-worktree mutation | current Patch Swarm run evidence |
| Existing runtime | Current Factory validation fanout | `cento factory validate-fanout RUN_ID --max-parallel 32 --json` | Candidate checks run in parallel before serialized Safe Integrator apply | Factory validation receipt |
| Existing runtime | Current Workset checker | `cento workset check WORKSET` | Overlap, glob, absolute, and missing write path issues are rejected | Workset check receipt |
| Current Call 1 | docs exist | `test -f docs/patch-swarm.md && test -f docs/patch-swarm-lifecycle.md && test -f docs/patch-swarm-implementation-map.md && test -f docs/patch-swarm-validation-matrix.md` | Canonical spec and support docs exist | `workspace/runs/patch-swarm-call-1-product-architecture/validation.log` |
| Current Call 1 | required headings exist | `rg -n "Product Definition|Operator Story|User-Facing CLI Contract|Artifact Lifecycle|Run State Machine|Worker / Task State Machine|What .100 Agents. Means Safely|Unsafe Inputs and Rejection Rules|E2E Demo Definition of Done" docs/patch-swarm.md` | All required headings found | validation log |
| Current Call 1 | lifecycle diagram exists | `rg -n "flowchart TD|request_received|run_completed|run_failed|run_aborted" docs/patch-swarm-lifecycle.md` | Diagram and terminal states found | validation log |
| Current Call 1 | unsafe rejection rules exist | `rg -n "change files outside their leased paths|copy .env.mcp|direct database writes|overwrite unrelated dirty work|git reset|delete durable evidence" docs/patch-swarm.md` | Unsafe rules found | validation log |
| Current Call 1 | implementation map exists | `rg -n "Milestone 0: Canonical Spec and Docs|Milestone 11: E2E Demo Harness" docs/patch-swarm-implementation-map.md` | Future slices are documented | validation log |
| Current Call 1 | evidence files exist | `test -f workspace/runs/patch-swarm-call-1-product-architecture/discovery.log` and related checks | Discovery, docs list, summary, and validation logs exist | run evidence directory |
