# Career Intake

Career intake is the CRM-side system for turning raw person context into a reproducible consulting dossier and artifact queue.

## Goal

The intake layer collects inputs such as:

- Telegram conversations with the consultant
- LinkedIn profile text
- Resume or CV files
- Existing cover letters
- Target job descriptions
- Target company notes
- Consultant notes

It then creates a local dossier with a manifest, source copies, a predefined artifact plan, and Codex-ready prompts.

## Storage

Each person gets a local folder under:

```text
workspace/runs/career-intake/<person>/
```

The folder contains:

- `manifest.json`: machine-readable dossier metadata, source list, and artifact plan
- `sources/`: copied raw inputs
- `artifact-plan.md`: human-readable artifact queue
- `prompts/`: one Codex-ready prompt per artifact
- `artifacts/`: placeholder files where processed outputs should be written

## Commands

Create or update a dossier:

```bash
cento crm intake init --person "Ada Lovelace" --target-role "Product Manager" --target-companies "Stripe,Notion,OpenAI,Linear,Figma"
```

Attach a source file:

```bash
cento crm intake add --person "Ada Lovelace" --kind resume --file ~/Downloads/ada-resume.pdf --title "Current resume"
cento crm intake add --person "Ada Lovelace" --kind linkedin --file ~/Downloads/linkedin.md --title "LinkedIn profile"
```

Attach inline Telegram or notes text:

```bash
cento crm intake add --person "Ada Lovelace" --kind telegram --text "Raw conversation summary..." --title "Telegram conversation"
cento crm intake add --person "Ada Lovelace" --kind notes --text "Wants US remote PM roles..." --title "Consultant notes"
```

Generate the artifact plan and prompt pack:

```bash
cento crm intake plan --person "Ada Lovelace"
```

Inspect paths:

```bash
cento crm intake show --person "Ada Lovelace"
cento crm intake paths --person "Ada Lovelace"
```

## Default Artifacts

The first artifact queue is intentionally opinionated:

1. Candidate intake synthesis
2. Resume review: grammar and conciseness
3. Resume review: impact and ATS alignment
4. LinkedIn profile review
5. Cover letters for top 5 target companies
6. Interview preparation brief
7. Client action plan

Blocked artifacts stay in the queue and explain what source is missing.

## Codex Processing Model

This module does not directly call an LLM yet. It prepares prompt files under `prompts/` so a Codex or agent run can process each artifact with controlled context.

The intended future automation is:

1. Intake raw sources into a dossier.
2. Generate the artifact plan.
3. Run a processor over `prompts/*.md`.
4. Write outputs under `artifacts/*.md`.
5. Attach final outputs back to CRM contacts, tasks, and notes.

This keeps the system auditable: raw sources, prompts, and outputs are all preserved locally.
