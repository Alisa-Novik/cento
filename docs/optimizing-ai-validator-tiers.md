# Optimizing AI: Dramatic Budget Cuts

Tag: `optimizing-ai`

Current constraint: 38% of the weekly AI budget remains. The goal is not a 1% efficiency tweak. The goal is to remove whole categories of model calls from the Cento dev loop.

## Research Inputs

- OpenAI cost guidance: reduce requests, minimize input/output tokens, and use smaller models when accuracy allows. Batch API and flex processing are explicit lower-cost options. Source: https://developers.openai.com/api/docs/guides/cost-optimization
- OpenAI prompt caching: stable repeated prompt prefixes can reduce latency by up to 80% and input token cost by up to 90% on supported API requests. Source: https://developers.openai.com/api/docs/guides/prompt-caching
- OpenAI Batch API: asynchronous work can run at 50% lower cost than synchronous API calls, with completion within 24 hours. Source: https://developers.openai.com/api/docs/guides/batch
- DORA small-batch research: small batches amplify the positive impact of AI adoption and act as a countermeasure to AI-driven delivery instability. Source: https://dora.dev/capabilities/working-in-small-batches/
- DORA AI SDLC research: AI speedups often create a verification tax, where saved generation time is re-spent auditing, prompting, and validating output. Source: https://dora.dev/insights/balancing-ai-tensions/
- Long-context research: models often use information best near the beginning or end of context, with degradation when relevant data is buried in the middle. Source: https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00638/119630/Lost-in-the-Middle-How-Language-Models-Use-Long
- Long-horizon agent caching research: strategic prompt caching across providers reduced API costs by 41-80% and improved time to first token by 13-31%; naive full-context caching can be worse than controlled cache blocks. Source: https://arxiv.org/abs/2601.06007
- OpenAI response-length guidance: cap output tokens and use verbosity/reasoning controls where available to reduce cost and latency. Source: https://help.openai.com/en/articles/5072518-controlling-the-length-of-openai-model-responses

## Emergency Budget Mode

Until the weekly budget recovers:

- One AI interpretation call per task, then stop and use artifacts.
- No manifestless task creation. `agent-work create --manifest` remains mandatory.
- No broad codebase exploration unless a manifest, failing check, or user explicitly names the files.
- No automatic cheap judge, no automatic Codex escalation, no dashboard work.
- No parallel exploratory agents. Use shell search, deterministic checks, and existing docs first.
- Any task expected to consume more than 30 minutes of active AI work must be split or blocked for approval.

## Dramatic Cuts

| Lever | Why It Is Big | Cento Action |
| --- | --- | --- |
| One-call intake | Replaces repeated clarification and rediscovery turns. | Generate `story.json` and validation draft up front, then operate from files. |
| Deterministic validation | Removes model review from routine pass/fail checks. | Expand Tier 0 checks before adding any Tier 1 model judge. |
| Context diet | Avoids paying for long, low-signal prompts and reduces lost-in-the-middle risk. | Read only manifest paths, failing files, and top search hits. Do not dump the repo. |
| Cache-first prompts | Can be a double-digit API cost and latency lever when using API-backed agents. | Put stable system/developer/tool instructions first; put dynamic logs, diffs, and tool output last. Track cached tokens when available. |
| Batch offline AI | Cuts non-urgent API jobs by 50% where Batch API is used. | Batch evals, classification, doc summarization, and backlog grooming. Do not batch interactive bug fixes. |
| Small batches | Reduces AI verification tax and review risk. | Slice work into changes that can be built and validated in under one hour. |
| Stop rules | Prevents budget death by open-ended debugging. | If deterministic evidence is missing after one loop, mark blocked instead of asking the model to guess. |

## Target Architecture

```text
user request
  -> one AI interpretation pass
  -> story.json draft with issue.id = 0
  -> validation.json draft from explicit expected outputs
  -> agent-work create --manifest story.json
  -> scoped implementation
  -> validator-tier0 run validation.json
  -> stats + decision
  -> Codex only for failed evidence with a narrow file/command target
```

## Current Implementation

The No-model validation epic now has an executable generated-manifest path:

