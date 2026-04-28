# Redmine Integration

The Redmine integration turns a generated `cento crm intake` artifact plan into a Redmine project workflow.

## Redmine Stack

The local Redmine experiment lives at:

```text
experimental/redmine-career-consulting/
```

Run it with:

```bash
cd experimental/redmine-career-consulting
./scripts/redmine.sh init
./scripts/redmine.sh up
./scripts/redmine.sh seed-sample
```

Default URL:

```text
http://localhost:47874
```

Docker access is required. If `docker info` reports permission denied for `/var/run/docker.sock`, add the user to the `docker` group and start a new login session.

## API Key

The workflow endpoint uses Redmine's REST API. Enable REST API in Redmine admin settings and create an API key for an admin or workflow-capable user.

Provide the key either as an environment variable:

```bash
export REDMINE_URL=http://localhost:47874
export REDMINE_API_KEY=...
```

or in local config:

```json
{
  "url": "http://localhost:47874",
  "api_key": "..."
}
```

at:

```text
~/.config/cento/redmine.json
```

## CLI Workflow

Create an intake dossier and artifact plan first:

```bash
cento crm intake init --person "Ada Lovelace" --target-role "Product Manager" --target-companies "Stripe,Notion,OpenAI,Linear,Figma"
cento crm intake add --person "Ada Lovelace" --kind resume --file ./resume.pdf
cento crm intake plan --person "Ada Lovelace"
```

Dry-run the Redmine workflow:

```bash
cento crm integration --provider redmine --person "Ada Lovelace" --start-workflow --dry-run
```

Create the Redmine project and issues:

```bash
cento crm integration --provider redmine --person "Ada Lovelace" --start-workflow
```

The integration creates one Redmine project per intake person and one Redmine issue per generated artifact.

## HTTP Endpoint

When `cento crm serve` is running, the same workflow is exposed at:

```text
POST /api/integrations/redmine/start-workflow
```

Example:

```bash
curl -sS http://127.0.0.1:47865/api/integrations/redmine/start-workflow \
  -H 'Content-Type: application/json' \
  -d '{"person":"Ada Lovelace","dry_run":true}'
```

Request fields:

- `person`: required intake person name or slug
- `dry_run`: optional boolean
- `redmine_url`: optional Redmine base URL override
- `api_key`: optional API key override

## Mapping

Artifact tracker hints:

- Intake synthesis -> `Intake`
- Resume reviews -> `Resume`
- LinkedIn review -> `LinkedIn`
- Cover-letter pack -> `Applications`
- Interview prep -> `Interview Prep`
- Client action plan -> `Follow-up`

If the preferred tracker is missing, the integration falls back to `Intake`, then to the first tracker returned by Redmine.

## Local State

Successful runs update the intake manifest under:

```text
workspace/runs/career-intake/<person>/manifest.json
```

The manifest stores the Redmine URL, project identifier, project id, and created issue ids so later runs avoid duplicate issue creation.

## E2E Test

Run the local dry-run e2e test:

```bash
make redmine-e2e
```

or:

```bash
./scripts/redmine_workflow_e2e.sh
```

The default test creates a unique career-intake dossier, adds Telegram/resume/LinkedIn sources, generates the artifact plan, validates the CLI Redmine dry-run output, starts a temporary CRM server, and validates `POST /api/integrations/redmine/start-workflow`.

It does not require Docker or a live Redmine instance by default.

To include the live Redmine REST path:

```bash
REDMINE_URL=http://localhost:47874 REDMINE_API_KEY=... ./scripts/redmine_workflow_e2e.sh --live-redmine
```
