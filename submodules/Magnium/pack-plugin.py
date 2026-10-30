#!/usr/bin/env python3
# Packs a plugin directory (manifest.json at its root) into a .mpp file.
# Usage: pack-plugin.py <plugin directory> [output.mpp]

import json
import os
import sys
import zipfile


def main():
    if len(sys.argv) not in (2, 3):
        print(__doc__ or 'Usage: pack-plugin.py <plugin directory> [output.mpp]')
        sys.exit(1)
    source = os.path.abspath(sys.argv[1])
    with open(os.path.join(source, 'manifest.json'), encoding='utf-8') as file:
        manifest = json.load(file)
    output = sys.argv[2] if len(sys.argv) == 3 else os.path.join(os.path.dirname(source), manifest['id'] + '.mpp')

    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for directory, directories, file_names in os.walk(source):
            directories[:] = sorted(name for name in directories if name != '__pycache__' and not name.startswith('.'))
            for file_name in sorted(file_names):
                if file_name.startswith('.') or file_name.endswith('.pyc'):
                    continue
                path = os.path.join(directory, file_name)
                archive.write(path, os.path.relpath(path, source))
    print('Packed {}'.format(output))


if __name__ == '__main__':
    main()
