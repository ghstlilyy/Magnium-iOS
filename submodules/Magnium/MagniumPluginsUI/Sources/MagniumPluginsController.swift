import Foundation
import UIKit
import Display
import SwiftSignalKit
import TelegramCore
import TelegramPresentationData
import ItemListUI
import PresentationDataUtils
import AccountContext
import LegacyMediaPickerUI
import MagniumPlugins

private final class MagniumPluginsControllerArguments {
    let installFromFile: () -> Void
    let exitSafeMode: () -> Void
    let openPlugin: (MagniumPluginInfo) -> Void
    let openLog: () -> Void

    init(installFromFile: @escaping () -> Void, exitSafeMode: @escaping () -> Void, openPlugin: @escaping (MagniumPluginInfo) -> Void, openLog: @escaping () -> Void) {
        self.installFromFile = installFromFile
        self.exitSafeMode = exitSafeMode
        self.openPlugin = openPlugin
        self.openLog = openLog
    }
}

private enum MagniumPluginsSection: Int32 {
    case runtimeError
    case safeMode
    case install
    case plugins
    case log
}

private enum MagniumPluginsEntryId: Hashable {
    case runtimeError
    case safeModeHeader
    case safeModeExit
    case safeModeFooter
    case install
    case installFooter
    case pluginsHeader
    case empty
    case plugin(String)
    case log
    case logFooter
}

private enum MagniumPluginsEntry: ItemListNodeEntry {
    case runtimeError(String)
    case safeModeHeader
    case safeModeExit
    case safeModeFooter
    case install
    case installFooter
    case pluginsHeader
    case empty
    case plugin(index: Int, MagniumPluginInfo)
    case log
    case logFooter

    var section: ItemListSectionId {
        switch self {
        case .runtimeError:
            return MagniumPluginsSection.runtimeError.rawValue
        case .safeModeHeader, .safeModeExit, .safeModeFooter:
            return MagniumPluginsSection.safeMode.rawValue
        case .install, .installFooter:
            return MagniumPluginsSection.install.rawValue
        case .pluginsHeader, .empty, .plugin:
            return MagniumPluginsSection.plugins.rawValue
        case .log, .logFooter:
            return MagniumPluginsSection.log.rawValue
        }
    }

    var stableId: MagniumPluginsEntryId {
        switch self {
        case .runtimeError:
            return .runtimeError
        case .safeModeHeader:
            return .safeModeHeader
        case .safeModeExit:
            return .safeModeExit
        case .safeModeFooter:
            return .safeModeFooter
        case .install:
            return .install
        case .installFooter:
            return .installFooter
        case .pluginsHeader:
            return .pluginsHeader
        case .empty:
            return .empty
        case let .plugin(_, info):
            return .plugin(info.id)
        case .log:
            return .log
        case .logFooter:
            return .logFooter
        }
    }

    private var sortIndex: Int {
        switch self {
        case .runtimeError:
            return 0
        case .safeModeHeader:
            return 1
        case .safeModeExit:
            return 2
        case .safeModeFooter:
            return 3
        case .install:
            return 4
        case .installFooter:
            return 5
        case .pluginsHeader:
            return 6
        case .empty:
            return 7
        case let .plugin(index, _):
            return 100 + index
        case .log:
            return 100000
        case .logFooter:
            return 100001
        }
    }

    static func ==(lhs: MagniumPluginsEntry, rhs: MagniumPluginsEntry) -> Bool {
        switch (lhs, rhs) {
        case let (.runtimeError(lhsText), .runtimeError(rhsText)):
            return lhsText == rhsText
        case (.safeModeHeader, .safeModeHeader), (.safeModeExit, .safeModeExit), (.safeModeFooter, .safeModeFooter), (.install, .install), (.installFooter, .installFooter), (.pluginsHeader, .pluginsHeader), (.empty, .empty), (.log, .log), (.logFooter, .logFooter):
            return true
        case let (.plugin(lhsIndex, lhsInfo), .plugin(rhsIndex, rhsInfo)):
            return lhsIndex == rhsIndex && lhsInfo == rhsInfo
        default:
            return false
        }
    }

