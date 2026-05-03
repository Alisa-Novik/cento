# Cento Temporary Commands

`cento temp run` is the stable bridge from Codex/Cento to ChatGPT Pro.

For the GPT Pro prompt workflow, the command is always exactly:

```bash
cento temp run
```

Do not add an ID or suffix for this workflow. The command copies the active
prompt Markdown into the clipboard and prints a short copied-to-clipboard report.

When an operator asks an agent to create a similar prompt for ChatGPT Pro, the
agent should:

1. Write the prompt Markdown under `workspace/runs/temp/chatgpt-pro/`.
2. Point the default temp entry `cento-dev-scale-pro-prompt` at that Markdown file.
3. Run `cento temp run` automatically.
4. Report that the prompt was copied to the clipboard.

Advanced `cento temp` entries can still store short-lived operator commands
behind stable names so an agent can give a human a clean command to run instead
of a fragile multiline shell paste.

Temp commands are intentionally not permanent product tools. They live under:

```text
workspace/runs/temp/commands/
```

## Usage

```bash
cento temp run
cento temp show
cento temp list
cento temp add ID --title TITLE --node local|macos|linux --command '...'
cento temp add ID --title TITLE --node local|macos|linux --command-file PATH
cento temp add ID --title TITLE --node local|macos|linux --copy-file PATH
cento temp run ID
cento temp run ID --dry-run
cento temp run ID --no-copy
cento temp remove ID
cento temp path
```

Use `cento temp run ID` only for advanced one-off temp commands. The ChatGPT Pro
bridge must use `cento temp run` with no suffix.

## Cluster Targets

- `--node local` runs on the node where `cento temp run ID` is invoked.
- `--node macos` runs locally on the Mac or routes through `cento cluster exec macos`.
- `--node linux` runs locally on Linux or routes through `cento cluster exec linux`.

## Operator Pattern

### ChatGPT Pro Prompt Bridge

The standard operator flow is:

```bash
cento temp run
```

Expected output:

```text
Copied to clipboard: /home/alice/projects/cento/workspace/runs/temp/chatgpt-pro/<prompt>.md
```

Then paste into ChatGPT Pro.

The default temp entry is:

```text
workspace/runs/temp/commands/cento-dev-scale-pro-prompt.json
```

It should contain a `copy_file` field pointing at the active prompt Markdown.

### Advanced One-Off Commands

An agent should create a temp command:

```bash
cento temp add watch-diag --title "Watch diagnostics" --node macos --command-file /tmp/watch-diag.sh
```

Then the human runs the named advanced command:

```bash
cento temp run watch-diag
```

For advanced shell commands, `run ID` saves output to
`workspace/runs/temp/history/<timestamp>-<id>/output.log`. By default it copies
the most useful path to the clipboard. If the command prints `Diagnostics written
to: PATH`, that path is copied; otherwise the temp run log path is copied. Use
`--no-copy` to skip clipboard writes.

Use `show` or `run --dry-run` before execution when the command affects external
state. Remove commands after they are obsolete:

```bash
cento temp remove watch-diag
```

## Safety

Temp commands can run arbitrary shell. They should be curated by an operator or
agent for a specific short-lived job, inspected before state-changing actions,
and removed when stale.
