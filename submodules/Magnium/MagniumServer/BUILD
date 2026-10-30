load("@build_bazel_rules_swift//swift:swift.bzl", "swift_library")

# The client of a future Magnium server: plugin catalog and badges. See ../SERVER.md.
swift_library(
    name = "MagniumServer",
    module_name = "MagniumServer",
    srcs = glob([
        "Sources/**/*.swift",
    ]),
    copts = [
        "-warnings-as-errors",
    ],
    deps = [
        "//submodules/SSignalKit/SwiftSignalKit:SwiftSignalKit",
    ],
    visibility = [
        "//visibility:public",
    ],
)
