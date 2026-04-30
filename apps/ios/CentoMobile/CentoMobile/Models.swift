import Foundation

struct MobileDashboard: Decodable {
    let updatedAt: String
    let health: MobileHealth
    let queue: [MobileIssue]
    let jobs: [MobileJob]
    let agents: [MobileAgent]

    enum CodingKeys: String, CodingKey {
        case updatedAt = "updated_at"
        case health
        case queue
        case jobs
        case agents
    }
}

struct MobileHealth: Decodable {
    let label: String
    let state: String
    let agentsOnline: Int
    let agentsTotal: Int
    let jobsRunning: Int
    let issuesOpen: Int
    let tasksPending: Int

    enum CodingKeys: String, CodingKey {
        case label
        case state
        case agentsOnline = "agents_online"
        case agentsTotal = "agents_total"
        case jobsRunning = "jobs_running"
        case issuesOpen = "issues_open"
        case tasksPending = "tasks_pending"
    }
}

struct MobileIssue: Identifiable, Decodable {
    let id: Int
    let title: String
    let status: String
    let node: String
    let package: String
}

struct MobileJob: Identifiable, Decodable {
    let id: String
    let title: String
    let status: String
    let taskCount: Int
    let currentStep: String

    enum CodingKeys: String, CodingKey {
        case id
        case title
        case status
        case taskCount = "task_count"
        case currentStep = "current_step"
    }
}

struct MobileAgent: Identifiable, Decodable {
    let id: String
    let name: String
    let role: String
    let platform: String
    let state: String
}

struct MobileIssueEnvelope: Decodable {
    let updatedAt: String
    let issue: MobileIssueDetail

    enum CodingKeys: String, CodingKey {
        case updatedAt = "updated_at"
        case issue
    }
}

struct MobileIssueDetail: Identifiable, Decodable {
    let id: Int
    let subject: String
    let description: String
    let project: String
    let tracker: String
    let status: String
    let isClosed: Bool
    let doneRatio: Int
    let updatedOn: String?
    let closedOn: String?
    let node: String
    let agent: String
    let role: String
    let package: String
    let dispatch: String
    let validationReport: String

    enum CodingKeys: String, CodingKey {
        case id
        case subject
        case description
        case project
        case tracker
        case status
        case isClosed = "is_closed"
        case doneRatio = "done_ratio"
        case updatedOn = "updated_on"
        case closedOn = "closed_on"
        case node
        case agent
        case role
        case package
        case dispatch
        case validationReport = "validation_report"
    }
}

struct MobileJobEnvelope: Decodable {
    let updatedAt: String
    let job: MobileJobDetail

    enum CodingKeys: String, CodingKey {
        case updatedAt = "updated_at"
        case job
    }
}

struct MobileJobDetail: Identifiable, Decodable {
    let id: String
    let title: String
    let status: String
    let createdAt: String?
    let finishedAt: String?
    let summary: String?
    let taskCount: Int
    let currentStep: String
    let tasks: [MobileJobTask]
    let summaryTail: [String]
    let artifacts: [MobileArtifact]

    enum CodingKeys: String, CodingKey {
        case id
        case title
        case status
        case createdAt = "created_at"
        case finishedAt = "finished_at"
        case summary
        case taskCount = "task_count"
        case currentStep = "current_step"
        case tasks
        case summaryTail = "summary_tail"
        case artifacts
    }
}

struct MobileJobTask: Identifiable, Decodable {
    let id: String
    let node: String
    let title: String
    let scope: String
    let ownership: [String]
    let returncode: Int?
    let elapsedSeconds: Double?
    let log: String?
    let logExists: Bool?
    let logTail: [String]

    enum CodingKeys: String, CodingKey {
        case id
        case node
        case title
        case scope
        case ownership
        case returncode
        case elapsedSeconds = "elapsed_seconds"
        case log
        case logExists = "log_exists"
        case logTail = "log_tail"
    }
}

struct MobileArtifact: Identifiable, Decodable {
    var id: String { path }

    let name: String
    let kind: String
    let path: String
    let exists: Bool
    let size: Int?
    let updatedAt: String?

    enum CodingKeys: String, CodingKey {
        case name
        case kind
        case path
        case exists
        case size
        case updatedAt = "updated_at"
    }
}

extension MobileDashboard {
    static let fixture = MobileDashboard(
        updatedAt: "fixture",
        health: MobileHealth(
            label: "All Systems",
            state: "degraded",
            agentsOnline: 2,
            agentsTotal: 3,
            jobsRunning: 6,
            issuesOpen: 10,
            tasksPending: 3
        ),
        queue: [
            MobileIssue(id: 18, title: "Build first PWA/mobile gateway delivery", status: "Review", node: "linux", package: "iphone-cento-app-ios-creation"),
            MobileIssue(id: 21, title: "Add job logs and artifacts workflow to PWA", status: "Running", node: "linux", package: "iphone-cento-app-ios-creation"),
            MobileIssue(id: 23, title: "Native SwiftUI shell for simulator and device", status: "Running", node: "macos", package: "iphone-cento-app-ios-creation")
        ],
        jobs: [
            MobileJob(id: "mobile-gateway", title: "Cento Mobile Gateway", status: "running", taskCount: 4, currentStep: "Serving LAN PWA"),
            MobileJob(id: "native-shell", title: "Native SwiftUI Shell", status: "running", taskCount: 3, currentStep: "Simulator build")
        ],
        agents: [
            MobileAgent(id: "linux", name: "cento-linux", role: "workstation", platform: "linux", state: "online"),
            MobileAgent(id: "macos", name: "cento-macos", role: "workstation", platform: "macos", state: "online"),
            MobileAgent(id: "iphone", name: "cento-iphone", role: "companion", platform: "ios-ish", state: "offline")
        ]
    )
}
