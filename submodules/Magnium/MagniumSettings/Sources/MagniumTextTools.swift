import Foundation

public enum MagniumTextTools {
    // Query parameters that only track where a link was shared from.
    private static let trackingParameters: Set<String> = [
        "fbclid", "gclid", "dclid", "yclid", "igshid", "igsh", "mc_cid", "mc_eid", "si", "_hsenc", "_hsmi", "ref_src", "ref_url", "feature", "pp"
    ]

    private static func isTracking(_ name: String) -> Bool {
        let name = name.lowercased()
        return name.hasPrefix("utm_") || self.trackingParameters.contains(name)
    }

    // Removes tracking parameters from every link in the text; returns nil when nothing changed.
    public static func removingTrackingParameters(from text: String) -> String? {
        guard text.contains("?"), let detector = try? NSDataDetector(types: NSTextCheckingResult.CheckingType.link.rawValue) else {
            return nil
        }
        let nsText = text as NSString
        var result = text
        var changed = false
        let matches = detector.matches(in: text, options: [], range: NSRange(location: 0, length: nsText.length))
        for match in matches.reversed() {
            let original = nsText.substring(with: match.range)
            guard var components = URLComponents(string: original), let items = components.queryItems, !items.isEmpty else {
                continue
            }
            let kept = items.filter { !self.isTracking($0.name) }
            if kept.count == items.count {
                continue
            }
            components.queryItems = kept.isEmpty ? nil : kept
            guard let cleaned = components.string, let range = Range(match.range, in: result) else {
                continue
            }
            result.replaceSubrange(range, with: cleaned)
            changed = true
        }
        return changed ? result : nil
    }
}
