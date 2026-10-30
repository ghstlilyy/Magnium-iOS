#!/usr/bin/env python3
# Downloads the BeeWare Python-Apple-support package and lays it out for Bazel.
#
# iOS only loads native code from signed frameworks, so every stdlib extension module
# (lib-dynload/*.so) becomes its own framework, and a .fwork stub is left in its place;
# CPython's AppleFrameworkLoader follows the stub. This mirrors install_python() in the
# package's build/utils.sh, which does the same at Xcode build time.
#
# Output (gitignored):
#   prepared/Frameworks/<module>.framework   one per extension module, plus Python.framework
#   prepared/python/lib/python3.X/...        the stdlib, copied into the app bundle as is
#   prepared/frameworks.bzl                  the framework names, read by BUILD
#
# Device (arm64) only for now; a simulator build would need the simulator slice too.

import hashlib
import os
import plistlib
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

PYTHON_VERSION = '3.14'
PACKAGE_BUILD = 'b14'
PACKAGE_SHA256 = '703ff822529f46edcbcd8b88096b2544f6990f3109ad38b4b4b61bb489a7c1ee'
PACKAGE_URL = 'https://github.com/beeware/Python-Apple-support/releases/download/{0}-{1}/Python-{0}-iOS-support.{1}.tar.gz'.format(PYTHON_VERSION, PACKAGE_BUILD)

# Pure-Python packages bundled into site-packages: (wheel url, sha256).
# rubicon-objc is the Objective-C bridge that gives plugins the whole UIKit/ObjC runtime.
BUNDLED_WHEELS = [
    ('https://files.pythonhosted.org/packages/09/68/f2548a31901e437c49b676a395bb7bef9f879d4df496e0a18e17160816ad/rubicon_objc-0.5.7-py3-none-any.whl', '3dc76bc29f300ee6b9a4f408748099f70f8472ca59fe70cca42dfa1f2f1bfe3f'),
]

SLICE = 'ios-arm64'
ARCH = 'arm64'

# Not usable inside the app, and the test suite alone is 37 MB.
STDLIB_EXCLUDES = ['test', 'idlelib', 'tkinter', 'turtledemo', 'ensurepip', '__phello__']

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_PATH = os.path.join(BASE_PATH, 'download')
OUTPUT_PATH = os.path.join(BASE_PATH, 'prepared')


def is_test_extension(file_name):
    # CPython's own test helpers: _testcapi, _ctypes_test, xxlimited, ...
    module_name = file_name.split('.')[0]
    return module_name.startswith('_test') or module_name.startswith('xx') or module_name == '_ctypes_test'


def run(*arguments):
    subprocess.run(arguments, check=True, capture_output=True)


def fetch(url, sha256, file_name):
    path = os.path.join(DOWNLOAD_PATH, file_name)
    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    if not os.path.exists(path):
        print('Downloading {}'.format(url))
        urllib.request.urlretrieve(url, path)
    with open(path, 'rb') as file:
        digest = hashlib.sha256(file.read()).hexdigest()
    if digest != sha256:
        print('Checksum mismatch for {}: {}'.format(path, digest))
        sys.exit(1)
    return path


def install_wheels(site_packages_path):
    for url, sha256 in BUNDLED_WHEELS:
        wheel_path = fetch(url, sha256, url.split('/')[-1])
        with zipfile.ZipFile(wheel_path) as wheel:
            wheel.extractall(site_packages_path)


def fetch_package():
    archive_path = fetch(PACKAGE_URL, PACKAGE_SHA256, 'py.tar.gz')
    xcframework_path = os.path.join(DOWNLOAD_PATH, 'Python.xcframework')
    shutil.rmtree(xcframework_path, ignore_errors=True)
    with tarfile.open(archive_path) as archive:
        archive.extractall(DOWNLOAD_PATH, filter='data')
    return xcframework_path


