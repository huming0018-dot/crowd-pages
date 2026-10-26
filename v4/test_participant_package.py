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
        archive.writestr('manifest.json', json.dumps({'version':'4.2.60','key':'dGVzdA=='}))
        archive.writestr('release.json', '{}')
        archive.writestr('src/example.js', 'fixture')
    with patch.object(module.subprocess, 'check_output', return_value='arm64 x86_64'), patch.object(module.subprocess, 'run') as run:
        result = module.build(package, helper, target)
        first = target.read_bytes()
        module.build(package, helper, target)
        assert target.read_bytes() == first
        assert any('--check-install' in call.args[0] for call in run.call_args_list)
    with zipfile.ZipFile(target) as archive:
        script = archive.read('.crowd-support/install.command').decode()
        assert '@EXTENSION_ARCHIVE@' not in script and 'crowd-v4.2.60-participant-extension.zip' in script
        assert script.index('shasum') < script.index('./reconnect.command')
        assert archive.getinfo('开始安装.command').external_attr >> 16 & 0o111
        for row in archive.read('.crowd-support/INSTALL-SHA256.txt').decode().splitlines():
            sha, name = row.split('  ')
            assert module.digest(archive.read('.crowd-support/'+name)) == sha
        assert 'invite' not in ' '.join(archive.namelist())
        top = [n for n in archive.namelist() if '/' not in n]
        assert sorted(top) == ['安装说明.html', '安装说明.md', '开始安装.command']
        assert archive.getinfo('.crowd-support/crowd-v4-participant-updater').external_attr >> 16 & 0o111
        assert 'exec' in archive.read('开始安装.command').decode()
        assert 'sw_vers' in script and 'PlistBuddy' in script and 'MAC_MAJOR < 14' in script and 'CHROME_MAJOR < 120' in script
        assert script.index('MAC_MAJOR < 14') < script.index('/bin/mkdir')
        assert script.index('--check-install') < script.index('./reconnect.command')
        assert script.index('BROWSER_CHECK=') < script.index('./reconnect.command') < script.index('/bin/mkdir')
        assert 'legacy_browser_extension' in script and 'browser_inventory_unavailable' in archive.read('.crowd-support/browser-preflight.js').decode()
        assert '/bin/mkdir -p' in script
        assert 'CrowdV4LocalTestUpdater' in script and '不迁移私人版的身份或队列' in script
        for page in ['安装说明.html', '.crowd-support/new.html', '.crowd-support/existing.html', '.crowd-support/help-chrome.html', '.crowd-support/help-integrity.html']:
            text=archive.read(page).decode()
            assert '@MODE@' not in text and '@VERSION@' not in text and '@ERROR_' not in text
            assert '开始安装.command' in text and '4.2.60' in text
        assert 'data-mode="new"' in archive.read('.crowd-support/new.html').decode()
        assert 'data-mode="existing"' in archive.read('.crowd-support/existing.html').decode()
        provenance=json.loads(archive.read('.crowd-support/package-source.json'))
        assert provenance['package_revision']==3 and provenance['helper_sha256']==module.digest(helper.read_bytes())
        assert archive.read('.crowd-support/crowd-v4.2.60-participant-extension.zip')==package.read_bytes()
    for bad in ['../escape', '/absolute', 'src\\escape']:
        with zipfile.ZipFile(package, 'w') as archive:
            archive.writestr(bad, 'bad')
        try: module.extension_files(package)
        except ValueError: pass
        else: raise AssertionError('unsafe path accepted')
print('PASS reproducible single-entry Mac pack; hidden resource layout; frozen nested bytes; Chinese preflight/result pages; source provenance; checksums/permissions/path guards (helper mocked)')
