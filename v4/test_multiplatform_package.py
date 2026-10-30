import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import json
import owner_runtime
import zipfile


spec = importlib.util.spec_from_file_location('workbench_builder', Path(__file__).with_name('build_multiplatform.py'))
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def fixture_runtime(root):
    runtime = root / 'prepared runtime'
    (runtime / 'bin').mkdir(parents=True)
    (runtime / 'lib/python3.12/encodings').mkdir(parents=True)
    (runtime / 'lib/python3.12/encodings/__init__.py').write_text('# fixture')
    (runtime / 'LICENSE').write_text('fixture license')
    (runtime / 'bin/python3').write_text('fixture executable')
    (runtime / 'bin/python3').chmod(0o755)
    (runtime / 'bin/python3.12').symlink_to('python3')
    (runtime / 'bin/python').symlink_to('python3')
    return runtime


REAL_RUN = subprocess.run

def probe_result(command, **kwargs):
    if Path(command[0]).name != 'python3':
        return REAL_RUN(command, **kwargs)
    prefix = str(Path(command[0]).parent.parent)
    return subprocess.CompletedProcess(command, 0, json.dumps({
        'implementation': 'CPython', 'system': 'Darwin', 'architecture': 'arm64',
        'version': '3.12.14', 'prefix': prefix, 'base_prefix': prefix}), '')


class PackageTest(unittest.TestCase):
    def test_uses_committed_runtime_without_dirty_files_or_private_data(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / 'crowd-kol'
            source = repo / builder.SOURCE_DIR
            source.mkdir(parents=True)
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            for name in builder.REQUIRED:
                (source / name).write_bytes(('committed ' + name).encode())
            (source / 'extra_runtime.py').write_text('committed extra')
            (source / 'test_hidden.py').write_text('test')
            (source / 'fixtures').mkdir()
            (source / 'fixtures' / 'private.txt').write_text('private')
            subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True)
            subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Fixture', '-c',
                            'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture'], check=True)
            commit = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
            (source / 'dashboard.py').write_text('dirty')
            (source / 'cloud-config.json').write_text('secret')
            (source / 'untracked.py').write_text('untracked')
            output = Path(temp) / 'package.zip'
            runtime = fixture_runtime(Path(temp))
            with patch.object(owner_runtime.subprocess, 'run', side_effect=probe_result):
                builder.build(source, output, commit, runtime, 'arm64')
            with zipfile.ZipFile(output) as package:
                names = set(package.namelist())
                self.assertEqual(package.read('多平台采集/dashboard.py'), b'committed dashboard.py')
                self.assertEqual(package.read('多平台采集/extra_runtime.py'), b'committed extra')
                for name in ('run_diagnostics.py', 'install_machine_node.py', 'prepare_machine_node.py'):
                    self.assertEqual(package.read('多平台采集/' + name), ('committed ' + name).encode())
                self.assertEqual(package.read('多平台采集/SOURCE-COMMIT.txt'), (commit + '\n').encode())
                self.assertFalse(any('test_' in name or 'fixtures/' in name or
                                     'cloud-config' in name or 'untracked' in name for name in names))
                self.assertEqual(json.loads(package.read('多平台采集/RUNTIME.json'))['architecture'], 'arm64')
                self.assertTrue(package.getinfo('多平台采集/runtime/bin/python3').external_attr >> 16 & 0o111)
                self.assertIn('多平台采集/runtime/LICENSE', names)
                self.assertEqual([n for n in names if '/runtime/bin/' in n], ['多平台采集/runtime/bin/python3'])
                self.assertTrue(all(not name.startswith('/') and '..' not in Path(name).parts for name in names))
                self.assertTrue(package.getinfo('多平台采集/打开工作台.command').external_attr >> 16 & 0o111)
            with patch.object(owner_runtime.subprocess, 'run', side_effect=probe_result):
                with self.assertRaises(FileExistsError):
                    builder.build(source, output, commit, runtime, 'arm64')

    def test_runtime_required_and_incomplete_rejected(self):
        with self.assertRaisesRegex(ValueError, 'requires --runtime'):
            builder.build(Path('/unused'), Path('/unused.zip'))
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, 'incomplete runtime'):
                owner_runtime.prepared_runtime(Path(temp), 'arm64')
            runtime = fixture_runtime(Path(temp))
            (runtime / 'LICENSE').unlink()
            with self.assertRaisesRegex(ValueError, 'license missing'):
                owner_runtime.prepared_runtime(runtime, 'arm64')

    def test_wrong_arch_and_broken_runtime_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = fixture_runtime(Path(temp))
            with patch.object(owner_runtime.subprocess, 'run', side_effect=probe_result):
                with self.assertRaisesRegex(ValueError, 'architecture/platform mismatch'):
                    owner_runtime.prepared_runtime(runtime, 'x86_64')
            with patch.object(owner_runtime.subprocess, 'run', side_effect=OSError('missing dylib')):
                with self.assertRaisesRegex(ValueError, 'relocation/stdlib probe failed'):
                    owner_runtime.prepared_runtime(runtime, 'arm64')

    def test_private_content_and_external_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = fixture_runtime(Path(temp))
            private = runtime / 'lib/python3.12/site-packages'
            private.mkdir()
            with self.assertRaisesRegex(ValueError, 'unexpected runtime content'):
                owner_runtime.prepared_runtime(runtime, 'arm64')
            private.rmdir()
            (runtime / 'bin/python3').unlink()
            (runtime / 'bin/python3').symlink_to('/bin/sh')
            with self.assertRaisesRegex(ValueError, 'internal regular file'):
                owner_runtime.prepared_runtime(runtime, 'arm64')


if __name__ == '__main__':
    unittest.main()
