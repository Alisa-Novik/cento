# Cento CLI

The canonical JSON source for the root `cento` built-in command surface is:

- `data/cento-cli.json`

Use these entrypoints:

- `cento help`
  Print root CLI help.
- `cento docs`
  Print CLI docs from the canonical JSON source.
- `cento docs --json`
  Print the raw JSON source.
- `cento docs --path`
  Print the JSON path.
- `cento docs conf`
  Print docs for one built-in command.
- `cento interactive`
  Open the Bubble Tea TUI for built-ins, tools, and aliases.
- `cento install terminal`
  Install Zsh/Oh My Zsh completion plus the Cento right-prompt segment.
- `cento tmux status`
  Show tmux badge integration state.

Checklist included in `cento docs`:

- Discover: start with `cento docs`, `cento tools`, and a repo search before
  adding a new command or workflow.
- Task: for Cento feature, automation, MCP, cluster, mobile, UI, or command
  behavior changes, create an `agent-work` story manifest and task before
  implementation.
- Align: keep `data/cento-cli.json`, affected docs in `docs/`, and any
  generated indexes aligned with the actual command surface.
- Validate: run the narrow deterministic checks for the files changed,
  including JSON validation for docs sources.
- Evidence: leave validation evidence in the relevant
  `workspace/runs/agent-work/<issue-id>/` bundle and update Taskstream status.

Built-ins currently documented in JSON:

- `help`
- `interactive`
- `docs`
- `tools`
- `aliases`
- `conf`
- `completion`
- `install`
- `tmux`
- `run`
- `build`
- `runtime`
- `workset`
- `factory`
- `storage`

Local build loop:

- `cento run fast --task ... --write PATH --local-builder fixture --fixture-case valid --apply`
  creates a manifest-owned build package, runs one isolated fixture/local builder,
  dry-runs the patch bundle, applies the accepted patch, validates, and writes
  Taskstream evidence.
- `cento build worker run MANIFEST --worker builder_1 --runtime fixture --fixture-case valid --worktree`
  collects `worker_artifact.json`, `patch_bundle.json`, `patch.diff`, and
  `handoff.md`.
- `cento runtime check codex-fast`
  validates the hardened local command runtime profile.
- `cento build worker run MANIFEST --runtime-profile codex-fast --worktree`
  runs a local command adapter through an argv-array profile; raw shell commands
  require `--allow-unsafe-command`.
- `cento build apply MANIFEST --bundle PATCH_BUNDLE --from-receipt RECEIPT`
  applies only from an accepted integration receipt.
- `cento workset run WORKSET --max-workers 3 --runtime-profile codex-fast --apply sequential`
  runs exclusive-path tasks in parallel worktrees, then integrates and applies
  accepted patches one at a time.
- `cento workset execute WORKSET --max-parallel 6 --runtime api-openai --budget-usd 3 --max-budget-usd 5 --integrate sequential --apply`
  runs ready tasks in parallel, requires structured API artifacts, materializes
  them locally into patch bundles, and keeps integration/apply sequential.
- `cento workset materialize-artifact ARTIFACT`
  converts one `cento.api_worker_artifact.v1` JSON artifact into a local build
  patch bundle without letting the API worker mutate repository files.

Routing rules:

- `cento TOOL [args...]`
  Dispatch to a registered tool id from `data/tools.json`.
- `cento ALIAS [args...]`
  Dispatch to a configured alias from `~/.config/cento/aliases.sh`.

Terminal integration:

- `cento install zsh`
  Writes `~/.config/cento/init.zsh`, installs `_cento`, and appends one guarded
  source block to `~/.zshrc`. The snippet works with plain Zsh and Oh My Zsh
  and adds a right-prompt segment like `[cento:linux:host]`.
- `cento install tmux`
  Writes `~/.config/cento/tmux.conf`, appends one guarded source block to
  `~/.tmux.conf`, and reloads tmux when a server is running.
- `cento install terminal`
  Installs the Zsh/Oh My Zsh prompt and completion path only.

See `docs/terminal-integration.md` for the AI-facing implementation contract
and e2e verification flow.
