"""Portable own-resource packaging tests; no SDK, account, network or install."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

BASE = Path(__file__).resolve().parent
RESOURCE = 'pro_xhs_download.mjs'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


assembler = load('own_resource_assembler', BASE/'participant/assemble-pro-runtime.py')
builder = load('own_resource_builder', BASE/'build_participant.py')


class Resources(unittest.TestCase):
    def test_complete_source_manifest_and_verifier_are_required_runtime_inputs(self):
        self.assertIn('PRO-LOCAL-SOURCE-PINS.json', assembler.ASSETS)
        self.assertIn('pro_source_artifact.py', assembler.NATIVE)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source, pinfile, pins = self.source(root)
            pins.pop('PRO-LOCAL-SOURCE-PINS.json'); pinfile.write_text(json.dumps(pins))
            with self.assertRaisesRegex(ValueError, 'resource_pin_required'):
                assembler.assemble(source, root/'runtime', pinfile)

    def source(self, root, resource=True):
        source = root/'repo/multiplatform'
        source.mkdir(parents=True)
        names = assembler.NATIVE | assembler.ASSETS | {
            'mc_runner.py', 'participant_pro.py', 'participant_pro_hooks.py', 'portable_node.py'}
        if resource:
            names |= {RESOURCE, 'pro_xhs_media.py'}
        for name in names:
            (source/name).write_bytes(b'// own fixture' if name.endswith('.mjs') else b'{}')
        (source/'foreign_sdk.mjs').write_bytes(b'not an allowed resource')
        subprocess.run(['git', 'init', '-q', str(root/'repo')], check=True)
        subprocess.run(['git', '-C', str(root/'repo'), 'add', '.'], check=True)
        pins = {name: hashlib.sha256((source/name).read_bytes()).hexdigest() for name in names}
        pinfile = root/'pins.json'
        pinfile.write_text(json.dumps(pins))
        return source, pinfile, pins

    def test_assembly_preserves_modules_and_exact_resource_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source, pinfile, pins = self.source(root)
            output = root/'runtime'
            assembler.assemble(source, output, pinfile)
            manifest = json.loads((output/'PRO-RUNTIME.json').read_text())
            self.assertEqual(manifest['files'], pins)
            self.assertEqual((output/RESOURCE).read_bytes(), (source/RESOURCE).read_bytes())
            self.assertNotIn('foreign_sdk.mjs', manifest['files'])

    def test_original_runtime_without_resource_still_assembles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source, pinfile, pins = self.source(root, resource=False)
            assembler.assemble(source, root/'runtime', pinfile)
            self.assertEqual(json.loads((root/'runtime/PRO-RUNTIME.json').read_text())['files'], pins)

    def test_resource_requires_external_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source, pinfile, pins = self.source(root)
            pins.pop(RESOURCE); pinfile.write_text(json.dumps(pins))
            with self.assertRaisesRegex(ValueError, 'resource_pin_required'):
                assembler.assemble(source, root/'runtime', pinfile)
            self.assertFalse((root/'runtime').exists())

    def test_changed_or_symlink_resource_refuses_before_output(self):
        for symlink in (False, True):
            with self.subTest(symlink=symlink), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); source, pinfile, pins = self.source(root)
                if symlink:
                    (source/RESOURCE).unlink(); (source/RESOURCE).symlink_to(source/'portable_node.py')
                else:
                    (source/RESOURCE).write_bytes(b'changed')
                with self.assertRaises(ValueError):
                    assembler.assemble(source, root/'runtime', pinfile)
                self.assertFalse((root/'runtime').exists())

    def build(self, root, runtime):
        extension, helper, output = root/'ext.zip', root/'helper', root/'package.zip'
        helper.write_bytes(b'own fixture helper, not shipped')
        with zipfile.ZipFile(extension, 'w') as archive:
            archive.writestr('manifest.json', json.dumps({'version': '4.2.102', 'key': 'dGVzdA=='}))
            archive.writestr('release.json', '{}')
        with patch.object(builder.subprocess, 'check_output', return_value='arm64 x86_64'), \
                patch.object(builder.subprocess, 'run'):
            builder.build(extension, helper, output, runtime)
        return output

    def test_builder_resource_in_archive_manifest_integrity_and_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source, pinfile, pins = self.source(root)
            runtime = root/'runtime'; assembler.assemble(source, runtime, pinfile)
            output = self.build(root, runtime)
            with zipfile.ZipFile(output) as archive:
                key = '.crowd-support/pro-runtime/' + RESOURCE
                self.assertEqual(archive.read(key), (source/RESOURCE).read_bytes())
                self.assertIn('pro-runtime/'+RESOURCE, archive.read('.crowd-support/INSTALL-SHA256.txt').decode())
                manifest = json.loads(archive.read('.crowd-support/pro-runtime/PRO-RUNTIME.json'))
                self.assertEqual(manifest['files'], pins)
                provenance = json.loads(archive.read('.crowd-support/package-source.json'))
                helper = 'prepare-pro-downloader.py'
                self.assertEqual(archive.read('.crowd-support/'+helper), (BASE/'participant'/helper).read_bytes())
                self.assertEqual(provenance['source_sha256']['participant/'+helper], hashlib.sha256((BASE/'participant'/helper).read_bytes()).hexdigest())
                self.assertEqual(provenance['pro_runtime_files'][helper], hashlib.sha256((BASE/'participant'/helper).read_bytes()).hexdigest())
                self.assertEqual(provenance['pro_runtime_files']['pro-runtime/'+RESOURCE], pins[RESOURCE])
                for row in archive.read('.crowd-support/INSTALL-SHA256.txt').decode().splitlines():
                    digest, name = row.split('  ')
                    self.assertEqual(hashlib.sha256(archive.read('.crowd-support/'+name)).hexdigest(), digest)

    def test_builder_rejects_other_mjs_and_traversal(self):
        for name in ('foreign_sdk.mjs', '../pro_xhs_download.mjs', 'nested/pro_xhs_download.mjs'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); source, pinfile, pins = self.source(root, resource=False)
                runtime = root/'runtime'; assembler.assemble(source, runtime, pinfile)
                manifest = json.loads((runtime/'PRO-RUNTIME.json').read_text())
                manifest['files'][name] = '0'*64
                (runtime/'PRO-RUNTIME.json').write_text(json.dumps(manifest))
                with self.assertRaises(ValueError): self.build(root, runtime)


if __name__ == '__main__':
    unittest.main()
