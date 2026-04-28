# Daily Execution Support

`cento daily` opens a local-first Bubble Tea execution cockpit for the daily loop:

- morning brief
- midday recalibration
- evening wrap-up

The app is intentionally not a journal. It is designed to keep the next execution decision visible and fast.

## Screens

- `Today`: proposed brief, accept/adjust/rewrite decisions, midday check-in, evening wrap-up.
- `History`: previous daily records and continuity details.
- `Settings`: reminder times, motivational tone, midday enablement, and process-question visibility.

## Data

Daily state is stored locally at:

- `workspace/runs/daily/history.json`

The JSON model includes:

- `DailyBrief`
- `BriefSection`
- `UserDecision`
- `MiddayCheckIn`
- `EveningWrapUp`
- `ExecutionHistory`

## Generation

The first version uses mock generation through a `BriefGenerator` interface. It uses yesterday's accepted brief and evening wrap-up when available, and assumes yesterday's accepted brief was executed unless the wrap-up says otherwise.

The interface boundary is deliberate so the generator can later be replaced with an LLM-backed provider without changing the TUI or persistence model.

## Controls

- `1`, `2`, `3`: switch Today, History, Settings
- `A`: accept the proposed brief
- `B`: adjust brief fields
- `C`: rewrite the brief manually
- `M`: midday recalibration
- `E`: evening wrap-up
- `S`: settings
- `Enter`: select or advance a form
- `Esc`: cancel editing
- `Ctrl+U`: clear the active field
- `q`: quit
