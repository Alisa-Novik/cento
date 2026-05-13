# Patch Swarm ProReq and ChatGPT Pro Prompt Bundles

## Overview

Patch Swarm prompt bundles turn local run artifacts into copy/paste prompts for ChatGPT Pro. The generator writes Markdown and JSON only. It does not call ChatGPT Pro, OpenAI APIs, Codex, MCP, Taskstream, Redmine, or worker pools.

## Operator Copy/Paste Flow

Generate the bundle, open `prompt-index.md`, paste a prompt into ChatGPT Pro, then paste the returned Codex implementation packet into Codex. Start with `prompt-0001-master.md`, then use lane or task-cluster prompts as needed.

## Inputs

- `request.md`
- `split-plan.json`
- `task-graph.json`
- `path-leases.json`

The generator can also create a deterministic fixture under `workspace/runs/parallel-delivery/proreq-fixture/`.

## Outputs

- `prompt-bundle.json`
- `prompt-index.json`
- `prompt-index.md`
- `prompts/prompt-0001-master.md`
- `prompts/prompt-*.md`
- `prompt-validation.json`
- `prompt-validation-report.md`
- `start-here.md`
- `temp-bridge.json` and `temp-current-prompt.md` when `--copy-to-temp` is used

## Prompt Bundle Layout

```text
workspace/runs/parallel-delivery/proreq-fixture/
  request.md
  split-plan.json
  task-graph.json
  path-leases.json
  prompt-bundle.json
  prompt-index.json
  prompt-index.md
  prompts/
  prompt-validation.json
  prompt-validation-report.md
  start-here.md
```

## Prompt Index

`prompt-index.json` records prompt ID, type, title, lane, task IDs, prompt path, SHA-256, owned paths, read-only paths, validation commands, evidence requirements, copy order, recommended model, and operator action.

`prompt-index.md` is the human copy order guide.

## Master Prompt

The master prompt is always first: `prompts/prompt-0001-master.md`. It summarizes the full run and asks ChatGPT Pro to produce a paste-ready Codex implementation packet.

## Lane Prompts

Lane prompts focus on `builder`, `validator`, `docs-evidence`, `coordinator`, `integrator`, and `human-handoff` scopes. Task-cluster prompts group task IDs without inventing tasks.

## Count and Lane Options

`--count` controls prompt count, not task count. It accepts `1..20`; use `15` or `20` for operator bundles.

`--lane all` includes all lanes. `--lane builder` emits a master prompt plus builder-scoped prompts and run-level review/evidence prompts scoped to the builder lane.

## Temp Bridge

`--copy-to-temp` writes a local mirror under:

```text
workspace/runs/temp/chatgpt-pro/<run-id>/
```

It also writes a `temp-bridge.json` manifest and updates the default `cento temp run` copy-file entry to point at `current.md`. The generator does not copy to the OS clipboard.

## Safety Rules

- Do not read or copy local secret files.
- Do not include local environment values, tokens, keys, credentials, or local secret values.
- Redact secret-like strings from request/context text.
- Do not include untracked file contents or broad repo dumps.
- Do not call live AI services or worker systems by default.
- Do not mutate Taskstream, Redmine, or story state through direct database writes.
- Do not reset, checkout, clean, stash, or overwrite unrelated work.

## CLI Examples

```bash
cento parallel-delivery patch-swarm prompts \
  --run-dir workspace/runs/parallel-delivery/proreq-fixture \
  --count 20 \
  --lane all \
  --chatgpt-pro \
  --copy-to-temp \
  --json
```

```bash
python3 scripts/parallel_delivery_prompts.py write-fixture \
  --run-dir workspace/runs/parallel-delivery/proreq-fixture \
  --run-id proreq-fixture \
  --count 20 \
  --fixed-timestamp 2026-01-01T00:00:00Z \
  --copy-to-temp \
  --json
```

## Fixture Run

The deterministic fixture writes 20 source tasks and exactly the requested number of prompts. `--count 15` writes 15 prompts. `--count 20` writes 20 prompts and reserves `prompt-0020-evidence.md` as the final evidence handoff prompt.

## Validation Commands

```bash
python3 scripts/parallel_delivery_prompts.py print-policy --json
python3 scripts/parallel_delivery_prompts.py validate-bundle \
  --run-dir workspace/runs/parallel-delivery/proreq-fixture \
  --json
pytest -q tests/test_parallel_delivery_proreq_prompts.py
```

## Failure Handling

If source artifacts are missing, the generator can create fixture inputs for local validation. If prompt validation fails, it writes exact errors in `prompt-validation.json` and `prompt-validation-report.md`. Temp bridge file-argument compatibility is documented as a bridge note rather than a prompt-bundle failure.
