load("@rules_cc//cc:objc_library.bzl", "objc_library")

objc_library(
    name = "MagniumPython",
    enable_modules = True,
    module_name = "MagniumPython",
    srcs = glob([
        "Sources/*.m",
    ]),
    copts = [
        "-Werror",
    ],
    hdrs = glob([
        "PublicHeaders/MagniumPython/*.h",
    ]),
    includes = [
        "PublicHeaders",
    ],
    deps = [
        "//third-party/python-ios:PythonFramework",
    ],
    sdk_frameworks = [
        "Foundation",
    ],
    visibility = [
        "//visibility:public",
    ],
)
