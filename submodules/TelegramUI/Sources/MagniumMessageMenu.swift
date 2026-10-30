import Foundation
import UIKit
import Display
import TelegramCore
import ContextUI
import MagniumPlugins

// What plugins see of a message in BasePlugin.message_menu_items and on_message_menu_action.
func magniumMessageDescription(_ message: EngineRawMessage) -> [String: Any] {
    return [
        "peer_id": message.id.peerId.toInt64(),
        "message_id": Int(message.id.id),
        "text": message.text,
        "outgoing": !message.flags.contains(.Incoming),
        "has_media": !message.media.isEmpty,
        "timestamp": Int(message.timestamp),
        "deleted": message.attributes.contains(where: { $0 is MagniumDeletedMessageAttribute })
    ]
}

// The plugins' items for the menu of a single message, after a separator.
func magniumPluginMessageMenuItems(messages: [EngineRawMessage]) -> [ContextMenuItem] {
    guard messages.count == 1, let message = messages.first else {
        return []
    }
    let description = magniumMessageDescription(message)
    let items = MagniumPluginManager.shared.messageMenuItems(message: description)
    if items.isEmpty {
        return []
    }
    var result: [ContextMenuItem] = [.separator]
    for item in items {
        result.append(.action(ContextMenuActionItem(text: item.title, icon: { _ in return nil }, action: { _, f in
            f(.default)
            MagniumPluginManager.shared.performMessageMenuItem(item, message: description)
        })))
    }
    return result
}