- `story-manifest draft` creates a valid `story.json` with `issue.id = 0`, no-model validation policy, escalation triggers, expected outputs, and review gate requirements.
- `validation-manifest draft` converts explicit artifacts into deterministic Tier 0 checks and records automation coverage plus `manual_review` count.
- `agent-work preflight` blocks dispatch when `story.json` is invalid, `validation.json` is missing, expected outputs lack owners, automation coverage is below 95%, or manual review is unresolved.
- `validator-tier0 run` executes deterministic checks and records mandatory timing, automation, and AI budget stats.

Latest local E2E evidence:

- Evidence root: `workspace/runs/agent-work/no-model-validation-e2e/`
- Automation coverage: `100%`
- Deterministic checks: `9`
- Manual-review items: `0`
- AI calls used: `0`
- Estimated AI cost: `0`
- Total E2E duration: `276.672 ms`

## Manifest Rules

The manifest is how we stop paying the model to remember the task.

- Generate deterministic checks only when the expected artifact is explicit.
- Use `file_exists`, `command`, `json_field`, `contains_text`, screenshot existence, and API smoke checks.
- Ambiguous, subjective, architectural, security-sensitive, or cross-module requirements become `manual_review`.
- Never invent checks to make the packet look complete.
- Every generated manifest is a draft until coordinator/builder confirms the acceptance criteria.

## Mandatory Stats

Every agent-work validation or optimization task must record:

- total duration
- per-check duration
- command executed
- output artifact paths
- decision: `approve`, `needs_fix`, or `blocked`
- `ai_calls_used`
- `estimated_ai_cost`
- cache hit/cached-token stats when an API path exposes them
- escalation reason, if any

No stats means the optimization loop failed.

## Current Backlog

| ID | Status | Priority | Scope | Acceptance |
| --- | --- | --- | --- | --- |
| AI-OPT-001 | Done | P0 | `story-manifest draft` helper. | Creates a valid draft `story.json` from title, package, acceptance bullets, expected outputs, owner, node, and role. |
| AI-OPT-002 | Done | P0 | `validation-manifest draft` helper. | Converts explicit expected outputs and commands into Tier 0 checks; uncertain items become `manual_review`. |
| AI-OPT-003 | Done | P0 | `agent-work preflight story.json`. | Blocks dispatch when story manifest, validation draft, owned paths, coverage, or manual-review status is missing. |
| AI-OPT-004 | Partial | P0 | Budget stop rules. | E2E and Tier 0 runs record elapsed time, AI calls, estimated cost, and automation coverage; broader task-loop stop enforcement is still pending. |
| AI-OPT-005 | Next | P1 | Context packer. | Builds a small context bundle from manifest paths, `rg` hits, failing commands, and recent diffs; no repo dump. |
| AI-OPT-006 | Next | P1 | Cache-aware API wrapper. | Stable prefix, dynamic suffix, cached-token metrics, and warning when cacheable prefix changes. |
| AI-OPT-007 | Next | P1 | Batch offline jobs. | Non-urgent eval/classification/doc jobs emit JSONL batch files instead of synchronous calls. |
| AI-OPT-008 | Deferred | Deferred | Cheap judge. | Revisit only after at least 10 Tier 0 packets show repeated ambiguous manual review that a cheap judge could resolve. |

## One-Hour Implementation Result

1. Added `story-manifest draft`.
2. Added `validation-manifest draft`.
3. Added `agent-work preflight`.
4. Added `no-model-validation-e2e` and recorded timing stats.

Still out of scope until budget recovers: Tier 1, routing engines, dashboards, generic planners, and automatic model judges.

## Practical Policy

For the next tasks, use this rule:

```text
If shell can answer it, shell answers it.
If a manifest can preserve it, write the manifest.
If Tier 0 can validate it, do not ask AI to review it.
If AI is needed, give it only the narrow failing artifact.
```

## Expected Impact

The biggest savings should come from removing repeated context reconstruction, not from shaving tokens inside a bad workflow. The target is 50-80% less AI usage on routine Cento dev tasks by making the default path: one interpretation pass, deterministic execution, deterministic validation, and narrow escalation only when evidence fails.
