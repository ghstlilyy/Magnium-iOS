import Foundation
import UIKit
import Display
import SwiftSignalKit
import TelegramCore
import TelegramPresentationData
import ItemListUI
import PresentationDataUtils
import AccountContext
import MagniumServer
import OverlayStatusController

// MARK: Plugin catalog

private final class MagniumCatalogArguments {
    let install: (MagniumCatalogPlugin) -> Void
    let retry: () -> Void

    init(install: @escaping (MagniumCatalogPlugin) -> Void, retry: @escaping () -> Void) {
        self.install = install
        self.retry = retry
    }
}

private enum MagniumCatalogState: Equatable {
    case loading
    case failed(String)
    case loaded([MagniumCatalogPlugin])
}

private enum MagniumCatalogEntry: ItemListNodeEntry {
    case status(String)
    case retry
    case plugin(Int, MagniumCatalogPlugin)

    var section: ItemListSectionId {
        switch self {
        case .status, .retry:
            return 0
        case .plugin:
            return 1
        }
    }

    var stableId: String {
        switch self {
        case .status:
            return "status"
        case .retry:
            return "retry"
        case let .plugin(_, plugin):
            return "plugin." + plugin.id
        }
    }

    private var sortIndex: Int {
        switch self {
        case .status:
            return 0
        case .retry:
            return 1
        case let .plugin(index, _):
            return 10 + index
        }
    }

    static func <(lhs: MagniumCatalogEntry, rhs: MagniumCatalogEntry) -> Bool {
        return lhs.sortIndex < rhs.sortIndex
    }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! MagniumCatalogArguments
        switch self {
        case let .status(text):
            return ItemListTextItem(presentationData: presentationData, text: .plain(text), sectionId: self.section)
        case .retry:
            return ItemListActionItem(presentationData: presentationData, systemStyle: .glass, title: "Повторить", kind: .generic, alignment: .natural, sectionId: self.section, style: .blocks, action: {
                arguments.retry()
            })
        case let .plugin(_, plugin):
            var details = [plugin.description ?? ""]
            if let author = plugin.author?.name {
                details.append("Автор: \(author) · v\(plugin.version)")
            }
            return ItemListDisclosureItem(presentationData: presentationData, systemStyle: .glass, title: plugin.name, label: details.filter { !$0.isEmpty }.joined(separator: "\n"), labelStyle: .multilineDetailText, sectionId: self.section, style: .blocks, action: {
                arguments.install(plugin)
            })
        }
    }
}

