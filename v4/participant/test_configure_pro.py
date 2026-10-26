#!/usr/bin/env python3
"""Offline local installer tests. No licensed SDK, existing profile or install is used."""
import hashlib,importlib.util,json,os,tempfile,unittest,uuid,subprocess
from pathlib import Path
S=importlib.util.spec_from_file_location('configure_pro',Path(__file__).with_name('configure-pro.py'));M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class ConfigureTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve();self.runtime=self.root/'own';self.runtime.mkdir();self.helper=self.root/'helper';self.helper.mkdir();sdk=self.root/'licensed-local';(sdk/'media_platform/xhs').mkdir(parents=True);(sdk/'PRIVATE-SDK.py').write_text('must not be copied')
  entry=self.runtime/'participant_pro_native.py';entry.write_text('# own fixture entry\n');self.man={'schema':'crowd-participant-pro-runtime-v1','files':{entry.name:hashlib.sha256(entry.read_bytes()).hexdigest()}};(self.runtime/'PRO-RUNTIME.json').write_text(json.dumps(self.man))
  self.settings=self.root/'local-settings.json';self.values={'python':os.sys.executable,'root':str(self.root),'mc_root':str(sdk),'session_id':str(uuid.uuid4()),'max_api_requests':14,'purpose':'noncommercial_research'};self.save()
 def save(self):self.settings.write_text(json.dumps(self.values));self.settings.chmod(0o600)
 def test_configured_preserves_binding_and_never_copies_sdk(self):
  r=M.configure(self.runtime,self.settings,self.helper);self.assertEqual(r['state'],'configured');c=self.helper/'pro-config.json';raw=c.read_bytes();v=json.loads(raw);self.assertEqual(v['session_id'],self.values['session_id']);self.assertEqual(c.stat().st_mode&0o777,0o600);self.assertFalse(list(self.helper.rglob('PRIVATE-SDK.py')))
  self.assertEqual(M.configure(self.runtime,self.settings,self.helper)['state'],'current');self.assertEqual(c.read_bytes(),raw)
 def test_upgrade_only_adapter_with_backup_and_idempotency(self):
  M.configure(self.runtime,self.settings,self.helper);c=self.helper/'pro-config.json';old=c.read_bytes();before=json.loads(old)
  entry=self.runtime/'participant_pro_native.py';entry.write_text('# next own adapter\n');self.man['files'][entry.name]=hashlib.sha256(entry.read_bytes()).hexdigest();(self.runtime/'PRO-RUNTIME.json').write_text(json.dumps(self.man))
  self.assertEqual(M.configure(self.runtime,self.settings,self.helper)['state'],'upgraded')
  after=json.loads(c.read_bytes());self.assertNotEqual(after['entry'],before['entry']);self.assertEqual({k:after[k] for k in M.FIELDS},{k:before[k] for k in M.FIELDS})
  backups=list(self.helper.glob('pro-config.before-*.json'));self.assertEqual(len(backups),1);self.assertEqual(backups[0].read_bytes(),old);self.assertEqual(backups[0].stat().st_mode&0o777,0o600)
  self.assertEqual(M.configure(self.runtime,self.settings,self.helper)['state'],'current');self.assertEqual(list(self.helper.glob('pro-config.before-*.json')),backups)
 def test_upgrade_refuses_binding_change_or_busy(self):
  M.configure(self.runtime,self.settings,self.helper);c=self.helper/'pro-config.json';old=c.read_bytes();self.values['session_id']=str(uuid.uuid4());self.save()
  with self.assertRaises(ValueError):M.configure(self.runtime,self.settings,self.helper)
  self.assertEqual(c.read_bytes(),old)
  self.values['session_id']=json.loads(old)['session_id'];self.save();f=self.helper/'pro-state.json';f.write_text(json.dumps({'busy':True,'state':'unknown'}));f.chmod(0o600)
  with self.assertRaises(ValueError):M.configure(self.runtime,self.settings,self.helper)
  self.assertEqual(c.read_bytes(),old);self.assertFalse(list(self.helper.glob('pro-config.before-*.json')))
 def test_actual_module_count_and_static_dependencies(self):
  for n in range(103):
   f=self.runtime/f'own_{n}.py';f.write_text('# own fixture\n');self.man['files'][f.name]=hashlib.sha256(f.read_bytes()).hexdigest()
  for name in ('SIGN-SOURCE-SHA.json','DEPENDENCIES.json','DEPENDENCY-SHA.json','NODE-SHA.json'):
   f=self.runtime/name;f.write_text('{}');self.man['files'][name]=hashlib.sha256(f.read_bytes()).hexdigest()
  (self.runtime/'PRO-RUNTIME.json').write_text(json.dumps(self.man))
  self.assertEqual(M.configure(self.runtime,self.settings,self.helper)['state'],'configured')
  self.assertEqual(len(list((self.helper/'pro-runtime').glob('*/*.py'))),104)
  # No arbitrary JSON, state or credentials can enter the public payload.
  self.man['files']['pro-config.json']='0'*64;(self.runtime/'PRO-RUNTIME.json').write_text(json.dumps(self.man))
  with self.assertRaises(ValueError):M.configure(self.runtime,self.settings,self.helper)
 def test_assemble_tracked_own_modules_plus_frozen_native(self):
  self.runtime.rename(self.root/'multiplatform');self.runtime=self.root/'multiplatform'
  names={'participant_pro_native.py','participant_native_rpc.py','pro_source_artifact.py','mc_runner.py','participant_pro.py','participant_pro_hooks.py'}|{f'own_{n}.py' for n in range(99)}
  for name in names:(self.runtime/name).write_text('# own fixture\n')
  resources=('SIGN-SOURCE-SHA.json','DEPENDENCIES.json','DEPENDENCY-SHA.json','NODE-SHA.json','PRO-LOCAL-SOURCE-PINS.json')
  for name in resources:(self.runtime/name).write_text('{}')
  subprocess.run(['git','init','-q',str(self.root)],check=True)
  tracked=names-{'participant_pro_native.py','participant_native_rpc.py','pro_source_artifact.py'}
  subprocess.run(['git','-C',str(self.root),'add',*[str(self.runtime/n) for n in sorted(tracked)],*[str(self.runtime/n) for n in resources]],check=True)
  spec=importlib.util.spec_from_file_location('assemble_pro',Path(__file__).with_name('assemble-pro-runtime.py'));a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
  pins=self.root/'pins.json';pins.write_text(json.dumps({n:hashlib.sha256((self.runtime/n).read_bytes()).hexdigest() for n in ('participant_pro_native.py','participant_native_rpc.py','pro_source_artifact.py','mc_runner.py','participant_pro.py','participant_pro_hooks.py','PRO-LOCAL-SOURCE-PINS.json')}))
  self.assertEqual(a.assemble(self.runtime,self.root/'assembled',pins)['files'],110)
  (self.runtime/'participant_pro_native.py').write_text('changed')
  with self.assertRaises(ValueError):a.assemble(self.runtime,self.root/'must-not-create',pins)
  self.assertFalse((self.root/'must-not-create').exists())
 def test_missing_sdk_and_public_settings_deny(self):
  self.values['mc_root']=str(self.root);self.save()
  with self.assertRaises(ValueError):M.configure(self.runtime,self.settings,self.helper)
  self.assertFalse((self.helper/'pro-config.json').exists());self.settings.chmod(0o644)
  with self.assertRaises(ValueError):M.configure(self.runtime,self.settings,self.helper)
 def test_hash_and_path_deny(self):
  (self.runtime/'participant_pro_native.py').write_text('changed')
  with self.assertRaises(ValueError):M.configure(self.runtime,self.settings,self.helper)
  self.man['files']={'../outside.py':'0'*64};(self.runtime/'PRO-RUNTIME.json').write_text(json.dumps(self.man))
  with self.assertRaises(ValueError):M.configure(self.runtime,self.settings,self.helper)
 def test_complete_source_pin_resource_exact_name_and_original_hash_gate(self):
  resource=self.runtime/'PRO-LOCAL-SOURCE-PINS.json';resource.write_text('{}')
  self.man['files'][resource.name]=hashlib.sha256(resource.read_bytes()).hexdigest();(self.runtime/'PRO-RUNTIME.json').write_text(json.dumps(self.man))
  try:r=M.configure(self.runtime,self.settings,self.helper)
  except ValueError:self.fail('new own source-pin resource rejected by original configure boundary')
  self.assertEqual(r['state'],'configured');config=self.helper/'pro-config.json';before=config.read_bytes()
  resource.write_text('{"changed":true}')
  with self.assertRaises(ValueError):M.configure(self.runtime,self.settings,self.helper)
  resource.write_text('{}');other=self.runtime/'OTHER-SOURCE-PINS.json';other.write_text('{}');self.man['files'][other.name]=hashlib.sha256(other.read_bytes()).hexdigest();(self.runtime/'PRO-RUNTIME.json').write_text(json.dumps(self.man))
  with self.assertRaises(ValueError):M.configure(self.runtime,self.settings,self.helper)
  self.assertEqual(config.read_bytes(),before)
 def test_busy_unknown_deny(self):
  p=self.helper/'pro-state.json';p.write_text(json.dumps({'busy':True,'state':'unknown'}));p.chmod(0o600)
  with self.assertRaises(ValueError):M.configure(self.runtime,self.settings,self.helper)
  self.assertFalse((self.helper/'pro-config.json').exists())
if __name__=='__main__':unittest.main()
