"""Actual fresh zsh entry; temporary HOME and explicit OS/UI/Native stubs only."""
import hashlib
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
import zipfile

BASE = Path(__file__).resolve().parent


class FreshEntry(unittest.TestCase):
    def test_tool_failure_precedes_extension_creation_and_native_registration(self):
        with tempfile.TemporaryDirectory(prefix='r1-fresh-entry-') as folder:
            root = Path(folder); home = root/'home'; support = root/'package/.crowd-support'
            support.mkdir(parents=True); tools = root/'tools'; tools.mkdir()
            (home/'Applications/Google Chrome.app').mkdir(parents=True)
            keep = home/'existing-user-file'; keep.write_bytes(b'preserve original data')
            calls = root/'native-called'
            for name, body in {'sw_vers': 'echo 14.0', 'PlistBuddy': 'echo 141.0', 'open': 'exit 0'}.items():
                path = tools/name; path.write_text('#!/bin/sh\n'+body+'\n'); path.chmod(0o700)
            script = (BASE/'participant/install.command').read_text().replace('@EXTENSION_ARCHIVE@', 'extension.zip')
            script = script.replace('/usr/bin/sw_vers', str(tools/'sw_vers')).replace('/usr/libexec/PlistBuddy', str(tools/'PlistBuddy')).replace('/usr/bin/open', str(tools/'open'))
            (support/'install.command').write_text(script); (support/'install.command').chmod(0o700)
            (support/'browser-preflight.command').write_text('#!/bin/sh\necho clear\n'); (support/'browser-preflight.command').chmod(0o700)
            (support/'bootstrap-pro-tools.command').write_text('#!/bin/sh\nexit 1\n')
            (support/'pro-runtime').mkdir(); (support/'pro-runtime/PRO-RUNTIME.json').write_text('{}')
            (support/'crowd-v4-participant-updater').write_text('#!/bin/sh\nprintf "%s\\n" "$1" >> "$NATIVE_CALLS"\nexit 0\n'); (support/'crowd-v4-participant-updater').chmod(0o700)
            with zipfile.ZipFile(support/'extension.zip', 'w') as archive: archive.writestr('manifest.json', '{}')
            paths = [p for p in support.rglob('*') if p.is_file()]
            (support/'INSTALL-SHA256.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(support).as_posix()+'\n' for p in paths))
            entry = support.parent/'开始安装.command'; entry.write_bytes((BASE/'participant/start.command').read_bytes())
            result = subprocess.run(['/bin/zsh', str(entry)], env={**os.environ, 'HOME': str(home), 'NATIVE_CALLS': str(calls)}, capture_output=True, timeout=15)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Pro 安装工具尚未'.encode(), result.stdout)
            self.assertFalse(calls.exists(), 'Native helper was called before dependencies were ready')
            self.assertFalse((home/'Library/Application Support/CrowdParticipantExtension').exists())
            self.assertFalse((home/'Library/Application Support/CrowdV4Updater/config.json').exists())
            self.assertEqual(keep.read_bytes(), b'preserve original data')


if __name__ == '__main__': unittest.main()
