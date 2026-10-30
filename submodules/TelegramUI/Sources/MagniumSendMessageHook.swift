import Foundation
import MagniumSettings
import TelegramCore
import MagniumPlugins

// Runs the `send_message` plugin hook over outgoing messages.
// Payload: {"text": str, "peer_id": int, "thread_id": int | None, "has_media": bool}.
// A plugin may change "text" (HookStrategy.MODIFY) or drop the message (HookStrategy.CANCEL).
func magniumApplySendMessageHook(_ messages: [EnqueueMessage], peerId: EnginePeer.Id) -> [EnqueueMessage] {
    var messages = messages
    // Native features first, so plugins see what will actually be sent.
    if MagniumSettings.isOn(.silentByDefault) {
        messages = messages.map { message in
            return message.withUpdatedAttributes { attributes in
                if attributes.contains(where: { $0 is NotificationInfoMessageAttribute }) {
                    return attributes
                }
                var attributes = attributes
                attributes.append(NotificationInfoMessageAttribute(flags: .muted))
                return attributes
            }
        }
    }
    if MagniumSettings.isOn(.stripTrackingParameters) {
        messages = messages.map { message in
            // Entity ranges would no longer match a shorter text, so formatted messages stay as they are.
            guard case let .message(text, attributes, inlineStickers, mediaReference, threadId, replyToMessageId, replyToStoryId, localGroupingKey, correlationId, bubbleUpEmojiOrStickersets) = message, !attributes.contains(where: { $0 is TextEntitiesMessageAttribute || $0 is RichTextMessageAttribute }), let cleaned = MagniumTextTools.removingTrackingParameters(from: text) else {
                return message
            }
            return .message(text: cleaned, attributes: attributes, inlineStickers: inlineStickers, mediaReference: mediaReference, threadId: threadId, replyToMessageId: replyToMessageId, replyToStoryId: replyToStoryId, localGroupingKey: localGroupingKey, correlationId: correlationId, bubbleUpEmojiOrStickersets: bubbleUpEmojiOrStickersets)
        }
    }
    return messages.compactMap { message -> EnqueueMessage? in
        guard case let .message(text, attributes, inlineStickers, mediaReference, threadId, replyToMessageId, replyToStoryId, localGroupingKey, correlationId, bubbleUpEmojiOrStickersets) = message else {
            return message
        }
        let payload: [String: Any] = [
            "text": text,
            "peer_id": peerId.toInt64(),
            "thread_id": threadId.flatMap { NSNumber(value: $0) } ?? NSNull(),
            "has_media": mediaReference != nil
        ]
        let result = MagniumPluginManager.shared.runHook("send_message", payload: payload)
        switch result.strategy {
        case .default:
            return message
        case .cancel:
            return nil
        case .modify:
            guard let updatedText = (result.payload as? [String: Any])?["text"] as? String, updatedText != text else {
                return message
            }
            // A rich message's layout is built from its text; leave it alone rather than desynchronize it.
            if attributes.contains(where: { $0 is RichTextMessageAttribute }) {
                return message
            }
            // Entity ranges refer to the old text.
            let updatedAttributes = attributes.filter { !($0 is TextEntitiesMessageAttribute) }
            return .message(text: updatedText, attributes: updatedAttributes, inlineStickers: inlineStickers, mediaReference: mediaReference, threadId: threadId, replyToMessageId: replyToMessageId, replyToStoryId: replyToStoryId, localGroupingKey: localGroupingKey, correlationId: correlationId, bubbleUpEmojiOrStickersets: bubbleUpEmojiOrStickersets)
        }
    }
}
