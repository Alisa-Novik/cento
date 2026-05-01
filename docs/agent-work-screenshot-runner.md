# Story Screenshot Runner

`cento story-screenshot-runner` turns a `story.json` screenshot section into repeatable evidence.

It is the narrow evidence runner for agent-work stories that need desktop and mobile browser captures.

## Command Surface

```bash
cento story-screenshot-runner workspace/runs/agent-work/59/story.json
cento story-screenshot-runner workspace/runs/agent-work/59/story.json --force
python3 scripts/story_screenshot_runner.py workspace/runs/agent-work/59/story.json --force
```

## Input Model

The runner reads the `screenshots[]` entries from `story.json`.

It uses:

- `issue.id` for the stable evidence namespace
- `paths.run_dir` for the output root
- `screenshots[].name` for deterministic filenames
- `screenshots[].url` or route-derived URLs for the target page
- `screenshots[].viewport` for the capture size
- `screenshots[].output` when a story already specifies an exact destination
- `screenshots[].auth` and `screenshots[].auth_note` for metadata notes

If a screenshot entry does not define an output path, the runner writes:

```text
workspace/runs/agent-work/<issue-id>/screenshots/issue-<issue-id>-<slug>-<width>x<height>.png
```

## Output Model

Each run writes:

- `screenshot-evidence.json`
- `screenshot-index.md`
- one PNG per screenshot target

The JSON metadata includes:

- agent-work issue id
- source story path
- generated run directory
- command used
- per-capture URL
- per-capture auth notes
- per-capture viewport dimensions
- success or failure summary

The markdown index is the reviewer-friendly summary for Docs/Evidence and Validator lanes.

## Failure Modes

The runner exits non-zero when:

- the target URL is missing or unavailable
- Playwright is not installed or cannot be launched
- the capture times out
- the screenshot command returns an error

Those failures are surfaced in the metadata JSON and printed in the terminal output so the builder can distinguish missing fixtures from browser problems.

## Demo Run

Issue `#59` is the repo-local demo story for this runner.

It captures `workspace/runs/agent-work/56/start-here.html` at desktop and mobile viewports and writes the evidence bundle under `workspace/runs/agent-work/59/`.

See:

- [`workspace/runs/agent-work/59/story.json`](../workspace/runs/agent-work/59/story.json)
- [`workspace/runs/agent-work/59/screenshot-evidence.json`](../workspace/runs/agent-work/59/screenshot-evidence.json)
- [`workspace/runs/agent-work/59/screenshot-index.md`](../workspace/runs/agent-work/59/screenshot-index.md)
