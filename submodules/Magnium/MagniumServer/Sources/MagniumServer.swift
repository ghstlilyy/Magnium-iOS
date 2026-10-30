import Foundation
import CryptoKit
import SwiftSignalKit

// Where the Magnium server is. Empty until one exists; everything here then stays idle.
public enum MagniumServerConfiguration {
    private static let urlKey = "magnium.server.url"
    private static let tokenKey = "magnium.server.ownerToken"

    public static var baseUrl: URL? {
        get {
            guard let string = UserDefaults.standard.string(forKey: self.urlKey), !string.isEmpty else {
                return nil
            }
            return URL(string: string.hasSuffix("/") ? String(string.dropLast()) : string)
        }
    }

    public static var baseUrlString: String {
        get {
            return UserDefaults.standard.string(forKey: self.urlKey) ?? ""
        }
        set {
            UserDefaults.standard.set(newValue.trimmingCharacters(in: .whitespacesAndNewlines), forKey: self.urlKey)
        }
    }

    // Lets the owner issue badges (POST /v1/badges). Kept in UserDefaults: it is a scaffold, not a secret store.
    public static var ownerToken: String {
        get {
            return UserDefaults.standard.string(forKey: self.tokenKey) ?? ""
        }
        set {
            UserDefaults.standard.set(newValue.trimmingCharacters(in: .whitespacesAndNewlines), forKey: self.tokenKey)
        }
    }
}

public enum MagniumServerError: LocalizedError {
    case notConfigured
    case http(Int)
    case invalidResponse
    case checksumMismatch
    case transport(String)

    public var errorDescription: String? {
        switch self {
        case .notConfigured:
            return "Сервер Magnium не настроен"
        case let .http(code):
            return "Сервер ответил ошибкой \(code)"
        case .invalidResponse:
            return "Сервер прислал непонятный ответ"
        case .checksumMismatch:
            return "Файл плагина повреждён: контрольная сумма не совпала"
        case let .transport(text):
            return text
        }
    }
}

enum MagniumServerRequest {
    static func data(path: String, method: String = "GET", body: Data? = nil, token: String? = nil) -> Signal<Data, MagniumServerError> {
        return Signal { subscriber in
            guard let baseUrl = MagniumServerConfiguration.baseUrl, let url = URL(string: baseUrl.absoluteString + path) else {
                subscriber.putError(.notConfigured)
                return EmptyDisposable
            }
            var request = URLRequest(url: url, timeoutInterval: 20.0)
            request.httpMethod = method
            request.httpBody = body
            if body != nil {
                request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            }
            if let token, !token.isEmpty {
                request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
            }
            let task = URLSession.shared.dataTask(with: request) { data, response, error in
                if let error {
                    subscriber.putError(.transport(error.localizedDescription))
                    return
                }
                guard let response = response as? HTTPURLResponse else {
                    subscriber.putError(.invalidResponse)
                    return
                }
                guard (200 ..< 300).contains(response.statusCode) else {
                    subscriber.putError(.http(response.statusCode))
                    return
                }
                subscriber.putNext(data ?? Data())
                subscriber.putCompletion()
            }
            task.resume()
            return ActionDisposable {
                task.cancel()
            }
        }
    }
}

// MARK: Plugin catalog

public struct MagniumCatalogPlugin: Codable, Equatable {
    public struct Author: Codable, Equatable {
        public let name: String
        public let url: String?
    }

    public let id: String
    public let name: String
    public let version: String
    public let description: String?
    public let author: Author?
    public let iconUrl: String?
    public let downloadUrl: String
    public let sha256: String

    enum CodingKeys: String, CodingKey {
        case id, name, version, description, author, sha256
        case iconUrl = "icon_url"
        case downloadUrl = "download_url"
    }
}

