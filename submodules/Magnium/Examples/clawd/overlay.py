"""A transparent, touch-through window above the app that holds the sprites.

Sprites live in their own window rather than inside Telegram's views, so they are never clipped
by them and leave Telegram's hierarchy untouched. The window has no root view controller, so it
does not take part in status bar appearance.
"""

import os

from rubicon.objc import CGRect, CGRectMake, ObjCClass, ObjCInstance, ns_from_py, objc_id, send_message

UIWindow = ObjCClass("UIWindow")
UIImageView = ObjCClass("UIImageView")
UIImage = ObjCClass("UIImage")
UIColor = ObjCClass("UIColor")

SPRITE_WIDTH = 32.0
SPRITE_HEIGHT = 28.0
FRAMES_PER_SECOND = 12.0
WINDOW_LEVEL = 1999.0


class Overlay:
    def __init__(self, scene, reference_window, assets_path):
        self.window = UIWindow.alloc().initWithWindowScene_(ObjCInstance(scene))
        # Same frame as the app's windows, so window coordinates match.
        if reference_window is not None:
            self.window.setFrame_(send_message(reference_window, "frame", restype=CGRect, argtypes=[]))
        self.window.setWindowLevel_(WINDOW_LEVEL)
        self.window.setUserInteractionEnabled_(False)
        self.window.setBackgroundColor_(ObjCInstance(send_message(UIColor, "clearColor", restype=objc_id, argtypes=[])))
        self.window.setHidden_(False)

        names = sorted(name for name in os.listdir(assets_path) if name.startswith("frame_") and name.endswith(".png"))
        self.frames = [UIImage.imageWithContentsOfFile_(ns_from_py(os.path.join(assets_path, name))) for name in names]
        self.sprites = {}
        self.animated = True

    def sprite(self, key):
        sprite = self.sprites.get(key)
        if sprite is None:
            sprite = UIImageView.alloc().initWithFrame_(CGRectMake(0, 0, SPRITE_WIDTH, SPRITE_HEIGHT))
            # Pixel art: scale without smoothing.
            layer = ObjCInstance(send_message(sprite, "layer", restype=objc_id, argtypes=[]))
            layer.setMagnificationFilter_(ns_from_py("nearest"))
            sprite.setImage_(self.frames[0])
            sprite.setAnimationImages_(ns_from_py(self.frames))
            sprite.setAnimationDuration_(len(self.frames) / FRAMES_PER_SECOND)
            sprite.setHidden_(True)
            self.window.addSubview_(sprite)
            self.sprites[key] = sprite
        return sprite

    def place(self, key, x, y):
        """Puts the sprite's bottom centre at (x, y) in window coordinates."""
        sprite = self.sprite(key)
        sprite.setFrame_(CGRectMake(round(x - SPRITE_WIDTH / 2.0), round(y - SPRITE_HEIGHT), SPRITE_WIDTH, SPRITE_HEIGHT))
        if sprite.isHidden():
            sprite.setHidden_(False)
        if self.animated and not sprite.isAnimating():
            sprite.startAnimating()
        elif not self.animated and sprite.isAnimating():
            sprite.stopAnimating()

    def hide(self, key):
        sprite = self.sprites.get(key)
        if sprite is not None and not sprite.isHidden():
            sprite.setHidden_(True)
            sprite.stopAnimating()

    def remove(self):
        for sprite in self.sprites.values():
            sprite.stopAnimating()
            sprite.removeFromSuperview()
        self.sprites = {}
        self.window.setHidden_(True)
        self.window = None
