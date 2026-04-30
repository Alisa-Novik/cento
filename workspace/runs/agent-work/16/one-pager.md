# iPhone Cento App - One-Pager

Updated: 2026-04-29

## Decision

Build a native SwiftUI iPhone app backed by a small Cento Mobile Gateway. Ship a local PWA link first if we need something usable on the phone before Xcode/signing are ready.

## Current Status

- Planning for Redmine #16 is complete and ready for review.
- Requirements, architecture, delivery roadmap, validation, and captain's notes are in `workspace/runs/agent-work/16/`.
- Existing Cento surfaces are enough to power the first app: Redmine agent work, jobs, network/agents, dashboard activity, and notifications.

## Main Blocker

Native iPhone install is blocked right now:

- Linux cannot build iOS apps.
- The Mac bridge is reachable.
- The Mac does not currently have full Xcode or valid signing identities.

## Recommended Delivery Path

1. Install full Xcode on the Mac and configure Apple signing/device trust.
2. In parallel, build `cento mobile serve` as a local gateway with token auth and read-only dashboard/jobs/agents APIs.
3. Ship a PWA/local link from the gateway for immediate iPhone use.
4. Build the SwiftUI app shell against fixtures, then wire it to the gateway.
5. Validate on simulator, then physical iPhone, then choose TestFlight for the cleanest install link.

## First Implementation Stories

- Mobile gateway: dashboard, jobs, agents, issue summaries, health.
- PWA shell: mockup-matching dashboard, issues, jobs, logs, artifacts, agents, actions, more.
- SwiftUI shell: bottom tabs, theme, fixture data, settings.
- Redmine activity: add journal/history read endpoint for the Activity tab.
- Delivery: Xcode setup, signing, screenshots, physical iPhone smoke test.

## Evidence Required Per Story

- Changed files.
- Commands/tests run.
- Screenshot paths for every UI story.
- Build logs for Xcode/native work.
- Redmine note with artifact links and known limitations.

## Manager Ask

Approve PWA-first as the fastest phone-visible delivery path, and install/configure full Xcode on the Mac to unblock native iPhone install.
