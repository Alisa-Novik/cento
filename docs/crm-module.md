# CRM Module

The CRM now lives inside `cento` as a first-class local module instead of as a disconnected side project.

## Entry points

- `cento crm`
  Open the interactive CRM menu.
- `cento crm questionnaire --profile career-consulting`
  Run or revise the requirements questionnaire.
- `cento crm init --profile career-consulting`
  Bootstrap the CRM app state from the saved questionnaire.
- `cento crm serve --profile career-consulting --open`
  Run the self-hosted local CRM and open it in a browser.
- `cento crm integration --provider telegram`
  Register and inspect the placeholder integration path for future Telegram CRM hooks.
- `cento crm integration --provider redmine --person "Ada Lovelace" --start-workflow`
  Create a Redmine project and one issue per generated career-intake artifact.
- `cento crm intake init --person "Ada Lovelace"`
  Create or update a career-intake dossier for one person.
- `cento crm intake add --person "Ada Lovelace" --kind resume --file ./resume.pdf`
  Attach raw intake sources such as Telegram conversations, LinkedIn profiles, resumes, job descriptions, and notes.
- `cento crm intake plan --person "Ada Lovelace"`
  Generate the artifact plan, placeholder outputs, and Codex-ready prompt pack.
- `cento crm show --profile career-consulting`
  Print the questionnaire summary.
- `cento crm paths --profile career-consulting`
  Print questionnaire and CRM state paths.
- `cento crm docs`
  Print this documentation.

## Hosting model

- The CRM is a no-build SPA served by `scripts/crm_module.py`.
- The backend uses Python standard-library HTTP serving and JSON persistence only.
- Startup is effectively instant because there is no Node toolchain, bundler, or database daemon.
- The preferred runtime is local `cento crm serve`; Docker is optional packaging, not the default runtime.

## Saved artifacts

- `workspace/runs/crm-questionnaire/<profile>/answers.json`
  Machine-readable questionnaire answers.
- `workspace/runs/crm-questionnaire/<profile>/summary.md`
  Human-readable requirements summary.
- `workspace/runs/crm-app/<profile>/state.json`
  Live CRM state for contacts, pipeline, tasks, notes, templates, and forms.
- `workspace/runs/crm-questionnaire/latest.json`
  Pointer to the latest questionnaire profile.
- `workspace/runs/crm-app/latest.json`
  Pointer to the latest CRM app state.
- `workspace/runs/career-intake/<person>/manifest.json`
  Career-intake dossier metadata, attached sources, and artifact plan.
- `workspace/runs/career-intake/<person>/sources/`
  Local copies of raw person inputs.
- `workspace/runs/career-intake/<person>/prompts/`
  Codex-ready prompts for each predefined artifact.
- `workspace/runs/career-intake/<person>/artifacts/`
  Placeholder and generated consulting artifacts.
- Redmine integration metadata is written back into `workspace/runs/career-intake/<person>/manifest.json`.

## MVP scope

- Questionnaire-derived pipeline stages, services, lead sources, channels, and integrations.
- A registered but deferred `cento crm integration` command path for Telegram-first CRM hooks.
- Self-hosted local SPA with views for overview, pipeline, contacts, tasks, and studio.
- Career-intake dossier system for raw person context and artifact planning.
- Local JSON persistence only.
- Privacy-specific hardening intentionally stays out of scope for MVP by user request.

## Suggested workflow

1. Run `cento crm questionnaire` when the operating model changes.
2. Run `cento crm init` to bootstrap or refresh the CRM state.
3. Run `cento crm serve --open` to use the app locally.
4. Let `workspace/runs/crm-app/<profile>/state.json` act as the MVP source of truth.
5. Use `cento crm intake ...` to collect raw candidate material before generating resume, LinkedIn, cover-letter, interview, and action-plan artifacts.

## Career intake

Career intake documentation lives in `docs/career-intake.md`.

The first artifact queue includes:

- candidate intake synthesis
- resume grammar and conciseness review
- resume impact and ATS review
- LinkedIn profile review
- cover letters for top 5 selected companies
- interview preparation brief
- client action plan

## Redmine workflow integration

Redmine integration documentation lives in `docs/redmine-integration.md`.

The MVP integration supports:

- CLI workflow start through `cento crm integration --provider redmine --person ... --start-workflow`
- dry-run planning with `--dry-run`
- HTTP workflow start through `POST /api/integrations/redmine/start-workflow`
- one Redmine project per career-intake person
- one Redmine issue per generated artifact

## Docker

Docker is not required and was not test-run in this environment because `docker` is not installed here, but a lightweight image definition is included at `templates/crm/Dockerfile`.

Build and run manually when Docker is available:

```bash
docker build -f templates/crm/Dockerfile -t cento-crm .
docker run --rm -p 47865:47865 -v "$PWD/workspace:/app/workspace" cento-crm
```
