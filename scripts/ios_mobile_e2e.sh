#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)

PROJECT="${CENTO_IOS_PROJECT:-$ROOT_DIR/apps/ios/CentoMobile/CentoMobile.xcodeproj}"
SCHEME="${CENTO_IOS_SCHEME:-CentoMobile}"
BUNDLE_ID="${CENTO_IOS_BUNDLE_ID:-com.willingtodev.CentoMobile}"
SIM_NAME="${CENTO_IOS_SIM_NAME:-iPhone 17}"
GATEWAY_URL="${CENTO_MOBILE_GATEWAY_URL:-http://10.0.0.56:47918}"
RUN_DIR="${CENTO_IOS_E2E_RUN_DIR:-$ROOT_DIR/workspace/runs/agent-work/26}"
DEVICE_ID="${CENTO_IOS_DEVICE_ID:-}"
RUN_PHYSICAL="${CENTO_IOS_E2E_PHYSICAL:-auto}"
export CENTO_MOBILE_GATEWAY_URL="$GATEWAY_URL"

LOG_DIR="$RUN_DIR/logs"
SCREENSHOT_DIR="$RUN_DIR/screenshots"
DEVICE_DIR="$RUN_DIR/devices"
mkdir -p "$LOG_DIR" "$SCREENSHOT_DIR" "$DEVICE_DIR"

summary="$RUN_DIR/summary.md"
: >"$summary"

log_step() {
  printf '\n== %s ==\n' "$1"
  printf '\n## %s\n\n' "$1" >>"$summary"
}

run_logged() {
  local name=$1
  shift
  printf '```bash\n' >>"$summary"
  printf '%q ' "$@" >>"$summary"
  printf '\n```\n\n' >>"$summary"
  "$@" 2>&1 | tee "$LOG_DIR/$name.log"
}

json_get_sim_udid() {
  local json_file=$1
  python3 -c '
import json, sys
name = sys.argv[2]
payload = json.load(open(sys.argv[1]))
for runtime, devices in payload.get("devices", {}).items():
    for device in devices:
        if device.get("name") == name and device.get("isAvailable", True):
            print(device["udid"])
            raise SystemExit(0)
raise SystemExit(f"no available simulator named {name!r}")
' "$json_file" "$SIM_NAME"
}

discover_physical_iphone() {
  xcrun xctrace list devices 2>/dev/null | python3 -c '
import re, sys
for line in sys.stdin:
    if line.startswith("iPhone ") or line.startswith("iPhone\t") or line.startswith("iPhone ("):
        match = re.search(r"\(([0-9A-F-]{25,})\)\s*$", line.strip())
        if match:
            print(match.group(1))
            raise SystemExit(0)
raise SystemExit(1)
'
}

log_step "Gateway Probe"
curl -sS -D "$LOG_DIR/gateway-health.headers" "$GATEWAY_URL/api/mobile/health" -o "$LOG_DIR/gateway-health.json"
python3 -m json.tool "$LOG_DIR/gateway-health.json" | tee "$LOG_DIR/gateway-health.pretty.json"
python3 -c '
import json, sys
payload = json.load(open(sys.argv[1]))
assert payload.get("ok") is True, payload
print("gateway health ok")
' "$LOG_DIR/gateway-health.json" | tee -a "$summary"

dashboard_status=$(
  curl -sS -w '%{http_code}' -D "$LOG_DIR/gateway-dashboard.headers" \
    "$GATEWAY_URL/api/mobile/dashboard" -o "$LOG_DIR/gateway-dashboard.json"
)
printf 'dashboard without token status: %s\n' "$dashboard_status" | tee -a "$summary"
if [[ -n "${CENTO_MOBILE_TOKEN:-}" ]]; then
  token_status=$(
    curl -sS -w '%{http_code}' -D "$LOG_DIR/gateway-dashboard-token.headers" \
      -H "X-Cento-Mobile-Token: $CENTO_MOBILE_TOKEN" \
      "$GATEWAY_URL/api/mobile/dashboard" -o "$LOG_DIR/gateway-dashboard-token.json"
  )
  printf 'dashboard with token status: %s\n' "$token_status" | tee -a "$summary"
  [[ "$token_status" == "200" ]]
  python3 -m json.tool "$LOG_DIR/gateway-dashboard-token.json" >"$LOG_DIR/gateway-dashboard-token.pretty.json"
else
  [[ "$dashboard_status" == "401" ]]
fi

