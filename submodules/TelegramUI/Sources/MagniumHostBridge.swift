import Foundation
import UIKit
import Display
import SwiftSignalKit
import TelegramCore
import AccountContext
import PresentationDataUtils
import UndoUI
import SaveToCameraRoll
import MagniumPlugins
import MagniumSettings
import MagniumServer

// Gives plugins the logged-in account: the host methods below read the current context, set
// by AppDelegate whenever the account changes. Without an account they fail with an error.
final class MagniumHostBridge {
    static let shared = MagniumHostBridge()

    private weak var context: AccountContextImpl?
    private weak var rootController: TelegramRootController?
    private weak var mainWindow: Window1?
    private var isRegistered = false

    func attach(context: AccountContextImpl?, rootController: TelegramRootController?, mainWindow: Window1?) {
        self.context = context
        self.rootController = rootController
        self.mainWindow = mainWindow
        if !self.isRegistered {
            self.isRegistered = true
            self.registerHostMethods()
            MagniumBadges.shared.refresh()
        }
    }

    private func requireContext() throws -> AccountContextImpl {
        guard let context = self.context else {
            throw MagniumPluginError.plugin("No account is logged in")
        }
        return context
    }

    // The chat on top of the navigation stack, if any.
    func currentChat() -> ChatControllerImpl? {
        guard let rootController = self.rootController else {
            return nil
        }
        for controller in rootController.viewControllers.reversed() {
            if let chat = controller as? ChatControllerImpl {
                return chat
            }
            if controller is ViewController {
                // Anything else on top hides the chat below.
                return nil
            }
        }
        return nil
    }

    // "Не гасить экран в чатах": the screen stays on while any chat is on screen.
    private var visibleChats = Set<ObjectIdentifier>()
    private var idleTimerDisposable: Disposable?

    func chatDidAppear(_ chat: ChatControllerImpl) {
        self.visibleChats.insert(ObjectIdentifier(chat))
        if MagniumSettings.isOn(.keepScreenAwakeInChats), self.idleTimerDisposable == nil {
            self.idleTimerDisposable = chat.context.sharedContext.applicationBindings.pushIdleTimerExtension()
        }
    }

    func chatWillDisappear(_ chat: ChatControllerImpl) {
        self.visibleChats.remove(ObjectIdentifier(chat))
        if self.visibleChats.isEmpty {
            self.idleTimerDisposable?.dispose()
            self.idleTimerDisposable = nil
        }
    }

    func present(_ controller: ViewController) {
        self.mainWindow?.present(controller, on: .root)
    }

    func toast(_ text: String) {
        guard let context = self.context else {
            return
        }
        let presentationData = context.sharedContext.currentPresentationData.with { $0 }
        self.present(UndoOverlayController(presentationData: presentationData, content: .info(title: nil, text: text, timeout: nil, customUndoText: nil), elevatedLayout: false, action: { _ in return false }))
    }

    // Postbox reads are asynchronous; host methods answer synchronously, so wait briefly.
    private func wait<T>(_ signal: Signal<T, NoError>, timeout: Double = 2.0) -> T? {
        let semaphore = DispatchSemaphore(value: 0)
        var result: T?
        let disposable = (signal |> take(1)).start(next: { value in
            result = value
            semaphore.signal()
        })
        let _ = semaphore.wait(timeout: .now() + timeout)
        disposable.dispose()
        return result
    }

    private func peerId(_ arguments: [String: Any]) throws -> EnginePeer.Id {
        guard let value = (arguments["peer_id"] as? NSNumber)?.int64Value else {
            throw MagniumPluginError.plugin("peer_id is required")
        }
        return EnginePeer.Id(value)
    }

