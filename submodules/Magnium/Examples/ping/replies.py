# A second module, imported by main.py with a relative import.


def device_description():
    # Full Objective-C access through rubicon-objc.
    from rubicon.objc import ObjCClass
    device = ObjCClass("UIDevice").currentDevice
    return "{} {} {}".format(device.model, device.systemName, device.systemVersion)


def reply_for(text):
    if text == "!ping":
        return "pong 🏓"
    if text == "!device":
        return device_description()
    return None
