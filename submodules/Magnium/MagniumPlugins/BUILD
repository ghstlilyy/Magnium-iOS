load("@build_bazel_rules_swift//swift:swift.bzl", "swift_library")
load(
    "@build_bazel_rules_apple//apple:resources.bzl",
    "apple_resource_group",
)

swift_library(
    name = "MagniumPlugins",
    module_name = "MagniumPlugins",
    srcs = glob([
        "Sources/**/*.swift",
    ]),
    copts = [
        "-warnings-as-errors",
    ],
    deps = [
        "//submodules/SSignalKit/SwiftSignalKit:SwiftSignalKit",
        "//submodules/Magnium/MagniumPython:MagniumPython",
    ],
    visibility = [
        "//visibility:public",
    ],
)

# The `magnium` Python package, at python/app/magnium inside the app bundle.
apple_resource_group(
    name = "MagniumPluginsPythonResources",
    structured_resources = glob(["Resources/python/**/*.py"]),
    strip_structured_resources_prefixes = ["Resources"],
    visibility = [
        "//visibility:public",
    ],
)
