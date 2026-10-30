"""Chats and messages of the logged-in account."""

from ._host import call


def current_peer_id():
    """The peer id of the chat on screen, or None."""
    result = call("chat.current")
    return None if result is None else result["peer_id"]


def my_peer_id():
    return call("account.info")["peer_id"]


def recent_messages(peer_id, limit=100):
    """The newest stored messages of a chat, newest first:
    [{"message_id", "timestamp", "outgoing", "text", "deleted"}]."""
    return call("messages.recent", peer_id=int(peer_id), limit=int(limit)) or []


def send_message(peer_id, text):
    call("messages.send", peer_id=int(peer_id), text=str(text))


def save_media_to_gallery(peer_id, message_id):
    """Saves the photo or video of a message to the photo library."""
    call("media.save_to_gallery", peer_id=int(peer_id), message_id=int(message_id))
