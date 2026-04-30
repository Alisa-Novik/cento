import SwiftUI

struct ContentView: View {
    @StateObject private var api = MobileAPI()

    var body: some View {
        TabView {
            DashboardView(api: api)
                .tabItem { Label("Dashboard", systemImage: "square.grid.2x2") }

            IssuesView(api: api)
                .tabItem { Label("Issues", systemImage: "diamond") }

            JobsView(api: api)
                .tabItem { Label("Jobs", systemImage: "rectangle.stack") }

            AgentsView(agents: api.dashboard.agents)
                .tabItem { Label("Agents", systemImage: "command") }

            SettingsView(api: api)
                .tabItem { Label("Settings", systemImage: "gearshape") }
        }
        .tint(.orange)
        .preferredColorScheme(.dark)
        .task {
            await api.refresh()
        }
    }
}

struct DashboardView: View {
    @ObservedObject var api: MobileAPI

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    HealthCard(health: api.dashboard.health)
                    MetricGrid(health: api.dashboard.health)

                    SectionHeader("My Queue")
                    ForEach(api.dashboard.queue) { issue in
                        NavigationLink {
                            IssueDetailView(api: api, issue: issue)
                        } label: {
                            IssueRow(issue: issue)
                        }
                        .buttonStyle(.plain)
                    }

                    if let error = api.lastError {
                        Text(error)
                            .font(.footnote.weight(.semibold))
                            .foregroundStyle(.red)
                            .padding()
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(CardBackground())
                    }
                }
                .padding()
            }
            .background(AppBackground())
            .navigationTitle("Dashboard")
            .toolbar {
                Button {
                    Task { await api.refresh() }
                } label: {
                    Image(systemName: api.isLoading ? "hourglass" : "arrow.clockwise")
                }
            }
        }
    }
}

struct IssuesView: View {
    @ObservedObject var api: MobileAPI

    var body: some View {
        NavigationStack {
            List(api.dashboard.queue) { issue in
                NavigationLink {
                    IssueDetailView(api: api, issue: issue)
                } label: {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("#\(issue.id) \(issue.title)")
                            .font(.headline)
                        Text("\(issue.node) · \(issue.package)")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        StatusPill(issue.status)
                    }
                }
                .listRowBackground(Color.clear)
            }
            .scrollContentBackground(.hidden)
            .background(AppBackground())
            .navigationTitle("Issues")
        }
    }
}

struct JobsView: View {
    @ObservedObject var api: MobileAPI

    var body: some View {
        NavigationStack {
            List(api.dashboard.jobs) { job in
                NavigationLink {
                    JobDetailView(api: api, job: job)
                } label: {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(job.title)
                            .font(.headline)
                        Text("\(job.taskCount) steps · \(job.currentStep)")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        StatusPill(job.status)
                    }
                }
                .listRowBackground(Color.clear)
            }
            .scrollContentBackground(.hidden)
            .background(AppBackground())
            .navigationTitle("Jobs")
        }
    }
}

struct IssueDetailView: View {
    @ObservedObject var api: MobileAPI
    let issue: MobileIssue

    @State private var detail: MobileIssueDetail?
    @State private var error: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                HStack(alignment: .firstTextBaseline) {
                    Text("#\(issue.id)")
                        .font(.title.weight(.bold))
                    Spacer()
                    StatusPill(detail?.status ?? issue.status)
                }

                Text(detail?.subject ?? issue.title)
                    .font(.title2.weight(.semibold))

