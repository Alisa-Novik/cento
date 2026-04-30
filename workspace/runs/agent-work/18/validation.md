# Validation

Generated: 2026-04-29T19:26:23-04:00

## Planned Checks

- Python syntax compile for `server.py`.
- Health endpoint without token.
- Authenticated dashboard, jobs, issues, and agents endpoints.
- Browser render on mobile viewport.
- Screenshot saved under `screenshots/`.
- Redmine #18 updated to Review with evidence.

## Results

### Syntax

```bash
python3 -m py_compile workspace/runs/agent-work/18/server.py
```

Result: passed.

### API

```bash
curl http://127.0.0.1:47918/api/mobile/health
curl -H "X-Cento-Mobile-Token: <token>" http://127.0.0.1:47918/api/mobile/dashboard
curl -H "X-Cento-Mobile-Token: <token>" http://127.0.0.1:47918/api/mobile/issues
curl -H "X-Cento-Mobile-Token: <token>" http://127.0.0.1:47918/api/mobile/jobs
curl -H "X-Cento-Mobile-Token: <token>" http://127.0.0.1:47918/api/mobile/agents
curl -H "X-Cento-Mobile-Token: <token>" -H "Content-Type: application/json" -d "{}" http://127.0.0.1:47918/api/mobile/actions/cluster.status
```

Results:

- Health endpoint returns `ok: true`.
- Unauthenticated dashboard returns HTTP 401 with `token_required`.
- Authenticated dashboard returns health metrics, Redmine queue, jobs, agents, activity, and quick actions.
- Issues endpoint returns Redmine agent-work items.
- Jobs endpoint returns trimmed job summaries.
- Agents endpoint returns linux/macos/iphone state.
- `cluster.status` allowlisted action returns cluster status output.

### Visual

Screenshots captured with Playwright Chromium:

```bash
npx --yes playwright screenshot --browser=chromium --viewport-size=390,844 --wait-for-timeout=6000 "http://127.0.0.1:47918/?token=<token>" workspace/runs/agent-work/18/screenshots/mobile-dashboard.png
npx --yes playwright screenshot --browser=chromium --viewport-size=390,844 --wait-for-timeout=6000 "http://127.0.0.1:47918/?token=<token>&view=jobs" workspace/runs/agent-work/18/screenshots/mobile-jobs.png
npx --yes playwright screenshot --browser=chromium --viewport-size=390,844 --wait-for-timeout=6000 "http://127.0.0.1:47918/?token=<token>&view=agents" workspace/runs/agent-work/18/screenshots/mobile-agents.png
npx --yes playwright screenshot --browser=chromium --viewport-size=390,844 --wait-for-timeout=6000 "http://127.0.0.1:47918/?token=<token>&view=actions" workspace/runs/agent-work/18/screenshots/mobile-actions.png
```

Screenshot files:

- `screenshots/mobile-dashboard.png`
- `screenshots/mobile-jobs.png`
- `screenshots/mobile-agents.png`
- `screenshots/mobile-actions.png`
- `screenshots/desktop-dashboard.png`

Inspection:

- Dashboard shows real metrics and Redmine queue.
- Jobs view shows trimmed job cards and status pills.
- Agents view shows linux and macos online, iphone offline.
- Actions view shows only allowlisted live actions plus disabled future actions.
- Fixed one visual issue found during validation: action button labels were wrapping into the icon column.

## Current Local Server

Running locally at:

```text
http://127.0.0.1:47918/
```

For iPhone LAN use, run:

```bash
python3 workspace/runs/agent-work/18/server.py --host 0.0.0.0 --port 47918
```

Then open the printed LAN URL and paste the printed gateway token.

## Issue Detail Workflow (#19)

Generated: 2026-04-29T19:54:00-04:00

### Delivered

