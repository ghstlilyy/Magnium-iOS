import Foundation
import Postbox
import SwiftSignalKit

// Switches Magnium plugins flip in TelegramCore. TelegramCore cannot depend on the plugin
// runtime (it is shared with every extension), so the app sets these and the core only reads
// them. Each switch is owned by plugins: it is on while any plugin turned it on.
public final class MagniumCoreHooks {
    public enum Flag: String {
        // Server-side deletions keep the message and mark it with MagniumDeletedMessageAttribute.
        case preserveDeletedMessages = "preserve_deleted"
        // Opening a message with a self-destruct timer does not consume it.
        case keepDisappearingMedia = "keep_disappearing_media"
    }

    private static let lock = NSLock()
    private static var flagOwners: [Flag: Set<String>] = [:]
    private static var blockedMethodsByOwner: [String: Set<String>] = [:]
    private static var blockedMethods: Set<String> = []

    public static func setFlag(_ flag: Flag, owner: String, isOn: Bool) {
        self.lock.lock()
        var owners = self.flagOwners[flag] ?? []
        if isOn {
            owners.insert(owner)
        } else {
            owners.remove(owner)
        }
        self.flagOwners[flag] = owners
        self.lock.unlock()
    }

    public static func isOn(_ flag: Flag) -> Bool {
        self.lock.lock()
        defer {
            self.lock.unlock()
        }
        return !(self.flagOwners[flag] ?? []).isEmpty
    }

    // Requests whose TL method name ("messages.readHistory") is blocked are never sent and
    // never complete: an error would make the many retrying callers spin.
    public static func setBlockedMethods(_ methods: Set<String>, owner: String) {
        self.lock.lock()
        if methods.isEmpty {
            self.blockedMethodsByOwner.removeValue(forKey: owner)
        } else {
            self.blockedMethodsByOwner[owner] = methods
        }
        self.blockedMethods = self.blockedMethodsByOwner.values.reduce(into: Set<String>()) { $0.formUnion($1) }
        self.lock.unlock()
    }

    public static func isRequestBlocked(_ method: String) -> Bool {
        self.lock.lock()
        defer {
            self.lock.unlock()
        }
        return !self.blockedMethods.isEmpty && self.blockedMethods.contains(method)
    }

    // Removes everything an owner (a plugin) switched on, when it is unloaded.
    public static func removeOwner(_ owner: String) {
        self.lock.lock()
        for (flag, owners) in self.flagOwners {
            self.flagOwners[flag] = owners.subtracting([owner])
        }
        self.blockedMethodsByOwner.removeValue(forKey: owner)
        self.blockedMethods = self.blockedMethodsByOwner.values.reduce(into: Set<String>()) { $0.formUnion($1) }
        self.lock.unlock()
    }
}

// Marks a message the server deleted while MagniumCoreHooks.Flag.preserveDeletedMessages was on.
public final class MagniumDeletedMessageAttribute: MessageAttribute, Equatable {
    public let date: Int32

    public init(date: Int32) {
        self.date = date
    }

    required public init(decoder: PostboxDecoder) {
        self.date = decoder.decodeInt32ForKey("d", orElse: 0)
    }

    public func encode(_ encoder: PostboxEncoder) {
        encoder.encodeInt32(self.date, forKey: "d")
    }

    public static func ==(lhs: MagniumDeletedMessageAttribute, rhs: MagniumDeletedMessageAttribute) -> Bool {
        return lhs.date == rhs.date
    }
}

// Called while replaying server deletions. Returns the ids it kept (marked as deleted), which
// the caller must then not delete. Messages already marked are kept again.
func magniumPreserveDeletedMessages(transaction: Transaction, ids: [MessageId]) -> Set<MessageId> {
    guard MagniumCoreHooks.isOn(.preserveDeletedMessages) else {
        return []
    }
    let now = Int32(Date().timeIntervalSince1970)
    var kept = Set<MessageId>()
    for id in ids {
        // Only cloud messages: local and scheduled ones are the user's own state.
        guard id.namespace == Namespaces.Message.Cloud, let message = transaction.getMessage(id) else {
            continue
        }
        kept.insert(id)
        if message.attributes.contains(where: { $0 is MagniumDeletedMessageAttribute }) {
            continue
        }
        transaction.updateMessage(id, update: { currentMessage in
            var storeForwardInfo: StoreMessageForwardInfo?
            if let forwardInfo = currentMessage.forwardInfo {
                storeForwardInfo = StoreMessageForwardInfo(authorId: forwardInfo.author?.id, sourceId: forwardInfo.source?.id, sourceMessageId: forwardInfo.sourceMessageId, date: forwardInfo.date, authorSignature: forwardInfo.authorSignature, psaType: forwardInfo.psaType, flags: forwardInfo.flags)
            }
            var attributes = currentMessage.attributes
            attributes.append(MagniumDeletedMessageAttribute(date: now))
            return .update(StoreMessage(id: currentMessage.id, customStableId: nil, globallyUniqueId: currentMessage.globallyUniqueId, groupingKey: currentMessage.groupingKey, threadId: currentMessage.threadId, timestamp: currentMessage.timestamp, flags: StoreMessageFlags(currentMessage.flags), tags: currentMessage.tags, globalTags: currentMessage.globalTags, localTags: currentMessage.localTags, forwardInfo: storeForwardInfo, authorId: currentMessage.author?.id, text: currentMessage.text, attributes: attributes, media: currentMessage.media))
        })
    }
    return kept
}

func magniumShouldKeepDisappearingContent(_ message: Message) -> Bool {
    guard MagniumCoreHooks.isOn(.keepDisappearingMedia) else {
        return false
    }
    return message.attributes.contains(where: { $0 is AutoremoveTimeoutMessageAttribute || $0 is AutoclearTimeoutMessageAttribute })
}

public struct MagniumRecentMessage: Equatable {
    public let id: EngineMessage.Id
    public let timestamp: Int32
    public let isIncoming: Bool
    public let text: String
    public let isDeleted: Bool
}

public extension TelegramEngine.Messages {
    // The newest cloud messages of a chat, newest first, as stored locally.
    func magniumRecentMessages(peerId: EnginePeer.Id, limit: Int) -> Signal<[MagniumRecentMessage], NoError> {
        return self.account.postbox.transaction { transaction -> [MagniumRecentMessage] in
            var result: [MagniumRecentMessage] = []
            transaction.scanTopMessages(peerId: peerId, namespace: Namespaces.Message.Cloud, limit: limit, { message in
                result.append(MagniumRecentMessage(
                    id: message.id,
                    timestamp: message.timestamp,
                    isIncoming: message.flags.contains(.Incoming),
                    text: message.text,
                    isDeleted: message.attributes.contains(where: { $0 is MagniumDeletedMessageAttribute })
                ))
                return true
            })
            return result
        }
    }
}
