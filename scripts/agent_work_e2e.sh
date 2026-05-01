#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
CENTO="$ROOT_DIR/scripts/cento.sh"

export CENTO_BIN="$CENTO"
export CENTO_AGENT_WORK_BACKEND="${CENTO_AGENT_WORK_BACKEND:-replacement}"

title="Cento Agent Work E2E $(date +%Y%m%d-%H%M%S)"
evidence_path="$ROOT_DIR/workspace/runs/agent-work/e2e-validation-${title// /-}.txt"
story_path="$ROOT_DIR/workspace/runs/agent-work/e2e-story-${title// /-}.json"

mkdir -p "$ROOT_DIR/workspace/runs/agent-work"
cat > "$evidence_path" <<EOD
agent-work e2e evidence placeholder
status: running
backend: ${CENTO_AGENT_WORK_BACKEND}
EOD
cat > "$story_path" <<EOD
{
  "schema_version": "1.0",
  "issue": {
    "id": 0,
    "title": "$title",
    "package": "e2e"
  },
  "lane": {
    "owner": "e2e",
    "node": "linux",
    "agent": "e2e",
    "role": "builder"
  },
  "paths": {
    "run_dir": "workspace/runs/agent-work/e2e-draft"
  },
  "scope": {
    "acceptance": [
      "agent-work create requires and canonicalizes this story manifest"
    ]
  },
  "expected_outputs": [
    {
      "path": "${evidence_path#$ROOT_DIR/}",
      "description": "E2E validation evidence placeholder",
      "required": true,
      "owner": "e2e"
    }
  ]
}
EOD

"$CENTO" agent-work bootstrap >/dev/null

created_json=$(
  "$CENTO" agent-work create \
    --title "$title" \
    --manifest "$story_path" \
    --description "E2E probe for the Cento agent work tracker." \
    --node linux \
    --agent e2e \
    --package e2e \
    --json
)

issue_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$created_json")
[[ "$issue_id" =~ ^[0-9]+$ ]]

"$CENTO" agent-work claim "$issue_id" --node linux --agent e2e --note "E2E claimed." >/dev/null
"$CENTO" agent-work update "$issue_id" --status validating --note "E2E update path validated." >/dev/null
"$CENTO" agent-work update "$issue_id" --status running --note "E2E moved to running." >/dev/null
"$CENTO" agent-work dispatch "$issue_id" --node linux --agent e2e --dry-run | grep -F "issue-$issue_id-" >/dev/null
"$CENTO" agent-work validate "$issue_id" --result pass --evidence "$evidence_path" --note "E2E validation evidence." >/dev/null
done_json=$("$CENTO" agent-work update "$issue_id" --status done --note "E2E complete." --json)
status=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])' <<<"$done_json")
[[ "$status" == "Done" ]]

show_json=$("$CENTO" agent-work show "$issue_id" --json)
show_status=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])' <<<"$show_json")
[[ "$show_status" == "Done" ]]

list_json=$("$CENTO" agent-work list --all --json)
python3 -c 'import json,sys
issue_id = int(sys.argv[1])
title = sys.argv[2]
payload = json.load(sys.stdin)
payload_issues = payload.get("issues", payload)
for issue in payload_issues:
    if issue.get("id") == issue_id and issue.get("subject") == title and issue.get("status") == "Done":
        raise SystemExit(0)
raise SystemExit(f"missing closed E2E issue #{issue_id}: {title}")' "$issue_id" "$title" <<<"$list_json"

printf 'agent-work e2e ok: #%s %s\n' "$issue_id" "$title"
printf 'backend=%s evidence=%s\n' "${CENTO_AGENT_WORK_BACKEND}" "$evidence_path"
