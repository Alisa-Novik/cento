# Cluster Bridge Incident: Stale Linux VM Socket

Incident date: 2026-04-30
Severity: SEV2 cluster health
Status: mitigated

## Summary

The Mac could read the agent-work board, but the live Linux bridge path failed. `cento gather-context` reported Linux SSH status `255`, and `cento bridge check` failed with:

```text
Ncat: Connection refused.
Connection closed by UNKNOWN port 65535
```

The VM still showed `/tmp/cento-linux.sock`, so a surface-level mesh check looked present. The socket was stale: the file existed on the OCI relay, but the remote forward behind it was dead.

## Impact

- Mac agents could not reliably verify live Linux agent activity through `cento bridge to-linux`.
- `cento gather-context` could not use the Linux mesh path.
- The board still showed Linux work in Redmine, but live evidence from Linux was unavailable until repair.
- `cento cluster exec linux` still had a direct LAN fallback to `alice@alisapad.local`, so repair remained possible without touching the Linux checkout.

## Detection

Useful checks:

```bash
cento gather-context
cento bridge check
cento bridge to-linux -- 'hostname; date'
cento cluster status
cento cluster exec linux -- 'systemctl --user is-active cento-bridge-linux.service || true'
```

Observed signals:

- `cento gather-context`: remote status `255`
- `cento bridge check`: `Connection refused`
- `cento bridge mesh-status`: socket file visible
- `cento cluster exec linux`: still reachable through fallback
- Linux service: `cento-bridge-linux.service` active

## Mitigation

Run the supported heal path:

```bash
cento cluster heal linux
```

For this incident, the command:

1. Reached Linux through the fallback path.
2. Reinstalled/confirmed the Linux user service.
3. Detected that `/tmp/cento-linux.sock` existed but was stale.
4. Removed the stale socket on the OCI VM.
5. Recreated the socket tunnel:

```text
linux socket tunnel started: /tmp/cento-linux.sock -> 127.0.0.1:22
```

The legacy TCP reverse tunnel was also confirmed:

```bash
cento cluster exec linux -- '/home/alice/projects/cento/scripts/cento.sh bridge start'
```

## Verification

After mitigation, all of these passed:

```bash
cento bridge to-linux -- 'hostname; git -C "$HOME/projects/cento" status --short --branch | head -1'
cento bridge from-mac -- 'hostname; git -C "$HOME/projects/cento" status --short --branch | head -1'
cento bridge check
cento gather-context
cento cluster status
```

Expected healthy signs:

- `cento bridge check` ends with `remote_status: ok`
- `cento gather-context` shows Linux remote status `0`
- `cento cluster status` shows `linux connected` and `macos connected`
- `cento bridge to-linux` returns `alisapad`

## Guardrail

Do not pull, reset, or overwrite the Linux checkout while repairing the bridge. The bridge can be repaired through `cento cluster heal linux` and service/socket commands without touching tracked Linux work.

## Follow-Up Improvements

- Add stale-socket detection to the cluster health dashboard.
- Make `cento bridge check` mention that it verifies the legacy `:2222` path, while `to-linux` verifies the Unix-socket mesh.
- Add an incident drill that intentionally leaves a stale VM socket and confirms `cento cluster heal linux` repairs it.
- Record bridge repair events in an append-only cluster health ledger.
