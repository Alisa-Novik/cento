# Redmine Career Consulting Experiment

Self-contained Redmine stack for evaluating Redmine as a career-consulting CRM/project system inside `cento`.

## Layout

- `compose.yml` runs Redmine 6 and PostgreSQL 16.
- `.env` stores local generated secrets and the exposed port.
- `data/` stores persistent Redmine uploads and PostgreSQL data.
- `plugins/` and `themes/` are mounted into Redmine for local extensions.
- `scripts/redmine.sh` wraps common operations from this directory.

## Run

```bash
./scripts/redmine.sh init
./scripts/redmine.sh up
```

Open:

```text
http://localhost:47874
```

Default first login:

```text
admin / admin
```

Redmine asks you to change that password after first login.

## Career Consulting Model

Recommended initial Redmine setup:

- Create one Redmine project per client.
- Use trackers such as `Intake`, `Resume`, `LinkedIn`, `Applications`, `Interview Prep`, `Follow-up`, and `Offer`.
- Add custom fields for `Target Role`, `Target Companies`, `Seniority`, `Resume Version`, `Application Deadline`, `Interview Date`, and `Current Stage`.
- Use issue statuses for the consulting pipeline: `New`, `In Progress`, `Waiting on Client`, `Submitted`, `Interviewing`, `Offer`, `Closed`.

## Commands

```bash
./scripts/redmine.sh doctor
./scripts/redmine.sh up
./scripts/redmine.sh ps
./scripts/redmine.sh logs
./scripts/redmine.sh seed-sample
./scripts/redmine.sh down
```

The sample seed creates/updates:

- Project: `Sample: Jane Doe Career Search`
- Trackers: `Intake`, `Resume`, `LinkedIn`, `Applications`, `Interview Prep`, `Follow-up`, `Offer`
- Statuses: `New`, `In Progress`, `Waiting on Client`, `Submitted`, `Interviewing`, `Offer`, `Closed`
- Custom issue fields for target role, target companies, seniority, resume version, deadlines, interview date, and current stage
- Six sample issues and a project wiki page

## Cento Workflow Integration

`cento crm` can create a Redmine workflow from a generated career-intake artifact plan.

After Redmine is running, enable Redmine's REST API in admin settings and provide an API key:

```bash
export REDMINE_URL=http://localhost:47874
export REDMINE_API_KEY=...
```

Dry-run:

```bash
cento crm integration --provider redmine --person "Ada Lovelace" --start-workflow --dry-run
```

Create the Redmine project and artifact issues:

```bash
cento crm integration --provider redmine --person "Ada Lovelace" --start-workflow
```

When `cento crm serve` is running, the equivalent HTTP endpoint is:

```text
POST /api/integrations/redmine/start-workflow
```

See `docs/redmine-integration.md` for the full contract.

## Docker Requirement

This experiment needs Docker Engine with Compose v2, or Podman plus `podman compose`. The stack is intentionally isolated to this directory; removing this directory removes the experiment configuration, and `./scripts/redmine.sh down` stops the containers.

On Ubuntu, Docker can be installed with:

```bash
./scripts/install-docker-ubuntu.sh
```

That script needs `sudo`. After it adds your user to the `docker` group, log out and back in, or run `newgrp docker`, then start Redmine with `./scripts/redmine.sh up`.
