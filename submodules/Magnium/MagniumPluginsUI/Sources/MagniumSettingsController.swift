import Foundation
import UIKit
import Display
import SwiftSignalKit
import TelegramCore
import TelegramPresentationData
import ItemListUI
import PresentationDataUtils
import AccountContext
import MagniumSettings
import MagniumServer

private final class MagniumSettingsControllerArguments {
    let toggle: (MagniumFeature, Bool) -> Void
    let updateServerUrl: (String) -> Void
    let updateOwnerToken: (String) -> Void
    let openCatalog: () -> Void
    let openBadges: () -> Void
    let openPlugins: () -> Void
    let openChannel: () -> Void

    init(toggle: @escaping (MagniumFeature, Bool) -> Void, updateServerUrl: @escaping (String) -> Void, updateOwnerToken: @escaping (String) -> Void, openCatalog: @escaping () -> Void, openBadges: @escaping () -> Void, openPlugins: @escaping () -> Void, openChannel: @escaping () -> Void) {
        self.toggle = toggle
        self.updateServerUrl = updateServerUrl
        self.updateOwnerToken = updateOwnerToken
        self.openCatalog = openCatalog
        self.openBadges = openBadges
        self.openPlugins = openPlugins
        self.openChannel = openChannel
    }
}

private enum MagniumSettingsEntryId: Hashable {
    case plugins
    case header(Int)
    case feature(String)
    case serverHeader
    case serverUrl
    case ownerToken
    case catalog
    case badges
    case serverFooter
    case channel
}

private enum MagniumSettingsEntry: ItemListNodeEntry {
    case plugins
    case header(Int, String)
    case feature(Int, Int, MagniumFeature, Bool)
    case serverHeader
    case serverUrl(String)
    case ownerToken(String)
    case catalog
    case badges
    case serverFooter
    case channel

    // Section 0 is the plugins link; categories follow; then the server and the channel.
    var section: ItemListSectionId {
        switch self {
        case .plugins:
            return 0
        case let .header(category, _), let .feature(category, _, _, _):
            return ItemListSectionId(1 + category)
        case .serverHeader, .serverUrl, .ownerToken, .catalog, .badges, .serverFooter:
            return 100
        case .channel:
            return 101
        }
    }

    var stableId: MagniumSettingsEntryId {
        switch self {
        case .plugins:
            return .plugins
        case let .header(category, _):
            return .header(category)
        case let .feature(_, _, feature, _):
            return .feature(feature.rawValue)
        case .serverHeader:
            return .serverHeader
        case .serverUrl:
            return .serverUrl
        case .ownerToken:
            return .ownerToken
        case .catalog:
            return .catalog
        case .badges:
            return .badges
        case .serverFooter:
            return .serverFooter
        case .channel:
            return .channel
        }
    }

    private var sortIndex: Int {
        switch self {
        case .plugins:
            return 0
        case let .header(category, _):
            return 1000 * (1 + category)
        case let .feature(category, index, _, _):
            return 1000 * (1 + category) + 1 + index
        case .serverHeader:
            return 100000
        case .serverUrl:
            return 100001
        case .ownerToken:
            return 100002
        case .catalog:
            return 100003
        case .badges:
            return 100004
        case .serverFooter:
            return 100005
        case .channel:
            return 200000
        }
    }

    static func ==(lhs: MagniumSettingsEntry, rhs: MagniumSettingsEntry) -> Bool {
        switch (lhs, rhs) {
        case (.plugins, .plugins), (.serverHeader, .serverHeader), (.catalog, .catalog), (.badges, .badges), (.serverFooter, .serverFooter), (.channel, .channel):
            return true
        case let (.header(lhsCategory, lhsText), .header(rhsCategory, rhsText)):
            return lhsCategory == rhsCategory && lhsText == rhsText
        case let (.feature(lhsCategory, lhsIndex, lhsFeature, lhsValue), .feature(rhsCategory, rhsIndex, rhsFeature, rhsValue)):
            return lhsCategory == rhsCategory && lhsIndex == rhsIndex && lhsFeature == rhsFeature && lhsValue == rhsValue
        case let (.serverUrl(lhsText), .serverUrl(rhsText)), let (.ownerToken(lhsText), .ownerToken(rhsText)):
            return lhsText == rhsText
        default:
            return false
        }
    }

