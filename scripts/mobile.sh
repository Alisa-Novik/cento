#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)

usage() {
    cat <<'USAGE'
Usage: cento mobile <command> [args...]

Commands:
  e2e [args...]          Run native iOS mobile e2e validation
  token-from-linux       Print the Linux mobile gateway token
  watch-status           Report Apple Watch physical/simulator readiness
  docs                  Show this help

Examples:
  cento mobile e2e
  CENTO_IOS_E2E_PHYSICAL=false cento mobile e2e
  CENTO_MOBILE_TOKEN="$(cento mobile token-from-linux)" cento mobile e2e
  cento mobile watch-status
USAGE
}

token_from_linux() {
    "$ROOT_DIR/scripts/cento.sh" bridge from-mac -- 'cd "$HOME/projects/cento" && cat workspace/runs/agent-work/18/state/token.txt'
}

watch_status() {
    local run_dir="${CENTO_WATCH_STATUS_DIR:-$ROOT_DIR/workspace/runs/agent-work/22}"
    local device_json="$run_dir/devices/devicectl-list.json"
    local sim_json="$run_dir/devices/simctl-devices.json"
    local xctrace_txt="$run_dir/devices/xctrace-devices.txt"

    mkdir -p "$run_dir/devices" "$run_dir/logs"

    printf '== Xcode ==\n'
    xcodebuild -version

    printf '\n== Physical Devices ==\n'
    if xcrun devicectl list devices --json-output "$device_json" >/dev/null 2>"$run_dir/logs/devicectl-list.err"; then
        jq -r '
            .result.devices[]
            | select(((.deviceProperties.name // .displayName // "") + " " + (.hardwareProperties.deviceType // "")) | test("watch|iphone"; "i"))
            | [
                (.deviceProperties.name // .displayName // "-"),
                (.identifier // "-"),
                (.connectionProperties.transportType // "-"),
                (.deviceProperties.developerModeStatus // "-"),
                ((if .deviceProperties.ddiServicesAvailable then "ddi" else "no-ddi" end) + "/" + (.deviceProperties.bootState // "-")),
                (.hardwareProperties.marketingName // .hardwareProperties.productType // "-")
              ]
            | @tsv
        ' "$device_json" | awk 'BEGIN { FS="\t"; printf "%-22s %-38s %-12s %-14s %-18s %s\n", "name", "id", "transport", "developer", "state", "model" } { printf "%-22s %-38s %-12s %-14s %-18s %s\n", $1, $2, $3, $4, $5, $6 }'
    else
        printf 'devicectl list failed; see %s\n' "$run_dir/logs/devicectl-list.err"
    fi

    printf '\n== Simulator Pairs ==\n'
    xcrun simctl list pairs | tee "$run_dir/devices/simctl-pairs.txt"

    printf '\n== Watch Simulators ==\n'
    xcrun simctl list devices --json > "$sim_json"
    jq -r '
        .devices
        | to_entries[]
        | .key as $runtime
        | .value[]
        | select((.name // "") | test("watch"; "i"))
        | [$runtime, .name, .udid, .state, (.availabilityError // "ok")]
        | @tsv
    ' "$sim_json" | awk 'BEGIN { FS="\t"; printf "%-42s %-34s %-38s %-10s %s\n", "runtime", "name", "udid", "state", "availability" } { printf "%-42s %-34s %-38s %-10s %s\n", $1, $2, $3, $4, $5 }'

    printf '\n== xctrace Destinations ==\n'
    xcrun xctrace list devices 2>&1 | tee "$xctrace_txt"

    printf '\n== Readiness Summary ==\n'
    if jq -e '.result.devices[] | select(((.deviceProperties.name // .displayName // "") + " " + (.hardwareProperties.deviceType // "")) | test("watch"; "i")) | select((.deviceProperties.developerModeStatus // "") == "enabled" and (.deviceProperties.ddiServicesAvailable // false) == true)' "$device_json" >/dev/null 2>&1; then
        printf 'physical watch: ready for Xcode destination validation\n'
    elif jq -e '.result.devices[] | select(((.deviceProperties.name // .displayName // "") + " " + (.hardwareProperties.deviceType // "")) | test("watch"; "i"))' "$device_json" >/dev/null 2>&1; then
        printf 'physical watch: visible, but Developer Mode/DDI is not ready yet\n'
        printf 'next manual step: enable Developer Mode on Apple Watch, keep it unlocked/nearby, then rerun cento mobile watch-status\n'
    else
        printf 'physical watch: not visible to CoreDevice\n'
    fi

    if xcrun simctl list pairs | grep -q 'active, connected'; then
        printf 'watch simulator pair: active and connected\n'
    else
        printf 'watch simulator pair: not active/connected\n'
    fi
}

main() {
    local command=${1:-docs}
    if [[ $# -gt 0 ]]; then
        shift
    fi

    case "$command" in
        e2e)
            if [[ -z "${CENTO_MOBILE_TOKEN:-}" ]]; then
                if token=$(token_from_linux 2>/dev/null) && [[ -n "$token" ]]; then
                    export CENTO_MOBILE_TOKEN="$token"
                else
                    printf 'warning: no CENTO_MOBILE_TOKEN available; e2e will validate the unauthenticated token gate only\n' >&2
                fi
            fi
            exec "$ROOT_DIR/scripts/ios_mobile_e2e.sh" "$@"
            ;;
        token-from-linux)
            token_from_linux
            ;;
        watch-status)
            watch_status
            ;;
        docs|help|-h|--help)
            usage
            ;;
        *)
            printf 'Unknown mobile command: %s\n\n' "$command" >&2
            usage >&2
            exit 2
            ;;
    esac
}

main "$@"
