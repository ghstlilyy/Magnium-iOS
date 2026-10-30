#!/usr/bin/env python3
# Generates fake provisioning profiles for Magnium from build-system/fake-codesigning.
# The upstream fake profiles are issued for C67CF9S4VU.ph.telegra.Telegraph; this rewrites
# them to the team_id/bundle_id from the given configuration and re-signs them with the same
# self-signed certificate. Sideloading tools re-sign the resulting IPA anyway.

import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile

UPSTREAM_TEAM_ID = 'C67CF9S4VU'
UPSTREAM_BUNDLE_ID = 'ph.telegra.Telegraph'


def replace_identifiers(value, team_id, bundle_id):
    if isinstance(value, str):
        return value.replace(UPSTREAM_BUNDLE_ID, bundle_id).replace(UPSTREAM_TEAM_ID, team_id)
    if isinstance(value, list):
        return [replace_identifiers(item, team_id, bundle_id) for item in value]
    if isinstance(value, dict):
        return {key: replace_identifiers(item, team_id, bundle_id) for key, item in value.items()}
    return value


def main():
    if len(sys.argv) != 2:
        print('Usage: generate-fake-codesigning.py <configuration.json>')
        sys.exit(1)

    with open(sys.argv[1]) as file:
        configuration = json.load(file)
    team_id = configuration['team_id']
    bundle_id = configuration['bundle_id']

    base_path = os.path.dirname(os.path.abspath(__file__))
    source_path = os.path.join(base_path, '..', 'fake-codesigning')
    output_path = os.path.join(base_path, 'codesigning')

    shutil.rmtree(output_path, ignore_errors=True)
    os.makedirs(os.path.join(output_path, 'profiles'))
    shutil.copytree(os.path.join(source_path, 'certs'), os.path.join(output_path, 'certs'))

    with tempfile.TemporaryDirectory() as temp_path:
        identity_path = os.path.join(temp_path, 'identity.pem')
        subprocess.run([
            'openssl', 'pkcs12', '-legacy', '-nodes', '-passin', 'pass:',
            '-in', os.path.join(source_path, 'certs', 'SelfSigned.p12'),
            '-out', identity_path
        ], check=True, capture_output=True)

        profiles_path = os.path.join(source_path, 'profiles')
        for file_name in sorted(os.listdir(profiles_path)):
            if not file_name.endswith('.mobileprovision'):
                continue
            profile_data = subprocess.run([
                'openssl', 'smime', '-inform', 'der', '-verify', '-noverify',
                '-in', os.path.join(profiles_path, file_name)
            ], check=True, capture_output=True).stdout

            profile = plistlib.loads(profile_data)
            developer_certificates = profile.pop('DeveloperCertificates', None)
            profile = replace_identifiers(profile, team_id, bundle_id)
            if developer_certificates is not None:
                profile['DeveloperCertificates'] = developer_certificates

            plist_path = os.path.join(temp_path, file_name + '.plist')
            with open(plist_path, 'wb') as file:
                plistlib.dump(profile, file)

            subprocess.run([
                'openssl', 'smime', '-sign', '-nodetach', '-outform', 'der',
                '-signer', identity_path, '-in', plist_path,
                '-out', os.path.join(output_path, 'profiles', file_name)
            ], check=True, capture_output=True)
            print('{}: {}'.format(file_name, profile['Entitlements']['application-identifier']))


if __name__ == '__main__':
    main()
