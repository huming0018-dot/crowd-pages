"""Shared base/Pro entry matrix; package helpers are always replaced by text stubs."""
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import zipfile

from test_participant_existing_chain import case

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('participant_builder', ROOT/'build_participant.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def matrix():
    with tempfile.TemporaryDirectory(prefix='participant-pro-matrix-') as folder:
        root = Path(folder)
        runtime = root/'runtime'
        runtime.mkdir()
        pro_archive = ROOT/'releases/participants/r1-mac-install-20261026/crowd-v4.2.104-pro-native128-mac-install-test.zip'
        with zipfile.ZipFile(pro_archive) as archive:
            for name in ('participant_pro_native.py','portable_node.py','PRO-LOCAL-SOURCE-PINS.json'):
                (runtime/name).write_bytes(archive.read('.crowd-support/pro-runtime/'+name))
        (runtime/'PRO-RUNTIME.json').write_text(json.dumps({'schema':'crowd-participant-pro-runtime-v1','files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in runtime.iterdir()}}))
        for profile, package in [
            ('base', ROOT/'releases/participants/v1-base-20261026-r2/crowd-v4.2.94-base-mac.zip'),
            ('pro', ROOT/'releases/participants/r1-mac-install-20261026/crowd-v4.2.104-pro-native128-mac-install-test.zip'),
        ]:
            with zipfile.ZipFile(package) as archive:
                helper = root/(profile+'-helper')
                helper.write_bytes(archive.read('.crowd-support/crowd-v4-participant-updater'))
                helper.chmod(0o600)  # Never executed, including builder preflight.
                extension = root/(profile+'-extension.zip')
                name = next(n for n in archive.namelist() if n.endswith('participant-extension.zip'))
                extension.write_bytes(archive.read(name))
            output = root/profile/'package.zip'
            with patch.object(builder.subprocess, 'check_output', return_value='arm64 x86_64'), \
                    patch.object(builder.subprocess, 'run'):
                result = builder.build(extension, helper, output, runtime if profile=='pro' else None)
            # Actual standalone reconnect has no runtime, even with a Pro helper.
            reconnect = Path(result['reconnect']['path'])
            with zipfile.ZipFile(reconnect) as archive:
                assert not any(n.startswith('.crowd-support/pro-runtime/') for n in archive.namelist())
            for selected, standalone in [(output, False), (reconnect, True)]:
                print(json.dumps({'profile':profile,'package':str(selected),'standalone':standalone}),flush=True)
                case('pro_existing', selected, standalone, pro_package=(profile=='pro'))
                case('success', selected, standalone, pro_package=(profile=='pro'))
            if profile=='base':
                # Runtime presence cannot grant a generic helper the Pro RPC contract.
                with patch.object(builder.subprocess, 'check_output', return_value='arm64 x86_64'), \
                        patch.object(builder.subprocess, 'run'):
                    builder.build(extension,helper,root/'mixed/package.zip',runtime)
                case('pro_existing',root/'mixed/package.zip',runtime_payload=True)
        print('PASS shared base/Pro x existing Pro/DOM x install/reconnect; all helper transports stubbed; protected bytes/mtimes unchanged')


if __name__ == '__main__':
    matrix()
