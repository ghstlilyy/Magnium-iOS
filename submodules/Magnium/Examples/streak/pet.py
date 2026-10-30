"""The pet on screen: an animated sprite, its accessories and the streak counter, in a
transparent touch-through window above the app."""

import json
import os

from rubicon.objc import CGRect, CGRectMake, CGSize, ObjCClass, ObjCInstance, ns_from_py, objc_id, send_message

UIWindow = ObjCClass("UIWindow")
UIImageView = ObjCClass("UIImageView")
UIImage = ObjCClass("UIImage")
UIColor = ObjCClass("UIColor")
UILabel = ObjCClass("UILabel")
UIFont = ObjCClass("UIFont")

SCALE = 2.0
CANVAS = 24
WINDOW_LEVEL = 1997.0
FRAMES_PER_SECOND = 5.0


def _clear_color():
    return ObjCInstance(send_message(UIColor, "clearColor", restype=objc_id, argtypes=[]))


def _pixelated(view):
    layer = ObjCInstance(send_message(view, "layer", restype=objc_id, argtypes=[]))
    layer.setMagnificationFilter_(ns_from_py("nearest"))


class PetView:
    def __init__(self, scene, reference_window, sprites_path):
        self.sprites_path = sprites_path
        with open(os.path.join(sprites_path, "layout.json")) as file:
            self.layout = json.load(file)
        self.images = {}

        self.window = UIWindow.alloc().initWithWindowScene_(ObjCInstance(scene))
        if reference_window is not None:
            self.window.setFrame_(send_message(reference_window, "frame", restype=CGRect, argtypes=[]))
        self.window.setWindowLevel_(WINDOW_LEVEL)
        self.window.setUserInteractionEnabled_(False)
        self.window.setBackgroundColor_(_clear_color())
        self.window.setHidden_(False)

        size = CANVAS * SCALE
        self.container = ObjCClass("UIView").alloc().initWithFrame_(CGRectMake(0, 0, size, size + 18))
        self.window.addSubview_(self.container)

        self.body = UIImageView.alloc().initWithFrame_(CGRectMake(0, 0, size, size))
        _pixelated(self.body)
        self.container.addSubview_(self.body)

        self.accessories = {}
        for slot in ("scarf", "glasses", "hat"):
            view = UIImageView.alloc().initWithFrame_(CGRectMake(0, 0, 1, 1))
            _pixelated(view)
            view.setHidden_(True)
            self.container.addSubview_(view)
            self.accessories[slot] = view

        self.label = UILabel.alloc().initWithFrame_(CGRectMake(-16, size, size + 32, 18))
        self.label.setTextAlignment_(1)
        self.label.setFont_(UIFont.boldSystemFontOfSize_(13.0))
        self.label.setTextColor_(ObjCInstance(send_message(UIColor, "whiteColor", restype=objc_id, argtypes=[])))
        label_layer = ObjCInstance(send_message(self.label, "layer", restype=objc_id, argtypes=[]))
        label_layer.setShadowOpacity_(0.8)
        label_layer.setShadowRadius_(2.0)
        label_layer.setShadowOffset_(CGSize(0, 1))
        self.container.addSubview_(self.label)
        self.container.setHidden_(True)
        self.shown = None

    def _image(self, name):
        image = self.images.get(name)
        if image is None:
            image = UIImage.imageWithContentsOfFile_(ns_from_py(os.path.join(self.sprites_path, name + ".png")))
            self.images[name] = image
        return image

    def configure(self, stage, color, equipped, streak_text):
        """equipped: {"hat": name or "none", "glasses": ..., "scarf": ...}."""
        key = (stage, color, tuple(sorted(equipped.items())), streak_text)
        if key == self.shown:
            return
        self.shown = key
        if stage == "egg":
            frames = [self._image("egg_{}".format(frame)) for frame in range(4)]
        else:
            frames = [self._image("{}_{}_{}".format(stage, color, frame)) for frame in range(4)]
        self.body.stopAnimating()
        self.body.setImage_(frames[0])
        self.body.setAnimationImages_(ns_from_py(frames))
        self.body.setAnimationDuration_(len(frames) / FRAMES_PER_SECOND)
        self.body.startAnimating()

        stage_layout = self.layout["stages"].get(stage)
        for slot, view in self.accessories.items():
            name = equipped.get(slot, "none")
            info = self.layout["accessories"].get(name)
            if stage_layout is None or info is None:
                view.setHidden_(True)
                continue
            y = stage_layout[info["anchor"]] + info["offset"]
            view.setImage_(self._image(name))
            view.setFrame_(CGRectMake(info["x"] * SCALE, y * SCALE, info["width"] * SCALE, info["height"] * SCALE))
            view.setHidden_(False)
        self.label.setText_(ns_from_py(streak_text))

    def place(self, x, y):
        """Puts the pet's top right corner at (x, y) in window coordinates."""
        size = CANVAS * SCALE
        self.container.setFrame_(CGRectMake(round(x - size), round(y), size, size + 18))
        if self.container.isHidden():
            self.container.setHidden_(False)

    def hide(self):
        if not self.container.isHidden():
            self.container.setHidden_(True)

    def window_width(self):
        return send_message(self.window, "bounds", restype=CGRect, argtypes=[]).size.width

    def remove(self):
        self.body.stopAnimating()
        self.container.removeFromSuperview()
        self.window.setHidden_(True)
        self.window = None
