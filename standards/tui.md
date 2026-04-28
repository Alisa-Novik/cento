# TUI Standard

## Purpose

All new interactive terminal applications in `cento` should follow one consistent approach.

## Required stack

- Use Bubble Tea v2 via `charm.land/bubbletea/v2`.
- Use Lip Gloss v2 via `charm.land/lipgloss/v2` for styling.
- Keep the user-facing launcher in `scripts/` as a shell wrapper when compilation or caching is needed.
- Keep the implementation source in repo-local Go files unless there is a stronger reason not to.

## Launcher pattern

- The `cento` tool registry should point at a launcher under `scripts/`.
- The launcher should compile a cached binary when sources or module files change.
- The launcher should execute the cached binary directly after a successful build.

## UX expectations

- Default entry should open the interactive TUI.
- Non-interactive or automation-friendly subcommands may coexist for status, docs, config, or exports.
- Provide clear quit keys and a visible action legend.
- Keep startup fast and dependency count low.

## Repo expectations

- Register the tool in `data/tools.json`.
- Update `README.md`, tool docs, and generated `docs/tool-index.md`.
- Add or update a focused `docs/<tool>.md` file.
- Add validation to `Makefile`.
