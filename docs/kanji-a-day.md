# Kanji a Day

Kanji a Day is a watch-friendly local learning app for one daily kanji. The product loop is intentionally narrow:

```text
Today -> stroke practice -> meaning -> Got it -> history
```

The current preview focuses on the ritual that makes the app distinct: learn the shape first, reveal the meaning second, then save the kanji into memory.

## User Flow

- `Today`
  Shows the current kanji, meaning, reading, and primary start action.
- `Stroke practice`
  Animates each stroke in order. Future strokes stay faint, completed strokes stay visible, and the current stroke draws in.
- `Meaning`
  Reveals the kanji, English meaning, reading, and one example word.
- `Got it`
  Records the kanji as learned for the day.
- `History`
  Shows learned kanji and gives the user a memory trail.

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

## Local Surfaces

- Product preview source: `workspace/runs/agent-work/1000104/public/`
- WatchOS app source: `apps/watch/KanjiADay/`
- Static repo preview: `apps/watch/KanjiADay/Preview/index.html`

The active local preview has been tested at:

```text
http://127.0.0.1:47924/
```

## Validation

Use Firefox responsive design mode or Playwright to check:

- 360px, 390px, 430px widths
- Today screen has no overlapping header text
- Stroke completion keeps Replay and Meaning fully inside the watch frame
- Meaning screen centers the kanji and keeps `Got it` visible inside the watch frame
- History has an empty state and learned cards
- Normal mode contains no debug or MVP copy
- `?debug=1` exposes debug-only controls when needed

Recent visual evidence lives under:

```text
workspace/runs/agent-work/1000104/screenshots/
```
