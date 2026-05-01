import Foundation

struct StrokePoint: Hashable {
    let x: Double
    let y: Double
}

struct KanjiStroke: Identifiable, Hashable {
    let id: Int
    let points: [StrokePoint]
}

struct DailyKanji: Identifiable, Hashable {
    let id: String
    let meaning: String
    let strokes: [KanjiStroke]
}

enum KanjiDataset {
    static let all: [DailyKanji] = [
        DailyKanji(
            id: "日",
            meaning: "sun, day",
            strokes: [
                KanjiStroke(id: 1, points: [StrokePoint(x: 0.30, y: 0.18), StrokePoint(x: 0.30, y: 0.82)]),
                KanjiStroke(id: 2, points: [StrokePoint(x: 0.30, y: 0.18), StrokePoint(x: 0.72, y: 0.18), StrokePoint(x: 0.72, y: 0.82)]),
                KanjiStroke(id: 3, points: [StrokePoint(x: 0.32, y: 0.50), StrokePoint(x: 0.70, y: 0.50)]),
                KanjiStroke(id: 4, points: [StrokePoint(x: 0.30, y: 0.82), StrokePoint(x: 0.72, y: 0.82)])
            ]
        ),
        DailyKanji(
            id: "月",
            meaning: "moon, month",
            strokes: [
                KanjiStroke(id: 1, points: [StrokePoint(x: 0.34, y: 0.16), StrokePoint(x: 0.34, y: 0.86)]),
                KanjiStroke(id: 2, points: [StrokePoint(x: 0.34, y: 0.16), StrokePoint(x: 0.72, y: 0.16), StrokePoint(x: 0.72, y: 0.86)]),
                KanjiStroke(id: 3, points: [StrokePoint(x: 0.36, y: 0.43), StrokePoint(x: 0.70, y: 0.43)]),
                KanjiStroke(id: 4, points: [StrokePoint(x: 0.36, y: 0.64), StrokePoint(x: 0.70, y: 0.64)])
            ]
        ),
        DailyKanji(
            id: "火",
            meaning: "fire",
            strokes: [
                KanjiStroke(id: 1, points: [StrokePoint(x: 0.40, y: 0.26), StrokePoint(x: 0.24, y: 0.52)]),
                KanjiStroke(id: 2, points: [StrokePoint(x: 0.63, y: 0.24), StrokePoint(x: 0.76, y: 0.52)]),
                KanjiStroke(id: 3, points: [StrokePoint(x: 0.52, y: 0.16), StrokePoint(x: 0.50, y: 0.48), StrokePoint(x: 0.32, y: 0.84)]),
                KanjiStroke(id: 4, points: [StrokePoint(x: 0.52, y: 0.48), StrokePoint(x: 0.76, y: 0.84)])
            ]
        )
    ]
}
