# Local iPhone Delivery Roadmap

## Current Environment Finding

The Linux workstation cannot build iOS apps because it has no Apple toolchain. The configured Cento bridge can reach the Mac, but the Mac currently has only Command Line Tools, not full Xcode, and has no valid code signing identities.

Practical consequence: a real native iPhone install is blocked until full Xcode and signing are configured on the Mac. A local web/PWA link can be delivered earlier.

## Apple Distribution Facts To Respect

- Running on a physical device requires Xcode device support, signing, and device trust/developer mode.
- Xcode automatic signing can create a development profile after an Apple account/team is selected.
- Ad hoc distribution requires an App ID, distribution certificate, and registered devices.
- TestFlight requires uploading a build to App Store Connect and is the cleanest "link" style beta path after Apple Developer Program setup.

Official references:

- Running on device: https://developer.apple.com/documentation/xcode/running-your-app-in-simulator-or-on-a-device
- Registered device distribution: https://developer.apple.com/documentation/xcode/distributing-your-app-to-registered-devices
- Ad hoc profiles: https://developer.apple.com/help/account/provisioning-profiles/create-an-ad-hoc-provisioning-profile
- TestFlight overview: https://developer.apple.com/help/app-store-connect/test-a-beta-version/testflight-overview

## Phase 0 - Planning Packet

Status: complete for issue #16.

Deliverables:

- Requirements.
- Architecture.
- Roadmap.
- Validation evidence.
- Captain's notes.
- Redmine update to Review.

Validation:

- Confirmed Redmine #16 exists and is Running.
- Confirmed Cento source paths and data contracts.
- Confirmed bridge and Xcode constraint.

## Phase 1 - Fastest Usable Phone Surface

Goal: give the iPhone a dumb link before native signing is ready.

Build:

- `cento mobile serve --host 0.0.0.0 --port 47916`
- No-build responsive PWA using the mockup screens.
- Gateway reads existing jobs/network/dashboard state.
- Add to Home Screen from Safari.

Stories:

- Mobile gateway read-only dashboard.
- PWA dashboard/issue/job/agents shell.
- Token setup page.
- Screenshot capture using Playwright mobile viewport.

Validation:

- `python3 -m py_compile scripts/mobile_gateway.py`
- Browser smoke for `/`, `/api/mobile/dashboard`, `/api/mobile/jobs`, `/api/mobile/agents`.
- Playwright screenshots for dashboard, issue detail, job detail, logs, artifacts, agents, quick actions, more.

User install:

1. Connect iPhone to same network/VPN/bridge path.
2. Open `http://<linux-lan-ip>:47916/`.
3. Share -> Add to Home Screen.

## Phase 2 - Native SwiftUI App Skeleton

Goal: create the Xcode-ready app while Xcode install is being handled.

Build:

- New isolated app project, likely outside dirty Cento root or under `apps/ios/CentoMobile` once approved.
- SwiftUI bottom-tab shell matching the provided screens.
- Mock DTO fixture mode for screenshots before backend wiring.
- API client abstraction with base URL/token settings.

Validation after Xcode is installed:

- `xcodebuild -scheme CentoMobile -destination 'platform=iOS Simulator,name=iPhone 16' test`
- Simulator screenshots for every screen.

## Phase 3 - Native Backend Integration

Goal: app reads and acts on real Cento data.

Build:

- Wire Swift API client to `mobile_gateway.py`.
- Implement issue details and status/comment writes.
- Implement jobs, step progress, logs, artifacts.
- Implement agents and quick actions.
- Implement settings/token storage in Keychain.

Validation:

- Gateway fixtures and live local smoke.
- iOS UI tests against fixture server.
- Physical device smoke: dashboard, issue #16, job logs, notification test.

## Phase 4 - Local Physical iPhone Install

Goal: run the native app on the user's iPhone through Xcode with minimal manual steps.

Prerequisites:

- Install full Xcode on the Mac.
- Run: `sudo xcode-select -s /Applications/Xcode.app/Contents/Developer`
- Open Xcode once and accept/install components.
- Add Apple account/team in Xcode settings.
- Connect iPhone to Mac, trust the computer, enable Developer Mode.
- Enable automatic signing in the project.

Build command target:

```bash
cento bridge to-mac -- 'cd /Users/anovik-air/cento/apps/ios/CentoMobile && xcodebuild -scheme CentoMobile -destination "platform=iOS,id=<DEVICE_ID>" build'
```

Manual install fallback:

- Open project in Xcode.
- Select connected iPhone.
- Press Run.

## Phase 5 - Minimal Link Distribution

Goal: provide the simplest install link after native build is working.

Preferred: TestFlight

- Requires Apple Developer Program and App Store Connect app record.
- Upload archive from Xcode.
- Add internal tester.
- User installs through TestFlight invite/link.

Alternative: ad hoc IPA for registered device

- Requires paid developer account, registered iPhone UDID, distribution certificate, and ad hoc provisioning profile.
- More fragile than TestFlight for one-user iteration.

Not recommended for this project:

- Arbitrary sideloading routes. They add avoidable signing/support risk and do not match a reliable operational tool.

## Delivery Evidence Standard

Every implementation story must attach:

- story id and Redmine issue id
- changed files
- command validation output
- screenshot paths for UI stories
- artifact paths for logs/build output
- known limitations

Preferred artifact directory pattern:

```text
workspace/runs/agent-work/<issue-id>/
  validation.md
  screenshots/
  build-logs/
  artifacts/
```
