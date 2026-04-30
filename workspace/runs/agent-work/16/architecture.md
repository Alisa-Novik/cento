# iPhone Cento App Architecture

## Recommended Shape

Use a native SwiftUI iPhone app backed by a local Cento Mobile Gateway. The app should not connect directly to Docker, PostgreSQL, repo files, or shell scripts. It should call a small HTTP API that aggregates existing Cento and Redmine data and exposes a narrow action allowlist.

```text
iPhone SwiftUI app
  |
  | HTTPS or LAN HTTP with token during local dev
  v
Cento Mobile Gateway
  |
  +-- Redmine / scripts/agent_work.py
  +-- scripts/jobs_server.py load_jobs contract
  +-- scripts/network_web_server.py cluster_snapshot contract
  +-- scripts/dashboard_server.py overview/activity contract
  +-- scripts/notify.sh for ntfy/iPhone notifications
  +-- workspace/runs for logs, screenshots, artifacts
```

## Existing Cento Inputs

- Redmine agent work: `scripts/agent_work.py`
  - `show`, `list`, `claim`, `update`, `dispatch`.
  - Uses Redmine PostgreSQL directly when local or via cluster transport.
  - Gap: current `show --json` does not expose Redmine journal/activity history, so the mobile Activity tab needs a small journal query or Redmine REST-backed endpoint.

- Jobs: `scripts/jobs_server.py`
  - Source: `workspace/runs/cluster-jobs/*/job.json`.
  - Existing API shape: `/api/jobs`.
  - Includes task state, node assignment, log tail, scripts, manifests, summaries.
  - Gap: jobs are exposed by `scripts/jobs_server.py`, but `jobs` is not currently registered as a `data/tools.json` tool id on this node.

- Network/agents: `scripts/network_web_server.py`
  - Existing API shape: `/api/network`.
  - Uses `~/.config/cento/cluster.json`, `cento cluster status`, and bridge mesh status.

- Dashboard/activity: `scripts/dashboard_server.py`
  - Existing API shape: `/api/state`, `/api/jobs`, `/api/network`.
  - Provides tools, aliases, recent logs, repo state, dashboard links.

- Notifications: `scripts/notify.sh`
  - Existing command: `cento notify iphone "message"` or direct script route through `cento.sh`.
  - State: `~/.config/cento/notify.json`, `~/.local/state/cento/notify-events.jsonl`.

- Quick action source candidates:
  - `data/tools.json` for registered tool metadata.
  - `~/.config/cento/aliases.sh` for local aliases.
  - `scripts/quick_help_fzf.sh` and `scripts/industrial_panel.py` for current palette/action patterns.

- Redmine experiment: `experimental/redmine-career-consulting/`
  - Local Redmine stack and REST workflow docs.
  - Current issue #16 is in the Redmine-backed `cento-agent-work` project.

## New Backend Component

Add a future `scripts/mobile_gateway.py` rather than extending every existing server. It should import existing safe functions where possible and avoid duplicating logic.

The gateway should also hide current CLI registration gaps. The app calls stable mobile endpoints; the gateway may call direct scripts until `agent-work` and `jobs` are registered in `cento.sh`/`data/tools.json`.

Proposed endpoints:

- `GET /api/mobile/dashboard`
- `GET /api/mobile/issues`
- `GET /api/mobile/issues/{id}`
- `POST /api/mobile/issues`
- `POST /api/mobile/issues/{id}/comments`
- `POST /api/mobile/issues/{id}/status`
- `GET /api/mobile/jobs`
- `GET /api/mobile/jobs/{id}`
- `GET /api/mobile/jobs/{id}/logs`
- `GET /api/mobile/jobs/{id}/artifacts`
- `GET /api/mobile/agents`
- `POST /api/mobile/actions/{action_id}`
- `POST /api/mobile/notify/test`
- `GET /api/mobile/health`

## Write Action Policy

The gateway should expose only named actions. No endpoint should accept arbitrary shell text from the phone.

Initial allowlist:

- `issue.comment`
- `issue.set_status`
- `job.create_from_template`
- `job.dispatch_existing`
- `pipeline.trigger_known`
- `notify.test`
- `cluster.status`
- `cluster.heal`

Every write action records:

- request id
- authenticated mobile client id
- action id
- input summary
- command/script path used
- output summary
- artifact path
- Redmine note if tied to an issue

## iOS App Modules

- `CentoApp`
  - App entry, dependency injection, global theme.

- `CentoAPI`
  - URLSession client, token auth, response models, retry/stale-state handling.

- `DashboardFeature`
  - Health cards, queue, activity, bottom tabs.

- `IssuesFeature`
  - Issue list, issue details, details/activity/relations tabs, comments/status actions.

- `JobsFeature`
  - Job list/detail, step progress, live logs, artifacts.

- `AgentsFeature`
  - Agent list, node health, online/offline filtering.

- `ActionsFeature`
  - Quick action forms and confirmation sheets.

- `SettingsFeature`
  - Server URL, token, notification permission, about/version.

## Data Model

Use stable app-level DTOs instead of binding SwiftUI directly to existing JSON. That lets Cento change internal scripts without breaking the app.

Core DTOs:

- `HealthSummary`
- `QueueItem`
- `ActivityEvent`
- `IssueSummary`
- `IssueDetail`
- `IssueJournalEntry`
- `JobSummary`
- `JobDetail`
- `JobStep`
- `LogLine`
- `Artifact`
- `AgentNode`
- `QuickAction`

## Install And Network Model

Development:

- Gateway binds to LAN IP or bridge-accessible host with a generated token.
- iPhone app stores `baseURL` and token.
- The app should support clear "stale/offline" state when the gateway is unreachable.

Production-local:

- Gateway should be launched by `cento mobile serve`.
- Optional reverse tunnel/bridge can expose it if the iPhone is not on the same LAN.
- Native app should not require public internet except TestFlight/App Store delivery and optional ntfy.

## Security Baseline

- Token required for all endpoints, including reads, after first setup.
- Gateway binds to `127.0.0.1` by default and requires explicit `--host 0.0.0.0` for phone access.
- Redact tokens, API keys, and shell environment from logs.
- Mutating endpoints require CSRF-style request nonce or signed request id.
- Dangerous actions require confirmation in app and an audit note in Redmine.

## Validation Strategy

- Backend: pytest/unittest for DTO mapping, fixture-based jobs, Redmine unavailable path, auth failures, and action audit logs.
- iOS unit tests: DTO decoding and state reducers.
- iOS UI tests: dashboard, issue detail, job logs, artifacts, agents, quick actions, settings.
- Screenshots: capture every delivered screen on simulator after Xcode is available.
- Physical iPhone smoke: install, launch, connect to gateway, view dashboard, open issue #16, run notification test.
