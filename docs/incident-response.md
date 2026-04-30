# Cento Incident Response

`cento incident` runs bounded checks for Cento control-plane failures and escalates actionable failures into `agent-work`.

## Cluster Bridge Incident Runbook

The 2026-04-30 Linux bridge outage is documented as a SEV2 cluster-health incident:

- Permanent runbook: [`docs/cluster-bridge-incident.md`](cluster-bridge-incident.md)
- Cluster incidents dashboard: [`workspace/runs/cluster-incidents/start-here.html`](../workspace/runs/cluster-incidents/start-here.html)
- Incident bundle: [`workspace/runs/cluster-incidents/bridge-stale-socket-20260430/start-here.html`](../workspace/runs/cluster-incidents/bridge-stale-socket-20260430/start-here.html)

Primary mitigation:

```bash
cento cluster heal linux
```

Use this when `/tmp/cento-linux.sock` exists on the OCI relay but `cento bridge to-linux` or `cento gather-context` reports `Connection refused`.

The first MVP check is `iphone-ce`. It watches whether the iPhone command path is healthy enough for:

```bash
ce "send me ..."
```

The check is intentionally local and bounded. It reads the Mac-side iPhone heartbeat and the local cluster request spool. It does not SSH into the iPhone and does not wait for a live test command to finish.

## Run The Check

Dry probe without creating work:

```bash
cento incident check iphone-ce --json --no-create
```

Normal operator check:

```bash
cento incident check iphone-ce
```

If unhealthy, the command creates a SEV2 `agent-work` issue:

```text
[SEV2][iphone-ce-ingress] iPhone ce inbound command path not working
```

The issue package is `incident-response`, and the issue includes the heartbeat age, stuck request ids, request-storm evidence, guardrail settings, and triage steps.

## What Counts As Unhealthy

- Missing or stale `~/.config/cento/heartbeats/iphone.json`
- Cluster request directories older than the stuck threshold without `exit_code` or `final.txt`
- Repeated incomplete request storms in the recent request window

Defaults:

```text
heartbeat ttl: 900 seconds
stuck request threshold: 600 seconds
request lookback: 86400 seconds
request storm window: 900 seconds
request storm threshold: 5 repeated incomplete requests
```

## Guardrails

The script is designed not to create a task flood.

- It uses a lock file: `~/.local/state/cento/incident-response.lock`
- It keeps state in: `~/.local/state/cento/incidents.json`
- It reuses an active issue with the same incident key instead of creating another one
- It enforces a six-hour cooldown by default
- It enforces one create per 24 hours by default
- `--no-create` records state but never creates an issue
- `--force` bypasses cooldown and daily cap, but still does not create a duplicate while an active issue exists

Useful state command:

```bash
cento incident status
cento incident status --json
```

## Install A Watcher

Preview the LaunchAgent:

```bash
cento incident install iphone-ce --interval 300 --dry-run
```

Install and start the watcher:

```bash
cento incident install iphone-ce --interval 300
```

Remove it:

```bash
cento incident uninstall iphone-ce
```

The watcher appends to:

```text
~/.local/state/cento/incident-response.log
```

## Repair The iPhone Helper

If `ce 'question?'` prints a Mac shell glob error such as `zsh: no matches found`, reinstall the iPhone companion helper from the iPhone shell:

```bash
$HOME/bin/cento-remote cluster companion-setup iphone | tr -d '\r' > /tmp/cento-setup.sh
sh /tmp/cento-setup.sh
. ~/.profile
```

The `tr -d '\r'` filter repairs scripts fetched through older TTY-forcing helpers. The generated helper disables SSH TTY allocation and shell-quotes every SSH argument, so punctuation, quotes, and multiline prompts are passed to `cento cluster ask` as text instead of being interpreted by the Mac shell.

## Manual Override

Use this only when an operator intentionally wants another issue after closing the previous one:

```bash
cento incident check iphone-ce --force
```

For dashboard probes and scripts that should never create Redmine work, always pass:

```bash
cento incident check iphone-ce --no-create --json
```
