import Foundation

@MainActor
final class MobileAPI: ObservableObject {
    @Published var baseURL = "http://10.0.0.56:47918"
    @Published var token = ""
    @Published var dashboard = MobileDashboard.fixture
    @Published var lastError: String?
    @Published var isLoading = false

    init() {
        let defaults = UserDefaults.standard
        let environment = ProcessInfo.processInfo.environment

        if let configuredURL = firstConfigured(environment["CENTO_MOBILE_GATEWAY_URL"], defaults.string(forKey: "CentoGatewayURL")) {
            baseURL = configuredURL
        }
        if let configuredToken = firstConfigured(environment["CENTO_MOBILE_TOKEN"], defaults.string(forKey: "CentoGatewayToken")) {
            token = configuredToken
        }
    }

    private func firstConfigured(_ values: String?...) -> String? {
        values
            .compactMap { $0?.trimmingCharacters(in: .whitespacesAndNewlines) }
            .first { !$0.isEmpty }
    }

    private func gatewayRequest(path: String) throws -> URLRequest {
        guard let url = URL(string: baseURL.trimmingCharacters(in: .whitespacesAndNewlines) + path) else {
            throw URLError(.badURL)
        }

        var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 8)
        if !token.isEmpty {
            request.setValue(token, forHTTPHeaderField: "X-Cento-Mobile-Token")
        }
        return request
    }

    private func decode<T: Decodable>(_ type: T.Type, from path: String) async throws -> T {
        let (data, response) = try await URLSession.shared.data(for: gatewayRequest(path: path))
        if let http = response as? HTTPURLResponse, http.statusCode == 401 {
            throw GatewayError.tokenRequired
        }
        return try JSONDecoder().decode(type, from: data)
    }

    func refresh() async {
        UserDefaults.standard.set(baseURL, forKey: "CentoGatewayURL")
        UserDefaults.standard.set(token, forKey: "CentoGatewayToken")

        isLoading = true
        defer { isLoading = false }

        do {
            dashboard = try await decode(MobileDashboard.self, from: "/api/mobile/dashboard")
            lastError = nil
        } catch GatewayError.tokenRequired {
            lastError = "Gateway token required"
        } catch {
            lastError = error.localizedDescription
        }
    }

    func fetchIssue(id: Int) async throws -> MobileIssueDetail {
        try await decode(MobileIssueEnvelope.self, from: "/api/mobile/issues/\(id)").issue
    }

    func fetchJob(id: String) async throws -> MobileJobDetail {
        try await decode(MobileJobEnvelope.self, from: "/api/mobile/jobs/\(id)").job
    }
}

enum GatewayError: Error {
    case tokenRequired
}
