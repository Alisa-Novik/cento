# Telegram TUI

The Telegram tool is now registered inside `cento` as `cento tg`.

## Current scope

This is a Bubble Tea TUI with scaffolded Telegram actions, not the full Telegram action engine yet.

It currently provides:

- `cento tg`
  Open the Bubble Tea terminal interface.
- `cento tg status`
  Show config and scaffold status.
- `cento tg config --path`
  Print the local config path.
- `cento tg config --show`
  Print the current config JSON.
- `cento tg config --bot-token ... --chat-id ...`
  Save local config values for later Telegram actions.
- `cento tg post --text "Hello from cento"`
  Send a message to the configured default chat through the Telegram Bot API.
- `cento tg post --chat-id ... --text "Hello"`
  Send a message to an explicit chat id.
- `cento tg history --limit 20`
  Read recent bot-visible Telegram updates and save a Markdown history report.
- `cento tg history --chat-id ... --no-save`
  Filter recent bot-visible updates to one chat and print without writing a report.
- `cento tg docs`
  Print this documentation.
- `cento tg plan`
  Write a future-work plan report under `workspace/runs/telegram-tui/`.

## Deferred actions

The following are intentionally deferred for later implementation:

- reading arbitrary personal account history; current history support uses bot-visible updates only
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
