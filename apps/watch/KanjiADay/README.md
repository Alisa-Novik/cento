# Kanji a Day MVP

Standalone watchOS SwiftUI MVP for the daily kanji loop.

## Scope

- 7 embedded beginner kanji: 日, 月, 火, 水, 木, 金, 土.
- Today screen.
- Stroke-order animation screen.
- Meaning screen with reading and example vocabulary.
- Local `UserDefaults` state for `currentIndex`, `streak`, and `lastOpenedDay`.
- Missed days reset the streak instead of counting as consecutive practice.

Out of scope for MVP: iPhone companion, translations, premium paywall, notifications, backend sync, and analytics.

## Build on macOS

```bash
xcodebuild \
  -project apps/watch/KanjiADay/KanjiADay.xcodeproj \
  -scheme KanjiADay \
  -destination 'platform=watchOS Simulator,name=Apple Watch Series 11 (46mm),OS=26.4' \
  build
```

Linux nodes cannot run `xcodebuild`; use the Mac node or open the project in Xcode.
