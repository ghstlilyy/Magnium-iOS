import Foundation
import SwiftSignalKit
import MagniumPython

// What a plugin's manifest.json says about it, plus its state in this app.
public struct MagniumPluginInfo: Equatable {
    public let id: String
    public let name: String
    public let version: String
    public let description: String?
    public let authorName: String?
    public let authorUrl: String?
    // Absolute path of the icon inside the installed package; nil before installation.
    public let iconPath: String?
    public let isEnabled: Bool
    // Set when the plugin failed to load; holds the error or traceback.
    public let loadError: String?
}

// One item of a plugin's settings page (BasePlugin.create_settings()).
public struct MagniumPluginSettingOption: Equatable {
    public let value: String
    public let title: String
}

public enum MagniumPluginSettingItem: Equatable {
    case header(String)
    case text(String)
    case toggle(key: String, title: String, subtitle: String?, value: Bool)
    case selector(key: String, title: String, options: [MagniumPluginSettingOption], value: String)
    case input(key: String, title: String, placeholder: String, value: String)
    case button(key: String, title: String, isDestructive: Bool)
}

public enum MagniumHookStrategy: String {
    case `default`
    case modify
    case cancel
}

public struct MagniumHookResult {
    public let strategy: MagniumHookStrategy
    public let payload: Any?

    public static let unchanged = MagniumHookResult(strategy: .default, payload: nil)
}

public enum MagniumPluginError: LocalizedError {
    case runtimeUnavailable(String)
    case plugin(String)

    public var errorDescription: String? {
        switch self {
        case let .runtimeUnavailable(text), let .plugin(text):
            return text
        }
    }
}

// Owns the Python runtime and the installed plugins. All methods must be called on the main thread.
//
// A plugin is installed from a .mpp package (a zip with manifest.json at its root) and lives
// unpacked in Application Support/Magnium/plugins/<id>/; its own files go to data/<id>/.
public final class MagniumPluginManager {
    public static let shared = MagniumPluginManager()

    public static let packageExtension = "mpp"

    // Launches that ended before `healthyLaunchDelay` in a row; at `safeModeLaunchCount` plugins are not loaded.
    private static let safeModeLaunchCount = 3
    private static let healthyLaunchDelay = 15.0
    private static let manifestName = "manifest.json"

    private let fileManager = FileManager.default
    private let baseDirectory: URL
    private let pluginsDirectory: URL
    private let dataDirectory: URL
    private let stateFile: URL
    private let launchGuardFile: URL

    private var state = State()
    private var loadErrors: [String: String] = [:]
    private var hostMethods: [String: ([String: Any]) throws -> Any?] = [:]
    // magnium.set_interval timers, by interval id.
    private var intervals: [Int: Foundation.Timer] = [:]
    private var isStarted = false

    public private(set) var runtimeError: String?
    public private(set) var isInSafeMode = false

    // Bumped whenever a plugin's settings may have changed, so open settings pages re-read them.
    private var currentSettingsRevision = 0
    private let settingsRevisionPromise = ValuePromise<Int>(0, ignoreRepeated: true)
    public var settingsRevision: Signal<Int, NoError> {
        return self.settingsRevisionPromise.get()
    }

    // The in-app log: plugin output, errors and Magnium's own messages, newest last.
    private static let maxLogLines = 1000
    private let logLock = NSLock()
    private var logLines: [String] = []
    private var logRevision = 0
    private let logRevisionPromise = ValuePromise<Int>(0, ignoreRepeated: true)
    public var logUpdates: Signal<Int, NoError> {
        return self.logRevisionPromise.get()
    }

    private let pluginsPromise = ValuePromise<[MagniumPluginInfo]>([], ignoreRepeated: true)
    public var plugins: Signal<[MagniumPluginInfo], NoError> {
        return self.pluginsPromise.get()
    }

    private struct State: Codable {
        var enabled: [String: Bool] = [:]
    }

