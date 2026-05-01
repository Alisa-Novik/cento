# Cento Mobile (iOS)

This folder contains the native SwiftUI companion app for Cento.

## Purpose

The app is the iOS implementation of the Cento mobile companion and consumes the existing Cento mobile gateway:

- Dashboard
- Issues queue
- Job details and artifacts
- Agents and health
- Gateway URL/token settings

## Prerequisites

- macOS with Xcode + iOS SDK
- A reachable Cento mobile gateway endpoint (`/api/mobile/*`)
- Optional: signing identity for device installs

## Build and run on simulator

From repo root:

```bash
cd apps/ios/CentoMobile
xcodebuild -project CentoMobile.xcodeproj -scheme CentoMobile -destination 'platform=iOS Simulator,name=iPhone 17' build
```

You can also run:

```bash
cd /home/alice/projects/cento
cento mobile e2e
```

`cento mobile e2e` performs gateway probing and installs/builds the app on the simulator. Add
`CENTO_IOS_E2E_PHYSICAL=false` to skip physical-device install attempts in non-physical environments.

## Configure gateway access

- Set `CENTO_MOBILE_GATEWAY_URL` to your mobile API URL.
- Set `CENTO_MOBILE_TOKEN` if the gateway requires token auth.
- Launch arguments/environment for simulator runs can pass these values directly.

Example:

```bash
CENTO_MOBILE_GATEWAY_URL="http://192.168.1.10:47918" \
CENTO_MOBILE_TOKEN="..." \
cento mobile e2e
```

## Run on a physical iPhone (optional)

1. Connect/trust an iPhone in Xcode.
2. Ensure signing settings in Xcode target are valid for your team/developer.
3. Use `CENTO_IOS_E2E_PHYSICAL=true` (default) and run `cento mobile e2e`.
4. Use `cento mobile watch-status` to validate companion watch readiness when needed.
