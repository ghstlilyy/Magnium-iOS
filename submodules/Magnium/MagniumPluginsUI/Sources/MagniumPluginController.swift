import Foundation
import UIKit
import Display
import SwiftSignalKit
import TelegramCore
import TelegramPresentationData
import ItemListUI
import PresentationDataUtils
import AccountContext
import MagniumPlugins

private final class MagniumPluginControllerArguments {
    let openAuthor: (String) -> Void
    let setEnabled: (Bool) -> Void
    let updateSetting: (String, Any) -> Void
    let openSelector: (String, String, [MagniumPluginSettingOption], String) -> Void
    let pressButton: (String) -> Void
    let reload: () -> Void
    let uninstall: () -> Void

    init(openAuthor: @escaping (String) -> Void, setEnabled: @escaping (Bool) -> Void, updateSetting: @escaping (String, Any) -> Void, openSelector: @escaping (String, String, [MagniumPluginSettingOption], String) -> Void, pressButton: @escaping (String) -> Void, reload: @escaping () -> Void, uninstall: @escaping () -> Void) {
        self.openAuthor = openAuthor
        self.setEnabled = setEnabled
        self.updateSetting = updateSetting
        self.openSelector = openSelector
        self.pressButton = pressButton
        self.reload = reload
        self.uninstall = uninstall
    }
}

private enum MagniumPluginSection: Int32 {
    case info
    case author
    case state
    case settings
    case error
    case uninstall
}

private enum MagniumPluginEntry: ItemListNodeEntry {
    case header(MagniumPluginInfo)
    case description(String)
    case authorHeader
    case author(name: String, url: String?)
    case enabled(Bool)
    // The plugin's own settings page items, in order.
    case setting(index: Int, MagniumPluginSettingItem)
    case errorHeader
    case error(String)
    case reload
    case uninstall

    var section: ItemListSectionId {
        switch self {
        case .header, .description:
            return MagniumPluginSection.info.rawValue
        case .authorHeader, .author:
            return MagniumPluginSection.author.rawValue
        case .enabled:
            return MagniumPluginSection.state.rawValue
        case .setting:
            return MagniumPluginSection.settings.rawValue
        case .errorHeader, .error:
            return MagniumPluginSection.error.rawValue
        case .reload, .uninstall:
            return MagniumPluginSection.uninstall.rawValue
        }
    }

    var stableId: Int32 {
        switch self {
        case .header:
            return 0
        case .description:
            return 1
        case .authorHeader:
            return 2
        case .author:
            return 3
        case .enabled:
            return 4
        case let .setting(index, _):
            return 100 + Int32(index)
        case .errorHeader:
            return 1000
        case .error:
            return 1001
        case .reload:
            return 1002
        case .uninstall:
            return 1003
        }
    }

    static func ==(lhs: MagniumPluginEntry, rhs: MagniumPluginEntry) -> Bool {
        switch (lhs, rhs) {
        case let (.header(lhsInfo), .header(rhsInfo)):
            return lhsInfo == rhsInfo
        case let (.description(lhsText), .description(rhsText)), let (.error(lhsText), .error(rhsText)):
            return lhsText == rhsText
        case let (.author(lhsName, lhsUrl), .author(rhsName, rhsUrl)):
            return lhsName == rhsName && lhsUrl == rhsUrl
        case let (.enabled(lhsValue), .enabled(rhsValue)):
            return lhsValue == rhsValue
        case let (.setting(lhsIndex, lhsItem), .setting(rhsIndex, rhsItem)):
            return lhsIndex == rhsIndex && lhsItem == rhsItem
        case (.authorHeader, .authorHeader), (.errorHeader, .errorHeader), (.reload, .reload), (.uninstall, .uninstall):
            return true
        default:
            return false
        }
    }

