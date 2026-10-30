import Foundation

// Sideloading signs the app with whatever profile the signer has; a wildcard profile (KSign,
// ESign and similar with a bought certificate) carries no App Group, so the group container is
// missing or not writable and launch stops before any window appears. Fall back to a directory
// in the app's own container. Extensions cannot reach it, so notification previews and the
// share extension lose access to the account data, but the app itself works.
func magniumAppGroupContainerUrl(appGroupName: String) -> URL? {
    let fileManager = FileManager.default
    if let groupUrl = fileManager.containerURL(forSecurityApplicationGroupIdentifier: appGroupName), magniumIsWritableDirectory(groupUrl) {
        return groupUrl
    }
    let fallbackUrl = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("MagniumAppGroup", isDirectory: true)
    try? fileManager.createDirectory(at: fallbackUrl, withIntermediateDirectories: true)
    NSLog("[Magnium] App Group \(appGroupName) is unavailable, using \(fallbackUrl.path)")
    return fallbackUrl
}

private func magniumIsWritableDirectory(_ url: URL) -> Bool {
    let testUrl = url.appendingPathComponent(".magnium-write-test-\(UUID().uuidString)")
    guard FileManager.default.createFile(atPath: testUrl.path, contents: Data()) else {
        return false
    }
    try? FileManager.default.removeItem(at: testUrl)
    return true
}
