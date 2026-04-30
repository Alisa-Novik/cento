# Cento Funnel

Cento Funnel is the local-first business layer for turning media, content, audience activity, referrals, and manual outreach into tracked leads, conversations, offers, revenue, and next actions.

## Entry points

- `cento funnel init`
  Create starter funnel data with career-consulting examples.
- `cento funnel show`
  Print state counts and storage paths.
- `cento funnel sources`
  List traffic sources such as LinkedIn, Telegram, GitHub, communities, ads, newsletters, and outreach.
- `cento funnel funnels`
  List funnel definitions and their stages.
- `cento funnel leads`
  List captured leads and next actions.
- `cento funnel event conversation_started --source linkedin-posts --funnel career-consulting-discovery --lead ada-lovelace-linkedin --note "Booked async consult"`
  Append an event.
- `cento funnel events`
  List tracked events.
- `cento funnel report`
  Generate a Markdown report under `workspace/runs/funnel/`.
- `cento funnel docs`
  Print this page.

## Storage model

Persistent funnel data defaults to:

- `~/.local/share/cento/funnel/state.json`

Generated reports are written to:

- `workspace/runs/funnel/`

For isolated validation or experiments, set:

```bash
CENTO_FUNNEL_DATA=/tmp/cento-funnel-state.json cento funnel init
```

The v0 JSON state contains:

- `sources`: traffic streams and their default funnel.
- `funnels`: stage definitions tied to offers and sources.
- `leads`: people or accounts currently moving through a funnel.
- `events`: observations such as capture, qualification, conversation, proposal, win, loss, or follow-up.
- `offers`: monetizable products or services.
- `actions`: reusable follow-up rules and operating prompts.

## Operating model

Use Cento Funnel as the ledger between attention and business work:

1. Define the source, for example LinkedIn posts, Telegram referrals, GitHub profile traffic, YouTube, X, newsletters, communities, ads, experiments, or manual outreach.
2. Attach each source to a funnel that describes what should happen next.
3. Capture leads with the source, funnel, current stage, value estimate, and next action.
4. Log events whenever the stream produces a useful signal.
5. Run `cento funnel report` to see which streams are creating leads, conversations, revenue, or follow-up work.

## Seed examples

The starter data includes:

- `linkedin-posts` feeding `career-consulting-discovery`
- `telegram-referrals` feeding `career-consulting-discovery`
- `github-profile` feeding `automation-advisory`
- `career-strategy-sprint` as the main career-consulting offer
- `automation-diagnostic` as a technical advisory offer
- one sample lead, `ada-lovelace-linkedin`, with a concrete next action

## Validation

Run the focused funnel check:

```bash
make funnel-check
```

The check uses an isolated temporary `CENTO_FUNNEL_DATA` path, initializes seed data, validates required collections, appends an event, generates a report, and verifies that unknown source events fail clearly.

## Extension path

High-leverage next automations:

- add `lead add` and `lead update` commands for daily intake and stage movement
- ingest Telegram messages and source tags into leads
- connect `cento crm` contacts and career-intake dossiers to funnel leads
- attach UTM or content IDs to source events
- produce weekly source ROI reports
- add export adapters for dashboards, Redmine, or a future CRM backend