public enum MagniumCatalog {
    // GET /v1/plugins -> {"plugins": [MagniumCatalogPlugin]}
    public static func plugins() -> Signal<[MagniumCatalogPlugin], MagniumServerError> {
        struct Response: Codable {
            let plugins: [MagniumCatalogPlugin]
        }
        return MagniumServerRequest.data(path: "/v1/plugins")
        |> mapToSignal { data -> Signal<[MagniumCatalogPlugin], MagniumServerError> in
            guard let response = try? JSONDecoder().decode(Response.self, from: data) else {
                return .fail(.invalidResponse)
            }
            return .single(response.plugins)
        }
    }

    // Downloads a plugin's .mpp into a temporary file, checking its SHA-256.
    public static func download(_ plugin: MagniumCatalogPlugin) -> Signal<URL, MagniumServerError> {
        return Signal { subscriber in
            guard let url = URL(string: plugin.downloadUrl) else {
                subscriber.putError(.invalidResponse)
                return EmptyDisposable
            }
            let task = URLSession.shared.downloadTask(with: url) { location, response, error in
                if let error {
                    subscriber.putError(.transport(error.localizedDescription))
                    return
                }
                guard let location, let data = try? Data(contentsOf: location) else {
                    subscriber.putError(.invalidResponse)
                    return
                }
                let digest = SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
                guard digest == plugin.sha256.lowercased() else {
                    subscriber.putError(.checksumMismatch)
                    return
                }
                let destination = FileManager.default.temporaryDirectory.appendingPathComponent("\(plugin.id).mpp")
                try? FileManager.default.removeItem(at: destination)
                do {
                    try data.write(to: destination)
                } catch let error {
                    subscriber.putError(.transport(error.localizedDescription))
                    return
                }
                subscriber.putNext(destination)
                subscriber.putCompletion()
            }
            task.resume()
            return ActionDisposable {
                task.cancel()
            }
        }
    }
}

// MARK: Badges

public struct MagniumBadge: Codable, Equatable, Hashable {
    public let id: String
    public let emoji: String
    public let title: String
    // Where the badge came from: "magnium" (server), "local" (issued here) or another provider's name.
    public var source: String

    public init(id: String, emoji: String, title: String, source: String) {
        self.id = id
        self.emoji = emoji
        self.title = title
        self.source = source
    }

    enum CodingKeys: String, CodingKey {
        case id, emoji, title, source
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.id = try container.decode(String.self, forKey: .id)
        self.emoji = try container.decode(String.self, forKey: .emoji)
        self.title = try container.decode(String.self, forKey: .title)
        self.source = (try? container.decode(String.self, forKey: .source)) ?? "magnium"
    }
}

// The badges the owner can issue; the server is expected to know the same ids.
public let magniumBadgePresets: [MagniumBadge] = [
    MagniumBadge(id: "founder", emoji: "👑", title: "Основатель Magnium", source: "local"),
    MagniumBadge(id: "developer", emoji: "🛠", title: "Разработчик", source: "local"),
    MagniumBadge(id: "plugin_author", emoji: "🧩", title: "Автор плагинов", source: "local"),
    MagniumBadge(id: "tester", emoji: "🧪", title: "Тестировщик", source: "local"),
    MagniumBadge(id: "supporter", emoji: "💎", title: "Поддержал проект", source: "local"),
    MagniumBadge(id: "early", emoji: "🌱", title: "С первых дней", source: "local"),
    MagniumBadge(id: "moderator", emoji: "🛡", title: "Модератор", source: "local"),
    MagniumBadge(id: "artist", emoji: "🎨", title: "Художник", source: "local"),
]

// A source of badges besides the Magnium server, e.g. another client's public badge list.
// Register one with MagniumBadges.register(provider:); its badges are shown under its name.
public protocol MagniumBadgeProvider: AnyObject {
    var name: String { get }
    // Returns badges by Telegram user id.
    func fetchBadges() -> Signal<[Int64: [MagniumBadge]], NoError>
}

// GET /v1/badges -> {"badges": {"<user id>": [MagniumBadge]}}
final class MagniumServerBadgeProvider: MagniumBadgeProvider {
    let name = "magnium"

