# Apple Watch Readiness Evidence

Generated: 2026-04-30T02:27:00Z

Ticket: #22 iPhone Cento App: Apple Watch pairing and watchOS readiness

## Result

The Apple Watch path is no longer invisible to Xcode tooling:

- `xcrun devicectl list devices` sees the physical iPhone as `available (paired)`.
- `cento mobile watch-status` sees the physical Apple Watch, but Developer Mode/DDI is not ready yet.
- `xcrun devicectl list devices` sees the physical Apple Watch as an Apple Watch Series 11 CoreDevice, but state is `unavailable`.
- `xcrun xctrace list devices` sees both physical devices under `Devices Offline`.
- The simulator watch path is ready: `simctl list pairs` reports an active, connected iPhone 17 + Apple Watch Ultra 3 pair.
- `xcodebuild -showdestinations` exposes the physical iPhone as an iOS destination for CentoMobile, but no physical watchOS destination is currently available because the app has no watchOS target and the Watch is unavailable.

## Evidence

- `logs/devicectl-devices.log`
- `logs/mobile-watch-status.log`
- `logs/xctrace-devices.log`
- `logs/simctl-pairs.log`
- `logs/xcodebuild-destinations.log`

## Current Blocker

The physical Apple Watch is discovered but unavailable/offline from Xcode's device stack. `cento mobile watch-status` reports Developer Mode disabled and DDI not ready for the Watch. The next hands-on step is to make the Watch available to Xcode: enable Developer Mode on the Watch, keep the Watch unlocked, near the paired iPhone, on charger if needed, and confirm trust prompts on the Watch and iPhone.

## Recommended Next Build Step

Once the physical Watch becomes available, add a minimal watchOS companion target to `apps/ios/CentoMobile/CentoMobile.xcodeproj` and verify `xcodebuild -showdestinations` exposes an iPhone + Apple Watch destination for the project.
