import Foundation
import Display
import AccountContext
import PresentationDataUtils
import MagniumPlugins

// Shows a .mpp package's metadata and the full-access warning, then installs and loads it.
public func magniumPresentPluginInstallConfirmation(context: AccountContext, url: URL, present: @escaping (ViewController) -> Void) {
    let presentAlert: (String?, String) -> Void = { title, text in
        present(textAlertController(context: context, title: title, text: text, actions: [TextAlertAction(type: .defaultAction, title: "OK", action: {})]))
    }

    let info: MagniumPluginInfo
    do {
        info = try MagniumPluginManager.shared.inspectPackage(at: url)
    } catch let error {
        presentAlert("Это не плагин Magnium", error.localizedDescription)
        return
    }

    var details: [String] = ["Версия \(info.version)"]
    if let authorName = info.authorName {
        details.append("Автор: \(authorName)")
    }
    if let description = info.description {
        details.append(description)
    }
    details.append("Плагин получит полный доступ к Magnium и вашему аккаунту Telegram. Устанавливайте только плагины из источников, которым доверяете.")

    present(textAlertController(context: context, title: "Установить «\(info.name)»?", text: details.joined(separator: "\n\n"), actions: [
        TextAlertAction(type: .genericAction, title: "Отмена", action: {}),
        TextAlertAction(type: .defaultAction, title: "Установить", action: {
            // A reinstall may replace the icon file in place.
            magniumResetPluginIconCache()
            do {
                let installed = try MagniumPluginManager.shared.installPackage(from: url)
                if MagniumPluginManager.shared.isInSafeMode {
                    presentAlert("«\(installed.name)» установлен", "Magnium в безопасном режиме, поэтому плагин включится после выхода из него.")
                } else {
                    presentAlert("«\(installed.name)» установлен", "Плагин уже работает.")
                }
            } catch let error {
                presentAlert("Плагин не запустился", error.localizedDescription)
            }
        })
    ]))
}