    func fetchBadges() -> Signal<[Int64: [MagniumBadge]], NoError> {
        struct Response: Codable {
            let badges: [String: [MagniumBadge]]
        }
        return MagniumServerRequest.data(path: "/v1/badges")
        |> map { data -> [Int64: [MagniumBadge]] in
            guard let response = try? JSONDecoder().decode(Response.self, from: data) else {
                return [:]
            }
            var result: [Int64: [MagniumBadge]] = [:]
            for (key, badges) in response.badges {
                if let userId = Int64(key) {
                    result[userId] = badges.map { badge in
                        var badge = badge
                        badge.source = "magnium"
                        return badge
                    }
                }
            }
            return result
        }
        |> `catch` { _ -> Signal<[Int64: [MagniumBadge]], NoError> in
            return .single([:])
        }
    }
}

public final class MagniumBadges {
    public static let shared = MagniumBadges()

    private let lock = NSLock()
    private var remote: [String: [Int64: [MagniumBadge]]] = [:]
    private var providers: [MagniumBadgeProvider] = [MagniumServerBadgeProvider()]
    private let disposables = DisposableSet()
    private static let localKey = "magnium.badges.local"

    // Badges issued on this device, by user id (shown here even without a server).
    private var local: [Int64: [MagniumBadge]] {
        get {
            guard let data = UserDefaults.standard.data(forKey: MagniumBadges.localKey), let decoded = try? JSONDecoder().decode([String: [MagniumBadge]].self, from: data) else {
                return [:]
            }
            var result: [Int64: [MagniumBadge]] = [:]
            for (key, badges) in decoded {
                if let userId = Int64(key) {
                    result[userId] = badges
                }
            }
            return result
        }
        set {
            var encoded: [String: [MagniumBadge]] = [:]
            for (userId, badges) in newValue {
                encoded["\(userId)"] = badges
            }
            UserDefaults.standard.set(try? JSONEncoder().encode(encoded), forKey: MagniumBadges.localKey)
        }
    }

    public func register(provider: MagniumBadgeProvider) {
        self.lock.lock()
        self.providers.append(provider)
        self.lock.unlock()
        self.refresh()
    }

    // Re-fetches every provider; cheap to call on launch and when the server address changes.
    public func refresh() {
        self.lock.lock()
        let providers = self.providers
        self.lock.unlock()
        for provider in providers {
            let name = provider.name
            self.disposables.add(provider.fetchBadges().start(next: { [weak self] badges in
                guard let self else {
                    return
                }
                self.lock.lock()
                self.remote[name] = badges
                self.lock.unlock()
            }))
        }
    }

    public func badges(userId: Int64) -> [MagniumBadge] {
        self.lock.lock()
        var result = self.remote.values.flatMap { $0[userId] ?? [] }
        self.lock.unlock()
        result.append(contentsOf: self.local[userId] ?? [])
        var seen = Set<String>()
        return result.filter { seen.insert($0.source + ":" + $0.id).inserted }
    }

    // Issues a badge: stored here at once, and sent to the server when the owner token is set.
    public func issue(_ badge: MagniumBadge, to userId: Int64) -> Signal<Void, MagniumServerError> {
        var local = self.local
        var badges = local[userId] ?? []
        if !badges.contains(where: { $0.id == badge.id }) {
            badges.append(MagniumBadge(id: badge.id, emoji: badge.emoji, title: badge.title, source: "local"))
        }
        local[userId] = badges
        self.local = local

        let token = MagniumServerConfiguration.ownerToken
        if MagniumServerConfiguration.baseUrl == nil || token.isEmpty {
            return .single(Void())
        }
        let body = try? JSONSerialization.data(withJSONObject: ["user_id": userId, "badge_id": badge.id])
        return MagniumServerRequest.data(path: "/v1/badges", method: "POST", body: body, token: token)
        |> map { _ in Void() }
    }

    public func revoke(badgeId: String, from userId: Int64) {
        var local = self.local
        local[userId] = (local[userId] ?? []).filter { $0.id != badgeId }
        self.local = local
    }
}
