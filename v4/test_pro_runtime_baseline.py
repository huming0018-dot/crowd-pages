"""Frozen public Native126 + source_info only; no SDK, identity, cloud or install."""
import ast
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

BASE = Path(__file__).resolve().parent
MP = BASE.parents[1]/'crowd-kol/server/crowd/v4/multiplatform'
ARCHIVE = BASE/'releases/participants/native-v2-runtime126/crowd-v4.2.104-pro-mac-runtime126-stable-search.zip'
spec = importlib.util.spec_from_file_location('baseline_assembler', BASE/'participant/assemble-pro-runtime.py')
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)


def function(raw):
    tree = ast.parse(raw)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'source_info')
    return b''.join(raw.splitlines(keepends=True)[node.lineno-1:node.end_lineno])


class Baseline(unittest.TestCase):
    def setUp(self):
        self.assertIn('baseline', inspect.signature(A.assemble).parameters, 'controlled Native126 baseline mode missing')
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve(); self.source = self.root/'source'; self.source.mkdir()
        for name in ('mc_runner.py', 'pro_source_artifact.py', 'PRO-LOCAL-SOURCE-PINS.json'):
            (self.source/name).write_bytes((MP/name).read_bytes())
        with zipfile.ZipFile(ARCHIVE) as archive:
            name = next(n for n in archive.namelist() if n.endswith('/PRO-RUNTIME.json'))
            self.baseline = {n: archive.read(str(Path(name).parent/n)) for n in json.loads(archive.read(name))['files']}
        old = function(self.baseline['mc_runner.py'])
        self.new = function((self.source/'mc_runner.py').read_bytes())
        self.expected = {**self.baseline, 'mc_runner.py': self.baseline['mc_runner.py'].replace(old, self.new, 1),
                         **{n: (self.source/n).read_bytes() for n in ('pro_source_artifact.py', 'PRO-LOCAL-SOURCE-PINS.json')}}
        self.pins = self.root/'pins.json'
        self.pins.write_text(json.dumps({n: hashlib.sha256(raw).hexdigest() for n, raw in self.expected.items()}))

    def assemble(self, baseline=ARCHIVE):
        return A.assemble(self.source, self.root/'runtime', self.pins, baseline=baseline,
                          source_info_sha256=hashlib.sha256(self.new).hexdigest())

    def test_128_files_preserve_other125_and_only_replace_approved_function(self):
        result = self.assemble(); output = self.root/'runtime'
        metadata = json.loads((output/'PRO-RUNTIME.json').read_bytes())
        self.assertEqual(len(metadata['files']), 128)
        self.assertEqual(set(metadata['files']), set(self.expected))
        for name, raw in self.expected.items(): self.assertEqual((output/name).read_bytes(), raw)
        self.assertEqual(result['provenance']['baseline_preserved_files'], 125)
        self.assertEqual(result['provenance']['source_info_sha256'], hashlib.sha256(self.new).hexdigest())

    def test_outside_current_function_is_never_copied(self):
        path = self.source/'mc_runner.py'
        path.write_bytes(b'UNRELATED_HEAD_CHANGE = True\n'+path.read_bytes())
        self.assemble()
        self.assertNotIn(b'UNRELATED_HEAD_CHANGE', (self.root/'runtime/mc_runner.py').read_bytes())

    def test_changed_function_or_archive_refuses_before_output(self):
        path = self.source/'mc_runner.py'; before = path.read_bytes()
        path.write_bytes(before.replace(b'core.fsmonitor=false', b'core.fsmonitor=true', 1))
        with self.assertRaisesRegex(ValueError, 'source_info_pin_changed'): self.assemble()
        self.assertFalse((self.root/'runtime').exists()); path.write_bytes(before)
        altered = self.root/'altered.zip'; altered.write_bytes(ARCHIVE.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError, 'baseline_package_changed'): self.assemble(altered)
        self.assertFalse((self.root/'runtime').exists())

    def test_complete_external_pins_are_required(self):
        pins = json.loads(self.pins.read_bytes()); pins.pop('PRO-LOCAL-SOURCE-PINS.json')
        self.pins.write_text(json.dumps(pins))
        with self.assertRaisesRegex(ValueError, 'complete_runtime_pin_required'): self.assemble()
        self.assertFalse((self.root/'runtime').exists())


if __name__ == '__main__': unittest.main()
