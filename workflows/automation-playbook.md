# Automation Playbook

Use this repo as a staging ground for automation:

1. Add or update a script under `scripts/`.
2. Register it in `data/tools.json`.
3. Add a `Makefile` entry if it has a common invocation.
4. Add a short usage note to `README.md`.
5. If the tool emits durable output, write it under `workspace/runs/`.
6. If the tool should be consumed externally, add or update a shell wrapper.
