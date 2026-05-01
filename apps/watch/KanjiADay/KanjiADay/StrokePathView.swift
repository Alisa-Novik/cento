import SwiftUI

struct StrokeShape: Shape {
    let points: [StrokePoint]

    func path(in rect: CGRect) -> Path {
        var path = Path()
        guard let first = points.first else {
            return path
        }
        path.move(to: CGPoint(x: first.x * rect.width, y: first.y * rect.height))
        for point in points.dropFirst() {
            path.addLine(to: CGPoint(x: point.x * rect.width, y: point.y * rect.height))
        }
        return path
    }
}

struct StrokePathView: View {
    let kanji: DailyKanji
    let activeStroke: Int
    let activeProgress: CGFloat

    var body: some View {
        ZStack {
            ForEach(kanji.strokes) { stroke in
                StrokeShape(points: stroke.points)
                    .trim(from: 0, to: trimAmount(for: stroke.id))
                    .stroke(
                        stroke.id <= activeStroke ? Color(red: 1.0, green: 0.34, blue: 0.22) : .white.opacity(0.24),
                        style: StrokeStyle(lineWidth: 8, lineCap: .round, lineJoin: .round)
                    )
            }
        }
        .aspectRatio(1, contentMode: .fit)
        .padding(.horizontal, 18)
        .padding(.vertical, 8)
        .accessibilityLabel("Stroke order for \(kanji.id)")
    }

    private func trimAmount(for id: Int) -> CGFloat {
        if id < activeStroke {
            return 1
        }
        if id == activeStroke {
            return activeProgress
        }
        return 0
    }
}