def make_extension_framework(xcframework_path, frameworks_path, stdlib_path, so_path):
    # lib-dynload/_hashlib.cpython-314-iphoneos.so -> _hashlib.framework/_hashlib
    module_name = os.path.relpath(so_path, os.path.join(stdlib_path, 'lib-dynload')).split('.')[0].replace('/', '.')
    framework_path = os.path.join(frameworks_path, module_name + '.framework')
    os.makedirs(framework_path)

    with open(os.path.join(xcframework_path, 'build', 'iOS-dylib-Info-template.plist'), 'rb') as file:
        info = plistlib.load(file)
    info['CFBundleExecutable'] = module_name
    info['CFBundleIdentifier'] = 'org.python.' + module_name.replace('_', '-')
    info['CFBundlePackageType'] = 'FMWK'
    with open(os.path.join(framework_path, 'Info.plist'), 'wb') as file:
        plistlib.dump(info, file)

    binary_path = os.path.join(framework_path, module_name)
    shutil.move(so_path, binary_path)
    run('install_name_tool', '-id', '@rpath/{0}.framework/{0}'.format(module_name), binary_path)

    privacy_path = os.path.join(os.path.dirname(so_path), module_name + '.xcprivacy')
    if os.path.exists(privacy_path):
        shutil.move(privacy_path, os.path.join(framework_path, 'PrivacyInfo.xcprivacy'))

    # Paths are relative to the app bundle root, as CPython resolves them.
    stub_path = so_path[:-len('.so')] + '.fwork'
    with open(stub_path, 'w') as file:
        file.write('Frameworks/{0}.framework/{0}'.format(module_name))
    with open(os.path.join(framework_path, module_name + '.origin'), 'w') as file:
        file.write(os.path.relpath(stub_path, OUTPUT_PATH))
    return module_name


def main():
    xcframework_path = fetch_package()

    shutil.rmtree(OUTPUT_PATH, ignore_errors=True)
    frameworks_path = os.path.join(OUTPUT_PATH, 'Frameworks')
    os.makedirs(frameworks_path)
    shutil.copytree(os.path.join(xcframework_path, SLICE, 'Python.framework'), os.path.join(frameworks_path, 'Python.framework'), symlinks=True)

    # The shared part of the stdlib, then the slice-specific part (lib-dynload, sysconfig) over it.
    lib_path = os.path.join(OUTPUT_PATH, 'python', 'lib')
    ignore = shutil.ignore_patterns('libpython*.dylib', '__pycache__')
    shutil.copytree(os.path.join(xcframework_path, 'lib'), lib_path, ignore=ignore)
    shutil.copytree(os.path.join(xcframework_path, SLICE, 'lib-' + ARCH), lib_path, ignore=ignore, dirs_exist_ok=True)

    stdlib_path = os.path.join(lib_path, 'python' + PYTHON_VERSION)
    for name in STDLIB_EXCLUDES:
        shutil.rmtree(os.path.join(stdlib_path, name), ignore_errors=True)
    install_wheels(os.path.join(stdlib_path, 'site-packages'))

    module_names = []
    for directory, _, file_names in os.walk(stdlib_path):
        for file_name in sorted(file_names):
            if file_name.endswith('.so'):
                if is_test_extension(file_name):
                    os.remove(os.path.join(directory, file_name))
                    continue
                module_names.append(make_extension_framework(xcframework_path, frameworks_path, stdlib_path, os.path.join(directory, file_name)))
    module_names.sort()

    with open(os.path.join(OUTPUT_PATH, 'frameworks.bzl'), 'w') as file:
        file.write('# Generated by prepare.py\n')
        file.write('PYTHON_VERSION = "{}"\n'.format(PYTHON_VERSION))
        file.write('PYTHON_EXTENSION_FRAMEWORKS = [\n')
        for name in module_names:
            file.write('    "{}",\n'.format(name))
        file.write(']\n')

    print('Prepared Python {} with {} extension frameworks'.format(PYTHON_VERSION, len(module_names)))


if __name__ == '__main__':
    main()
