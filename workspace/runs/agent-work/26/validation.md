# Agent Work 26 - Native iOS E2E Harness

Generated: 2026-04-29

## Scope

Added a repeatable Mac-side e2e script for the native Cento iOS app:

```text
scripts/ios_mobile_e2e.sh
```

The harness verifies:

- Mobile gateway health from the Mac
- Expected dashboard token gate when no token is configured
- Simulator build
- Simulator boot/install/launch
- Simulator screenshot capture
- Physical iPhone discovery, build, install, and launch when connected

The app now accepts gateway configuration from launch environment/defaults:

```text
CENTO_MOBILE_GATEWAY_URL
CENTO_MOBILE_TOKEN
CentoGatewayURL
CentoGatewayToken
```

## E2E Command

```bash
scripts/ios_mobile_e2e.sh
```

Promoted Cento CLI route:

```bash
cento mobile e2e
```

Helper to fetch the current gateway token from the Linux node:

```bash
cento mobile token-from-linux
```

Optional live-auth command when the gateway token is available:

```bash
CENTO_MOBILE_TOKEN=... scripts/ios_mobile_e2e.sh
```

Optional simulator-only command:

```bash
CENTO_IOS_E2E_PHYSICAL=false scripts/ios_mobile_e2e.sh
```

## Result

The first full run completed successfully:

```text
ios mobile e2e ok: /Users/anovik-air/cento/workspace/runs/agent-work/26
```

A token-backed run also completed successfully. It verified:

```text
dashboard without token status: 401
dashboard with token status: 200
```

The simulator screenshot now shows live decoded gateway data:

```text
agents: 2/3
jobs: 6
issues: 14
tasks: 2
first queue item: #13 Test task
```

The same token-backed run completed the physical iPhone build/install/launch path.

## Cento CLI Promotion

Added a Mac-side `mobile` tool entry in `data/tools.json` and wired it through:

```text
cento mobile e2e
cento mobile token-from-linux
cento mobile docs
```

The `cento mobile e2e` command runs `scripts/ios_mobile_e2e.sh`. When `CENTO_MOBILE_TOKEN`
is not already set, it attempts to fetch the token from the Linux gateway state through
the Cento bridge. If that bridge path is unavailable, the harness still runs the
unauthenticated token-gate validation path instead of failing before build/install checks.

Validation:

```text
python3 -m json.tool data/tools.json
cento mobile docs
cento tools | rg '^mobile\s'
CENTO_IOS_E2E_PHYSICAL=false cento mobile e2e
```

Result:

```text
tools JSON valid
mobile tool registered
simulator build/install/launch succeeded through cento mobile e2e
```

## Native Drilldowns

Added native SwiftUI issue/job drilldowns:

- Queue and Issues rows now open issue detail screens.
- Jobs rows now open job detail screens.
- `MobileAPI` can fetch `GET /api/mobile/issues/{id}` and `GET /api/mobile/jobs/{id}`.
- The issue detail screen renders status, node/agent/package metadata, dispatch state,
  validation report, and description.
- The job detail screen renders summary, step/task progress, task log tails, and artifacts.

Focused simulator build:

```bash
xcodebuild \
  -project apps/ios/CentoMobile/CentoMobile.xcodeproj \
  -scheme CentoMobile \
  -destination 'platform=iOS Simulator,name=iPhone 17' \
  -derivedDataPath workspace/runs/agent-work/26/DerivedData-detail \
  build
```

Result:

```text
BUILD SUCCEEDED
```

Build log:

```text
workspace/runs/agent-work/26/logs/detail-screens-build.log
```

## Latest Physical Device Check

After unlocking the connected iPhone, the promoted e2e route completed the full
physical-device path:

```text
cento mobile e2e
```

Result:

```text
dashboard without token status: 401
dashboard with token status: 200
simulator build/install/launch succeeded
physical iPhone build succeeded
physical iPhone install succeeded
Launched application with com.willingtodev.CentoMobile bundle identifier.
ios mobile e2e ok: /Users/anovik-air/cento/workspace/runs/agent-work/26
```

## Residual Risk

`cento mobile token-from-linux` depends on the current Cento bridge/socket path to the
Linux node. It was available for the latest promoted physical e2e run. If that bridge
path is unavailable later, the promoted CLI route falls back to the unauthenticated
token-gate path instead of failing before build/install checks.

## Artifacts

```text
workspace/runs/agent-work/26/summary.md
workspace/runs/agent-work/26/logs/gateway-health.json
workspace/runs/agent-work/26/logs/gateway-dashboard.json
workspace/runs/agent-work/26/logs/simulator-build.log
workspace/runs/agent-work/26/logs/simulator-install.log
workspace/runs/agent-work/26/logs/simulator-launch.log
workspace/runs/agent-work/26/logs/device-build.log
workspace/runs/agent-work/26/logs/device-install.json
workspace/runs/agent-work/26/logs/device-launch.json
workspace/runs/agent-work/26/logs/detail-screens-build.log
workspace/runs/agent-work/26/screenshots/native-dashboard-simulator-e2e.png
```

## Observations

The unauthenticated gateway path is working as designed: health returns 200 and dashboard returns 401 with `token_required`.

Without `CENTO_MOBILE_TOKEN`, the app launches and keeps fixture dashboard data with a visible `Gateway token required` error. With the token set, the app decodes and renders the live dashboard payload.

The e2e harness redacts `CENTO_MOBILE_TOKEN` from `devicectl` JSON output after physical launches because `devicectl` records launch environment in `device-launch.json`.
