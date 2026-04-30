# Agent Work 16 - iPhone Cento App Planning

Generated: 2026-04-29T19:11:00-04:00

This packet is isolated planning output for Redmine agent-work issue #16.

## Files

- `requirements.md` - product requirements, scope, acceptance criteria, and story grouping.
- `architecture.md` - proposed iOS, Cento gateway, data, auth, and notification architecture.
- `delivery-roadmap.md` - local iPhone install path, blockers, milestones, and validation gates.
- `validation.md` - evidence gathered and checks run for this planning task.
- `captains-notes.md` - append-only process/resource notes for later follow-up.
- `one-pager.md` - short manager-facing summary and next actions.

## Current Decision

Build the first shippable version as a SwiftUI iPhone app backed by a small local Cento mobile gateway. The fastest interim installable surface is a PWA/local web link because the reachable Mac does not currently have full Xcode or signing identities. Native iPhone install becomes unblocked after full Xcode is installed on the Mac and signing/device trust are configured.