                if let detail {
                    DetailGrid(items: [
                        ("Node", detail.node),
                        ("Agent", detail.agent.isEmpty ? "-" : detail.agent),
                        ("Package", detail.package),
                        ("Done", "\(detail.doneRatio)%")
                    ])

                    if !detail.dispatch.isEmpty {
                        TextBlock(title: "Dispatch", text: detail.dispatch)
                    }
                    if !detail.validationReport.isEmpty {
                        TextBlock(title: "Validation", text: detail.validationReport)
                    }
                    TextBlock(title: "Description", text: detail.description)
                } else if let error {
                    TextBlock(title: "Error", text: error)
                } else {
                    ProgressView()
                        .frame(maxWidth: .infinity)
                        .padding()
                }
            }
            .padding()
        }
        .background(AppBackground())
        .navigationTitle("Issue")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            do {
                detail = try await api.fetchIssue(id: issue.id)
                error = nil
            } catch {
                self.error = error.localizedDescription
            }
        }
    }
}

struct JobDetailView: View {
    @ObservedObject var api: MobileAPI
    let job: MobileJob

    @State private var detail: MobileJobDetail?
    @State private var error: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                HStack(alignment: .firstTextBaseline) {
                    Text("Job")
                        .font(.title.weight(.bold))
                    Spacer()
                    StatusPill(detail?.status ?? job.status)
                }

                Text(detail?.title ?? job.title)
                    .font(.title2.weight(.semibold))

                if let detail {
                    DetailGrid(items: [
                        ("Tasks", "\(detail.taskCount)"),
                        ("Current", detail.currentStep),
                        ("Created", detail.createdAt ?? "-"),
                        ("Finished", detail.finishedAt ?? "-")
                    ])

                    if !detail.summaryTail.isEmpty {
                        TextBlock(title: "Summary Tail", text: detail.summaryTail.joined(separator: "\n"))
                    }

                    SectionHeader("Tasks")
                    ForEach(detail.tasks) { task in
                        JobTaskCard(task: task)
                    }

                    if !detail.artifacts.isEmpty {
                        SectionHeader("Artifacts")
                        ForEach(detail.artifacts) { artifact in
                            ArtifactRow(artifact: artifact)
                        }
                    }
                } else if let error {
                    TextBlock(title: "Error", text: error)
                } else {
                    ProgressView()
                        .frame(maxWidth: .infinity)
                        .padding()
                }
            }
            .padding()
        }
        .background(AppBackground())
        .navigationTitle("Job")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            do {
                detail = try await api.fetchJob(id: job.id)
                error = nil
            } catch {
                self.error = error.localizedDescription
            }
        }
    }
}

struct DetailGrid: View {
    let items: [(String, String)]

    var body: some View {
        VStack(spacing: 8) {
            ForEach(items, id: \.0) { label, value in
                HStack(alignment: .top) {
                    Text(label)
                        .font(.caption.weight(.bold))
                        .foregroundStyle(.secondary)
                        .frame(width: 72, alignment: .leading)
                    Text(value)
                        .font(.caption)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
        }
        .padding()
        .background(CardBackground())
    }
}

struct TextBlock: View {
    let title: String
    let text: String

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            SectionHeader(title)
            Text(text)
                .font(.caption.monospaced())
                .foregroundStyle(.secondary)
                .textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding()
        .background(CardBackground())
    }
}

struct JobTaskCard: View {
    let task: MobileJobTask

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(task.title)
                        .font(.headline)
                    Text("\(task.node) · \(task.id)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                StatusPill(task.returncode == 0 ? "ok" : "check")
            }

            if !task.scope.isEmpty {
                Text(task.scope)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            if !task.logTail.isEmpty {
                Text(task.logTail.suffix(18).joined(separator: "\n"))
                    .font(.caption2.monospaced())
                    .foregroundStyle(.secondary)
                    .textSelection(.enabled)
            }
        }
        .padding()
        .background(CardBackground())
    }
}

struct ArtifactRow: View {
    let artifact: MobileArtifact

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(artifact.name)
                    .font(.headline)
                Text("\(artifact.kind) · \(artifact.path)")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }
            Spacer()
            StatusPill(artifact.exists ? "exists" : "missing")
        }
        .padding()
        .background(CardBackground())
    }
}

struct AgentsView: View {
    let agents: [MobileAgent]