    static func <(lhs: MagniumSettingsEntry, rhs: MagniumSettingsEntry) -> Bool {
        return lhs.sortIndex < rhs.sortIndex
    }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! MagniumSettingsControllerArguments
        let titleColor = presentationData.theme.list.itemPrimaryTextColor
        switch self {
        case .plugins:
            return ItemListDisclosureItem(presentationData: presentationData, systemStyle: .glass, title: "Плагины", label: "", sectionId: self.section, style: .blocks, action: {
                arguments.openPlugins()
            })
        case let .header(_, text):
            return ItemListSectionHeaderItem(presentationData: presentationData, text: text.uppercased(), sectionId: self.section)
        case let .feature(_, _, feature, value):
            return ItemListSwitchItem(presentationData: presentationData, systemStyle: .glass, title: feature.title, text: feature.subtitle, value: value, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggle(feature, value)
            })
        case .serverHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "СЕРВЕР MAGNIUM", sectionId: self.section)
        case let .serverUrl(text):
            return ItemListSingleLineInputItem(presentationData: presentationData, systemStyle: .glass, title: NSAttributedString(string: "Адрес", textColor: titleColor), text: text, placeholder: "https://…", type: .regular(capitalization: false, autocorrection: false), spacing: 12.0, sectionId: self.section, textUpdated: { text in
                arguments.updateServerUrl(text)
            }, action: {})
        case let .ownerToken(text):
            return ItemListSingleLineInputItem(presentationData: presentationData, systemStyle: .glass, title: NSAttributedString(string: "Токен", textColor: titleColor), text: text, placeholder: "только для владельца", type: .password, spacing: 12.0, sectionId: self.section, textUpdated: { text in
                arguments.updateOwnerToken(text)
            }, action: {})
        case .catalog:
            return ItemListDisclosureItem(presentationData: presentationData, systemStyle: .glass, title: "Каталог плагинов", label: "", sectionId: self.section, style: .blocks, action: {
                arguments.openCatalog()
            })
        case .badges:
            return ItemListDisclosureItem(presentationData: presentationData, systemStyle: .glass, title: "Значки", label: "", sectionId: self.section, style: .blocks, action: {
                arguments.openBadges()
            })
        case .serverFooter:
            return ItemListTextItem(presentationData: presentationData, text: .plain("С сервера ставятся плагины из каталога и приходят значки пользователей. Пока адрес пуст, значки показываются только выданные на этом устройстве."), sectionId: self.section)
        case .channel:
            return ItemListDisclosureItem(presentationData: presentationData, systemStyle: .glass, title: "Канал Magnium", label: "@magniumtg", sectionId: self.section, style: .blocks, action: {
                arguments.openChannel()
            })
        }
    }
}

private func magniumSettingsEntries() -> [MagniumSettingsEntry] {
    var entries: [MagniumSettingsEntry] = [.plugins]
    for (categoryIndex, category) in MagniumFeature.Category.allCases.enumerated() {
        entries.append(.header(categoryIndex, category.title))
        for (index, feature) in MagniumSettings.features(in: category).enumerated() {
            entries.append(.feature(categoryIndex, index, feature, MagniumSettings.isOn(feature)))
        }
    }
    entries.append(.serverHeader)
    entries.append(.serverUrl(MagniumServerConfiguration.baseUrlString))
    entries.append(.ownerToken(MagniumServerConfiguration.ownerToken))
    entries.append(.catalog)
    entries.append(.badges)
    entries.append(.serverFooter)
    entries.append(.channel)
    return entries
}

public func magniumSettingsController(context: AccountContext) -> ViewController {
    let revision = ValuePromise<Int>(0, ignoreRepeated: true)
    var currentRevision = 0
    let bump = {
        currentRevision += 1
        revision.set(currentRevision)
    }
    var pushControllerImpl: ((ViewController) -> Void)?
    var openUrlImpl: ((String) -> Void)?

    let arguments = MagniumSettingsControllerArguments(
        toggle: { feature, value in
            MagniumSettings.set(feature, isOn: value)
            bump()
        },
        updateServerUrl: { text in
            MagniumServerConfiguration.baseUrlString = text
            MagniumBadges.shared.refresh()
        },
        updateOwnerToken: { text in
            MagniumServerConfiguration.ownerToken = text
        },
        openCatalog: {
            pushControllerImpl?(magniumCatalogController(context: context))
        },
        openBadges: {
            pushControllerImpl?(magniumBadgesController(context: context))
        },
        openPlugins: {
            pushControllerImpl?(magniumPluginsController(context: context))
        },
        openChannel: {
            openUrlImpl?("https://t.me/magniumtg")
        }
    )

    let signal = combineLatest(queue: .mainQueue(), context.sharedContext.presentationData, revision.get())
    |> map { presentationData, _ -> (ItemListControllerState, (ItemListNodeState, Any)) in
        var presentationData = presentationData
        presentationData = presentationData.withUpdated(theme: presentationData.theme.withModalBlocksBackground())
        let controllerState = ItemListControllerState(presentationData: ItemListPresentationData(presentationData), title: .text("Magnium"), leftNavigationButton: nil, rightNavigationButton: nil, backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back))
        let listState = ItemListNodeState(presentationData: ItemListPresentationData(presentationData), entries: magniumSettingsEntries(), style: .blocks, animateChanges: false)
        return (controllerState, (listState, arguments))
    }

    let controller = ItemListController(context: context, state: signal)
    pushControllerImpl = { [weak controller] pushed in
        controller?.push(pushed)
    }
    openUrlImpl = { [weak controller] url in
        let presentationData = context.sharedContext.currentPresentationData.with { $0 }
        context.sharedContext.openExternalUrl(context: context, urlContext: .generic, url: url, forceExternal: false, presentationData: presentationData, navigationController: controller?.navigationController as? NavigationController, dismissInput: {})
    }
    return controller
}
