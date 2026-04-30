# Cluster Health E2E

Generated: 2026-04-30T02:08:01Z

Validated from macOS:

- bridge mesh status is readable
- cluster status can evaluate Linux reachability
- `cento cluster exec linux -- 'cd ... && ...'` handles quoted shell commands
- `cento cluster exec linux -- printf ...` handles argv-style commands
- `cento bridge to-linux -- 'cd ... && ...'` handles quoted shell commands

Logs:

- `logs/mesh-status.log`
- `logs/cluster-status.log`
- `logs/cluster-exec-quoted.log`
- `logs/cluster-exec-argv.log`
- `logs/bridge-to-linux-quoted.log`
