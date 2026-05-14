# Demo Evidence Recorder

`cento demo-evidence` records short desktop videos for Factory, Codex worker, and Validator evidence bundles.

Use it when a worker has a visible product flow to prove and a screenshot is too weak. The tool enforces a 10-30 second window, writes an MP4, and records a machine-readable receipt with the command, recorder backend, requested and measured duration, hash, and output paths.

## Quick Start

Record a 15 second local demo:

```bash
cento demo-evidence record --title "Settings panel save flow" --duration 15
```

Record evidence directly into a Factory task bundle:

```bash
cento demo-evidence record \
  --factory-run workspace/runs/factory/<run-id> \
  --task <task-id> \
  --worker <worker-id> \
  --title "Factory task demo" \
  --duration 15 \
  --notes "Shows the completed user flow and visible validation result"
```

Verify a receipt before handoff:

```bash
cento demo-evidence verify workspace/runs/factory/<run-id>/tasks/<task-id>/evidence/demo-<timestamp>
```

## Output Layout

Default output without Factory metadata:

```text
workspace/runs/demo-evidence/<title>-<timestamp>/
  demo.mp4
  receipt.json
  summary.md
```

With `--factory-run` and `--task`, output is colocated with the task:

```text
workspace/runs/factory/<run-id>/tasks/<task-id>/evidence/demo-<timestamp>/
  demo.mp4
  receipt.json
  summary.md
```

`summary.md` is the human review entry point. `receipt.json` is the validator-friendly artifact and includes:

- schema version `cento.demo_evidence.v1`
- status, title, notes, tags, worker, Factory run, and task id
- requested duration and allowed duration window
- measured duration from `ffprobe` when available
- recorder backend and planned command
- video size and SHA-256 hash for completed captures

## Worker Contract

Builders and Codex workers should record demo evidence after the focused validation command passes and before moving a task to Validator or release handoff.

Use this checklist:

1. Prepare the app or terminal UI in the state the reviewer should inspect.
2. Run `cento demo-evidence record --duration 10` to `--duration 30`.
3. Keep the clip focused on one accepted flow or one clear before/after result.
4. Run `cento demo-evidence verify <run-dir>`.
5. Reference both `summary.md` and `receipt.json` in the handoff evidence list.

Do not use this tool to capture secrets, tokens, private messages, or unrelated desktop windows. If the UI contains sensitive content, switch to sanitized fixture data before recording.

## Recorder Backends

`--recorder auto` is the default.

- Linux Wayland: uses `wf-recorder` when available.
- Linux X11: uses `ffmpeg` with `x11grab`.
- macOS: uses `ffmpeg` with `avfoundation`; the Terminal or agent host may need Screen Recording permission.
- Synthetic: `--recorder synthetic` creates a generated ffmpeg test pattern for plumbing checks only. It is not product evidence.

For X11, pass `--geometry WIDTHxHEIGHT+X,Y` to capture a smaller region:

```bash
cento demo-evidence record --duration 12 --geometry 1280x720+0,0
```

## Dry Runs And Smoke Tests

Plan the command without recording:

```bash
cento demo-evidence record --duration 15 --dry-run --json
```

Smoke-test the receipt and verification path without desktop capture:

```bash
cento demo-evidence record \
  --duration 10 \
  --recorder synthetic \
  --out workspace/runs/demo-evidence/smoke \
  --json

cento demo-evidence verify workspace/runs/demo-evidence/smoke
```

## Troubleshooting

- `x11grab recorder requires DISPLAY`: run from a graphical X11 session or pass the command through the Linux desktop node.
- `no Linux screen recorder found`: install `ffmpeg` for X11 or `wf-recorder` for Wayland.
- macOS permission failures: grant Screen Recording permission to Terminal, the agent host, or the ffmpeg launcher, then rerun the command.
- duration verification failed: rerecord with `--duration` between 10 and 30 seconds. Very small encoder rounding differences are tolerated by `verify`.
