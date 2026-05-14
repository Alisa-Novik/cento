# Cento Temp Clipboard

`cento temp run` is intentionally a dumb clipboard bridge.

The command is always exactly:

```bash
cento temp run
```

It copies the fixed Markdown file configured in `scripts/cento_temp.sh`:

```bash
COPY_FILE="/home/alice/projects/cento/workspace/runs/temp/cento-ultimate-ai-reference.md"
```

To change what `cento temp run` copies, edit only that `COPY_FILE` line. Do not
add IDs, flags, `show`, `list`, `add`, `remove`, cross-node routing, secret
prompts, generated temp command registries, or clipboard probing loops.

Clipboard transport is handled by `pbcopy`. On Linux, fix the local `pbcopy`
shim if the terminal clipboard bridge breaks; do not expand `cento temp`.

## Contract

- Validate the command is exactly `run`.
- Validate `COPY_FILE` exists.
- Run `pbcopy < "$COPY_FILE"`.
- Print one copied line.

## Validation

```bash
bash -n scripts/cento_temp.sh
cento temp run
bash scripts/cento_temp.sh show
bash scripts/cento_temp.sh run extra
```

The last two commands should print `Usage: cento temp run` and exit non-zero.
