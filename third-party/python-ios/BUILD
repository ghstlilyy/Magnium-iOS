load("@rules_cc//cc:objc_library.bzl", "objc_library")
load(
    "@build_bazel_rules_apple//apple:apple.bzl",
    "apple_dynamic_framework_import",
)
load(
    "@build_bazel_rules_apple//apple:resources.bzl",
    "apple_resource_group",
)
load(
    "//third-party/python-ios:prepared/frameworks.bzl",
    "PYTHON_EXTENSION_FRAMEWORKS",
)

# Run prepare.py first: it downloads CPython for iOS and fills prepared/.

apple_dynamic_framework_import(
    name = "PythonFramework",
    framework_imports = glob(["prepared/Frameworks/Python.framework/**"]),
    visibility = ["//visibility:public"],
)

[
    apple_dynamic_framework_import(
        name = "PythonExtension_" + name,
        framework_imports = glob(["prepared/Frameworks/{}.framework/**".format(name)]),
    )
    for name in PYTHON_EXTENSION_FRAMEWORKS
]

# Embeds every stdlib extension module; CPython loads them through the .fwork stubs.
objc_library(
    name = "PythonExtensions",
    deps = [":PythonExtension_" + name for name in PYTHON_EXTENSION_FRAMEWORKS],
    visibility = ["//visibility:public"],
)

# The stdlib, at python/lib/python3.X inside the app bundle.
apple_resource_group(
    name = "PythonStdlib",
    structured_resources = glob(["prepared/python/**"]),
    strip_structured_resources_prefixes = ["prepared"],
    visibility = ["//visibility:public"],
)
