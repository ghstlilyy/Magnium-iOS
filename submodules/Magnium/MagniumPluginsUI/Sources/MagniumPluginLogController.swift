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

private final class MagniumPluginLogControllerArguments {
    let copy: () -> Void
    let clear: () -> Void

    init(copy: @escaping () -> Void, clear: @escaping () -> Void) {
        self.copy = copy
        self.clear = clear
    }
}

private enum MagniumPluginLogEntry: ItemListNodeEntry {
    case copy
    case clear
    case text(String)

    var section: ItemListSectionId {
        switch self {
        case .copy, .clear:
            return 0
        case .text:
            return 1
        }
    }

    var stableId: Int32 {
        switch self {
        case .copy:
            return 0
        case .clear:
            return 1
        case .text:
            return 2
        }
    }

    static func <(lhs: MagniumPluginLogEntry, rhs: MagniumPluginLogEntry) -> Bool {
        return lhs.stableId < rhs.stableId
    }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! MagniumPluginLogControllerArguments
        switch self {
        case .copy:
            return ItemListActionItem(presentationData: presentationData, systemStyle: .glass, title: "Скопировать журнал", kind: .generic, alignment: .natural, sectionId: self.section, style: .blocks, action: {
                arguments.copy()
            })
        case .clear:
            return ItemListActionItem(presentationData: presentationData, systemStyle: .glass, title: "Очистить", kind: .destructive, alignment: .natural, sectionId: self.section, style: .blocks, action: {
                arguments.clear()
            })
        case let .text(text):
            return ItemListTextItem(presentationData: presentationData, text: .plain(text), sectionId: self.section)
        }
    }
}

// The list shows only the end of the log; copying takes all of it.
private let visibleLogCharacters = 12000

func magniumPluginLogController(context: AccountContext) -> ViewController {
    let manager = MagniumPluginManager.shared
    var presentControllerImpl: ((ViewController) -> Void)?

    let arguments = MagniumPluginLogControllerArguments(
        copy: {
            UIPasteboard.general.string = manager.logText()
            presentControllerImpl?(textAlertController(context: context, title: nil, text: "Журнал скопирован.", actions: [TextAlertAction(type: .defaultAction, title: "OK", action: {})]))
        },
        clear: {
            manager.clearLog()
        }
    )

    let signal = combineLatest(queue: .mainQueue(),
        context.sharedContext.presentationData,
        manager.logUpdates
    )
    |> map { presentationData, _ -> (ItemListControllerState, (ItemListNodeState, Any)) in
        var presentationData = presentationData
        presentationData = presentationData.withUpdated(theme: presentationData.theme.withModalBlocksBackground())

        var text = manager.logText()
        if text.isEmpty {
            text = "Журнал пуст."
        } else if text.count > visibleLogCharacters {
            text = "…\n" + String(text.suffix(visibleLogCharacters))
        }
        let controllerState = ItemListControllerState(presentationData: ItemListPresentationData(presentationData), title: .text("Журнал"), leftNavigationButton: nil, rightNavigationButton: nil, backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back))
        let listState = ItemListNodeState(presentationData: ItemListPresentationData(presentationData), entries: [MagniumPluginLogEntry.copy, .clear, .text(text)], style: .blocks, animateChanges: false)
        return (controllerState, (listState, arguments))
    }

    let controller = ItemListController(context: context, state: signal)
    presentControllerImpl = { [weak controller] presented in
        controller?.present(presented, in: .window(.root))
    }
    return controller
}