func magniumCatalogController(context: AccountContext) -> ViewController {
    let statePromise = ValuePromise<MagniumCatalogState>(.loading, ignoreRepeated: false)
    let loadDisposable = MetaDisposable()
    var presentControllerImpl: ((ViewController) -> Void)?

    let load = {
        if MagniumServerConfiguration.baseUrl == nil {
            statePromise.set(.failed("Сервер Magnium не настроен. Укажите его адрес в Настройки ▸ Magnium ▸ Сервер, когда он появится. Плагины можно ставить и без него: нажмите на файл .mpp в чате."))
            return
        }
        statePromise.set(.loading)
        loadDisposable.set((MagniumCatalog.plugins()
        |> deliverOnMainQueue).start(next: { plugins in
            statePromise.set(.loaded(plugins))
        }, error: { error in
            statePromise.set(.failed(error.localizedDescription))
        }))
    }

    let arguments = MagniumCatalogArguments(
        install: { plugin in
            let presentationData = context.sharedContext.currentPresentationData.with { $0 }
            let progress = OverlayStatusController(theme: presentationData.theme, type: .loading(cancelled: nil))
            presentControllerImpl?(progress)
            let _ = (MagniumCatalog.download(plugin)
            |> deliverOnMainQueue).start(next: { url in
                progress.dismiss()
                magniumPresentPluginInstallConfirmation(context: context, url: url, present: { controller in
                    presentControllerImpl?(controller)
                })
            }, error: { error in
                progress.dismiss()
                presentControllerImpl?(textAlertController(context: context, title: "Не удалось скачать", text: error.localizedDescription, actions: [TextAlertAction(type: .defaultAction, title: "OK", action: {})]))
            })
        },
        retry: {
            load()
        }
    )

    let signal = combineLatest(queue: .mainQueue(), context.sharedContext.presentationData, statePromise.get())
    |> map { presentationData, state -> (ItemListControllerState, (ItemListNodeState, Any)) in
        var presentationData = presentationData
        presentationData = presentationData.withUpdated(theme: presentationData.theme.withModalBlocksBackground())
        var entries: [MagniumCatalogEntry] = []
        switch state {
        case .loading:
            entries.append(.status("Загрузка каталога…"))
        case let .failed(text):
            entries.append(.status(text))
            if MagniumServerConfiguration.baseUrl != nil {
                entries.append(.retry)
            }
        case let .loaded(plugins):
            if plugins.isEmpty {
                entries.append(.status("В каталоге пока нет плагинов."))
            }
            for (index, plugin) in plugins.enumerated() {
                entries.append(.plugin(index, plugin))
            }
        }
        let controllerState = ItemListControllerState(presentationData: ItemListPresentationData(presentationData), title: .text("Каталог плагинов"), leftNavigationButton: nil, rightNavigationButton: nil, backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back))
        let listState = ItemListNodeState(presentationData: ItemListPresentationData(presentationData), entries: entries, style: .blocks, animateChanges: true)
        return (controllerState, (listState, arguments))
    }
    |> afterDisposed {
        loadDisposable.dispose()
    }

    let controller = ItemListController(context: context, state: signal)
    presentControllerImpl = { [weak controller] presented in
        controller?.present(presented, in: .window(.root))
    }
    load()
    return controller
}

// MARK: Badges

private final class MagniumBadgesArguments {
    let updateUserId: (String) -> Void
    let issue: (MagniumBadge) -> Void
    let lookUp: () -> Void

    init(updateUserId: @escaping (String) -> Void, issue: @escaping (MagniumBadge) -> Void, lookUp: @escaping () -> Void) {
        self.updateUserId = updateUserId
        self.issue = issue
        self.lookUp = lookUp
    }
}

private enum MagniumBadgesEntry: ItemListNodeEntry {
    case info
    case userId(String)
    case lookUp
    case current(String)
    case presetsHeader
    case preset(Int, MagniumBadge)

    var section: ItemListSectionId {
        switch self {
        case .info:
            return 0
        case .userId, .lookUp, .current:
            return 1
        case .presetsHeader, .preset:
            return 2
        }
    }

    var stableId: String {
        switch self {
        case .info:
            return "info"
        case .userId:
            return "userId"
        case .lookUp:
            return "lookUp"
        case .current:
            return "current"
        case .presetsHeader:
            return "presetsHeader"
        case let .preset(_, badge):
            return "preset." + badge.id
        }
    }

    private var sortIndex: Int {
        switch self {
        case .info:
            return 0
        case .userId:
            return 1
        case .lookUp:
            return 2
        case .current:
            return 3
        case .presetsHeader:
            return 4
        case let .preset(index, _):
            return 10 + index
        }
    }

