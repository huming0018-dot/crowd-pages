"""Freeze base candidate bytes; only a freshly compiled -DTESTING helper is run."""
import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parent
UPDATER = ROOT.parents[1]/'crawler-extension/v4/updater'
spec = importlib.util.spec_from_file_location('participant_builder',ROOT/'build_participant.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def build(previous, output):
    with tempfile.TemporaryDirectory(prefix='participant-candidate-build-',dir='/tmp') as folder:
        work = Path(folder).resolve()
        helper, extension = work/'production-helper', work/'extension.zip'
        with zipfile.ZipFile(previous) as archive:
            helper.write_bytes(archive.read('.crowd-support/crowd-v4-participant-updater'))
            extension.write_bytes(archive.read(next(n for n in archive.namelist() if n.endswith('participant-extension.zip'))))
        helper.chmod(0o600)  # Packaging bytes only; never executable in this fixture.
        pin = work/'ParticipantManifest.swift'
        encoded = base64.b64encode((UPDATER/'participant-manifest-shape.json').read_bytes()).decode()
        pin.write_text('let participantManifestShapeBase64 = '+json.dumps(encoded)+'\n')
        test_helper, test_home = work/'test-helper', work/'explicit-test-home'
        test_home.mkdir()
        compile_command = ['swiftc','-O','-DTESTING','-DPARTICIPANT','-module-cache-path',str(work/'swift-cache'),str(UPDATER/'main.swift'),str(UPDATER/'ReleaseKey.swift'),str(pin),'-o',str(test_helper)]
        compiled = subprocess.run(compile_command,capture_output=True,text=True)
        print(json.dumps({'compile_command':compile_command,'exit':compiled.returncode,'stdout':compiled.stdout,'stderr':compiled.stderr}),flush=True)
        compiled.check_returncode()
        assert b'CROWD_TEST_INSTALL_HOME' in test_helper.read_bytes()
        original_run = subprocess.run
        checks = []

        def checked_run(command, *args, **kwargs):
            if str(command[0]) == str(helper):
                assert len(command)==3 and command[1]=='--check-install'
                actual = [str(test_helper),*command[1:]]
                result = original_run(actual,env={'PATH':os.environ['PATH'],'CROWD_TEST_INSTALL_HOME':str(test_home)},capture_output=True,text=True)
                checks.append(actual)
                print(json.dumps({'actual_preflight':actual,'test_home':str(test_home),'helper_root':str(test_helper.parent),'exit':result.returncode,'stdout':result.stdout,'stderr':result.stderr}),flush=True)
                result.check_returncode()
                return result
            assert command[0] in ('codesign','lipo'), command
            return original_run(command,*args,**kwargs)

        with patch.object(builder.subprocess,'run',side_effect=checked_run):
            result = builder.build(extension,helper,output)
        assert len(checks)==1
        print(json.dumps({'production_helper_executed':False,'extension_sha256':hashlib.sha256(extension.read_bytes()).hexdigest(),'helper_sha256':hashlib.sha256(helper.read_bytes()).hexdigest(),'result':result}),flush=True)
        return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--previous',type=Path,default=ROOT/'releases/participants/v1-base-20261026-r2/crowd-v4.2.94-base-mac.zip')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    assert not args.output.exists(), 'frozen candidate already exists'
    build(args.previous,args.output)
