# Agent Work 30 - Cluster Health Reliability

Generated: 2026-04-30

## Scope

Fixed Mac-to-Linux cluster health failures observed during review work:

- `cento cluster exec linux -- 'cd ... && ...'` treated the whole string as a
  bad executable instead of a shell command.
- Remote `bash -lc` invocation split incorrectly across SSH arguments.
- Stale `/tmp/cento-linux.sock` probes could hang cluster health checks.
- `cento cluster heal linux` inherited the same quoted-command bug.

## Changes

- `scripts/cluster.sh`
  - Normalizes remote commands for both shell-string and argv-style execution.
  - Sends remote work as a single quoted `bash -lc` invocation.
  - Adds bounded VM socket ProxyCommand settings.
  - Repairs the Linux socket once and retries before falling back to direct LAN SSH.
  - Fixes `cluster heal linux` by making its remote shell command executable.

- `scripts/bridge.sh`
  - Applies the same remote shell normalization to `bridge to-linux -- ...`.

- `scripts/cluster_health_e2e.sh`
  - Adds a repeatable health deliverable for this ticket.

- `data/tools.json`
  - Registers the health e2e command and artifacts.

## Validation

Syntax and registry checks:

```bash
bash -n scripts/cluster.sh scripts/bridge.sh scripts/cluster_health_e2e.sh
python3 -m json.tool data/tools.json
```

Repair command:

```bash
cento cluster heal linux
```

Result:

```text
Installed and started /home/alice/.config/systemd/user/cento-bridge-linux.service
linux socket tunnel started: /tmp/cento-linux.sock -> 127.0.0.1:22
```

End-to-end command:

```bash
scripts/cluster_health_e2e.sh
```

Result:

```text
cluster status: linux connected, macos connected
cluster exec quoted shell: remote:alisapad:/home/alice/projects/cento
cluster exec argv mode: argv:hello:cluster
bridge to-linux quoted shell: bridge:alisapad:/home/alice/projects/cento
cluster health e2e ok
```

## Artifacts

```text
workspace/runs/agent-work/30/summary.md
workspace/runs/agent-work/30/validation.md
workspace/runs/agent-work/30/logs/mesh-status.log
workspace/runs/agent-work/30/logs/cluster-status.log
workspace/runs/agent-work/30/logs/cluster-exec-quoted.log
workspace/runs/agent-work/30/logs/cluster-exec-argv.log
workspace/runs/agent-work/30/logs/bridge-to-linux-quoted.log
```

## Remaining Risk

`iphone` remains disconnected in cluster status, but that is outside this
Mac/Linux cluster-health fix. The Mac/Linux path now has a repair command and a
repeatable e2e check.
