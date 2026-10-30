"""A transparent, touch-through window with a CAEmitterLayer.

The render server animates the particles; Python only configures the emitter. CAEmitterCell
properties are set through key-value coding, which Core Animation supports for every property.
"""

import os
from ctypes import c_bool, c_void_p

from rubicon.objc import CGPoint, CGRect, CGSize, ObjCClass, ObjCInstance, ns_from_py, objc_id, send_message

UIWindow = ObjCClass("UIWindow")
UIImage = ObjCClass("UIImage")
UIColor = ObjCClass("UIColor")
NSValue = ObjCClass("NSValue")
CAEmitterLayer = ObjCClass("CAEmitterLayer")
CAEmitterCell = ObjCClass("CAEmitterCell")

# Just under Клодик's window, above the app.
WINDOW_LEVEL = 1998.0
# Particles start this far outside the screen, so they do not pop in.
MARGIN = 40.0


def _set(target, key, value):
    target.setValue_forKey_(value, ns_from_py(key))


def _set_pointer(target, key, pointer):
    # CGImageRef and CGColorRef are Core Foundation objects, passed as ids.
    send_message(target, "setValue:forKey:", pointer, ns_from_py(key), restype=None, argtypes=[c_void_p, objc_id])


def _cg_color(red, green, blue, alpha=1.0):
    color = UIColor.colorWithRed_green_blue_alpha_(red, green, blue, alpha)
    return color, send_message(color, "CGColor", restype=c_void_p, argtypes=[])


class Sky:
    def __init__(self, scene, reference_window, particles_path):
        self.window = UIWindow.alloc().initWithWindowScene_(ObjCInstance(scene))
        if reference_window is not None:
            self.window.setFrame_(send_message(reference_window, "frame", restype=CGRect, argtypes=[]))
        self.window.setWindowLevel_(WINDOW_LEVEL)
        self.window.setUserInteractionEnabled_(False)
        self.window.setBackgroundColor_(ObjCInstance(send_message(UIColor, "clearColor", restype=objc_id, argtypes=[])))
        self.window.setHidden_(False)
        self.particles_path = particles_path
        self.images = {}
        self.colors = []
        self.emitter = None
        self.origin = "top"
        self.size = (0.0, 0.0)

    def _image(self, name):
        image = self.images.get(name)
        if image is None:
            image = UIImage.imageWithContentsOfFile_(ns_from_py(os.path.join(self.particles_path, name + ".png")))
            self.images[name] = image
        return image

    def bounds_size(self):
        bounds = send_message(self.window, "bounds", restype=CGRect, argtypes=[])
        return bounds.size.width, bounds.size.height

    def show(self, effect, intensity, speed, size, wind, opacity):
        """Replaces the running effect. Multipliers scale the effect's own parameters."""
        self.clear()
        emitter = CAEmitterLayer.layer()
        cells = []
        for spec in effect["cells"]:
            cell = CAEmitterCell.emitterCell()
            image = self._image(spec["image"])
            _set_pointer(cell, "contents", send_message(image, "CGImage", restype=c_void_p, argtypes=[]))
            _set(cell, "birthRate", ns_from_py(spec["birth"] * intensity))
            _set(cell, "lifetime", ns_from_py(spec["life"] / max(speed, 0.3)))
            _set(cell, "lifetimeRange", ns_from_py(spec["life"] * 0.2))
            _set(cell, "velocity", ns_from_py(spec["velocity"] * speed))
            _set(cell, "velocityRange", ns_from_py(spec["velocity_range"] * speed))
            _set(cell, "yAcceleration", ns_from_py(spec["y_acceleration"] * speed * speed))
            _set(cell, "xAcceleration", ns_from_py((spec["x_acceleration"] + wind * 22.0) * speed))
            # Rain and other fast particles lean into the wind.
            _set(cell, "emissionLongitude", ns_from_py(spec["longitude"] - wind * 0.12))
            _set(cell, "emissionRange", ns_from_py(spec["emission_range"]))
            _set(cell, "scale", ns_from_py(spec["scale"] * size))
            _set(cell, "scaleRange", ns_from_py(spec["scale_range"] * size))
            _set(cell, "scaleSpeed", ns_from_py(spec["scale_speed"]))
            _set(cell, "spin", ns_from_py(spec["spin"] * speed))
            _set(cell, "spinRange", ns_from_py(spec["spin_range"]))
            _set(cell, "alphaRange", ns_from_py(spec["alpha_range"]))
            _set(cell, "alphaSpeed", ns_from_py(spec["alpha_speed"] * speed))
            if spec["color"] is not None:
                color, cg_color = _cg_color(*spec["color"])
                self.colors.append(color)
                _set_pointer(cell, "color", cg_color)
                for channel in ("redRange", "greenRange", "blueRange"):
                    _set(cell, channel, ns_from_py(spec["color_range"]))
            cells.append(cell)
        _set(emitter, "emitterCells", ns_from_py(cells))
        _set(emitter, "renderMode", ns_from_py(effect["render"]))
        _set(emitter, "opacity", ns_from_py(opacity))
        self.origin = effect["origin"]
        self.emitter = emitter
        self.layout()
        window_layer = ObjCInstance(send_message(self.window, "layer", restype=objc_id, argtypes=[]))
        window_layer.addSublayer_(emitter)

    def layout(self):
        """Places the emitter for the window's current size (rotation, split view)."""
        if self.emitter is None:
            return
        width, height = self.bounds_size()
        self.size = (width, height)
        if self.origin == "area":
            position, size, shape = CGPoint(width / 2.0, height / 2.0), CGSize(width, height), "rectangle"
        elif self.origin == "bottom":
            position, size, shape = CGPoint(width / 2.0, height + MARGIN), CGSize(width * 1.2, 1.0), "line"
        else:
            # Wider than the screen, so wind does not leave an empty band at one edge.
            position, size, shape = CGPoint(width / 2.0, -MARGIN), CGSize(width * 1.6, 1.0), "line"
        _set(self.emitter, "emitterPosition", NSValue.valueWithCGPoint_(position))
        _set(self.emitter, "emitterSize", NSValue.valueWithCGSize_(size))
        _set(self.emitter, "emitterShape", ns_from_py(shape))
        _set(self.emitter, "emitterMode", ns_from_py("surface" if shape == "rectangle" else "outline"))

    def set_visible(self, visible):
        if self.emitter is None:
            return
        # Pausing births lets the particles already on screen finish instead of vanishing.
        _set(self.emitter, "birthRate", ns_from_py(1.0 if visible else 0.0))

    def clear(self):
        if self.emitter is not None:
            self.emitter.removeFromSuperlayer()
            self.emitter = None
        self.colors = []

    def remove(self):
        self.clear()
        self.window.setHidden_(True)
        self.window = None


def low_power_mode():
    process = send_message(ObjCClass("NSProcessInfo"), "processInfo", restype=objc_id, argtypes=[])
    return bool(send_message(process, "isLowPowerModeEnabled", restype=c_bool, argtypes=[]))
