# Tool Central

Tool Central is a local-first repo and dashboard for running your work from one place.

It starts with four operating lanes:

- career consulting
- media creation
- scraping and research
- general ops

The repo is dependency-free. The dashboard runs on Python's standard library, and the rest of the project is plain files you can adapt as your system matures.

## Quick start

```bash
cd /Users/anovik-air/tool-central
make serve
```

Open `http://127.0.0.1:8421`.

## Included

- `AGENTS.md` repo instructions for AI agents working here
- `src/` browser dashboard
- `data/tools.json` central registry for tools, prompts, templates, and workflows
- `prompts/` reusable prompt packs for consulting, media, and research tasks
- `templates/` project, client, content, and scraping templates
- `workflows/` repeatable operating playbooks
- `workspace/` starter directories for client work, content, and research runs
- `scripts/serve.py` tiny local server
- `Makefile` simple entry points

## Common commands

```bash
make serve     # run the dashboard locally
make check     # verify the Python launcher compiles
make tree      # print a compact repo tree
```

## How to customize

1. Edit `data/tools.json` to point categories at your real files, URLs, or scripts.
2. Fill `workspace/clients`, `workspace/content`, and `workspace/research` with active project folders.
3. Expand the prompt packs and templates as you learn which workflows repeat.
4. Add automation scripts under `scripts/` or a future `automation/` directory.

## Recommended next upgrades

- connect a real lead database or CSV workflow for scraping output
- add your preferred AI prompts and persona packs to `prompts/`
- add a CRM or client tracking file under `workspace/clients`
- create publication pipelines for your content channels
# cento
# cento
