import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile


spec = importlib.util.spec_from_file_location('workbench_builder', Path(__file__).with_name('build_multiplatform.py'))
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


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
            builder.build(source, output, commit)
            with zipfile.ZipFile(output) as package:
                names = set(package.namelist())
                self.assertEqual(package.read('多平台采集/dashboard.py'), b'committed dashboard.py')
                self.assertEqual(package.read('多平台采集/extra_runtime.py'), b'committed extra')
                for name in ('run_diagnostics.py', 'install_machine_node.py', 'prepare_machine_node.py'):
                    self.assertEqual(package.read('多平台采集/' + name), ('committed ' + name).encode())
                self.assertEqual(package.read('多平台采集/SOURCE-COMMIT.txt'), (commit + '\n').encode())
                self.assertFalse(any('test_' in name or 'fixtures/' in name or
                                     'cloud-config' in name or 'untracked' in name for name in names))
                self.assertTrue(package.getinfo('多平台采集/打开工作台.command').external_attr >> 16 & 0o111)
            with self.assertRaises(FileExistsError):
                builder.build(source, output, commit)


if __name__ == '__main__':
    unittest.main()