    private init() {
        let applicationSupport = self.fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        self.baseDirectory = applicationSupport.appendingPathComponent("Magnium", isDirectory: true)
        self.pluginsDirectory = self.baseDirectory.appendingPathComponent("plugins", isDirectory: true)
        self.dataDirectory = self.baseDirectory.appendingPathComponent("data", isDirectory: true)
        self.stateFile = self.baseDirectory.appendingPathComponent("state.json")
        self.launchGuardFile = self.baseDirectory.appendingPathComponent("launch-guard")
    }

    // Called first thing in application(_:didFinishLaunchingWithOptions:), so that plugins
    // can act before any Telegram UI exists.
    public func start() {
        assert(Thread.isMainThread)
        if self.isStarted {
            return
        }
        self.isStarted = true

        try? self.fileManager.createDirectory(at: self.pluginsDirectory, withIntermediateDirectories: true)
        try? self.fileManager.createDirectory(at: self.dataDirectory, withIntermediateDirectories: true)
        self.loadState()

        let unhealthyLaunches = (try? String(contentsOf: self.launchGuardFile, encoding: .utf8)).flatMap { Int($0) } ?? 0
        self.isInSafeMode = unhealthyLaunches >= MagniumPluginManager.safeModeLaunchCount
        try? "\(unhealthyLaunches + 1)".write(to: self.launchGuardFile, atomically: true, encoding: .utf8)
        DispatchQueue.main.asyncAfter(deadline: .now() + MagniumPluginManager.healthyLaunchDelay) { [weak self] in
            guard let self else {
                return
            }
            try? self.fileManager.removeItem(at: self.launchGuardFile)
        }

        self.registerBuiltinHostMethods()
        if self.startRuntime() && !self.isInSafeMode {
            for id in self.installedPluginIds() where self.state.enabled[id] ?? true {
                self.loadPlugin(id: id)
            }
        }
        self.publish()
        let _ = self.runHook("app_launch", payload: [:])
    }

    // Leaves safe mode for the next launch; plugins are loaded right away.
    public func exitSafeMode() {
        try? self.fileManager.removeItem(at: self.launchGuardFile)
        guard self.isInSafeMode else {
            return
        }
        self.isInSafeMode = false
        for id in self.installedPluginIds() where self.state.enabled[id] ?? true {
            self.loadPlugin(id: id)
        }
        self.publish()
    }

    // MARK: Plugins

    public static func isPackageFileName(_ fileName: String) -> Bool {
        return (fileName as NSString).pathExtension.lowercased() == MagniumPluginManager.packageExtension
    }

    // Validates a .mpp package and reads its manifest without running it, for the install confirmation.
    public func inspectPackage(at url: URL) throws -> MagniumPluginInfo {
        let metadata = try self.send(["command": "inspect", "path": url.path]) as? [String: String] ?? [:]
        guard let info = self.info(metadata: metadata, iconDirectory: nil) else {
            throw MagniumPluginError.plugin("The package has no valid manifest.json")
        }
        return info
    }

    // Unpacks a .mpp package (replacing an installed version of it), enables and loads it.
    @discardableResult
    public func installPackage(from url: URL) throws -> MagniumPluginInfo {
        let metadata = try self.send(["command": "install", "path": url.path, "plugins_path": self.pluginsDirectory.path]) as? [String: String] ?? [:]
        guard let id = metadata["id"] else {
            throw MagniumPluginError.plugin("The package has no valid manifest.json")
        }
        self.loadErrors.removeValue(forKey: id)
        self.state.enabled[id] = true
        self.saveState()
        if !self.isInSafeMode {
            self.loadPlugin(id: id)
        }
        self.publish()
        if let error = self.loadErrors[id] {
            throw MagniumPluginError.plugin(error)
        }
        guard let info = self.installedPlugin(id: id) else {
            throw MagniumPluginError.plugin("The plugin was not installed")
        }
        return info
    }

