# Agent Work 23 - Native SwiftUI Shell Validation

Generated: 2026-04-29

## Scope

Created the first native SwiftUI shell for the iPhone Cento app under:

```text
apps/ios/CentoMobile/
```

The app includes:

- Dashboard tab
- Issues tab
- Jobs tab
- Agents tab
- Settings tab for gateway URL/token
- Fixture data shaped like the Linux PWA gateway
- Live dashboard refresh path for `GET /api/mobile/dashboard`

## Simulator Build

Command:

```bash
xcodebuild \
  -project apps/ios/CentoMobile/CentoMobile.xcodeproj \
  -scheme CentoMobile \
  -destination 'platform=iOS Simulator,name=iPhone 17' \
  -derivedDataPath workspace/runs/agent-work/23/DerivedData \
  build
```

Result:

```text
BUILD SUCCEEDED
```

Build log:

```text
workspace/runs/agent-work/23/build-logs/simulator-build.log
```

## Simulator Launch

Installed and launched on explicit iPhone 17 simulator:

```text
52721F06-326E-4BB5-AC04-2055C05DA175
```

Bundle id:

```text
com.willingtodev.CentoMobile
```

Screenshot:

```text
workspace/runs/agent-work/23/screenshots/native-dashboard-simulator.png
```

## Physical Device Build

Device:

```text
iPhone 15 Pro Max
UDID: 00008130-000E68823E81001C
```

Command:

```bash
xcodebuild \
  -project apps/ios/CentoMobile/CentoMobile.xcodeproj \
  -scheme CentoMobile \
  -destination 'platform=iOS,id=00008130-000E68823E81001C' \
  -derivedDataPath workspace/runs/agent-work/23/DerivedData-device \
  -allowProvisioningUpdates \
  -allowProvisioningDeviceRegistration \
  build
```

Result:

```text
BUILD SUCCEEDED
```

Resolved signing:

```text
Development team: 3GS8534Z3V
Signing identity: Apple Development: willingtodev@gmail.com (MXM23F692J)
Provisioning profile: iOS Team Provisioning Profile: com.willingtodev.CentoMobile
Profile UUID: 635fcc82-ce3a-486d-b847-87c0e86673a0
```

Build logs:

```text
workspace/runs/agent-work/23/build-logs/device-build.log
workspace/runs/agent-work/23/build-logs/device-build-allow-provisioning.log
workspace/runs/agent-work/23/build-logs/device-build-register-device.log
workspace/runs/agent-work/23/build-logs/device-build-with-info-plist.log
```

## Physical Device Install

Command:

```bash
xcrun devicectl device install app \
  --device 00008130-000E68823E81001C \
  workspace/runs/agent-work/23/DerivedData-device/Build/Products/Debug-iphoneos/CentoMobile.app
```

Result:

```text
App installed
bundleID: com.willingtodev.CentoMobile
```

Install logs:

```text
workspace/runs/agent-work/23/devicectl/install-device.json
workspace/runs/agent-work/23/devicectl/install-device-after-plist.json
```

## Network Permissions

The physical app bundle includes:

```text
NSLocalNetworkUsageDescription
NSAppTransportSecurity.NSAllowsArbitraryLoads = true
```

This allows the native app to call the local Cento mobile gateway over LAN HTTP during development.

## Physical Device Launch

Command:

```bash
xcrun devicectl device process launch \
  --device 00008130-000E68823E81001C \
  --terminate-existing \
  com.willingtodev.CentoMobile
```

Result after trusting the developer profile on iPhone:

```text
Launched application with com.willingtodev.CentoMobile bundle identifier.
```

Launch log:

```text
workspace/runs/agent-work/23/devicectl/launch-device-after-trust.log
```
