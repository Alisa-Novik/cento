# Validation: Stale Linux Bridge Socket Incident

Date: 2026-04-30

## Commands Run

```bash
cento cluster heal linux
cento bridge to-linux -- 'hostname; date; git -C "$HOME/projects/cento" status --short --branch; systemctl --user is-active cento-bridge-linux.service 2>/dev/null || true'
cento gather-context
cento cluster status
cento bridge check
cento bridge from-mac -- 'hostname; git -C "$HOME/projects/cento" status --short --branch | head -1'
```

## Result

The Linux bridge was restored.

- `cento bridge to-linux` returned `alisapad`.
- `cento bridge from-mac` returned `alisapad`.
- `cento bridge check` returned `remote_status: ok`.
- `cento gather-context` returned Linux status `0`.
- `cento cluster status` returned `linux connected` and `macos connected`.

## Residual Risk

The current mitigation is manual. A future improvement should add a periodic stale-socket detector and append-only bridge repair ledger.
