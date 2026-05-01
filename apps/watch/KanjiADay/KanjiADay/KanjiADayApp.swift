import SwiftUI

@main
struct KanjiADayApp: App {
    @StateObject private var store = KanjiStore()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(store)
        }
    }
}