    public func setPluginEnabled(id: String, isEnabled: Bool) {
        self.state.enabled[id] = isEnabled
        self.saveState()
        if isEnabled {
            if !self.isInSafeMode {
                self.loadPlugin(id: id)
            }
        } else {
            self.unloadPlugin(id: id)
        }
        self.publish()
    }

    public func uninstallPlugin(id: String) {
        self.unloadPlugin(id: id)
        try? self.fileManager.removeItem(at: self.pluginDirectory(id: id))
        try? self.fileManager.removeItem(at: self.dataDirectory.appendingPathComponent(id, isDirectory: true))
        self.state.enabled.removeValue(forKey: id)
        self.loadErrors.removeValue(forKey: id)
        self.saveState()
        self.publish()
    }

    // MARK: Log

    // Thread-safe; may be called while Python holds the GIL, so it never waits for the main thread.
    public func log(_ line: String) {
        NSLog("[Magnium] \(line)")
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm:ss"
        let stamped = "\(formatter.string(from: Date())) \(line)"
        self.logLock.lock()
        self.logLines.append(stamped)
        if self.logLines.count > MagniumPluginManager.maxLogLines {
            self.logLines.removeFirst(self.logLines.count - MagniumPluginManager.maxLogLines)
        }
        self.logRevision += 1
        let revision = self.logRevision
        self.logLock.unlock()
        DispatchQueue.main.async {
            self.logRevisionPromise.set(revision)
        }
    }

    public func logText() -> String {
        self.logLock.lock()
        defer {
            self.logLock.unlock()
        }
        return self.logLines.joined(separator: "\n")
    }

    public func clearLog() {
        self.logLock.lock()
        self.logLines.removeAll()
        self.logRevision += 1
        let revision = self.logRevision
        self.logLock.unlock()
        self.logRevisionPromise.set(revision)
    }

    // MARK: Settings

    // The settings page of a running plugin; empty when it is disabled or has none.
    public func pluginSettings(id: String) -> [MagniumPluginSettingItem] {
        guard let items = (try? self.send(["command": "settings", "id": id])) as? [[String: Any]] else {
            return []
        }
        return items.compactMap { item -> MagniumPluginSettingItem? in
            switch item["type"] as? String {
            case "header":
                return (item["text"] as? String).map(MagniumPluginSettingItem.header)
            case "text":
                return (item["text"] as? String).map(MagniumPluginSettingItem.text)
            case "switch":
                guard let key = item["key"] as? String, let title = item["text"] as? String else {
                    return nil
                }
                return .toggle(key: key, title: title, subtitle: item["subtext"] as? String, value: item["value"] as? Bool ?? false)
            case "selector":
                guard let key = item["key"] as? String, let title = item["text"] as? String, let rawOptions = item["options"] as? [[String]] else {
                    return nil
                }
                let options = rawOptions.compactMap { option -> MagniumPluginSettingOption? in
                    return option.count == 2 ? MagniumPluginSettingOption(value: option[0], title: option[1]) : nil
                }
                return .selector(key: key, title: title, options: options, value: item["value"] as? String ?? "")
            case "input":
                guard let key = item["key"] as? String, let title = item["text"] as? String else {
                    return nil
                }
                return .input(key: key, title: title, placeholder: item["placeholder"] as? String ?? "", value: item["value"] as? String ?? "")
            case "button":
                guard let key = item["key"] as? String, let title = item["text"] as? String else {
                    return nil
                }
                return .button(key: key, title: title, isDestructive: item["destructive"] as? Bool ?? false)
            default:
                return nil
            }
        }
    }

    // `value` is a Bool for a switch and a String for a selector.
    public func updatePluginSetting(id: String, key: String, value: Any) {
        do {
            let _ = try self.send(["command": "set_setting", "id": id, "key": key, "value": value])
        } catch let error {
            self.log("Plugin \(id) failed to apply setting \(key): \(error.localizedDescription)")
        }
        self.bumpSettingsRevision()
    }