    static func <(lhs: MagniumBadgesEntry, rhs: MagniumBadgesEntry) -> Bool {
        return lhs.sortIndex < rhs.sortIndex
    }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! MagniumBadgesArguments
        switch self {
        case .info:
            return ItemListTextItem(presentationData: presentationData, text: .plain("Значки видны в профиле пользователя. Выданный здесь значок сразу появляется на этом устройстве, а с токеном владельца отправляется на сервер, и его видят все."), sectionId: self.section)
        case let .userId(text):
            return ItemListSingleLineInputItem(presentationData: presentationData, systemStyle: .glass, title: NSAttributedString(string: "ID", textColor: presentationData.theme.list.itemPrimaryTextColor), text: text, placeholder: "ID пользователя Telegram", type: .number, spacing: 12.0, sectionId: self.section, textUpdated: { text in
                arguments.updateUserId(text)
            }, action: {})
        case .lookUp:
            return ItemListActionItem(presentationData: presentationData, systemStyle: .glass, title: "Показать его значки", kind: .generic, alignment: .natural, sectionId: self.section, style: .blocks, action: {
                arguments.lookUp()
            })
        case let .current(text):
            return ItemListTextItem(presentationData: presentationData, text: .plain(text), sectionId: self.section)
        case .presetsHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "ВЫДАТЬ ЗНАЧОК", sectionId: self.section)
        case let .preset(_, badge):
            return ItemListActionItem(presentationData: presentationData, systemStyle: .glass, title: "\(badge.emoji) \(badge.title)", kind: .generic, alignment: .natural, sectionId: self.section, style: .blocks, action: {
                arguments.issue(badge)
            })
        }
    }
}

func magniumBadgesController(context: AccountContext) -> ViewController {
    var userIdText = ""
    let currentPromise = ValuePromise<String>("", ignoreRepeated: true)
    var presentControllerImpl: ((ViewController) -> Void)?

    let describe: (Int64) -> String = { userId in
        let badges = MagniumBadges.shared.badges(userId: userId)
        if badges.isEmpty {
            return "У пользователя \(userId) значков нет."
        }
        return badges.map { "\($0.emoji) \($0.title) (\($0.source))" }.joined(separator: "\n")
    }

    let arguments = MagniumBadgesArguments(
        updateUserId: { text in
            userIdText = text
        },
        issue: { badge in
            guard let userId = Int64(userIdText.trimmingCharacters(in: .whitespaces)) else {
                presentControllerImpl?(textAlertController(context: context, title: nil, text: "Сначала укажите ID пользователя.", actions: [TextAlertAction(type: .defaultAction, title: "OK", action: {})]))
                return
            }
            let _ = (MagniumBadges.shared.issue(badge, to: userId)
            |> deliverOnMainQueue).start(error: { error in
                presentControllerImpl?(textAlertController(context: context, title: "Сервер не принял значок", text: "\(error.localizedDescription). На этом устройстве значок уже выдан.", actions: [TextAlertAction(type: .defaultAction, title: "OK", action: {})]))
            }, completed: {
                currentPromise.set(describe(userId))
            })
        },
        lookUp: {
            if let userId = Int64(userIdText.trimmingCharacters(in: .whitespaces)) {
                currentPromise.set(describe(userId))
            }
        }
    )

    let signal = combineLatest(queue: .mainQueue(), context.sharedContext.presentationData, currentPromise.get())
    |> map { presentationData, current -> (ItemListControllerState, (ItemListNodeState, Any)) in
        var presentationData = presentationData
        presentationData = presentationData.withUpdated(theme: presentationData.theme.withModalBlocksBackground())
        var entries: [MagniumBadgesEntry] = [.info, .userId(userIdText), .lookUp]
        if !current.isEmpty {
            entries.append(.current(current))
        }
        entries.append(.presetsHeader)
        for (index, badge) in magniumBadgePresets.enumerated() {
            entries.append(.preset(index, badge))
        }
        let controllerState = ItemListControllerState(presentationData: ItemListPresentationData(presentationData), title: .text("Значки"), leftNavigationButton: nil, rightNavigationButton: nil, backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back))
        let listState = ItemListNodeState(presentationData: ItemListPresentationData(presentationData), entries: entries, style: .blocks, animateChanges: false)
        return (controllerState, (listState, arguments))
    }

    let controller = ItemListController(context: context, state: signal)
    presentControllerImpl = { [weak controller] presented in
        controller?.present(presented, in: .window(.root))
    }
    return controller
}
