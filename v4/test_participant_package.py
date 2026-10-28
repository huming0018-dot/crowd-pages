import importlib.util
import json
import os
from pathlib import Path
import plistlib
import subprocess
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
        assert script.index('BROWSER_CHECK=') < script.index('./reconnect.command') < script.index('/bin/mkdir -m 700 "$INSTALL_DIR"')
        assert 'legacy_browser_extension' in script and 'browser_inventory_unavailable' in archive.read('.crowd-support/browser-preflight.js').decode()
        assert '/bin/mkdir -p' in script
        assert 'CrowdV4LocalTestUpdater' in script and '不迁移私人版的身份或队列' in script
        for page in ['安装说明.html', '.crowd-support/new.html', '.crowd-support/existing.html', '.crowd-support/help-chrome.html', '.crowd-support/help-native-host.html', '.crowd-support/help-integrity.html']:
            text=archive.read(page).decode()
            assert '@MODE@' not in text and '@VERSION@' not in text and '@ERROR_' not in text
            assert '开始安装.command' in text and '4.2.60' in text
        assert 'data-mode="new"' in archive.read('.crowd-support/new.html').decode()
        assert 'data-mode="existing"' in archive.read('.crowd-support/existing.html').decode()
        provenance=json.loads(archive.read('.crowd-support/package-source.json'))
        assert provenance['package_revision']==3 and provenance['helper_sha256']==module.digest(helper.read_bytes())
        assert archive.read('.crowd-support/crowd-v4.2.60-participant-extension.zip')==package.read_bytes()
        assert 'dl.google.com/chrome/mac/universal/stable/GGRO/googlechrome.dmg' in script
        chrome_help = archive.read('.crowd-support/help-chrome.html').decode()
        assert '自动下载' in chrome_help and '重新双击' in chrome_help and 'https://www.google.com/chrome/' in chrome_help
    tools = root/'chrome-test-tools'
    tools.mkdir()
    dispatcher = tools/'dispatch'
    dispatcher.write_text('''#!/usr/bin/env python3
import os
from pathlib import Path
import plistlib
import shutil
import sys

name = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['CHROME_TEST_LOG'], 'a') as log:
    print(name, *args, file=log)
mode = os.environ['CHROME_TEST_MODE']
if name == 'sw_vers':
    print('27.0.1')
elif name == 'curl':
    Path(args[args.index('--output') + 1]).write_bytes(b'fixture dmg')
    if mode == 'download-fail': sys.exit(22)
elif name == 'hdiutil' and args[0] == 'attach':
    mount = Path(args[args.index('-mountpoint') + 1])
    mount.mkdir(exist_ok=True)
    if mode == 'attach-fail': sys.exit(1)
    app = mount/'Google Chrome.app'/'Contents'
    app.mkdir(parents=True)
    with (app/'Info.plist').open('wb') as out:
        plistlib.dump({'CFBundleIdentifier': 'com.google.Chrome', 'CFBundleShortVersionString': '156.0.0'}, out)
    if mode == 'race':
        target = Path(os.environ['CHROME_TEST_TARGET'])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('existing file')
elif name == 'ditto':
    if mode == 'copy-fail':
        Path(args[-1]).mkdir(parents=True, exist_ok=True)
        (Path(args[-1])/'partial').write_text('partial')
        sys.exit(1)
    shutil.copytree(args[-2], args[-1], dirs_exist_ok=True)
''')
    dispatcher.chmod(0o755)
    for name in ('shasum', 'sw_vers', 'mdfind', 'curl', 'hdiutil', 'ditto', 'open'):
        (tools/name).symlink_to(dispatcher)
    anchor = 'if [[ "$PACKAGE_FRESH_ONLY" == true && ('
    assert anchor in script
    preflight = script.replace(anchor, 'print CHROME_PREFLIGHT_OK\nexit 0\n' + anchor, 1)
    preflight = preflight.replace("'/Applications/Google Chrome.app'", "'" + str(root/'system-chrome-absent.app') + "'")
    for name in ('shasum', 'sw_vers', 'mdfind', 'curl', 'hdiutil', 'ditto', 'open'):
        preflight = preflight.replace('/usr/bin/' + name, str(tools/name))
    for mode in ('existing', 'success', 'download-fail', 'attach-fail', 'copy-fail', 'race'):
        case = root/mode
        home, temporary = case/'home', case/'tmp'
        home.mkdir(parents=True)
        temporary.mkdir()
        app = home/'Applications'/'Google Chrome.app'
        if mode == 'existing':
            (app/'Contents').mkdir(parents=True)
            with (app/'Contents'/'Info.plist').open('wb') as out:
                plistlib.dump({'CFBundleIdentifier': 'com.google.Chrome', 'CFBundleShortVersionString': '156.0.0'}, out)
            (app/'keep').write_text('original')
        support = case/'package'
        support.mkdir()
        command = support/'install.command'
        command.write_text(preflight)
        log = case/'commands.log'
        result = subprocess.run(['/bin/zsh', str(command)], cwd=support, text=True, capture_output=True,
            env={**os.environ, 'HOME': str(home), 'TMPDIR': str(temporary), 'CHROME_TEST_LOG': str(log),
                 'CHROME_TEST_MODE': mode, 'CHROME_TEST_TARGET': str(app)})
        calls = log.read_text()
        if mode in ('existing', 'success'):
            assert result.returncode == 0, (mode, result.stdout, result.stderr)
            assert 'CHROME_PREFLIGHT_OK' in result.stdout
            assert app.is_dir() and (app/'Contents'/'Info.plist').is_file()
            if mode == 'existing':
                assert (app/'keep').read_text() == 'original'
                assert 'curl ' not in calls and 'hdiutil ' not in calls and 'ditto ' not in calls
            else:
                assert 'dl.google.com/chrome/mac/universal/stable/GGRO/googlechrome.dmg' in calls
                assert calls.index('curl ') < calls.index('hdiutil attach') < calls.index('ditto ') < calls.index('hdiutil detach')
        else:
            assert result.returncode != 0, (mode, result.stdout, result.stderr)
            assert '重新双击' in result.stdout
            if mode == 'race':
                assert app.read_text() == 'existing file'
            else:
                assert not app.exists()
            if mode in ('attach-fail', 'copy-fail', 'race'):
                assert 'hdiutil detach' in calls
        assert not list(temporary.glob('crowd-chrome.*')), mode
    host_start = script.index('NATIVE_HOSTS=')
    host_end = script.index('if ! ./crowd-v4-participant-updater --install')
    assert script.index('BROWSER_CHECK=') < script.index('if [[ -e "$INSTALL_DIR" ]]') < host_start < host_end
    host_preflight = script[host_start:host_end]
    for mode in ('new', 'existing-directory', 'symlink', 'non-directory', 'old-registration'):
        case = root/('native-host-' + mode)
        home = case/'home'
        support = home/'Library/Application Support'
        support.mkdir(parents=True)
        google = support/'Google'
        hosts = google/'Chrome/NativeMessagingHosts'
        if mode == 'existing-directory':
            hosts.mkdir(parents=True)
            existing_mode = hosts.stat().st_mode & 0o777
        elif mode == 'symlink':
            outside = case/'outside'
            outside.mkdir()
            (outside/'keep').write_text('original')
            google.symlink_to(outside, target_is_directory=True)
        elif mode == 'non-directory':
            google.write_text('original')
        elif mode == 'old-registration':
            hosts.mkdir(parents=True)
            (hosts/'com.crowd.v4.updater.json').write_text('original')
        runner = case/'preflight.command'
        runner.write_text('#!/bin/zsh\nset -eu\nfail() { print -r -- "$2"; exit 1; }\n' + host_preflight + 'print HOSTS_READY\n')
        result = subprocess.run(['/bin/zsh', str(runner)], env={**os.environ, 'HOME': str(home)}, capture_output=True, text=True)
        if mode in ('new', 'existing-directory'):
            assert result.returncode == 0 and 'HOSTS_READY' in result.stdout, (mode, result.stdout, result.stderr)
            assert hosts.is_dir() and not (hosts/'com.crowd.v4.updater.json').exists()
            assert hosts.stat().st_mode & 0o777 == (existing_mode if mode == 'existing-directory' else 0o700)
        else:
            assert result.returncode != 0 and '没有覆盖' in result.stdout, (mode, result.stdout, result.stderr)
            if mode == 'symlink': assert (case/'outside/keep').read_text() == 'original' and not hosts.exists()
            if mode == 'non-directory': assert google.read_text() == 'original'
            if mode == 'old-registration': assert (hosts/'com.crowd.v4.updater.json').read_text() == 'original'
    for bad in ['../escape', '/absolute', 'src\\escape']:
        with zipfile.ZipFile(package, 'w') as archive:
            archive.writestr(bad, 'bad')
        try: module.extension_files(package)
        except ValueError: pass
        else: raise AssertionError('unsafe path accepted')
print('PASS reproducible single-entry Mac pack; Chrome preflight and cleanup; native-host preparation with real mkdir in temporary HOME; source provenance; checksums/permissions/path guards (helper mocked)')