    public func pressPluginSettingButton(id: String, key: String) {
        do {
            let _ = try self.send(["command": "settings_button", "id": id, "key": key])
        } catch let error {
            self.log("Plugin \(id) failed in settings button \(key): \(error.localizedDescription)")
        }
        self.bumpSettingsRevision()
    }

    private func bumpSettingsRevision() {
        self.currentSettingsRevision += 1
        self.settingsRevisionPromise.set(self.currentSettingsRevision)
    }

    // MARK: Message menu

    public struct MenuItem {
        public let pluginId: String
        public let itemId: String
        public let title: String
    }

    // Items plugins add to the menu of `message` (see BasePlugin.message_menu_items).
    public func messageMenuItems(message: [String: Any]) -> [MenuItem] {
        guard MGPythonRuntime.shared().isStarted, let items = (try? self.send(["command": "message_menu", "message": message])) as? [[String: String]] else {
            return []
        }
        return items.compactMap { item in
            guard let pluginId = item["plugin"], let itemId = item["id"], let title = item["title"] else {
                return nil
            }
            return MenuItem(pluginId: pluginId, itemId: itemId, title: title)
        }
    }

    public func performMessageMenuItem(_ item: MenuItem, message: [String: Any]) {
        do {
            let _ = try self.send(["command": "message_menu_action", "plugin": item.pluginId, "id": item.itemId, "message": message])
        } catch let error {
            self.log("Plugin \(item.pluginId) failed in menu action \(item.itemId): \(error.localizedDescription)")
        }
    }

    // Unloads and loads a plugin again from its installed files.
    public func reloadPlugin(id: String) {
        self.unloadPlugin(id: id)
        if self.state.enabled[id] ?? true, !self.isInSafeMode {
            self.loadPlugin(id: id)
        }
        self.publish()
    }

    // MARK: Hooks

    // Runs a hook through the plugins that subscribed to it. Cheap when Python is not running.
    public func runHook(_ name: String, payload: Any) -> MagniumHookResult {
        guard MGPythonRuntime.shared().isStarted else {
            return .unchanged
        }
        do {
            let result = try self.send(["command": "hook", "name": name, "payload": payload]) as? [String: Any]
            let strategy = (result?["strategy"] as? String).flatMap(MagniumHookStrategy.init(rawValue:)) ?? .default
            return MagniumHookResult(strategy: strategy, payload: result?["payload"])
        } catch let error {
            self.log("Hook \(name) failed: \(error.localizedDescription)")
            return .unchanged
        }
    }

    // Exposes a host method to Python as magnium.call(name, **arguments).
    // The handler runs on the main thread and returns a JSON-serializable value.
    public func registerHostMethod(_ name: String, handler: @escaping ([String: Any]) throws -> Any?) {
        self.hostMethods[name] = handler
    }

    // MARK: Private

    private func startRuntime() -> Bool {
        let runtime = MGPythonRuntime.shared()
        runtime.setLogHandler { [weak self] line in
            self?.log(line)
        }
        runtime.setHostHandler { [weak self] method, argumentsJson, errorPointer in
            return self?.handleHostCall(method: method, argumentsJson: argumentsJson, errorPointer: errorPointer)
        }

        let bundle = Bundle.main.bundleURL
        let home = bundle.appendingPathComponent("python", isDirectory: true)
        let caches = self.fileManager.urls(for: .cachesDirectory, in: .userDomainMask)[0].appendingPathComponent("magnium-pycache", isDirectory: true)
        do {
            try runtime.start(withHomePath: home.path, searchPaths: [home.appendingPathComponent("app", isDirectory: true).path], cachePath: caches.path)
            return true
        } catch let error {
            self.runtimeError = error.localizedDescription
            self.log(error.localizedDescription)
            return false
        }
    }