    static func <(lhs: MagniumPluginEntry, rhs: MagniumPluginEntry) -> Bool {
        return lhs.stableId < rhs.stableId
    }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! MagniumPluginControllerArguments
        switch self {
        case let .header(info):
            return ItemListDisclosureItem(presentationData: presentationData, systemStyle: .glass, icon: magniumPluginIcon(info, size: 32.0), title: info.name, label: "Версия \(info.version)", labelStyle: .multilineDetailText, sectionId: self.section, style: .blocks, disclosureStyle: .none, action: nil)
        case let .description(text):
            return ItemListTextItem(presentationData: presentationData, text: .plain(text), sectionId: self.section)
        case .authorHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "АВТОР", sectionId: self.section)
        case let .author(name, url):
            let label = url.map { URL(string: $0)?.host ?? $0 } ?? ""
            var action: (() -> Void)?
            if let url {
                action = {
                    arguments.openAuthor(url)
                }
            }
            return ItemListDisclosureItem(presentationData: presentationData, systemStyle: .glass, title: name, label: label, labelStyle: .detailText, sectionId: self.section, style: .blocks, disclosureStyle: url == nil ? .none : .arrow, action: action)
        case let .enabled(value):
            return ItemListSwitchItem(presentationData: presentationData, systemStyle: .glass, title: "Включён", value: value, sectionId: self.section, style: .blocks, updated: { value in
                arguments.setEnabled(value)
            })
        case let .setting(_, item):
            switch item {
            case let .header(text):
                return ItemListSectionHeaderItem(presentationData: presentationData, text: text.uppercased(), sectionId: self.section)
            case let .text(text):
                return ItemListTextItem(presentationData: presentationData, text: .plain(text), sectionId: self.section)
            case let .toggle(key, title, subtitle, value):
                return ItemListSwitchItem(presentationData: presentationData, systemStyle: .glass, title: title, text: subtitle, value: value, sectionId: self.section, style: .blocks, updated: { value in
                    arguments.updateSetting(key, value)
                })
            case let .input(key, title, placeholder, value):
                return ItemListSingleLineInputItem(presentationData: presentationData, systemStyle: .glass, title: NSAttributedString(string: title, textColor: presentationData.theme.list.itemPrimaryTextColor), text: value, placeholder: placeholder, spacing: 12.0, sectionId: self.section, textUpdated: { text in
                    arguments.updateSetting(key, text)
                }, action: {})
            case let .button(key, title, isDestructive):
                return ItemListActionItem(presentationData: presentationData, systemStyle: .glass, title: title, kind: isDestructive ? .destructive : .generic, alignment: .natural, sectionId: self.section, style: .blocks, action: {
                    arguments.pressButton(key)
                })
            case let .selector(key, title, options, value):
                let label = options.first(where: { $0.value == value })?.title ?? value
                return ItemListDisclosureItem(presentationData: presentationData, systemStyle: .glass, title: title, label: label, sectionId: self.section, style: .blocks, action: {
                    arguments.openSelector(key, title, options, value)
                })
            }
        case .errorHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "ОШИБКА ЗАГРУЗКИ", sectionId: self.section)
        case let .error(text):
            return ItemListTextItem(presentationData: presentationData, text: .plain(text), sectionId: self.section)
        case .reload:
            return ItemListActionItem(presentationData: presentationData, systemStyle: .glass, title: "Перезагрузить", kind: .generic, alignment: .natural, sectionId: self.section, style: .blocks, action: {
                arguments.reload()
            })
        case .uninstall:
            return ItemListActionItem(presentationData: presentationData, systemStyle: .glass, title: "Удалить плагин", kind: .destructive, alignment: .natural, sectionId: self.section, style: .blocks, action: {
                arguments.uninstall()
            })
        }
    }
}

private func magniumPluginEntries(info: MagniumPluginInfo, settings: [MagniumPluginSettingItem]) -> [MagniumPluginEntry] {
    var entries: [MagniumPluginEntry] = []
    entries.append(.header(info))
    if let description = info.description {
        entries.append(.description(description))
    }
    if let authorName = info.authorName {
        entries.append(.authorHeader)
        entries.append(.author(name: authorName, url: info.authorUrl))
    }
    entries.append(.enabled(info.isEnabled))
    for (index, item) in settings.enumerated() {
        entries.append(.setting(index: index, item))
    }
    if let error = info.loadError, info.isEnabled {
        entries.append(.errorHeader)
        entries.append(.error(error))
    }
    if info.isEnabled {
        entries.append(.reload)
    }
    entries.append(.uninstall)
    return entries
}

