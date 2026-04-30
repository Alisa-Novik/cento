#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
CENTO="$ROOT_DIR/scripts/cento.sh"

export CENTO_BIN="$CENTO"

title="Cento Agent Work E2E $(date +%Y%m%d-%H%M%S)"

"$CENTO" agent-work bootstrap >/dev/null

created_json=$(
  "$CENTO" agent-work create \
    --title "$title" \
    --description "E2E probe for the Cento agent work tracker." \
    --node linux \
    --agent e2e \
    --package e2e \
    --json
)

issue_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$created_json")
[[ "$issue_id" =~ ^[0-9]+$ ]]

"$CENTO" agent-work claim "$issue_id" --node linux --agent e2e --note "E2E claimed." >/dev/null
"$CENTO" agent-work validate "$issue_id" --result pass --node linux --agent e2e-validator --evidence scripts/agent_work_e2e.sh --note "E2E moved to review." >/dev/null
"$CENTO" agent-work dispatch "$issue_id" --node linux --agent e2e --dry-run | grep -F "issue-$issue_id-" >/dev/null

pool_title="Cento Agent Work Pool E2E $(date +%Y%m%d-%H%M%S)"
pool_json=$(
  "$CENTO" agent-work create \
    --title "$pool_title" \
    --description "E2E probe for dispatch-pool planning." \
    --node linux \
    --agent spark-e2e \
    --package e2e-pool \
    --json
)
pool_issue_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$pool_json")
pool_plan=$("$CENTO" agent-work dispatch-pool --package e2e-pool --limit 1 --json)
python3 -c 'import json,sys
issue_id = int(sys.argv[1])
payload = json.load(sys.stdin)
planned = payload.get("planned") or []
if payload.get("execute") is not False:
    raise SystemExit("dispatch-pool should default to plan-only")
if payload.get("count") != 1 or planned[0].get("issue") != issue_id:
    raise SystemExit(f"unexpected dispatch-pool plan: {payload}")
if "--runtime codex" not in planned[0].get("command", ""):
    raise SystemExit(f"missing codex runtime in plan: {planned[0]}")
' "$pool_issue_id" <<<"$pool_plan"
"$CENTO" agent-work update "$pool_issue_id" --status done --note "Dispatch-pool E2E complete." >/dev/null

done_json=$("$CENTO" agent-work update "$issue_id" --status done --note "E2E complete." --json)
status=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])' <<<"$done_json")
[[ "$status" == "Done" ]]

list_json=$("$CENTO" agent-work list --all --json)
python3 -c 'import json,sys
issue_id = int(sys.argv[1])
title = sys.argv[2]
payload = json.load(sys.stdin)
for issue in payload["issues"]:
    if issue["id"] == issue_id and issue["subject"] == title and issue["status"] == "Done":
        raise SystemExit(0)
raise SystemExit(f"missing closed E2E issue #{issue_id}: {title}")' "$issue_id" "$title" <<<"$list_json"

printf 'agent-work e2e ok: #%s %s\n' "$issue_id" "$title"
