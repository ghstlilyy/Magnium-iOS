import Foundation
import UIKit
import MagniumPlugins

private var cachedIcons: [String: UIImage] = [:]

// The plugin's icon from its package, or a lettered placeholder, as a rounded square.
func magniumPluginIcon(_ info: MagniumPluginInfo, size: CGFloat) -> UIImage {
    let key = "\(info.id):\(info.iconPath ?? ""):\(size)"
    if let image = cachedIcons[key] {
        return image
    }
    let source = info.iconPath.flatMap { UIImage(contentsOfFile: $0) }
    let bounds = CGRect(origin: .zero, size: CGSize(width: size, height: size))
    let image = UIGraphicsImageRenderer(size: bounds.size).image { _ in
        UIBezierPath(roundedRect: bounds, cornerRadius: size * 0.225).addClip()
        if let source {
            source.draw(in: bounds)
        } else {
            UIColor(red: 0.42, green: 0.30, blue: 0.91, alpha: 1.0).setFill()
            UIRectFill(bounds)
            let letter = String(info.name.prefix(1)).uppercased() as NSString
            let attributes: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: size * 0.55, weight: .semibold),
                .foregroundColor: UIColor.white
            ]
            let letterSize = letter.size(withAttributes: attributes)
            letter.draw(at: CGPoint(x: (size - letterSize.width) / 2.0, y: (size - letterSize.height) / 2.0), withAttributes: attributes)
        }
    }
    cachedIcons[key] = image
    return image
}

// Reinstalling a plugin may change its icon file in place.
func magniumResetPluginIconCache() {
    cachedIcons.removeAll()
}