func magniumPluginController(context: AccountContext, pluginId: String) -> ViewController {
    let manager = MagniumPluginManager.shared

    var presentControllerImpl: ((ViewController) -> Void)?
    var openUrlImpl: ((String) -> Void)?
    var dismissImpl: (() -> Void)?

    let arguments = MagniumPluginControllerArguments(
        openAuthor: { url in
            openUrlImpl?(url)
        },
        setEnabled: { isEnabled in
            manager.setPluginEnabled(id: pluginId, isEnabled: isEnabled)
        },
        updateSetting: { key, value in
            manager.updatePluginSetting(id: pluginId, key: key, value: value)
        },
        openSelector: { key, title, options, value in
            let presentationData = context.sharedContext.currentPresentationData.with { $0 }
            let actionSheet = ActionSheetController(presentationData: presentationData)
            var items: [ActionSheetItem] = [ActionSheetTextItem(title: title)]
            for option in options {
                items.append(ActionSheetButtonItem(title: option.value == value ? "✓ \(option.title)" : option.title, color: .accent, action: { [weak actionSheet] in
                    actionSheet?.dismissAnimated()
                    manager.updatePluginSetting(id: pluginId, key: key, value: option.value)
                }))
            }
            actionSheet.setItemGroups([
                ActionSheetItemGroup(items: items),
                ActionSheetItemGroup(items: [ActionSheetButtonItem(title: presentationData.strings.Common_Cancel, color: .accent, font: .bold, action: { [weak actionSheet] in
                    actionSheet?.dismissAnimated()
                })])
            ])
            presentControllerImpl?(actionSheet)
        },
        pressButton: { key in
            manager.pressPluginSettingButton(id: pluginId, key: key)
        },
        reload: {
            manager.reloadPlugin(id: pluginId)
        },
        uninstall: {
            presentControllerImpl?(textAlertController(context: context, title: "Удалить плагин?", text: "Плагин и его настройки будут удалены.", actions: [
                TextAlertAction(type: .genericAction, title: "Отмена", action: {}),
                TextAlertAction(type: .destructiveAction, title: "Удалить", action: {
                    dismissImpl?()
                    manager.uninstallPlugin(id: pluginId)
                })
            ]))
        }
    )

    let signal = combineLatest(queue: .mainQueue(),
        context.sharedContext.presentationData,
        manager.plugins |> map { plugins in plugins.first(where: { $0.id == pluginId }) },
        manager.settingsRevision
    )
    |> map { presentationData, info, _ -> (ItemListControllerState, (ItemListNodeState, Any)) in
        var presentationData = presentationData
        presentationData = presentationData.withUpdated(theme: presentationData.theme.withModalBlocksBackground())

        let controllerState = ItemListControllerState(presentationData: ItemListPresentationData(presentationData), title: .text(info?.name ?? "Плагин"), leftNavigationButton: nil, rightNavigationButton: nil, backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back))
        let listState = ItemListNodeState(presentationData: ItemListPresentationData(presentationData), entries: info.flatMap { magniumPluginEntries(info: $0, settings: $0.isEnabled ? manager.pluginSettings(id: pluginId) : []) } ?? [], style: .blocks, animateChanges: true)
        return (controllerState, (listState, arguments))
    }

    let controller = ItemListController(context: context, state: signal)
    presentControllerImpl = { [weak controller] presented in
        controller?.present(presented, in: .window(.root))
    }
    openUrlImpl = { [weak controller] url in
        let presentationData = context.sharedContext.currentPresentationData.with { $0 }
        context.sharedContext.openExternalUrl(context: context, urlContext: .generic, url: url, forceExternal: false, presentationData: presentationData, navigationController: controller?.navigationController as? NavigationController, dismissInput: {})
    }
    dismissImpl = { [weak controller] in
        let _ = controller?.navigationController?.popViewController(animated: true)
    }
    return controller
}
