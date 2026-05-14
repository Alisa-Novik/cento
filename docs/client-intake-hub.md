# Client Intake Hub

Client Intake Hub is the first real-file Tool Foundry bundle for the career consulting workflow. It is still fixture-only: it proves Cento can materialize a repo-ready tool surface without using real resumes, LinkedIn exports, private notes, or client PII.

## Current State

- `status`: materialized MVP
- `target_root`: `templates/foundry/client-intake-hub`
- `domain`: `career-consulting`
- `privacy`: fixture data only, local-first, no public upload

## Materialized Files

- `templates/foundry/client-intake-hub/client-intake-hub.html`
- `templates/foundry/client-intake-hub/client-profile.schema.json`
- `templates/foundry/client-intake-hub/command-api.json`
- `templates/foundry/client-intake-hub/storage-leak-policy.json`
- `templates/foundry/client-intake-hub/validation-plan.json`
- `templates/foundry/client-intake-hub/README.md`

## Preview

Run the CRM server and open the Studio view:

```bash
cento crm serve
```

The CRM exposes Foundry tool metadata at `/api/foundry/tools` and serves the generated preview from `/foundry/client-intake-hub/client-intake-hub.html`.

## Safety

- The bundle uses only the built-in Ada Lovelace fixture profile.
- Existing materialized files are not overwritten by Foundry unless their content is identical.
- OCI upload is not part of this MVP; storage remains local unless a later explicit storage promotion is approved.
