"""Fresh Mac dependency preparation never needs an old account/settings file."""
from pathlib import Path
import unittest
from unittest.mock import patch

import test_pro_dependencies as legacy
import json
D, W = legacy.D, legacy.W


class FreshDependencies(unittest.TestCase):
    setUp = legacy.Dependencies.setUp
    save = legacy.Dependencies.save
    def transport(self, argv, **kwargs):
        if argv[:2] == ['/usr/bin/xcode-select', '-p']:
            return b'/fixture/existing-command-line-tools\n'
        return legacy.Dependencies.transport(self, argv, **kwargs)

    def test_fresh_wrapper_prepares_without_settings_or_account_configuration(self):
        self.settings.unlink()
        calls = []

        class Facade:
            read = staticmethod(D.read)
            need = staticmethod(D.need)
            prepare = lambda _, a, b: D.prepare(a, b, run=self.transport)

        try:
            result = W.install(Facade(), lambda *a: calls.append(a), self.descriptor,
                               self.settings, self.root/'runtime', self.helper)
        except FileNotFoundError:
            self.fail('dependency preparation still requires old account settings')
        self.assertEqual(result['state'], 'prepared_unbound')
        self.assertIs(result['authenticated'], False)
        self.assertIs(result['configured'], False)
        self.assertEqual(sum('sync' in a for a, _ in self.calls), 2)
        self.assertEqual(calls, [])
        self.assertFalse(self.settings.exists())
        self.assertFalse((self.helper/'pro-config.json').exists())

    def test_metadata_only_git_candidate_cannot_prepare_without_trusted_runtime_manifest(self):
        self.assertTrue(callable(getattr(D, 'discover', None)), 'fresh discovery missing')
        home = self.root/'home'; home.mkdir()
        for role in ('pro', 'signer'): (self.root/role/'.git').mkdir()
        tools = {'uv': self.value['uv_sha256'],
                 'pro': self.value['projects']['pro']['python_sha256'],
                 'signer': self.value['projects']['signer']['python_sha256']}
        pins = {k: {field: value[field] for field in ('commit', 'files')}
                for k, value in self.value['projects'].items()}
        # Canonical fixture projects/tools have already been supplied locally.
        with patch.object(D, 'LOCAL_SOURCE_PINS', pins), patch.object(D, 'LOCAL_TOOL_PINS', tools), \
             patch.object(D, 'local_candidates', return_value={
                 'pro': [self.root/'pro'], 'signer': [self.root/'signer'],
                 'uv': [self.binary], 'pro_python': [self.binary], 'signer_python': [self.binary]}):
            def no_git(argv, **kwargs):
                self.assertNotIn(argv[0], ('/usr/bin/git', '/usr/bin/xcode-select'))
                return self.transport(argv, **kwargs)
            with self.assertRaisesRegex(ValueError, 'pro_artifact_manifest_changed'):
                D.discover(self.helper, home=home, run=no_git)
        self.assertFalse((self.helper/'pro-dependency-settings.json').exists())
        self.assertEqual(self.settings.read_bytes(), self.old)

    def test_discovery_rejects_ambiguous_source_and_untrusted_tool_without_writes(self):
        self.assertTrue(callable(getattr(D, 'discover', None)), 'fresh discovery missing')
        other = self.root/'other'; other.mkdir()
        candidates = {'pro': [self.root/'pro', other], 'signer': [self.root/'signer'],
                      'uv': [self.binary], 'pro_python': [self.binary], 'signer_python': [self.binary]}
        with patch.object(D, 'local_candidates', return_value=candidates):
            with self.assertRaisesRegex(ValueError, 'dependency_pro_missing_or_ambiguous'):
                D.discover(self.helper, home=self.root, run=self.transport)
        candidates['pro'] = [self.root/'pro']
        with patch.object(D, 'local_candidates', return_value=candidates):
            with self.assertRaisesRegex(ValueError, 'dependency_uv_unavailable'):
                D.discover(self.helper, home=self.root, run=self.transport)
        self.assertFalse((self.helper/'pro-dependency-settings.json').exists())

    def test_existing_descriptor_is_not_rediscovered_or_rewritten(self):
        descriptor = self.helper/'pro-dependency-settings.json'
        descriptor.write_bytes(self.descriptor.read_bytes()); descriptor.chmod(0o600)
        before = descriptor.read_bytes(), descriptor.stat().st_ino
        with patch.object(D, 'local_candidates', side_effect=AssertionError('rediscovered')):
            self.assertEqual(D.discover(self.helper), descriptor)
        self.assertEqual((descriptor.read_bytes(), descriptor.stat().st_ino), before)

    def test_symlink_descriptor_cannot_be_followed(self):
        descriptor = self.helper/'pro-dependency-settings.json'
        descriptor.symlink_to(self.descriptor)
        before = self.descriptor.read_bytes()
        with self.assertRaises(OSError):
            D.discover(self.helper)
        self.assertEqual(self.descriptor.read_bytes(), before)

    def test_default_candidates_follow_new_home_without_owner_paths(self):
        home = self.root/'new-user'
        candidates = D.local_candidates(home, home/'helper')
        self.assertTrue(all(p.is_relative_to(home) for values in candidates.values() for p in values))

    def test_git_marker_symlink_without_trusted_runtime_proof_never_executes_git(self):
        (self.root/'pro/.git').symlink_to(self.root/'outside-git')
        tools = {'uv': self.value['uv_sha256'],
                 'pro': self.value['projects']['pro']['python_sha256'],
                 'signer': self.value['projects']['signer']['python_sha256']}
        pins = {k: {field: value[field] for field in ('commit', 'files')}
                for k, value in self.value['projects'].items()}
        candidates = {'pro': [self.root/'pro'], 'signer': [self.root/'signer'],
                      'uv': [self.binary], 'pro_python': [self.binary], 'signer_python': [self.binary]}
        def unavailable(argv, **kwargs):
            if argv[:2] == ['/usr/bin/xcode-select', '-p']:
                raise ValueError('dependency_command_failed')
            return self.transport(argv, **kwargs)
        with patch.object(D, 'LOCAL_SOURCE_PINS', pins), patch.object(D, 'LOCAL_TOOL_PINS', tools), \
             patch.object(D, 'local_candidates', return_value=candidates):
            with self.assertRaisesRegex(ValueError, 'pro_artifact_manifest_changed'):
                D.discover(self.helper, home=self.root, run=unavailable)
        self.assertFalse(any(a[0] == '/usr/bin/git' for a, _ in self.calls))
        self.assertFalse((self.helper/'pro-dependency-settings.json').exists())

    def test_frozen_sdk_prepares_without_git_and_refuses_unlisted_source(self):
        self.assertTrue(callable(getattr(D, 'source_artifact', None)), 'shared artifact verifier missing')
        import importlib.util
        module_path = Path(__file__).parents[2]/'crowd-kol/server/crowd/v4/multiplatform/pro_source_artifact.py'
        spec = importlib.util.spec_from_file_location('fresh_artifact_fixture', module_path)
        artifact = importlib.util.module_from_spec(spec); spec.loader.exec_module(artifact)
        pins = {role: {'commit': value['commit'], 'files': {
            name: {'sha256': digest, 'bytes': (Path(value['root'])/name).stat().st_size}
            for name, digest in value['files'].items()}}
            for role, value in self.value['projects'].items()}
        tools = {'uv': self.value['uv_sha256'],
                 'pro': self.value['projects']['pro']['python_sha256'],
                 'signer': self.value['projects']['signer']['python_sha256']}
        candidates = {'pro': [self.root/'pro'], 'signer': [self.root/'signer'],
                      'uv': [self.binary], 'pro_python': [self.binary], 'signer_python': [self.binary]}
        for role in ('pro', 'signer'):
            (self.root/role/'.git').mkdir()
            (self.root/role/'.git/config').write_text('never execute these hooks or filters')
            (self.root/role/'private-account.json').write_text('synthetic private data')
        def no_git(argv, **kwargs):
            self.assertNotIn(argv[0], ('/usr/bin/git', '/usr/bin/xcode-select'))
            return self.transport(argv, **kwargs)
        with patch.object(D, 'source_artifact', return_value=artifact), \
             patch.object(artifact, 'load_pins', return_value=pins), \
             patch.object(D, 'LOCAL_SOURCE_PINS', {role: {k: value[k] for k in ('commit', 'files')}
                                                 for role, value in self.value['projects'].items()}), \
             patch.object(D, 'LOCAL_TOOL_PINS', tools), \
             patch.object(D, 'local_candidates', return_value=candidates):
            try: descriptor = D.discover(self.helper, home=self.root, run=no_git)
            except ValueError as error: self.fail('trusted factory source was not privately prepared: '+str(error))
            self.assertEqual(D.prepare(descriptor, self.helper, run=no_git)['state'], 'prepared')
            selected = Path(json.loads(descriptor.read_bytes())['projects']['pro']['root'])
            self.assertNotEqual(selected, self.root/'pro')
            self.assertFalse((selected/'.git').exists())
            self.assertFalse((selected/'private-account.json').exists())
            self.assertTrue((self.root/'pro/private-account.json').exists())
            (selected/'unlisted.py').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'pro_artifact_source_changed'):
                D.plan(descriptor, self.helper, no_git)

    def test_tools_record_requires_fixed_bootstrap_check_not_self_reported_hashes(self):
        self.assertTrue(callable(getattr(D, 'bootstrap_tools', None)), 'bootstrap trust gate missing')
        folder = self.helper/'bootstrap-tools'; folder.mkdir(mode=0o700)
        record = folder/'TOOLS.json'
        value = {'schema': 'crowd-pro-bootstrap-tools-v1', 'arch': 'arm64',
                 **{role: {'path': str(self.binary), 'sha256': D.digest(self.binary.read_bytes()), 'version': version}
                    for role, version in [('uv', '0.12.7'), ('pro_python', '3.11.16'), ('signer_python', '3.12.14')]}}
        record.write_bytes(D.encode(value)); record.chmod(0o600)
        (self.root/'bootstrap-pro-tools.command').write_text('# fixture proof command\n')
        calls = []
        def proof(argv, **kwargs):
            calls.append(argv)
            return (str(self.binary)+'\n').encode()
        with patch.object(D, '__file__', str(self.root/'prepare-pro-dependencies.py')):
            result = D.bootstrap_tools(self.helper, proof)
            self.assertEqual(result['signer_python'], self.binary)
            self.assertIn('--check', calls[0])
            self.assertEqual(calls[0][0], '/bin/sh')
            def refused(*a, **kw): raise ValueError('resource_changed')
            with self.assertRaisesRegex(ValueError, 'dependency_bootstrap_unavailable'):
                D.bootstrap_tools(self.helper, refused)
        self.assertEqual(record.read_bytes(), D.encode(value))


if __name__ == '__main__': unittest.main()