    private func registerHostMethods() {
        let manager = MagniumPluginManager.shared

        manager.registerHostMethod("ui.toast") { [unowned self] arguments in
            self.toast(arguments["text"] as? String ?? "")
            return nil
        }
        manager.registerHostMethod("ui.alert") { [unowned self] arguments in
            let context = try self.requireContext()
            self.present(textAlertController(context: context, title: arguments["title"] as? String, text: arguments["text"] as? String ?? "", actions: [TextAlertAction(type: .defaultAction, title: "OK", action: {})]))
            return nil
        }
        manager.registerHostMethod("ui.copy") { arguments in
            UIPasteboard.general.string = arguments["text"] as? String ?? ""
            return nil
        }
        manager.registerHostMethod("account.info") { [unowned self] _ in
            let context = try self.requireContext()
            return ["peer_id": context.account.peerId.toInt64()]
        }
        manager.registerHostMethod("chat.current") { [unowned self] _ in
            guard let chat = self.currentChat(), let peerId = chat.chatLocation.peerId else {
                return nil
            }
            return ["peer_id": peerId.toInt64()]
        }
        manager.registerHostMethod("messages.send") { [unowned self] arguments in
            let context = try self.requireContext()
            let peerId = try self.peerId(arguments)
            guard let text = arguments["text"] as? String, !text.isEmpty else {
                throw MagniumPluginError.plugin("text is required")
            }
            let _ = enqueueMessages(account: context.account, peerId: peerId, messages: [.message(text: text, attributes: [], inlineStickers: [:], mediaReference: nil, threadId: nil, replyToMessageId: nil, replyToStoryId: nil, localGroupingKey: nil, correlationId: nil, bubbleUpEmojiOrStickersets: [])]).start()
            return nil
        }
        manager.registerHostMethod("messages.recent") { [unowned self] arguments in
            let context = try self.requireContext()
            let peerId = try self.peerId(arguments)
            let limit = min(max((arguments["limit"] as? Int) ?? 100, 1), 2000)
            let messages = self.wait(context.engine.messages.magniumRecentMessages(peerId: peerId, limit: limit)) ?? []
            return messages.map { message -> [String: Any] in
                return [
                    "message_id": Int(message.id.id),
                    "timestamp": Int(message.timestamp),
                    "outgoing": !message.isIncoming,
                    "text": message.text,
                    "deleted": message.isDeleted
                ]
            }
        }
        manager.registerHostMethod("media.save_to_gallery") { [unowned self] arguments in
            let context = try self.requireContext()
            let peerId = try self.peerId(arguments)
            guard let messageId = arguments["message_id"] as? Int else {
                throw MagniumPluginError.plugin("message_id is required")
            }
            let id = EngineMessage.Id(peerId: peerId, namespace: Namespaces.Message.Cloud, id: Int32(messageId))
            let _ = (context.engine.data.get(TelegramEngine.EngineData.Item.Messages.Message(id: id))
            |> deliverOnMainQueue).start(next: { [weak self] message in
                guard let self, let message, let media = message.media.first(where: { $0 is TelegramMediaImage || $0 is TelegramMediaFile }) else {
                    self?.toast("В сообщении нет фото или видео")
                    return
                }
                let reference = AnyMediaReference.message(message: MessageReference(message._asMessage()), media: media)
                let _ = (saveToCameraRoll(context: context, userLocation: .peer(peerId), mediaReference: reference)
                |> deliverOnMainQueue).start(completed: { [weak self] in
                    self?.toast("Сохранено в галерею")
                })
            })
            return nil
        }
        manager.registerHostMethod("core.set_flag") { arguments in
            guard let owner = arguments["owner"] as? String, let rawFlag = arguments["flag"] as? String, let flag = MagniumCoreHooks.Flag(rawValue: rawFlag) else {
                throw MagniumPluginError.plugin("Unknown core flag")
            }
            MagniumCoreHooks.setFlag(flag, owner: owner, isOn: arguments["value"] as? Bool ?? false)
            return nil
        }
        manager.registerHostMethod("network.set_blocked") { arguments in
            guard let owner = arguments["owner"] as? String else {
                throw MagniumPluginError.plugin("owner is required")
            }
            MagniumCoreHooks.setBlockedMethods(Set(arguments["methods"] as? [String] ?? []), owner: owner)
            return nil
        }
        manager.registerHostMethod("core.release_owner") { arguments in
            if let owner = arguments["owner"] as? String {
                MagniumCoreHooks.removeOwner(owner)
            }
            return nil
        }
        manager.registerHostMethod("app.open_url") { [unowned self] arguments in
            let context = try self.requireContext()
            guard let url = arguments["url"] as? String else {
                throw MagniumPluginError.plugin("url is required")
            }
            let presentationData = context.sharedContext.currentPresentationData.with { $0 }
            context.sharedContext.openExternalUrl(context: context, urlContext: .generic, url: url, forceExternal: false, presentationData: presentationData, navigationController: self.rootController, dismissInput: {})
            return nil
        }
    }
}
