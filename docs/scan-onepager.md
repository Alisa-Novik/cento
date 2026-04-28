# Scan One Pager

`cento scan` scans the cento repo and produces a single-file HTML report with a short explanation plus the strongest matching files and snippets.

By default it also serves the latest report on a local high port and opens it in your browser.

## Command surface

- `cento scan --query "mcp"`
  Generate a new one-pager, start or reuse the local preview server, and open the page.
- `cento scan --query "telegram" --no-open`
  Generate the page without opening the browser.
- `cento scan --query "crm" --case-sensitive`
  Use case-sensitive matching.
- `cento scan --query "cento .* integration" --regex`
  Treat the query as a regex.
- `cento scan --query "mcp" --port 47890`
  Prefer a specific high port for the preview server.

## Output model

- Current run:
  `workspace/runs/scan-onepager/latest/index.html`
- Machine-readable summary:
  `workspace/runs/scan-onepager/latest/summary.json`
- Archived previous runs:
  `workspace/runs/scan-onepager/archive/<timestamp>/`
- Preview metadata:
  `workspace/runs/scan-onepager/server.json`

Each new run archives the previous `latest/` directory before writing the new page.
The preview is served from `http://127.0.0.1:<high-port>/` by a lightweight background `python -m http.server` process.

## Defaults

- Root directory defaults to the cento repo root.
- Generated and runtime-heavy directories such as `.git`, `workspace`, and `logs` are excluded from the scan.
- The report shows the top matching files, snippets, extension breakdown, and a compact explanation layer.
- The preview server defaults to `127.0.0.1:47873` and will reuse that server when possible.
