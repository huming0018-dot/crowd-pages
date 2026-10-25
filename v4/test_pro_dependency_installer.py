"""Execute only the original configure function in temp HOME, never install main."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import shlex
import tempfile
import unittest

BASE = Path(__file__).resolve().parent


def chain(source, succeed=True, descriptor=True, settings=True, selected_python=False):
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp); package = root/'package'; package.mkdir()
        helper = root/'Library/Application Support/CrowdV4Updater'; helper.mkdir(parents=True)
        marker = package/'dependency-called'
        if descriptor: (helper/'pro-dependency-settings.json').write_text('{}')
        if settings:
            (helper/'pro-install-settings.json').write_text(json.dumps({'python': '/usr/bin/python3'}))
        (package/'pro-runtime').mkdir(); (package/'pro-runtime/PRO-RUNTIME.json').write_text('{}')
        (package/'configure-pro.py').write_text("from pathlib import Path\nPath(__file__).with_name('legacy-called').touch()\n")
        chosen = package/'selected-python'
        chosen.write_text('#!/bin/sh\nprintf "selected-python-used\\n" >&2\nexec /usr/bin/python3 "$@"\n'); chosen.chmod(0o700)
        (package/'bootstrap-pro-tools.command').write_text('#!/bin/sh\nprintf "%s\\n" '+shlex.quote(str(chosen) if selected_python else '/usr/bin/python3')+'\n')
        (package/'prepare-and-configure-pro.py').write_text("from pathlib import Path\nPath(__file__).with_name('dependency-called').touch()\nraise SystemExit(%d)\n" % (0 if succeed else 1))
        text = source.read_text(); start = text.index('configure_pro_if_present() {')
        end = text.index("\nprint '\\n众包采集安装助手", start)
        script = text[start:end] + '\nconfigure_pro_if_present\n'
        result = subprocess.run(['/bin/zsh', '-c', script], env={'HOME':temp, 'PACKAGE_DIR':str(package), 'PATH':'/usr/bin:/bin'}, capture_output=True)
        return result, marker.exists(), (package/'legacy-called').exists()


class Chain(unittest.TestCase):
    def test_missing_descriptor_preserves_original_legacy_path(self):
        result, called, legacy = chain(BASE/'participant/install.command', descriptor=False)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(called)  # Preserved actual baseline failure evidence.
        self.assertTrue(legacy)

    def test_new_original_function_uses_fixed_dependency_entry(self):
        result, called, legacy = chain(BASE/'participant/install.command')
        self.assertEqual(result.returncode, 0); self.assertTrue(called); self.assertFalse(legacy)

    def test_dependency_failure_no_legacy_bypass(self):
        result, called, legacy = chain(BASE/'participant/install.command', False)
        self.assertNotEqual(result.returncode, 0); self.assertTrue(called); self.assertFalse(legacy)
        self.assertIn('尚未就绪'.encode(), result.stdout)

    def test_fresh_install_without_descriptor_or_settings_calls_preparer(self):
        result, called, legacy = chain(BASE/'participant/install.command', descriptor=False, settings=False)
        self.assertEqual(result.returncode, 0); self.assertTrue(called); self.assertFalse(legacy)
        self.assertIn('账号绑定'.encode(), result.stdout)

    def test_fresh_dependency_failure_cannot_report_install_success(self):
        result, called, legacy = chain(BASE/'participant/install.command', False, descriptor=False, settings=False)
        self.assertNotEqual(result.returncode, 0); self.assertTrue(called); self.assertFalse(legacy)

    def test_preparation_uses_shell_selected_python(self):
        result, called, legacy = chain(BASE/'participant/install.command', descriptor=False, settings=False, selected_python=True)
        self.assertEqual(result.returncode, 0); self.assertTrue(called); self.assertFalse(legacy)
        self.assertIn(b'selected-python-used', result.stderr)


if __name__ == '__main__': unittest.main()