    var body: some View {
        NavigationStack {
            List(agents) { agent in
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(agent.name)
                            .font(.headline)
                        Text("\(agent.role) · \(agent.platform)")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    StatusPill(agent.state)
                }
                .listRowBackground(Color.clear)
            }
            .scrollContentBackground(.hidden)
            .background(AppBackground())
            .navigationTitle("Agents")
        }
    }
}

struct SettingsView: View {
    @ObservedObject var api: MobileAPI

    var body: some View {
        NavigationStack {
            Form {
                Section("Gateway") {
                    TextField("URL", text: $api.baseURL)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.URL)
                    SecureField("Token", text: $api.token)
                    Button("Refresh") {
                        Task { await api.refresh() }
                    }
                }
                Section("State") {
                    LabeledContent("Agents", value: "\(api.dashboard.health.agentsOnline)/\(api.dashboard.health.agentsTotal)")
                    LabeledContent("Issues", value: "\(api.dashboard.health.issuesOpen)")
                    LabeledContent("Jobs", value: "\(api.dashboard.health.jobsRunning)")
                }
            }
            .scrollContentBackground(.hidden)
            .background(AppBackground())
            .navigationTitle("Settings")
        }
    }
}

struct HealthCard: View {
    let health: MobileHealth

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(health.label)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                Text(health.state == "healthy" ? "Healthy" : "Needs Attention")
                    .font(.title2.weight(.bold))
            }
            Spacer()
            StatusPill(health.state == "healthy" ? "Healthy" : "Degraded")
        }
        .padding()
        .background(CardBackground())
    }
}

struct MetricGrid: View {
    let health: MobileHealth

    var body: some View {
        Grid(horizontalSpacing: 8, verticalSpacing: 8) {
            GridRow {
                MetricCell(value: "\(health.agentsOnline)/\(health.agentsTotal)", label: "Agents")
                MetricCell(value: "\(health.jobsRunning)", label: "Jobs")
                MetricCell(value: "\(health.issuesOpen)", label: "Issues")
                MetricCell(value: "\(health.tasksPending)", label: "Tasks")
            }
        }
    }
}

struct MetricCell: View {
    let value: String
    let label: String

    var body: some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.title2.weight(.bold))
            Text(label)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, minHeight: 64)
        .background(CardBackground())
    }
}

struct IssueRow: View {
    let issue: MobileIssue

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("#\(issue.id) \(issue.title)")
                    .font(.headline)
                Text("\(issue.node) · \(issue.package)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            StatusPill(issue.status)
        }
        .padding()
        .background(CardBackground())
    }
}

struct StatusPill: View {
    let value: String

    init(_ value: String) {
        self.value = value
    }

    var body: some View {
        Text(value)
            .font(.caption.weight(.bold))
            .foregroundStyle(color)
            .padding(.horizontal, 8)
            .padding(.vertical, 5)
            .background(color.opacity(0.14), in: RoundedRectangle(cornerRadius: 6))
    }

    private var color: Color {
        let lowered = value.lowercased()
        if lowered.contains("offline") || lowered.contains("blocked") || lowered.contains("degraded") {
            return .red
        }
        if lowered.contains("running") || lowered.contains("review") || lowered.contains("planned") {
            return .orange
        }
        return .green
    }
}

struct SectionHeader: View {
    let title: String

    init(_ title: String) {
        self.title = title
    }

    var body: some View {
        Text(title.uppercased())
            .font(.caption.weight(.bold))
            .foregroundStyle(.secondary)
    }
}

struct CardBackground: View {
    var body: some View {
        RoundedRectangle(cornerRadius: 8)
            .fill(.white.opacity(0.045))
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(.white.opacity(0.12), lineWidth: 1)
            )
    }
}

struct AppBackground: View {
    var body: some View {
        LinearGradient(colors: [Color(red: 0.04, green: 0.04, blue: 0.05), .black], startPoint: .top, endPoint: .bottom)
            .ignoresSafeArea()
    }
}

#Preview {
    ContentView()
}
