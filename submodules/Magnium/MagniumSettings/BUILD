load("@build_bazel_rules_swift//swift:swift.bzl", "swift_library")

# Native Magnium features and their switches. Foundation only, so any UI module can read them.
swift_library(
    name = "MagniumSettings",
    module_name = "MagniumSettings",
    srcs = glob([
        "Sources/**/*.swift",
    ]),
    copts = [
        "-warnings-as-errors",
    ],
    visibility = [
        "//visibility:public",
    ],
)
