# Kanji a Day

Kanji a Day is a watch-friendly local learning app for one daily kanji.

```text
Today -> stroke practice -> meaning -> Got it -> history
```

The Docs route now treats the app page as a Product Control Surface, not a static article. It follows `app_overview_page_v1` so an operator or agent can understand state, open entry points, validate behavior, and continue work from one page.

## Current State

- Status: `development`
- Version: `0.3.0`
- Updated: `2026-05-01`
- Environment: local preview
- Live preview: `http://127.0.0.1:47924/`
- Taskstream epic: `1000110`
- Implementation branch: `codex/kanji-pwa-learning-loop`

## Page Contract

The `/docs#kanji-a-day` page must include:

- Header: app identity, description, status, version, updated date
- Control Strip: live app, repository, and Taskstream links
- Project Dashboard: status, version, environment, validation date, daily lesson count, kanji set size, subscription state
- About: what the app does every day and the core mechanics
- Current Release: actual version, build, date, and shipped notes
- System Architecture: readable pipeline from PWA preview to local storage
- Operations: Taskstream, preview, validation, and architecture entry points
- Links + Entry Points: User Guide, Data Model, Changelog, and PR

## Product Rules

- The learner should see the stroke order before the meaning is treated as complete.
- `Meaning` stays locked until all strokes finish.
- `Learned` increments only after the user confirms with `Got it`.
- Normal user mode must not show internal language such as MVP, PWA, AI calls, reset, localhost, or backend notes.
- Debug controls belong behind `?debug=1`.

## Content

The embedded starter set is:

- `日` - sun, day
- `月` - moon, month
- `火` - fire
- `水` - water
- `木` - tree, wood
- `金` - gold, money
- `土` - earth, soil

Each item should include meaning, reading, example vocabulary, stroke count, and SVG stroke path data.

## Architecture

```text
PWA Preview -> Stroke Player -> Kanji Dataset -> Local Storage
```

- PWA Preview: watch-style compact UI under `workspace/runs/agent-work/1000104/public/`
- Stroke Player: sequential SVG stroke playback and replay
- Kanji Dataset: seven embedded beginner records
- Local Storage: learned history, streak state, and current kanji progress

## Validation

Use Firefox responsive design mode or screenshot automation to check:

- `/docs#kanji-a-day` renders the Product Control Surface
- desktop layout has dense operational cards and a right action column
- 360px, 390px, and 430px widths have no horizontal clipping
- Today screen has no overlapping header text
- Stroke completion keeps Replay and Meaning fully inside the watch frame
- Meaning screen centers the kanji and keeps `Got it` visible inside the watch frame
- Normal app mode contains no debug or MVP copy
- `?debug=1` exposes debug-only controls when needed

Reference screenshot:

```text
/home/alice/Downloads/kanji a day.png
```

Recent app visual evidence lives under:

```text
workspace/runs/agent-work/1000104/screenshots/
```
