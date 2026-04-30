#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)

case "$(uname -s)" in
    Darwin) NODE_ID=macos ;;
    Linux) NODE_ID=linux ;;
    *) NODE_ID=$(uname -s | tr '[:upper:]' '[:lower:]') ;;
esac

OUTPUT=$("$ROOT_DIR/scripts/cento.sh" cluster activity --json "$NODE_ID")

CENTO_ACTIVITY_OUTPUT="$OUTPUT" python3 - "$NODE_ID" <<'PY'
import json
import os
import sys

node_id = sys.argv[1]
payload = json.loads(os.environ["CENTO_ACTIVITY_OUTPUT"])
nodes = payload.get("nodes")
assert isinstance(nodes, list), "nodes must be a list"
assert len(nodes) == 1, f"expected one node, got {len(nodes)}"
node = nodes[0]
assert node.get("node") == node_id, f"expected node {node_id}, got {node.get('node')}"
assert node.get("reachable") is True, "local node should be reachable"
assert isinstance(node.get("state"), str) and node["state"], "state must be non-empty"
assert isinstance(node.get("summary"), str) and node["summary"], "summary must be non-empty"
assert isinstance(node.get("tmux"), dict), "tmux must be an object"
assert isinstance(node.get("agents"), dict), "agents must be an object"
print(f"cluster activity json e2e passed for {node_id}")
PY