log_step "Simulator Build"
xcrun simctl list devices available --json >"$DEVICE_DIR/simctl-devices.json"
SIM_UDID=$(json_get_sim_udid "$DEVICE_DIR/simctl-devices.json")
printf 'simulator: %s (%s)\n' "$SIM_NAME" "$SIM_UDID" | tee -a "$summary"

SIM_DERIVED_DATA="$RUN_DIR/DerivedData-simulator"
run_logged simulator-build \
  xcodebuild \
    -project "$PROJECT" \
    -scheme "$SCHEME" \
    -destination "platform=iOS Simulator,id=$SIM_UDID" \
    -derivedDataPath "$SIM_DERIVED_DATA" \
    build

SIM_APP="$SIM_DERIVED_DATA/Build/Products/Debug-iphonesimulator/$SCHEME.app"

log_step "Simulator Install And Launch"
xcrun simctl boot "$SIM_UDID" >/dev/null 2>&1 || true
xcrun simctl bootstatus "$SIM_UDID" -b | tee "$LOG_DIR/simulator-bootstatus.log"
xcrun simctl install "$SIM_UDID" "$SIM_APP" 2>&1 | tee "$LOG_DIR/simulator-install.log"

SIMCTL_CHILD_CENTO_MOBILE_GATEWAY_URL="$GATEWAY_URL" \
SIMCTL_CHILD_CENTO_MOBILE_TOKEN="${CENTO_MOBILE_TOKEN:-}" \
  xcrun simctl launch \
    --terminate-running-process \
    "$SIM_UDID" \
    "$BUNDLE_ID" \
    2>&1 | tee "$LOG_DIR/simulator-launch.log"
sleep 3
xcrun simctl io "$SIM_UDID" screenshot "$SCREENSHOT_DIR/native-dashboard-simulator-e2e.png" | tee "$LOG_DIR/simulator-screenshot.log"

if [[ "$RUN_PHYSICAL" != "0" && "$RUN_PHYSICAL" != "false" ]]; then
  log_step "Physical Device Build Install Launch"
  if [[ -z "$DEVICE_ID" ]]; then
    DEVICE_ID=$(discover_physical_iphone || true)
  fi

  if [[ -z "$DEVICE_ID" ]]; then
    printf 'No physical iPhone discovered; skipping physical path.\n' | tee -a "$summary"
  else
    printf 'physical iPhone: %s\n' "$DEVICE_ID" | tee -a "$summary"
    DEVICE_DERIVED_DATA="$RUN_DIR/DerivedData-device"
    run_logged device-build \
      xcodebuild \
        -project "$PROJECT" \
        -scheme "$SCHEME" \
        -destination "platform=iOS,id=$DEVICE_ID" \
        -derivedDataPath "$DEVICE_DERIVED_DATA" \
        -allowProvisioningUpdates \
        -allowProvisioningDeviceRegistration \
        build

    DEVICE_APP="$DEVICE_DERIVED_DATA/Build/Products/Debug-iphoneos/$SCHEME.app"
    xcrun devicectl device install app \
      --device "$DEVICE_ID" \
      "$DEVICE_APP" \
      --json-output "$LOG_DIR/device-install.json" \
      --log-output "$LOG_DIR/device-install.log"

    launch_env='{}'
    if [[ -n "${CENTO_MOBILE_TOKEN:-}" ]]; then
      launch_env=$(python3 -c 'import json, os; print(json.dumps({"CENTO_MOBILE_GATEWAY_URL": os.environ["CENTO_MOBILE_GATEWAY_URL"], "CENTO_MOBILE_TOKEN": os.environ["CENTO_MOBILE_TOKEN"]}))')
    else
      launch_env=$(python3 -c 'import json, os; print(json.dumps({"CENTO_MOBILE_GATEWAY_URL": os.environ["CENTO_MOBILE_GATEWAY_URL"]}))')
    fi
    xcrun devicectl device process launch \
      --device "$DEVICE_ID" \
      --terminate-existing \
      --environment-variables "$launch_env" \
      "$BUNDLE_ID" \
      --json-output "$LOG_DIR/device-launch.json" \
      --log-output "$LOG_DIR/device-launch.log"
    python3 - "$LOG_DIR/device-launch.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))

def redact(value):
    if isinstance(value, dict):
        return {key: ("<redacted>" if key == "CENTO_MOBILE_TOKEN" else redact(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str) and "CENTO_MOBILE_TOKEN" in value:
        try:
            parsed = json.loads(value)
        except Exception:
            return "<redacted launch environment>"
        return json.dumps(redact(parsed), sort_keys=True)
    return value

path.write_text(json.dumps(redact(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  fi
fi

printf '\nios mobile e2e ok: %s\n' "$RUN_DIR" | tee -a "$summary"
