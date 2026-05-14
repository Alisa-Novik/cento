---
name: app_overview_page_v1
description: Use when creating or refactoring a Cento app documentation page into a Product Control Surface with mandatory docs, dashboard, status, operations, architecture, and entry-point sections.
---

# App Overview Page v1

Create a single source-of-truth page for an app that combines docs, dashboard, status, operations, and entry points.

## Required Page Contract

Every app overview page must include these sections, in this order:

1. Header
2. Control Strip
3. Project Dashboard
4. About
5. Current Release
6. System Architecture
7. Operations
8. Links + Entry Points

Do not skip sections. If a system does not have a production value yet, state the real local/dev value and why.

## Section Requirements

### Header

Include:

- app name
- one-line functional description
- status badge: `development`, `staging`, or `production`
- version
- last updated date

### Control Strip

Include clickable, real links:

- live app URL
- repository URL
- Cento Dashboard or Taskstream entry

Optional links are allowed only when real: API endpoint, preview build, feature flags panel.

### Project Dashboard

Include:

- status
- version
- environment
- last deploy, validation, or preview refresh time

Prefer product-specific metrics over fake business metrics. Use realistic values and avoid placeholder rows.

### About

Use a short operational paragraph, then feature bullets. Answer what the system does every day.

### Current Release

Include:

- version
- build number
- release date
- release notes

Release notes must reflect actual capabilities. Do not add aspirational features.

### System Architecture

Use a simple readable pipeline, for example:

```text
PWA Preview -> Stroke Player -> Kanji Dataset -> Local Storage
```

Include components, data flow, storage type, and analytics or validation path when applicable.

### Operations

Include agent-executable actions such as:

- open in Taskstream
- open preview or build target
- view logs or evidence
- run validation

Actions can link to the relevant route, issue, artifact, or docs anchor. Do not include nonfunctional buttons.

### Links + Entry Points

Include real anchors or links for:

- User Guide
- Data Model
- Changelog
- API, when one exists

## Design Rules

- Use a two-column or three-column operational grid on desktop: core content left, actions and links right.
- Stack cleanly on mobile.
- Every section is a dense information card.
- Use dark surfaces, subtle borders, and orange only for primary accents/actions.
- Avoid marketing hero sections, filler copy, and empty space.

## AI Generation Rules

Must:

- fill every section
- reflect actual system behavior
- use realistic values
- keep links clickable and real
- validate visually at desktop and mobile widths

Must not:

- say `TBD`
- say `coming soon`
- invent fake features not present in the release notes
- use placeholder metrics without explanation
- bury operations below marketing content
