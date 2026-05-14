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
    let reading: String
    let example: String
    let strokes: [KanjiStroke]
}

enum KanjiDataset {
    static let all: [DailyKanji] = [
        DailyKanji(
            id: "日",
            meaning: "sun, day",
            reading: "ニチ / ひ",
            example: "日曜日 - Sunday",
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
            reading: "ゲツ / つき",
            example: "月曜日 - Monday",
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
            reading: "カ / ひ",
            example: "火曜日 - Tuesday",
            strokes: [
                KanjiStroke(id: 1, points: [StrokePoint(x: 0.40, y: 0.26), StrokePoint(x: 0.24, y: 0.52)]),
                KanjiStroke(id: 2, points: [StrokePoint(x: 0.63, y: 0.24), StrokePoint(x: 0.76, y: 0.52)]),
                KanjiStroke(id: 3, points: [StrokePoint(x: 0.52, y: 0.16), StrokePoint(x: 0.50, y: 0.48), StrokePoint(x: 0.32, y: 0.84)]),
                KanjiStroke(id: 4, points: [StrokePoint(x: 0.52, y: 0.48), StrokePoint(x: 0.76, y: 0.84)])
            ]
        ),
        DailyKanji(
            id: "水",
            meaning: "water",
            reading: "スイ / みず",
            example: "水曜日 - Wednesday",
            strokes: [
                KanjiStroke(id: 1, points: [StrokePoint(x: 0.50, y: 0.16), StrokePoint(x: 0.50, y: 0.86)]),
                KanjiStroke(id: 2, points: [StrokePoint(x: 0.28, y: 0.36), StrokePoint(x: 0.42, y: 0.50), StrokePoint(x: 0.24, y: 0.72)]),
                KanjiStroke(id: 3, points: [StrokePoint(x: 0.70, y: 0.32), StrokePoint(x: 0.56, y: 0.52)]),
                KanjiStroke(id: 4, points: [StrokePoint(x: 0.55, y: 0.52), StrokePoint(x: 0.76, y: 0.80)])
            ]
        ),
        DailyKanji(
            id: "木",
            meaning: "tree, wood",
            reading: "モク / き",
            example: "木曜日 - Thursday",
            strokes: [
                KanjiStroke(id: 1, points: [StrokePoint(x: 0.24, y: 0.38), StrokePoint(x: 0.78, y: 0.38)]),
                KanjiStroke(id: 2, points: [StrokePoint(x: 0.51, y: 0.16), StrokePoint(x: 0.51, y: 0.86)]),
                KanjiStroke(id: 3, points: [StrokePoint(x: 0.50, y: 0.40), StrokePoint(x: 0.26, y: 0.78)]),
                KanjiStroke(id: 4, points: [StrokePoint(x: 0.52, y: 0.40), StrokePoint(x: 0.78, y: 0.78)])
            ]
        ),
        DailyKanji(
            id: "金",
            meaning: "gold, money",
            reading: "キン / かね",
            example: "金曜日 - Friday",
            strokes: [
                KanjiStroke(id: 1, points: [StrokePoint(x: 0.52, y: 0.14), StrokePoint(x: 0.28, y: 0.34)]),
                KanjiStroke(id: 2, points: [StrokePoint(x: 0.52, y: 0.14), StrokePoint(x: 0.78, y: 0.34)]),
                KanjiStroke(id: 3, points: [StrokePoint(x: 0.34, y: 0.38), StrokePoint(x: 0.70, y: 0.38)]),
                KanjiStroke(id: 4, points: [StrokePoint(x: 0.40, y: 0.54), StrokePoint(x: 0.64, y: 0.54)]),
                KanjiStroke(id: 5, points: [StrokePoint(x: 0.28, y: 0.72), StrokePoint(x: 0.76, y: 0.72)]),
                KanjiStroke(id: 6, points: [StrokePoint(x: 0.42, y: 0.58), StrokePoint(x: 0.34, y: 0.68)]),
                KanjiStroke(id: 7, points: [StrokePoint(x: 0.60, y: 0.58), StrokePoint(x: 0.70, y: 0.68)]),
                KanjiStroke(id: 8, points: [StrokePoint(x: 0.52, y: 0.38), StrokePoint(x: 0.52, y: 0.84)])
            ]
        ),
        DailyKanji(
            id: "土",
            meaning: "earth, soil",
            reading: "ド / つち",
            example: "土曜日 - Saturday",
            strokes: [
                KanjiStroke(id: 1, points: [StrokePoint(x: 0.28, y: 0.42), StrokePoint(x: 0.74, y: 0.42)]),
                KanjiStroke(id: 2, points: [StrokePoint(x: 0.51, y: 0.18), StrokePoint(x: 0.51, y: 0.76)]),
                KanjiStroke(id: 3, points: [StrokePoint(x: 0.22, y: 0.78), StrokePoint(x: 0.80, y: 0.78)])
            ]
        )
    ]
}
