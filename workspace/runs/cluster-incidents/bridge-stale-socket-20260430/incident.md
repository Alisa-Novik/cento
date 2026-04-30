# Incident: Stale Linux Bridge Socket

Date: 2026-04-30
Severity: SEV2
System: Cento cluster bridge
Status: mitigated

## What Happened

The Mac control node could see Redmine task state, but Linux live verification failed. The OCI VM still listed `/tmp/cento-linux.sock`, but commands using that socket returned `Connection refused`.

## Root Cause

The Linux Unix-socket remote forward on the OCI VM became stale. The socket file remained present after the backing tunnel died.

## Mitigation Applied

```bash
cento cluster heal linux
```

The repair command removed the stale VM socket and restarted the Linux socket tunnel. The legacy `:2222` bridge path was also confirmed with:

```bash
cento cluster exec linux -- '/home/alice/projects/cento/scripts/cento.sh bridge start'
```

## Evidence

Before repair:

```text
Ncat: Connection refused.
Connection closed by UNKNOWN port 65535
```

Repair output:

```text
[WARN] linux socket exists on VM but is stale; removing /tmp/cento-linux.sock.
linux socket tunnel started: /tmp/cento-linux.sock -> 127.0.0.1:22
```

After repair:

```text
cento bridge check -> remote_status: ok
cento bridge to-linux -> alisapad
cento gather-context -> remote status 0
cento cluster status -> linux connected, macos connected
```

## Operator Runbook

1. Confirm the failure:

   ```bash
   cento gather-context
   cento bridge check
   cento bridge to-linux -- 'hostname; date'
   ```

2. Heal Linux bridge:

   ```bash
   cento cluster heal linux
   ```

3. Confirm both bridge paths:

   ```bash
   cento bridge to-linux -- 'hostname'
   cento bridge from-mac -- 'hostname'
   cento bridge check
   ```

4. Confirm cluster state:

   ```bash
   cento cluster status
   cento agent-work runs --json --active
   ```

## Non-Goals

- Do not reset the Linux repo.
- Do not pull into the Linux dirty checkout during bridge repair.
- Do not create duplicate incident tasks unless the failure persists after heal.
