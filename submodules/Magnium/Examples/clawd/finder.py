"""Finds Telegram UI elements by class name, straight through the Objective-C runtime.

Telegram builds its UI from AsyncDisplayKit nodes; a node's view is an _ASDisplayView, so
each view is matched both by its own class and by its node's class. Swift class names are
mangled ("_TtC22ChatTextInputPanelNode22ChatTextInputPanelNode"), which still contain the
plain name, so a substring match works for both.
"""

from ctypes import c_bool, c_char_p, c_double, c_ulong

from rubicon.objc import SEL, CGPoint, CGRect, ObjCClass, objc_id, send_message
from rubicon.objc.runtime import libobjc

libobjc.object_getClassName.restype = c_char_p
libobjc.object_getClassName.argtypes = [objc_id]

UIApplication = ObjCClass("UIApplication")
UIWindowScene = ObjCClass("UIWindowScene")

# Lists hold thousands of views (messages, chats); nothing we look for is inside one.
PRUNED_CLASS_PARTS = ("ListViewImpl", "CoreVirtualListView", "ChatMessage", "ChatListItemNode", "UITableView", "UICollectionView")
MAX_VIEWS = 6000

_NODE_SELECTOR = SEL("asyncdisplaykit_node")
_responds_to_node = {}


def _id(receiver, selector, *args, argtypes=()):
    result = send_message(receiver, selector, *args, restype=objc_id, argtypes=list(argtypes))
    return result if result.value else None


def _bool(receiver, selector, *args, argtypes=()):
    return send_message(receiver, selector, *args, restype=c_bool, argtypes=list(argtypes))


def class_name(pointer):
    return libobjc.object_getClassName(pointer).decode("utf-8", "replace")


def _node(view, view_class):
    responds = _responds_to_node.get(view_class)
    if responds is None:
        responds = _bool(view, "respondsToSelector:", _NODE_SELECTOR, argtypes=[SEL])
        _responds_to_node[view_class] = responds
    return _id(view, "asyncdisplaykit_node") if responds else None


def _array(array):
    if array is None:
        return []
    count = send_message(array, "count", restype=c_ulong, argtypes=[])
    return [_id(array, "objectAtIndex:", index, argtypes=[c_ulong]) for index in range(count)]


def _subviews(view):
    return _array(_id(view, "subviews"))


def app_windows(excluded=None):
    """The visible windows of the foreground scene, bottom to top, and that scene."""
    application = _id(UIApplication, "sharedApplication")
    for scene in _array(_id(_id(application, "connectedScenes"), "allObjects")):
        if not _bool(scene, "isKindOfClass:", UIWindowScene, argtypes=[objc_id]):
            continue
        # UISceneActivationStateForegroundActive = 0, ForegroundInactive = 1.
        if send_message(scene, "activationState", restype=c_ulong, argtypes=[]) > 1:
            continue
        windows = []
        for window in _array(_id(scene, "windows")):
            if excluded is not None and window.value == excluded.value:
                continue
            if _bool(window, "isHidden"):
                continue
            windows.append(window)
        return scene, windows
    return None, []


def find(windows, class_parts_by_key):
    """Returns {key: [view, ...]} in drawing order (later is on top)."""
    found = {key: [] for key in class_parts_by_key}
    stack = list(reversed(windows))
    visited = 0
    while stack and visited < MAX_VIEWS:
        view = stack.pop()
        visited += 1
        if _bool(view, "isHidden"):
            continue
        names = class_name(view)
        node = _node(view, names)
        if node is not None:
            names = names + " " + class_name(node)
        for key, parts in class_parts_by_key.items():
            if any(part in names for part in parts):
                found[key].append(view)
        if any(part in names for part in PRUNED_CLASS_PARTS):
            continue
        # Depth-first in drawing order: push children reversed so the first is visited first.
        stack.extend(reversed(_subviews(view)))
    return found


def frame_in_window(view, window):
    bounds = send_message(view, "bounds", restype=CGRect, argtypes=[])
    return send_message(view, "convertRect:toView:", bounds, window, restype=CGRect, argtypes=[CGRect, objc_id])


def window_of(view):
    return _id(view, "window")


def is_on_top(view, window, point):
    """Whether a touch at `point` (window coordinates) would land in `view`: it is visible and uncovered."""
    hit = _id(window, "hitTest:withEvent:", point, None, argtypes=[CGPoint, objc_id])
    return hit is not None and _bool(hit, "isDescendantOfView:", view, argtypes=[objc_id])


def is_effectively_visible(view):
    """No hidden or transparent ancestor; for views that hit testing passes through."""
    current = view
    for _ in range(64):
        if current is None:
            return False
        if _bool(current, "isHidden") or send_message(current, "alpha", restype=c_double, argtypes=[]) < 0.01:
            return False
        superview = _id(current, "superview")
        if superview is None:
            return class_name(current).find("Window") >= 0
        current = superview
    return False


def convert_rect(rect, source_window, target_window):
    return send_message(source_window, "convertRect:toWindow:", rect, target_window, restype=CGRect, argtypes=[CGRect, objc_id])
