import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parent


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, BASE / 'participant' / file)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


D = load('deps', 'prepare-pro-dependencies.py')
W = load('wrapper', 'prepare-and-configure-pro.py')


class Dependencies(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve(); self.helper = self.root / 'helper'; self.helper.mkdir(mode=0o700)
        self.calls = []; self.fail_sync = False; self.mutate = False
        self.binary = self.root / 'binary'; self.binary.write_bytes(b'fixture executable'); self.binary.chmod(0o700)
        self.value = {'schema': D.SCHEMA, 'uv': str(self.binary), 'uv_sha256': D.digest(self.binary.read_bytes()), 'projects': {}}
        for name in ['pro', 'signer']:
            source = self.root / name; source.mkdir()
            for filename in D.FILES:
                (source / filename).write_text('licensed fixture ' + filename)
            self.value['projects'][name] = {'root': str(source), 'commit': 'a' * 40,
                'files': {f: D.digest((source/f).read_bytes()) for f in D.FILES},
                'python': str(self.binary), 'python_sha256': D.digest(self.binary.read_bytes())}
        self.descriptor = self.helper / 'input.json'; self.save()
        self.settings = self.helper / 'pro-install-settings.json'; self.settings.write_text('{"old":"preserved"}'); self.settings.chmod(0o600)
        self.old = self.settings.read_bytes()
        # Existing Python/uv unit fixtures do not acquire a real Node resource.
        # Full resource validation is tested by test_portable_node's18 cases.
        for operation in ('prepare','check'):
            fixture = patch.object(D.portable_node, operation, side_effect=lambda helper, **kw: self.binary)
            fixture.start(); self.addCleanup(fixture.stop)

    def save(self):
        self.descriptor.write_bytes(D.encode(self.value)); self.descriptor.chmod(0o600)

    def transport(self, argv, *, env, cwd, timeout=600):
        self.calls.append((argv, dict(env)))
        if argv[0] == '/usr/bin/git':
            return b'' if 'status' in argv else b'a' * 40 + b'\n'
        if 'sync' in argv:
            self.assertIn('--frozen', argv); self.assertIn('--no-python-downloads', argv)
            self.assertNotIn('UV_INDEX_PASSWORD', env); self.assertNotIn('PYTHONPATH', env)
            target = Path(env['UV_PROJECT_ENVIRONMENT']); (target / 'bin').mkdir(parents=True)
            (target / 'bin/python').symlink_to(self.binary)
            if self.fail_sync:
                raise ValueError('dependency_command_failed')
            if self.mutate:
                (Path(cwd) / 'uv.lock').write_text('drift')
            return b''
        if '--acquisition-capabilities' in argv:
            return D.encode({'schema_version': D.PROTOCOL, 'platforms': ['xhs']})
        if 'version' in argv[-1]:
            name = Path(argv[0]).parents[1].name
            return D.encode({'version': [3, 11 if name == 'pro' else 12], 'prefix': str(Path(argv[0]).parents[1])})
        return b''

    def prepare(self, **kw):
        return D.prepare(self.descriptor, self.helper, run=self.transport, **kw)

    def test_online_two_separate_envs_and_no_settings_write(self):
        result = self.prepare(); syncs = [c for c in self.calls if 'sync' in c[0]]
        self.assertEqual(len(syncs), 2); self.assertTrue(all('--offline' not in a for a,e in syncs))
        self.assertNotEqual(syncs[0][1]['UV_PROJECT_ENVIRONMENT'], syncs[1][1]['UV_PROJECT_ENVIRONMENT'])
        self.assertEqual(result['state'], 'prepared'); self.assertIs(result['authenticated'], False)
        self.assertEqual(self.settings.read_bytes(), self.old)

    def test_plan_is_write_free_no_uv_or_python(self):
        before = sorted(str(p.relative_to(self.helper)) for p in self.helper.rglob('*'))
        D.plan(self.descriptor, self.helper, self.transport)
        self.assertEqual(before, sorted(str(p.relative_to(self.helper)) for p in self.helper.rglob('*')))
        self.assertFalse(any('sync' in a or '--acquisition-capabilities' in a for a,e in self.calls))

    def test_check_never_installs(self):
        self.prepare(); self.calls.clear()
        r = D.check(self.descriptor, self.helper, self.transport, lambda: None)
        self.assertEqual(r['state'], 'ready'); self.assertFalse(any('sync' in a for a,e in self.calls))

    def test_offline_explicit(self):
        self.prepare(offline=True)
        self.assertTrue(all('--offline' in a for a,e in self.calls if 'sync' in a))

    def test_failed_sync_preserves_settings_and_unknown_no_repeat(self):
        self.fail_sync = True
        with self.assertRaisesRegex(ValueError, 'dependency_pro_sync_failed'): self.prepare()
        count = sum('sync' in a for a,e in self.calls)
        with self.assertRaisesRegex(ValueError, 'dependency_attempt_unknown'): self.prepare()
        self.assertEqual(count, sum('sync' in a for a,e in self.calls))
        self.assertEqual(self.settings.read_bytes(), self.old)

    def test_completed_prepare_is_idempotent(self):
        self.prepare(); self.calls.clear(); self.prepare()
        self.assertFalse(any('sync' in a for a,e in self.calls))

    def test_host_unknown_busy_denied_before_install(self):
        D.write_once(self.helper / 'pro-state.json', {'busy': True, 'state': 'unknown'})
        with self.assertRaisesRegex(ValueError, 'dependency_host_busy'): self.prepare()
        self.assertFalse(any('sync' in a for a,e in self.calls))

    def test_source_hash_drift_before_install(self):
        (self.root / 'pro/uv.lock').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'dependency_source_changed'): self.prepare()
        self.assertFalse(any('sync' in a for a,e in self.calls))

    def test_source_drift_during_sync_no_result(self):
        self.mutate = True
        with self.assertRaisesRegex(ValueError, 'dependency_source_changed'): self.prepare()
        self.assertEqual(list(self.helper.rglob('RESULT.json')), [])
        self.assertEqual(self.settings.read_bytes(), self.old)

    def test_wrong_tool_and_interpreter_hash(self):
        self.value['uv_sha256'] = 'b' * 64; self.save()
        with self.assertRaisesRegex(ValueError, 'dependency_tool_changed'): self.prepare()
        self.value['uv_sha256'] = D.digest(self.binary.read_bytes())
        self.value['projects']['pro']['python_sha256'] = 'b' * 64; self.save()
        with self.assertRaisesRegex(ValueError, 'dependency_interpreter_changed'): self.prepare()

    def test_insecure_descriptor_denied(self):
        self.descriptor.chmod(0o644)
        with self.assertRaisesRegex(ValueError, 'dependency_input_permissions'): self.prepare()

    def test_target_symlink_denied(self):
        (self.helper / 'pro-environments').symlink_to(self.root / 'pro')
        with self.assertRaisesRegex(ValueError, 'dependency_target_invalid'): self.prepare()

    def test_bad_pro_protocol_not_prepared(self):
        original = self.transport
        def run(a, **kw):
            if '--acquisition-capabilities' in a: return b'{"schema_version":"wrong","platforms":["xhs"]}'
            return original(a, **kw)
        with self.assertRaisesRegex(ValueError, 'dependency_protocol_invalid'):
            D.prepare(self.descriptor, self.helper, run=run)
        self.assertEqual(list(self.helper.rglob('RESULT.json')), [])

    def test_wrong_python_version_denied(self):
        original = self.transport
        def run(a, **kw):
            if 'version' in a[-1]: return D.encode({'version': [3, 10], 'prefix': str(Path(a[0]).parents[1])})
            return original(a, **kw)
        with self.assertRaisesRegex(ValueError, 'dependency_environment_invalid'):
            D.prepare(self.descriptor, self.helper, run=run)

    def test_signer_unavailable_does_not_mean_ready(self):
        self.prepare()
        def health(): raise ValueError('signer_not_ready')
        with self.assertRaisesRegex(ValueError, 'signer_not_ready'):
            D.check(self.descriptor, self.helper, self.transport, health)
        self.assertEqual(self.settings.read_bytes(), self.old)

    def test_wrapper_configure_only_after_ready_and_exact_original_bindings(self):
        self.prepare(); p = D.plan(self.descriptor, self.helper, self.transport)
        self.settings.write_bytes(D.encode({'python': str(Path(p['target'])/'pro/bin/python'), 'mc_root': str(self.root/'pro')}))
        class Facade:
            read = staticmethod(D.read); need = staticmethod(D.need)
            prepare = lambda _,a,b: D.prepare(a,b,run=self.transport)
            plan = lambda _,a,b: D.plan(a,b,self.transport)
            check = lambda _,a,b: D.check(a,b,self.transport,lambda:None)
        calls = []
        W.install(Facade(), lambda *a: calls.append(a), self.descriptor, self.settings, self.root/'runtime', self.helper)
        self.assertEqual(len(calls), 1)
        self.settings.write_bytes(self.old)
        with self.assertRaisesRegex(ValueError, 'dependency_binding_migration_required'):
            W.install(Facade(), lambda *a: calls.append(a), self.descriptor, self.settings, self.root/'runtime', self.helper)
        self.assertEqual(len(calls), 1)


if __name__ == '__main__': unittest.main()