- Dashboard queue and Issues list cards are tappable via `data-issue-id`.
- The PWA opens a real issue detail panel using `GET /api/mobile/issues/{id}`.
- Detail panel shows issue id, subject, status, tracker, project, node, agent, package, updated timestamp, description, and detail/activity/relations tabs.
- Activity is explicitly labeled as pending Redmine journal support instead of fake journal history.

### Validation

```bash
curl -H "X-Cento-Mobile-Token: <token>" http://127.0.0.1:47918/api/mobile/issues/18 | python3 -m json.tool
npx --yes playwright screenshot --browser=chromium --viewport-size=390,844 --wait-for-timeout=6000 "http://127.0.0.1:47918/?token=<token>&view=issues&issue=18" workspace/runs/agent-work/18/screenshots/mobile-issue-detail.png
```

Result:

- API returned live Redmine issue #18 detail.
- Screenshot inspected and shows issue detail above the list on mobile.
- Fixed one mobile usability issue: detail panel originally appeared below the full issue list.

Screenshot:

- `workspace/runs/agent-work/18/screenshots/mobile-issue-detail.png`

## Business-Approval Retest For #19

Generated: 2026-04-29T19:59:00-04:00

### Route

- LAN URL tested: `http://10.0.0.56:47918/`
- Method: iPhone-sized Chromium browser automation from Linux.
- Limitation: physical tapping on the user's iPhone was not possible from this environment.

### Checks

```bash
curl -H "X-Cento-Mobile-Token: <token>" http://10.0.0.56:47918/api/mobile/health
curl -H "X-Cento-Mobile-Token: <token>" http://10.0.0.56:47918/api/mobile/issues/18
npx --yes playwright screenshot --browser=chromium --viewport-size=390,844 --wait-for-timeout=6000 "http://10.0.0.56:47918/?token=<token>&view=issues&issue=18" workspace/runs/agent-work/18/screenshots/mobile-issue-detail.png
npx --yes playwright screenshot --browser=chromium --viewport-size=390,844 --wait-for-timeout=6000 "http://10.0.0.56:47918/?token=<token>&view=issues&issue=18&detailTab=activity" workspace/runs/agent-work/18/screenshots/mobile-issue-activity.png
```

### Results

- LAN gateway health returned `ok: true`.
- Live issue endpoint returned issue #18 fields: id, subject, project, tracker, status, node, agent.
- Detail screenshot shows issue detail panel near the top.
- Activity screenshot shows the explicit pending-journal message.

Screenshots:

- `screenshots/mobile-issue-detail.png`
- `screenshots/mobile-issue-activity.png`

## Install Polish And Docs (#20)

Generated: 2026-04-29T20:02:00-04:00

### Delivered

- Added `docs/install.html` as the iPhone PWA install checklist.
- Linked install checklist from `docs/index.html`.
- Updated `README.md` to point to the install checklist.
- Included LAN URL, token file, gateway start command, Add to Home Screen steps, smoke test, and screenshot evidence.

### Validation

```bash
npx --yes playwright screenshot --browser=chromium --viewport-size=1280,1200 --wait-for-timeout=1000 "file:///home/alice/projects/cento/workspace/runs/agent-work/18/docs/install.html" workspace/runs/agent-work/18/screenshots/install-docs.png
npx --yes playwright screenshot --browser=chromium --viewport-size=390,844 --wait-for-timeout=1000 "file:///home/alice/projects/cento/workspace/runs/agent-work/18/docs/install.html" workspace/runs/agent-work/18/screenshots/mobile-install-docs.png
```

Result:

- Desktop install docs render cleanly.
- Mobile install docs are readable; long commands wrap instead of overlapping.

Screenshots:

- `screenshots/install-docs.png`
- `screenshots/mobile-install-docs.png`

## Job Logs And Artifacts Workflow (#21)

Generated: 2026-04-29T20:36:00-04:00

### Delivered

