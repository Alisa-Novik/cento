# Telegram TUI

The Telegram tool is now registered inside `cento` as `cento tui`.

## Current scope

This is a Bubble Tea TUI with scaffolded Telegram actions, not the full Telegram action engine yet.

It currently provides:

- `cento tui`
  Open the Bubble Tea terminal interface.
- `cento tui status`
  Show config and scaffold status.
- `cento tui config --path`
  Print the local config path.
- `cento tui config --show`
  Print the current config JSON.
- `cento tui config --bot-token ... --chat-id ...`
  Save local config values for later Telegram actions.
- `cento tui docs`
  Print this documentation.
- `cento tui plan`
  Write a future-work plan report under `workspace/runs/telegram-tui/`.

## Deferred actions

The following are intentionally deferred for later implementation:

- sending Telegram bot messages
- reading Telegram bot updates
- CRM event notifications over Telegram
- richer Telegram workflows and templates

## Files

- config: `~/.config/cento/telegram.json`
- docs: `docs/telegram-tui.md`
- reports: `workspace/runs/telegram-tui/`

## CRM registration

The CRM side now exposes `cento crm integration` as a placeholder command for future Telegram integration work.

## Standard

This tool follows `standards/tui.md` and is the reference pattern for future interactive terminal apps in `cento`.
