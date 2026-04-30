# iPhone Cento App Requirements

## Objective

Deliver an iPhone control surface for Cento that matches the supplied dark/orange operational mockup and lets the user inspect and act on Redmine issues, Cento jobs, agents, logs, artifacts, quick actions, and notifications from a phone.

## Users

- Primary user: Cento operator using one iPhone as a mobile cockpit.
- Secondary users: future agents/operators who need read-only status and safe command triggers.

## Product Principles

- The first screen is the operational dashboard, not marketing or onboarding.
- The app must expose the existing Cento system instead of creating a parallel tracker.
- Every write action must leave an audit trail in Redmine, Cento run artifacts, or notification event logs.
- Local-first is preferred. The app should work on the user's LAN/bridge before any cloud path.
- The default action surface must be constrained and reversible where possible.

## Required Screens

1. Dashboard
   - System health summary.
   - Counts for agents, running jobs, open issues, and pending tasks.
   - My queue list with status pills.
   - Recent activity from Cento logs and Redmine journals.

2. Issue details
   - Redmine issue key, subject, type, priority, status, assignee, reporter, created/updated dates.
   - Details, activity, and relations tabs.
   - Comment, edit, execute action, and more action entry points.
   - Clear status colors for blocked, open, in progress, review, and done.

3. Job details
   - Job key, title, status, step progress, and current execution step.
   - Step list with completed, in progress, pending, and failed states.
   - Assigned agent card.
   - View logs primary action.

4. Live logs
   - Streaming log view with timestamped lines.
   - Pause/resume.
   - Full logs action.
   - Failure lines must stand out without reducing terminal readability.

5. Artifacts
   - Files, logs, screenshots tabs.
   - File name, size, timestamp, and type icon.
   - Download/share affordances for artifacts that are reachable from the gateway.

6. Agents
   - Online/offline tabs.
   - Agent id, role, node, and health/status.
   - Support local, build, docs, monitor, report roles.

7. Quick actions
   - Create Redmine issue.
   - Create Cento job.
   - Trigger pipeline/runbook.
   - Create pull request or handoff artifact when supported.
   - Upload/attach artifact.
   - Search issues.
   - System status.

8. More
   - Terminal, scripts, workspaces, MCP servers, clusters.
   - Preferences, notifications, about/version.

## Functional Requirements

- Read current Cento dashboard state from existing local APIs or a new gateway aggregator.
- Read cluster jobs from `workspace/runs/cluster-jobs/*/job.json` through the existing jobs server contract.
- Read cluster/node state from the existing network snapshot contract.
- Read Redmine issue details and journals through `agent_work.py`/Redmine access or Redmine REST when available.
- Update Redmine work item status and notes through `scripts/agent_work.py update`.
- Dispatch or trigger safe Cento actions through a server-side allowlist, not arbitrary phone-submitted shell.
- Send completion/failure notifications through existing `scripts/notify.sh` and future iOS local notifications.
- Store app settings, server URL, and token in iOS Keychain.
- Provide offline stale state display with last updated timestamps.

## Nonfunctional Requirements

- Visual style: black/near-black surfaces, orange action color, compact industrial layout, 8px-or-less card radii, legible small operational text.
- Responsiveness: designed first for iPhone 15/16 class screens, with dynamic type support for accessibility.
- Security: local token required for gateway writes; write endpoints are allowlisted and logged.
- Reliability: app handles Mac/Linux node disconnects, Redmine down, jobs unavailable, and stale gateway state.
- Performance: dashboard initial load under 2 seconds on LAN after gateway is warm.
- Observability: every story must produce a validation artifact and screenshots when it changes UI.

## Story Grouping

The current Redmine package should stay combined under epic #15 and task #16 for planning. Implementation should be split only when work starts:

- Story A: Mobile gateway and read-only dashboard data.
- Story B: Native SwiftUI shell and dashboard/queue navigation.
- Story C: Redmine issue details, comments, and status updates.
- Story D: Job details, live logs, and artifacts.
- Story E: Agents, quick actions, notifications, and settings.
- Story F: Packaging, local iPhone install, screenshots, and release checklist.

## Acceptance Criteria For Planning Task #16

- Requirements are written and traceable to existing Cento components.
- Architecture identifies app, gateway, Redmine, jobs, agents, notifications, and artifact boundaries.
- Delivery roadmap names the fastest local iPhone install path and current blockers.
- Validation evidence is recorded.
- Redmine #16 is updated to Review with links to these artifacts.
