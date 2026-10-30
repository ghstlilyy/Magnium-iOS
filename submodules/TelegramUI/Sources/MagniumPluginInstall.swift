import Foundation
import Display
import TelegramCore
import AccountContext
import PresentationDataUtils
import MagniumPlugins
import MagniumPluginsUI

func magniumIsPluginFile(_ file: TelegramMediaFile) -> Bool {
    return file.fileName.flatMap(MagniumPluginManager.isPackageFileName) ?? false
}

// Asks to install a .mpp document opened in a chat.
func magniumPresentPluginInstall(context: AccountContext, file: TelegramMediaFile, present: @escaping (ViewController) -> Void) {
    guard let path = context.engine.resources.completedResourcePath(id: EngineMediaResource.Id(file.resource.id)) else {
        present(textAlertController(context: context, title: nil, text: "Файл плагина ещё не загружен.", actions: [TextAlertAction(type: .defaultAction, title: "OK", action: {})]))
        return
    }
    magniumPresentPluginInstallConfirmation(context: context, url: URL(fileURLWithPath: path), present: present)
}