    private func handleHostCall(method: String, argumentsJson: String, errorPointer: NSErrorPointer) -> String? {
        let work: () -> String? = {
            do {
                guard let handler = self.hostMethods[method] else {
                    throw MagniumPluginError.plugin("Unknown host method \(method)")
                }
                let arguments = try JSONSerialization.jsonObject(with: Data(argumentsJson.utf8)) as? [String: Any] ?? [:]
                guard let value = try handler(arguments) else {
                    return nil
                }
                let data = try JSONSerialization.data(withJSONObject: value, options: [.fragmentsAllowed])
                return String(data: data, encoding: .utf8)
            } catch let error {
                self.log("Host method \(method) failed: \(error.localizedDescription)")
                errorPointer?.pointee = error as NSError
                return nil
            }
        }
        if Thread.isMainThread {
            return work()
        } else {
            return DispatchQueue.main.sync(execute: work)
        }
    }

    private func registerBuiltinHostMethods() {
        self.registerHostMethod("app.info") { _ in
            let info = Bundle.main.infoDictionary ?? [:]
            return [
                "bundle_id": Bundle.main.bundleIdentifier ?? "",
                "version": info["CFBundleShortVersionString"] as? String ?? "",
                "build": info["CFBundleVersion"] as? String ?? "",
                "safe_mode": self.isInSafeMode
            ] as [String: Any]
        }
        self.registerHostMethod("runtime.runOnMainThread") { arguments in
            let callbackId = arguments["callback_id"] as? Int ?? 0
            DispatchQueue.main.async {
                let _ = try? self.send(["command": "main_thread_callback", "callback_id": callbackId])
            }
            return nil
        }
        self.registerHostMethod("runtime.setInterval") { arguments in
            guard let intervalId = arguments["interval_id"] as? Int else {
                return nil
            }
            // At least one frame, so a plugin cannot spin the main thread.
            let seconds = max(arguments["seconds"] as? Double ?? 1.0, 1.0 / 60.0)
            self.intervals[intervalId]?.invalidate()
            self.intervals[intervalId] = Foundation.Timer.scheduledTimer(withTimeInterval: seconds, repeats: true) { _ in
                do {
                    let _ = try self.send(["command": "interval", "interval_id": intervalId])
                } catch let error {
                    self.log("Interval \(intervalId) failed: \(error.localizedDescription)")
                }
            }
            return nil
        }
        self.registerHostMethod("runtime.clearInterval") { arguments in
            if let intervalId = arguments["interval_id"] as? Int {
                self.intervals.removeValue(forKey: intervalId)?.invalidate()
            }
            return nil
        }
        self.registerHostMethod("plugins.list") { _ in
            return self.currentPlugins().map { ["id": $0.id, "name": $0.name, "version": $0.version, "enabled": $0.isEnabled] }
        }
    }

    // Sends a command to magnium._manager.handle and unwraps its {"ok", "result"} answer.
    private func send(_ request: [String: Any]) throws -> Any? {
        let runtime = MGPythonRuntime.shared()
        guard runtime.isStarted else {
            throw MagniumPluginError.runtimeUnavailable(self.runtimeError ?? "Python is not running")
        }
        let requestData = try JSONSerialization.data(withJSONObject: request)
        let responseString = try runtime.callFunction("handle", inModule: "magnium._manager", argument: String(decoding: requestData, as: UTF8.self))
        guard let response = try JSONSerialization.jsonObject(with: Data(responseString.utf8)) as? [String: Any] else {
            throw MagniumPluginError.plugin("Malformed plugin manager response")
        }
        if response["ok"] as? Bool == true {
            return response["result"]
        }
        throw MagniumPluginError.plugin(response["traceback"] as? String ?? response["error"] as? String ?? "Plugin error")
    }

