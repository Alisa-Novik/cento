# Kanji a Day MVP

Standalone watchOS SwiftUI MVP for the daily kanji loop.

## Scope

- 3 embedded kanji: 日, 月, 火.
- Today screen.
- Stroke-order animation screen.
- Meaning screen.
- Local `UserDefaults` state for `currentIndex`, `streak`, and `lastOpenedDay`.

Out of scope for MVP: iPhone companion, translations, premium paywall, notifications, backend sync, and analytics.

## Build on macOS

```bash
xcodebuild \
  -project apps/watch/KanjiADay/KanjiADay.xcodeproj \
  -scheme KanjiADay \
  -destination 'platform=watchOS Simulator,name=Apple Watch Series 10 (46mm)' \
  build
```

This Linux node cannot run `xcodebuild`; use the Mac node or open the project in Xcode.
