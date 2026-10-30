load("@build_bazel_rules_swift//swift:swift.bzl", "swift_library")

swift_library(
    name = "MagniumPluginsUI",
    module_name = "MagniumPluginsUI",
    srcs = glob([
        "Sources/**/*.swift",
    ]),
    copts = [
        "-warnings-as-errors",
    ],
    deps = [
        "//submodules/SSignalKit/SwiftSignalKit:SwiftSignalKit",
        "//submodules/Display:Display",
        "//submodules/TelegramCore:TelegramCore",
        "//submodules/TelegramPresentationData:TelegramPresentationData",
        "//submodules/ItemListUI:ItemListUI",
        "//submodules/PresentationDataUtils:PresentationDataUtils",
        "//submodules/AccountContext:AccountContext",
        "//submodules/LegacyMediaPickerUI:LegacyMediaPickerUI",
        "//submodules/Magnium/MagniumPlugins:MagniumPlugins",
        "//submodules/OverlayStatusController:OverlayStatusController",
        "//submodules/Magnium/MagniumServer:MagniumServer",
        "//submodules/Magnium/MagniumSettings:MagniumSettings",
    ],
    visibility = [
        "//visibility:public",
    ],
)