    private func loadPlugin(id: String) {
        let dataPath = self.dataDirectory.appendingPathComponent(id, isDirectory: true)
        do {
            let _ = try self.send(["command": "load", "path": self.pluginDirectory(id: id).path, "data_path": dataPath.path])
            self.loadErrors.removeValue(forKey: id)
        } catch let error {
            self.loadErrors[id] = error.localizedDescription
            self.log("Plugin \(id) failed to load: \(error.localizedDescription)")
        }
    }

    private func unloadPlugin(id: String) {
        do {
            let _ = try self.send(["command": "unload", "id": id])
        } catch let error {
            self.log("Plugin \(id) failed to unload: \(error.localizedDescription)")
        }
        self.loadErrors.removeValue(forKey: id)
    }

    private func pluginDirectory(id: String) -> URL {
        return self.pluginsDirectory.appendingPathComponent(id, isDirectory: true)
    }

    private func installedPluginIds() -> [String] {
        let directories = (try? self.fileManager.contentsOfDirectory(at: self.pluginsDirectory, includingPropertiesForKeys: nil)) ?? []
        return directories.filter { directory in
            // Skips the staging directories (<id>.installing, <id>.previous) of an interrupted install.
            return !["installing", "previous"].contains(directory.pathExtension)
        }.filter { directory in
            return self.fileManager.fileExists(atPath: directory.appendingPathComponent(MagniumPluginManager.manifestName).path)
        }.map { $0.lastPathComponent }.sorted()
    }

    // Reads an installed manifest.json directly, so the list works even when Python does not.
    private func installedPlugin(id: String) -> MagniumPluginInfo? {
        let directory = self.pluginDirectory(id: id)
        guard let data = try? Data(contentsOf: directory.appendingPathComponent(MagniumPluginManager.manifestName)), let manifest = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return nil
        }
        var metadata: [String: String] = [:]
        for key in ["id", "name", "version", "description", "icon"] {
            if let value = manifest[key] as? String {
                metadata[key] = value
            }
        }
        if let author = manifest["author"] as? String {
            metadata["author_name"] = author
        } else if let author = manifest["author"] as? [String: Any] {
            metadata["author_name"] = author["name"] as? String
            metadata["author_url"] = author["url"] as? String
        }
        // The directory name is the id the package was validated under.
        metadata["id"] = id
        return self.info(metadata: metadata, iconDirectory: directory)
    }

    private func info(metadata: [String: String], iconDirectory: URL?) -> MagniumPluginInfo? {
        guard let id = metadata["id"] else {
            return nil
        }
        var iconPath: String?
        if let icon = metadata["icon"], let iconDirectory {
            let path = iconDirectory.appendingPathComponent(icon).standardizedFileURL.path
            if path.hasPrefix(iconDirectory.standardizedFileURL.path + "/") {
                iconPath = path
            }
        }
        return MagniumPluginInfo(
            id: id,
            name: metadata["name"] ?? id,
            version: metadata["version"] ?? "",
            description: metadata["description"],
            authorName: metadata["author_name"],
            authorUrl: metadata["author_url"],
            iconPath: iconPath,
            isEnabled: self.state.enabled[id] ?? true,
            loadError: self.loadErrors[id]
        )
    }

    private func currentPlugins() -> [MagniumPluginInfo] {
        return self.installedPluginIds().compactMap { self.installedPlugin(id: $0) }.sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
    }

    private func publish() {
        self.pluginsPromise.set(self.currentPlugins())
        // Loading or unloading a plugin changes what its settings page shows.
        self.bumpSettingsRevision()
    }

    private func loadState() {
        if let data = try? Data(contentsOf: self.stateFile), let state = try? JSONDecoder().decode(State.self, from: data) {
            self.state = state
        }
    }

    private func saveState() {
        if let data = try? JSONEncoder().encode(self.state) {
            try? data.write(to: self.stateFile, options: .atomic)
        }
    }
}
