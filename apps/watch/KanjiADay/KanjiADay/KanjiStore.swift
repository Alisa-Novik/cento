import Foundation

struct KanjiProgress: Codable {
    var currentIndex: Int
    var streak: Int
    var lastOpenedDay: String
}

@MainActor
final class KanjiStore: ObservableObject {
    @Published private(set) var progress: KanjiProgress

    private let defaults: UserDefaults
    private let storageKey = "kanji-a-day.progress.v1"

    var currentKanji: DailyKanji {
        KanjiDataset.all[progress.currentIndex % KanjiDataset.all.count]
    }

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        if
            let data = defaults.data(forKey: storageKey),
            let saved = try? JSONDecoder().decode(KanjiProgress.self, from: data)
        {
            progress = saved
        } else {
            progress = KanjiProgress(currentIndex: 0, streak: 1, lastOpenedDay: Self.dayKey(Date()))
        }
        advanceForTodayIfNeeded()
    }

    func markMeaningSeen() {
        save()
    }

    private func advanceForTodayIfNeeded(now: Date = Date()) {
        let today = Self.dayKey(now)
        guard progress.lastOpenedDay != today else {
            return
        }
        progress.currentIndex = (progress.currentIndex + 1) % KanjiDataset.all.count
        progress.streak += 1
        progress.lastOpenedDay = today
        save()
    }

    private func save() {
        guard let data = try? JSONEncoder().encode(progress) else {
            return
        }
        defaults.set(data, forKey: storageKey)
    }

    private static func dayKey(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = .current
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.string(from: date)
    }
}