- Added live job detail endpoint: `GET /api/mobile/jobs/{id}`.
- Added live job log endpoint: `GET /api/mobile/jobs/{id}/logs`.
- Added live artifact endpoint: `GET /api/mobile/jobs/{id}/artifacts`.
- Added mobile job detail panel with Steps, Logs, and Artifacts tabs.
- Kept detail panel above the job list on iPhone-sized screens.

### Validation

```bash
node -c workspace/runs/agent-work/18/public/app.js
python3 -m py_compile workspace/runs/agent-work/18/server.py
curl -H "X-Cento-Mobile-Token: <token>" http://127.0.0.1:47918/api/mobile/jobs/<job-id> | python3 -m json.tool
curl -H "X-Cento-Mobile-Token: <token>" http://127.0.0.1:47918/api/mobile/jobs/<job-id>/logs | python3 -m json.tool
curl -H "X-Cento-Mobile-Token: <token>" http://127.0.0.1:47918/api/mobile/jobs/<job-id>/artifacts | python3 -m json.tool
npx --yes playwright screenshot --browser=chromium --viewport-size=390,844 --wait-for-timeout=6000 "http://10.0.0.56:47918/?token=<token>&view=jobs&job=<job-id>" workspace/runs/agent-work/18/screenshots/mobile-job-detail.png
npx --yes playwright screenshot --browser=chromium --viewport-size=390,844 --wait-for-timeout=6000 "http://10.0.0.56:47918/?token=<token>&view=jobs&job=<job-id>&jobTab=logs" workspace/runs/agent-work/18/screenshots/mobile-job-logs.png
npx --yes playwright screenshot --browser=chromium --viewport-size=390,844 --wait-for-timeout=6000 "http://10.0.0.56:47918/?token=<token>&view=jobs&job=<job-id>&jobTab=artifacts" workspace/runs/agent-work/18/screenshots/mobile-job-artifacts.png
```

Result:

- API returned job metadata, task records, log tails, summary artifact, manifest artifact, task logs, task scripts, and task manifests.
- Mobile detail screenshot shows the selected job detail near the top of the Jobs screen.
- Mobile logs screenshot shows multiline task log output under the Logs tab.
- Mobile artifacts screenshot shows artifact names, kind, size, and availability under the Artifacts tab.

Screenshots:

- `screenshots/mobile-job-detail.png`
- `screenshots/mobile-job-logs.png`
- `screenshots/mobile-job-artifacts.png`

## Generated Deliverables Hub Standard (#25)

Generated: 2026-04-29T20:54:00-04:00

### Delivered

- Added `scripts/deliverables_hub.py` to generate a stable `start-here.html` from `deliverables.json`.
- Added link validation for local deliverable links before review.
- Added `docs/agent-work-deliverables-hub.md` with the required workflow and review gate.
- Added `workspace/runs/agent-work/18/deliverables.json` as the first real manifest.
- Regenerated `workspace/runs/agent-work/18/start-here.html` from the manifest.

### Validation

```bash
python3 -m py_compile scripts/deliverables_hub.py
python3 scripts/deliverables_hub.py workspace/runs/agent-work/18/deliverables.json --check-links
python3 scripts/deliverables_hub.py workspace/runs/agent-work/18/deliverables.json --check-links --check-only
npx --yes playwright screenshot --browser=chromium --viewport-size=1280,1200 --wait-for-timeout=1000 "file:///home/alice/projects/cento/workspace/runs/agent-work/18/start-here.html" workspace/runs/agent-work/18/screenshots/start-here.png
npx --yes playwright screenshot --browser=chromium --viewport-size=390,844 --wait-for-timeout=1000 "file:///home/alice/projects/cento/workspace/runs/agent-work/18/start-here.html" workspace/runs/agent-work/18/screenshots/mobile-start-here.png
```

Result:

- Generator syntax check passed.
- Hub was regenerated from `deliverables.json`.
- Local link validation passed.
- Desktop and mobile screenshots were inspected; content is readable and links are discoverable without chat context.

Screenshots:

