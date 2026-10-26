"""Run the installer dependency gate in temporary HOME; no Native/OS install."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).parent / 'participant/install.command'


class OptionalPro(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='participant-optional-pro-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.package = self.root / 'package'
        self.package.mkdir()
        self.helper = self.root / 'Library/Application Support/CrowdV4Updater'
        self.helper.mkdir(parents=True)

    def run_gate(self, options=()):
        text = SOURCE.read_text()
        start = text.index('configure_pro_if_present() {')
        end = text.index("\nprint '\\n众包采集安装助手", start)
        script = 'PRO_INSTALL_OPTIONS=("$@")\n' + text[start:end] + '\nconfigure_pro_if_present\n'
        return subprocess.run(
            ['/bin/zsh', '-c', script, 'dependency-gate', *options],
            env={'HOME': str(self.root), 'PACKAGE_DIR': str(self.package), 'PATH': '/usr/bin:/bin'},
            capture_output=True, timeout=5)

    def snapshot(self):
        return {p.relative_to(self.helper).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.helper.rglob('*') if p.is_file()}

    def test_base_package_needs_no_pro_components(self):
        result = self.run_gate()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn('基础采集包'.encode(), result.stdout)
        self.assertNotIn('Pro 尚未就绪'.encode(), result.stdout)

    def test_unrelated_old_pro_descriptor_does_not_block_base_install(self):
        (self.helper / 'pro-dependency-settings.json').write_bytes(b'old descriptor, not a new installation')
        before = self.snapshot()
        result = self.run_gate()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(self.snapshot(), before)

    def test_base_install_preserves_unknown_state_and_old_config(self):
        for name in ('pro-dependency-settings.json', 'pro-install-settings.json', 'pro-config.json', 'pro-state.json'):
            (self.helper / name).write_bytes(b'preserve this existing unknown state')
        (self.helper / 'outbox.sqlite').write_bytes(b'outbox fixture, never opened')
        before = self.snapshot()
        result = self.run_gate()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(self.snapshot(), before)

    def test_explicit_pro_capacity_on_base_package_is_rejected(self):
        before = self.snapshot()
        result = self.run_gate(('--pro-max-api-requests', '60'))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.snapshot(), before)

    def test_partial_enhancement_package_cannot_be_treated_as_base(self):
        (self.package / 'pro-runtime').mkdir()
        result = self.run_gate()
        self.assertNotEqual(result.returncode, 0)

    def test_orphan_enhancement_script_cannot_be_treated_as_base(self):
        (self.package / 'configure-pro.py').write_text('raise RuntimeError("must not run")')
        self.assertNotEqual(self.run_gate().returncode, 0)

    def test_runtime_directory_symlink_is_rejected(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'PRO-RUNTIME.json').write_text('{}')
        (self.package / 'pro-runtime').symlink_to(outside, target_is_directory=True)
        self.assertNotEqual(self.run_gate().returncode, 0)

    def test_manifest_symlink_is_rejected(self):
        runtime = self.package / 'pro-runtime'
        runtime.mkdir()
        manifest = self.root / 'manifest'
        manifest.write_text('{}')
        (runtime / 'PRO-RUNTIME.json').symlink_to(manifest)
        self.assertNotEqual(self.run_gate().returncode, 0)

    def test_dangling_enhancement_artifact_is_not_base(self):
        (self.package / 'prepare-and-configure-pro.py').symlink_to(self.root / 'missing')
        self.assertNotEqual(self.run_gate().returncode, 0)


if __name__ == '__main__':
    unittest.main()
