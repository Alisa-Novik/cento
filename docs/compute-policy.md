# Compute Policy

`cento compute-policy` controls the preferred mix of Codex, Claude Code, and metered OpenAI API usage.

Use it when you have agent subscription or limit available and want Cento to avoid API spend for work that can run through an agent.

## Quick Start

Prefer Codex for most agent dispatch and disable metered API by default:

```bash
cento compute-policy preset codex-first --json
```

Prefer Codex/Claude agents for roughly 70-80% of eligible work while still allowing explicit API-only lanes:

```bash
cento compute-policy preset agent-preferred --json
```

Set exact shares:

```bash
cento compute-policy set --codex 85 --claude 15 --openai-api 0 --json
```

Inspect the active policy:

```bash
cento compute-policy show --json
cento agent-work runtimes --sample 100 --json
```

## What It Changes

- Writes `.cento/compute-policy.json`.
- Synchronizes Codex and Claude shares into `data/agent-runtimes.json`.
- Leaves explicit `api-openai` commands explicit. If a command asks for `--runtime api-openai`, that remains an intentional API path.
- Records OpenAI API share as policy metadata so autopilot logs can analyze intended API usage separately from agent runtime usage.

## Presets

- `codex-first`: Codex 85, Claude 15, OpenAI API 0.
- `agent-preferred`: Codex 55, Claude 20, OpenAI API 25.
- `balanced`: Codex 50, Claude 30, OpenAI API 20.
- `claude-first`: Codex 20, Claude 80, OpenAI API 0.
- `api-minimal`: Codex 70, Claude 30, OpenAI API 0.
- `api-assisted`: Codex 50, Claude 25, OpenAI API 25.

## Agent-Preferred Threshold

When Codex/Claude weekly utilization is above 30% and capacity remains usable, Cento should prefer Codex/Claude agent lanes over metered OpenAI API for about 70-80% of eligible non-API-only work.

OpenAI API remains the explicit route for structured Responses API work, image generation, ProReq planning, and other API-only behavior. The policy is recorded in `.cento/compute-policy.json` as `agent_preference_policy` so nightly planning and follow-up handoffs can carry the same spending rule.

## Agent Pool Behavior

`cento agent-pool-kick` now defaults to Agent Work `auto` runtime routing instead of forcing Claude Code.

That means:

- non-validator agent dispatch follows the weighted Codex/Claude registry,
- strong GPT validator dispatch still forces Codex when the model override is a GPT model,
- explicit `CENTO_AGENT_RUNTIME=claude-code` or `CENTO_AGENT_RUNTIME=codex` still overrides policy.

## Guardrails

OpenAI API share does not silently block or rewrite explicit API commands. It is a policy signal: pipelines should prefer agents where possible and reserve API calls for structured Responses, image generation, ProReq lanes, or other API-only behavior.