- `screenshots/start-here.png`
- `screenshots/mobile-start-here.png`

## Validation Manifest And Validator Runner (#28)

Generated: 2026-04-29T21:41:00-04:00

### Delivered

- Added `agent_work.py handoff` for Builder handoff reports and automatic move to `Validating`.
- Added `agent_work.py validate-run` to execute `validation.json` checks, capture screenshots, write reports, and call the validator gate.
- Added `workspace/runs/agent-work/28/validation.json` as the first real validation manifest.
- Added `workspace/runs/agent-work/28/builder-report.md` from the Builder handoff command.
- Added `workspace/runs/agent-work/28/validation-report.md` and `.json` from the Validator runner.
- Added required UI screenshot support through manifest `screenshot` checks.
- Added optional validator identity restrictions through `CENTO_VALIDATOR_AGENTS` and `requires.validator_agents`.
- Documented `validation.json`, `handoff`, and `validate-run` in `docs/agent-work-validator-lane.md`.

### Validation

```bash
python3 scripts/agent_work.py handoff 28 --run-dir workspace/runs/agent-work/28 --manifest workspace/runs/agent-work/28/validation.json ...
python3 scripts/agent_work.py validate-run 28 --manifest workspace/runs/agent-work/28/validation.json --agent alice-validator --node linux
python3 scripts/agent_work.py validate-run 28 --manifest workspace/runs/agent-work/28/validation.json --agent not-authorized --node linux --no-update
CENTO_VALIDATOR_AGENTS=alice-validator python3 scripts/agent_work.py validate 28 --result pass --agent not-authorized --node linux --note "authorization test"
```

Result:

- Builder handoff wrote `builder-report.md` and moved #28 to `Validating`.
- First Validator run failed because help-text checks were too brittle; this correctly blocked #28.
- Builder fixed the issue and handed off again.
- Second Validator run passed all checks and moved #28 to `Review`.
- Manifest checks covered syntax, command help, deliverables hub link validation, required files, desktop screenshot, and mobile screenshot.
- Unauthorized manifest and direct Validator attempts failed before updating Redmine.
- Desktop and mobile screenshots were inspected; #28 is visible in the generated hub.

Evidence:

- `workspace/runs/agent-work/28/validation.json`
- `workspace/runs/agent-work/28/builder-report.md`
- `workspace/runs/agent-work/28/validation-report.md`
- `workspace/runs/agent-work/28/validation-report.json`
- `workspace/runs/agent-work/28/screenshots/start-here.png`
- `workspace/runs/agent-work/28/screenshots/mobile-start-here.png`

## Claude Code Weighted Runtime Registration (#29)

Generated: 2026-04-29T22:10:00-04:00

### Delivered

- Registered `claude-code` in `data/agent-runtimes.json`.
- Set Claude Code model to `claude-sonnet-4-6`.
- Set Codex weight to `75` and Claude Code weight to `25`.
- Added deterministic weighted runtime selection to `agent_work.py dispatch`.
- Added `agent_work.py runtimes` for route visibility and sample distribution.
- Added forced runtime dispatch via `--runtime codex` or `--runtime claude-code`.
- Added Claude Code dispatch runner branch using `claude --print --model claude-sonnet-4-6`.
- Added `docs/agent-work-runtimes.md`.
- Added `workspace/runs/agent-work/29/validation.json`.

### Concrete Validation Results

```text
python3 scripts/agent_work.py runtimes --sample 1000 --json
codex: 740 / 1000 = 74.0%
claude-code: 260 / 1000 = 26.0%
```

```text
python3 scripts/agent_work.py dispatch 29 --runtime claude-code --dry-run
runtime=claude-code node=linux model=claude-sonnet-4-6 session=cento-agent-29-221018 local_prompt=/home/alice/projects/cento/workspace/runs/agent-work/issue-29-20260429-221018-0eb9f8/prompt.md
```

