# Cento Web App

The Cento web app is the operator console for the whole Cento system. Taskstream is the first complete application area, but the shell is intentionally broader than tasking.

## Main Sections

- `Taskstream`: issues, review queue, dispatch, validation evidence, and agent-work lifecycle.
- `Cluster`: node health, bridge mesh, Agent Processes, manual agents, worker pools, and runtime usage.
- `Consulting`: CRM, career intake, funnel, and client deliverables.
- `Docs`: operating guides, tasking contracts, validation lanes, runbooks, and generated tool references.

## Navigation Rule

Top-level header sections represent Cento product areas. Taskstream-specific views, including `Issues` and `Review`, live inside the Taskstream section instead of occupying the global product header.

## Implementation Notes

- Keep the brand as `Cento Console`.
- Keep Taskstream language for issue lifecycle and review workflow only.
- Add new app areas as real views as soon as their API surfaces exist; until then, show useful command/documentation entry points rather than empty placeholders.
- Document new global sections in this file and in `docs/agent-work.md` before wiring deeper implementation.
