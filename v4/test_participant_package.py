import importlib.util
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location('participant', Path(__file__).with_name('build_participant.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    package, helper, target = root/'extension.zip', root/'helper', root/'participant-mac.zip'
    helper.write_bytes(b'test helper, not shipped')
    with zipfile.ZipFile(package, 'w') as archive:
        archive.writestr('manifest.json', json.dumps({'version':'4.2.60'}))
        archive.writestr('release.json', '{}')
        archive.writestr('src/example.js', 'fixture')
    with patch.object(module.subprocess, 'check_output', return_value='arm64 x86_64'), patch.object(module.subprocess, 'run') as run:
        result = module.build(package, helper, target)
        first = target.read_bytes()
        module.build(package, helper, target)
        assert target.read_bytes() == first
        assert any('--check-install' in call.args[0] for call in run.call_args_list)
    with zipfile.ZipFile(target) as archive:
        script = archive.read('install.command').decode()
        assert '@EXTENSION_ARCHIVE@' not in script and 'crowd-v4.2.60-participant-extension.zip' in script
        assert script.index('shasum') < script.index('./reconnect.command')
        assert archive.getinfo('install.command').external_attr >> 16 & 0o111
        for row in archive.read('INSTALL-SHA256.txt').decode().splitlines():
            sha, name = row.split('  ')
            assert module.digest(archive.read(name)) == sha
        assert 'invite' not in ' '.join(archive.namelist())
    for bad in ['../escape', '/absolute', 'src\\escape']:
        with zipfile.ZipFile(package, 'w') as archive:
            archive.writestr(bad, 'bad')
        try: module.extension_files(package)
        except ValueError: pass
        else: raise AssertionError('unsafe path accepted')
print('PASS reproducible Mac pack, helper preflight, checksums, permissions and path rejection (helper mocked)')