    static func <(lhs: MagniumPluginsEntry, rhs: MagniumPluginsEntry) -> Bool {
        return lhs.sortIndex < rhs.sortIndex
    }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! MagniumPluginsControllerArguments
        switch self {
        case let .runtimeError(text):
            return ItemListTextItem(presentationData: presentationData, text: .plain("Python не запустился, плагины недоступны.\n\n\(text)"), sectionId: self.section)
        case .safeModeHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "БЕЗОПАСНЫЙ РЕЖИМ", sectionId: self.section)
        case .safeModeExit:
            return ItemListActionItem(presentationData: presentationData, systemStyle: .glass, title: "Включить плагины", kind: .generic, alignment: .natural, sectionId: self.section, style: .blocks, action: {
                arguments.exitSafeMode()
            })
        case .safeModeFooter:
            return ItemListTextItem(presentationData: presentationData, text: .plain("Magnium несколько раз подряд закрылся при запуске, поэтому плагины не загружены. Отключите плагин, который мог вызвать сбой, и включите плагины снова."), sectionId: self.section)
        case .install:
            return ItemListActionItem(presentationData: presentationData, systemStyle: .glass, title: "Установить из файла…", kind: .generic, alignment: .natural, sectionId: self.section, style: .blocks, action: {
                arguments.installFromFile()
            })
        case .installFooter:
            return ItemListTextItem(presentationData: presentationData, text: .plain("Плагины распространяются файлами .mpp. Чтобы установить плагин из чата, просто нажмите на сообщение с ним."), sectionId: self.section)
        case .pluginsHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "УСТАНОВЛЕННЫЕ", sectionId: self.section)
        case .empty:
            return ItemListTextItem(presentationData: presentationData, text: .plain("Плагины ещё не установлены."), sectionId: self.section)
        case .log:
            return ItemListDisclosureItem(presentationData: presentationData, systemStyle: .glass, title: "Журнал", label: "", sectionId: self.section, style: .blocks, action: {
                arguments.openLog()
            })
        case .logFooter:
            return ItemListTextItem(presentationData: presentationData, text: .plain("Сообщения и ошибки плагинов. Если плагин ведёт себя странно, скопируйте журнал и отправьте автору."), sectionId: self.section)
        case let .plugin(_, info):
            let description: String
            if info.loadError != nil && info.isEnabled {
                description = "⚠️ Не загрузился"
            } else if !info.isEnabled {
                description = "Выключен"
            } else {
                description = info.description ?? ""
            }
            return ItemListDisclosureItem(presentationData: presentationData, systemStyle: .glass, icon: magniumPluginIcon(info, size: 32.0), title: info.name, label: description, labelStyle: .multilineDetailText, additionalDetailLabel: info.authorName.flatMap { "Автор: \($0)" }, sectionId: self.section, style: .blocks, action: {
                arguments.openPlugin(info)
            })
        }
    }
}

private func magniumPluginsEntries(plugins: [MagniumPluginInfo], runtimeError: String?, isInSafeMode: Bool) -> [MagniumPluginsEntry] {
    var entries: [MagniumPluginsEntry] = []
    if let runtimeError {
        entries.append(.runtimeError(runtimeError))
    }
    if isInSafeMode {
        entries.append(.safeModeHeader)
        entries.append(.safeModeExit)
        entries.append(.safeModeFooter)
    }
    entries.append(.install)
    entries.append(.installFooter)
    entries.append(.pluginsHeader)
    if plugins.isEmpty {
        entries.append(.empty)
    }
    for (index, info) in plugins.enumerated() {
        entries.append(.plugin(index: index, info))
    }
    entries.append(.log)
    entries.append(.logFooter)
    return entries
}

public func magniumPluginsController(context: AccountContext) -> ViewController {
    let manager = MagniumPluginManager.shared
    // The manager has no signal for safe mode; bump this to re-read it.
    let safeModeRevision = ValuePromise<Int>(0, ignoreRepeated: true)
    var currentSafeModeRevision = 0

    var presentControllerImpl: ((ViewController) -> Void)?
    var pushControllerImpl: ((ViewController) -> Void)?

    let arguments = MagniumPluginsControllerArguments(
        installFromFile: {
            let presentationData = context.sharedContext.currentPresentationData.with { $0 }
            let picker = legacyICloudFilePicker(theme: presentationData.theme, mode: .import, documentTypes: ["public.item"], completion: { urls in
                guard let url = urls.first else {
                    return
                }
                magniumPresentPluginInstallConfirmation(context: context, url: url, present: { controller in
                    presentControllerImpl?(controller)
                })
            })
            presentControllerImpl?(picker)
        },
        exitSafeMode: {
            manager.exitSafeMode()
            currentSafeModeRevision += 1
            safeModeRevision.set(currentSafeModeRevision)
        },
        openPlugin: { info in
            pushControllerImpl?(magniumPluginController(context: context, pluginId: info.id))
        },
        openLog: {
            pushControllerImpl?(magniumPluginLogController(context: context))
        }
    )

    let signal = combineLatest(queue: .mainQueue(),
        context.sharedContext.presentationData,
        manager.plugins,
        safeModeRevision.get()
    )
    |> map { presentationData, plugins, _ -> (ItemListControllerState, (ItemListNodeState, Any)) in
        var presentationData = presentationData
        presentationData = presentationData.withUpdated(theme: presentationData.theme.withModalBlocksBackground())

        let controllerState = ItemListControllerState(presentationData: ItemListPresentationData(presentationData), title: .text("Плагины"), leftNavigationButton: nil, rightNavigationButton: nil, backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back))
        let listState = ItemListNodeState(presentationData: ItemListPresentationData(presentationData), entries: magniumPluginsEntries(plugins: plugins, runtimeError: manager.runtimeError, isInSafeMode: manager.isInSafeMode), style: .blocks, animateChanges: true)
        return (controllerState, (listState, arguments))
    }

    let controller = ItemListController(context: context, state: signal)
    presentControllerImpl = { [weak controller] presented in
        controller?.present(presented, in: .window(.root))
    }
    pushControllerImpl = { [weak controller] pushed in
        controller?.push(pushed)
    }
    return controller
}