```text
command -v claude
/home/alice/.npm-global/bin/claude

claude --version
2.1.123 (Claude Code)

claude --print --model claude-sonnet-4-6 'Reply exactly: ok'
ok
```

### Validator Run

```text
python3 scripts/agent_work.py validate-run 29 --manifest workspace/runs/agent-work/29/validation.json --agent alice-validator --node linux
validate-run #29: PASS report=workspace/runs/agent-work/29/validation-report.md
PASS Builder report exists: exists
PASS agent_work syntax: exit 0
PASS runtime registry JSON parses: exit 0
PASS runtime sample keeps Claude around 25 percent: exit 0
PASS forced Claude dispatch dry-run: exit 0
PASS Claude Code binary exists: exit 0
PASS Claude Code Sonnet 4.6 smoke: exit 0
PASS runtime documentation exists: exists
PASS runtime registry exists: exists
PASS deliverables hub link validation: exit 0
PASS desktop deliverables hub screenshot: exit 0
PASS mobile deliverables hub screenshot: exit 0
```

Evidence:

- `data/agent-runtimes.json`
- `docs/agent-work-runtimes.md`
- `workspace/runs/agent-work/29/validation.json`
- `workspace/runs/agent-work/29/builder-report.md`
- `workspace/runs/agent-work/29/validation-report.md`
- `workspace/runs/agent-work/29/validation-report.json`
- `workspace/runs/agent-work/29/screenshots/start-here.png`
- `workspace/runs/agent-work/29/screenshots/mobile-start-here.png`

## Separate Validator Agent Review Gate (#27)

Generated: 2026-04-29T21:09:00-04:00

### Delivered

- Added `Validating` status to agent-work Redmine bootstrap.
- Added `Agent Role` and `Validation Report` custom fields.
- Added Builder, Validator, and Coordinator roles to `scripts/agent_work.py`.
- Added `agent_work.py validate` command for Validator pass/fail results.
- Changed generated Builder prompts so Builders move work to `Validating`, not `Review`.
- Changed generated Validator prompts so Validators own evidence checks and move passing work to `Review`.
- Added `docs/agent-work-validator-lane.md`.
- Updated deliverables hub manifest with the Validator Lane doc and #27 status.

### Validation

```bash
python3 -m py_compile scripts/agent_work.py scripts/deliverables_hub.py
python3 scripts/agent_work.py bootstrap
python3 scripts/agent_work.py --help
python3 scripts/agent_work.py validate --help
python3 scripts/agent_work.py update 27 --status validating --role builder --note "Builder implementation complete; ready for validator gate test."
python3 scripts/agent_work.py update 27 --status review --role builder --note "This should be blocked by the validator gate."
python3 scripts/agent_work.py prompt 27 --role builder
python3 scripts/agent_work.py prompt 27 --role validator
python3 scripts/deliverables_hub.py workspace/runs/agent-work/18/deliverables.json --check-links
npx --yes playwright screenshot --browser=chromium --viewport-size=1280,1200 --wait-for-timeout=1000 "file:///home/alice/projects/cento/workspace/runs/agent-work/18/start-here.html" workspace/runs/agent-work/18/screenshots/start-here.png
npx --yes playwright screenshot --browser=chromium --viewport-size=390,844 --wait-for-timeout=1000 "file:///home/alice/projects/cento/workspace/runs/agent-work/18/start-here.html" workspace/runs/agent-work/18/screenshots/mobile-start-here.png
```

Result:

- Bootstrap created/found `Validating`, `Agent Role`, and `Validation Report`.
- Builder move to `Validating` passed.
- Builder move to `Review` failed with validator-gate error.
- Builder prompt says Builders do not move issues to Review.
- Validator prompt says only Validator pass moves the issue to Review.
- Hub link validation passed.
- Desktop and mobile hub screenshots were inspected; Validator Lane is discoverable.

Screenshots:

- `screenshots/start-here.png`
- `screenshots/mobile-start-here.png`
