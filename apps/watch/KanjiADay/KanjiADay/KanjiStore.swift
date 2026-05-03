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

    var currentPosition: Int {
        (progress.currentIndex % KanjiDataset.all.count) + 1
    }

    var totalCount: Int {
        KanjiDataset.all.count
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
        let elapsedDays = max(Self.daysBetween(progress.lastOpenedDay, today), 1)
        progress.currentIndex = (progress.currentIndex + elapsedDays) % KanjiDataset.all.count
        progress.streak = elapsedDays == 1 ? progress.streak + 1 : 1
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

    private static func daysBetween(_ startKey: String, _ endKey: String) -> Int {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = .current
        formatter.dateFormat = "yyyy-MM-dd"

        guard
            let startDate = formatter.date(from: startKey),
            let endDate = formatter.date(from: endKey)
        else {
            return 1
        }

        let calendar = Calendar(identifier: .gregorian)
        return calendar.dateComponents([.day], from: startDate, to: endDate).day ?? 1
    }
}
