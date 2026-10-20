import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from test_pro_dependencies import D


class Process(unittest.TestCase):
    def setUp(self):
        # This suite executes the original Python/uv fixture, not a Node download.
        self.node_temp = tempfile.TemporaryDirectory(); self.addCleanup(self.node_temp.cleanup)
        node = Path(self.node_temp.name)/'fixture-node'; node.write_bytes(b'fixture executable'); node.chmod(0o700)
        for operation in ('prepare','check'):
            fixture = patch.object(D.portable_node, operation, return_value=node)
            fixture.start(); self.addCleanup(fixture.stop)

    def test_real_process_two_envs_fixed_online_command_and_protocol(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve(); helper = root/'helper'; helper.mkdir(mode=0o700)
            binary = root/'fixture-python-uv'
            binary.write_text('''#!/usr/bin/python3
import os,sys,json
from pathlib import Path
a=sys.argv[1:]
if 'sync' in a:
 assert '--frozen' in a and '--no-python-downloads' in a and '--offline' not in a
 assert not any(k.startswith('UV_INDEX_') for k in os.environ)
 p=Path(os.environ['UV_PROJECT_ENVIRONMENT'])/'bin';p.mkdir(parents=True)
 (p/'python').symlink_to(Path(__file__).resolve())
elif '--acquisition-capabilities' in a:
 print(json.dumps({'schema_version':'vox-acquisition-v1','platforms':['xhs']}))
elif 'version' in a[-1]:
 p=Path(sys.argv[0]).parents[1]
 print(json.dumps({'version':[3,11 if p.name=='pro' else 12],'prefix':str(p)}))
'''); binary.chmod(0o700)
            value = {'schema':D.SCHEMA,'uv':str(binary),'uv_sha256':D.digest(binary.read_bytes()),'projects':{}}
            for name in ['pro','signer']:
                project = root/name; project.mkdir()
                for filename in D.FILES: (project/filename).write_text('synthetic authorized project')
                env = {**os.environ,'GIT_CONFIG_GLOBAL':'/dev/null','GIT_CONFIG_SYSTEM':'/dev/null'}
                subprocess.run(['/usr/bin/git','init','-q',str(project)],env=env,check=True)
                subprocess.run(['/usr/bin/git','-C',str(project),'add','.'],env=env,check=True)
                subprocess.run(['/usr/bin/git','-C',str(project),'-c','user.name=fixture','-c','user.email=fixture@localhost','-c','commit.gpgsign=false','commit','-qm','fixture'],env=env,check=True)
                commit = subprocess.check_output(['/usr/bin/git','-C',str(project),'rev-parse','HEAD']).decode().strip()
                value['projects'][name]={'root':str(project),'commit':commit,'files':{f:D.digest((project/f).read_bytes()) for f in D.FILES},'python':str(binary),'python_sha256':D.digest(binary.read_bytes())}
            descriptor=helper/'input.json';descriptor.write_bytes(D.encode(value));descriptor.chmod(0o600)
            result=D.prepare(descriptor,helper)
            self.assertEqual(result['state'],'prepared')
            self.assertFalse(result['authenticated'])
            self.assertFalse((helper/'pro-install-settings.json').exists())
            self.assertFalse((helper/'pro-config.json').exists())

    def test_real_process_timeout_is_fixed_error(self):
        with self.assertRaisesRegex(ValueError,'dependency_command_timeout'):
            D.execute(['/usr/bin/python3','-c','import time;time.sleep(2)'],env=D.environment(),cwd='/',timeout=0.05)

    def test_real_process_error_does_not_expose_raw_stderr(self):
        with self.assertRaisesRegex(ValueError,'^dependency_command_failed$'):
            D.execute(['/usr/bin/python3','-c','import sys;print("SECRET",file=sys.stderr);sys.exit(1)'],env=D.environment(),cwd='/',timeout=2)


if __name__ == '__main__':unittest.main()
