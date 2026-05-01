import SwiftUI

enum PracticeStep {
    case today
    case strokes
    case meaning
}

struct ContentView: View {
    @EnvironmentObject private var store: KanjiStore
    @State private var step: PracticeStep = .today
    @State private var activeStroke = 1
    @State private var activeProgress: CGFloat = 0

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            switch step {
            case .today:
                TodayView(
                    kanji: store.currentKanji,
                    streak: store.progress.streak,
                    onStart: startPractice
                )
            case .strokes:
                StrokePracticeView(
                    kanji: store.currentKanji,
                    activeStroke: activeStroke,
                    activeProgress: activeProgress,
                    onReplay: replayStrokes,
                    onDone: { step = .meaning }
                )
            case .meaning:
                MeaningView(
                    kanji: store.currentKanji,
                    streak: store.progress.streak,
                    onDone: {
                        store.markMeaningSeen()
                        step = .today
                    }
                )
            }
        }
    }

    private func startPractice() {
        step = .strokes
        replayStrokes()
    }

    private func replayStrokes() {
        activeStroke = 1
        activeProgress = 0
        animateStroke(index: 1)
    }

    private func animateStroke(index: Int) {
        guard index <= store.currentKanji.strokes.count else {
            return
        }
        activeStroke = index
        activeProgress = 0
        withAnimation(.easeInOut(duration: 0.55)) {
            activeProgress = 1
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.72) {
            animateStroke(index: index + 1)
        }
    }
}

struct TodayView: View {
    let kanji: DailyKanji
    let streak: Int
    let onStart: () -> Void

    var body: some View {
        VStack(spacing: 8) {
            HStack {
                Text("Today")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(.white.opacity(0.72))
                Spacer()
                Text("\(streak)d")
                    .font(.system(size: 13, weight: .bold))
                    .foregroundStyle(Color(red: 1.0, green: 0.34, blue: 0.22))
            }

            Spacer(minLength: 0)

            Text(kanji.id)
                .font(.system(size: 76, weight: .medium, design: .serif))
                .foregroundStyle(.white)
                .minimumScaleFactor(0.7)

            Text(kanji.meaning)
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(Color(red: 1.0, green: 0.34, blue: 0.22))

            Spacer(minLength: 4)

            Button(action: onStart) {
                Text("Let's learn")
                    .font(.system(size: 15, weight: .bold))
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(Color(red: 1.0, green: 0.34, blue: 0.22))
        }
        .padding(14)
    }
}

struct StrokePracticeView: View {
    let kanji: DailyKanji
    let activeStroke: Int
    let activeProgress: CGFloat
    let onReplay: () -> Void
    let onDone: () -> Void

    var body: some View {
        VStack(spacing: 6) {
            HStack {
                Text("\(min(activeStroke, kanji.strokes.count)) / \(kanji.strokes.count)")
                    .font(.system(size: 13, weight: .bold))
                    .foregroundStyle(Color(red: 1.0, green: 0.34, blue: 0.22))
                Spacer()
                Button(action: onReplay) {
                    Image(systemName: "arrow.clockwise")
                }
                .buttonStyle(.plain)
                .foregroundStyle(.white.opacity(0.8))
            }

            StrokePathView(kanji: kanji, activeStroke: activeStroke, activeProgress: activeProgress)

            Button(action: onDone) {
                Text(activeStroke >= kanji.strokes.count ? "Meaning" : "Skip")
                    .font(.system(size: 14, weight: .bold))
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(Color(red: 1.0, green: 0.34, blue: 0.22))
        }
        .padding(12)
    }
}

struct MeaningView: View {
    let kanji: DailyKanji
    let streak: Int
    let onDone: () -> Void

    var body: some View {
        VStack(spacing: 8) {
            Text("Meaning")
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(.white.opacity(0.72))

            Text(kanji.id)
                .font(.system(size: 56, weight: .medium, design: .serif))
                .foregroundStyle(.white)

            Text(kanji.meaning)
                .font(.system(size: 16, weight: .bold))
                .foregroundStyle(Color(red: 1.0, green: 0.34, blue: 0.22))

            Text("Current streak \(streak) day\(streak == 1 ? "" : "s")")
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(.white.opacity(0.64))

            Spacer(minLength: 0)

            Button(action: onDone) {
                Label("Got it", systemImage: "checkmark")
                    .font(.system(size: 14, weight: .bold))
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(Color(red: 1.0, green: 0.34, blue: 0.22))
        }
        .padding(14)
    }
}

#Preview {
    ContentView()
        .environmentObject(KanjiStore(defaults: .standard))
}
