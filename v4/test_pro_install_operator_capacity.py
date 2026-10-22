"""Offline original installer transaction fixtures; no source or live settings."""
import json,hashlib,unittest,subprocess,shutil
from pathlib import Path
from unittest.mock import patch
import test_pro_binding_continuation as fixture
B,C,W=fixture.B,fixture.C,fixture.W
class OperatorInstall(fixture.Binding):
 def test_exact_mjs_resource_installs(self):
  f=self.runtime/'pro_xhs_download.mjs';f.write_text('// own resource fixture')
  m=json.loads((self.runtime/'PRO-RUNTIME.json').read_text());m['files'][f.name]=B.sha(f.read_bytes());self.put(self.runtime/'PRO-RUNTIME.json',m)
  result=C.configure(self.runtime,self.settings,self.helper);self.assertTrue(result['configured']);self.assertEqual(list((self.helper/'pro-runtime').glob('*/pro_xhs_download.mjs'))[0].read_bytes(),f.read_bytes())
 def test_explicit60_preserves_original_settings_and_identity(self):
  C.configure(self.runtime,self.settings,self.helper);old=B.read(self.helper/'pro-config.json')
  tx=B.BindingContinuation(self.deps,self.prepared,self.plan,self.settings,self.runtime,self.helper,max_api_requests=60);tx.install(C.configure)
  cfg=json.loads(B.read(self.helper/'pro-config.json'));self.assertEqual(cfg['max_api_requests'],60);self.assertEqual(json.loads(B.read(tx.evidence/'INTENT.json'))['operator_max_api_requests'],60);self.assertEqual(B.read(tx.evidence/'config.before.json'),old);self.assertEqual(json.loads(B.read(tx.derived))['max_api_requests'],60);self.assertEqual({k:cfg[k]for k in ['root','mc_root','session_id','purpose']},{k:self.values[k]for k in ['root','mc_root','session_id','purpose']});self.preserve()
 def test_other_resources_hash_or_symlink_rejected(self):
  for name,mode in [('other.mjs','good'),('pro_xhs_download.mjs','badsha'),('pro_xhs_download.mjs','symlink')]:
   with self.subTest(name=name,mode=mode):
    f=self.runtime/name
    if f.exists() or f.is_symlink():f.unlink()
    if mode=='symlink':f.symlink_to(self.entry)
    else:f.write_text('// own')
    m={'schema':'crowd-participant-pro-runtime-v1','files':{self.entry.name:B.sha(self.entry.read_bytes()),name:'0'*64 if mode=='badsha'else B.sha(f.read_bytes())}};self.put(self.runtime/'PRO-RUNTIME.json',m)
    with self.assertRaises(ValueError):C.configure(self.runtime,self.settings,self.helper)
    self.assertFalse((self.helper/'pro-config.json').exists())
 def test_bad_operator_capacity_no_intent(self):
  for value in [True,False,0,101,-1,1.5,'60']:
   with self.subTest(value=value),self.assertRaisesRegex(ValueError,'operator_capacity_invalid'):B.BindingContinuation(self.deps,self.prepared,self.plan,self.settings,self.runtime,self.helper,max_api_requests=value)
  self.assertFalse((self.helper/'pro-binding-continuations').exists());self.preserve()
 def test_operator60_idempotency_and_exact_rollback(self):
  C.configure(self.runtime,self.settings,self.helper);old=B.read(self.helper/'pro-config.json');oldexecutor=B.read(self.root/'pro-executor.json');self.deps.execute=lambda*a,**kw:(_ for _ in ()).throw(ValueError('local_probe_failed'))
  tx=B.BindingContinuation(self.deps,self.prepared,self.plan,self.settings,self.runtime,self.helper,max_api_requests=60)
  with self.assertRaisesRegex(ValueError,'local_probe_failed'):tx.install(C.configure)
  self.assertEqual(B.read(self.helper/'pro-config.json'),old);self.assertEqual(B.read(self.root/'pro-executor.json'),oldexecutor);self.assertTrue((tx.evidence/'ROLLBACK.json').exists());self.assertFalse((tx.evidence/'RESULT.json').exists());self.preserve()
 def test_operator_capacity_uses_distinct_once_and_stays_idempotent(self):
  default=self.tx();tx=B.BindingContinuation(self.deps,self.prepared,self.plan,self.settings,self.runtime,self.helper,max_api_requests=60);self.assertNotEqual(tx.evidence,default.evidence);tx.install(C.configure);before=B.read(self.helper/'pro-config.json');again=B.BindingContinuation(self.deps,self.prepared,self.plan,self.settings,self.runtime,self.helper,max_api_requests=60);again.install(C.configure);self.assertEqual(B.read(self.helper/'pro-config.json'),before);self.preserve()
 def test_shell_visible_entry_forwards_explicit_operator_argument(self):
  here=Path(__file__).parent/'participant';folder=self.base/'pack';support=folder/'.crowd-support';support.mkdir(parents=True);shutil.copy2(here/'start.command',folder/'开始安装.command');stub=support/'install.command';stub.write_text('#!/bin/zsh\nprint -r -- "$@"\n');stub.chmod(0o700)
  done=subprocess.run(['/bin/zsh',str(folder/'开始安装.command'),'--pro-max-api-requests','60'],capture_output=True,text=True);self.assertEqual(done.returncode,0);self.assertEqual(done.stdout.strip(),'--pro-max-api-requests 60')
  done=subprocess.run(['/bin/zsh',str(here/'install.command'),'--pro-max-api-requests','101'],capture_output=True,text=True);self.assertEqual(done.returncode,2);self.assertIn('1..100',done.stdout)
  parser=(here/'install.command').read_text().split('PACKAGE_DIR=',1)[0]+'\nprint -r -- \"${PRO_INSTALL_OPTIONS[@]}\"\n'
  done=subprocess.run(['/bin/zsh','-c',parser,'--','--pro-max-api-requests','60'],capture_output=True,text=True);self.assertEqual(done.returncode,0,done.stderr);self.assertEqual(done.stdout.strip(),'--max-api-requests 60')
 def test_actual_wrapper_forwards_option_and_returns_explicit_capacity(self):
  from types import SimpleNamespace
  calls=[]
  class Tx:
   def signer_ready(self):pass
   def install(self,configure):calls.append(configure);return {'state':'configured','configured':True}
  def factory(*args,**kw):self.assertEqual(kw,{'max_api_requests':60});return Tx()
  deps=SimpleNamespace(prepare=lambda*a:self.prepared,read=lambda p:p.read_bytes(),plan=lambda*a:self.plan,need=B.need,check=lambda*a,**kw:None)
  descriptor=self.base/'descriptor';descriptor.write_text('{}')
  self.assertEqual(W.install(deps,C.configure,descriptor,self.settings,self.runtime,self.helper,factory,max_api_requests=60),{'state':'configured','configured':True,'max_api_requests':60});self.assertEqual(calls,[C.configure]);self.preserve()
 def test_old_completed_task_budget_and_delivery_unchanged(self):
  import sqlite3
  f=self.root/'cloud-outbox/outbox.sqlite3';f.parent.mkdir();db=sqlite3.connect(f);db.execute('create table participant_runs(task integer,state text,context text)');db.execute("insert into participant_runs values(29,'complete',?)",(json.dumps({'max_api_requests':14,'received':2,'target':2}),));db.execute('create table participant_delivery(state text,receipt text)');db.execute("insert into participant_delivery values('delivered','original receipt')");db.commit();db.close();old=f.read_bytes()
  tx=B.BindingContinuation(self.deps,self.prepared,self.plan,self.settings,self.runtime,self.helper,max_api_requests=60);tx.install(C.configure);self.assertEqual(f.read_bytes(),old);self.preserve()
 def test_next_ordinary_upgrade_without_override_retains60(self):
  tx=B.BindingContinuation(self.deps,self.prepared,self.plan,self.settings,self.runtime,self.helper,max_api_requests=60);tx.install(C.configure)
  again=self.tx();again.install(C.configure);self.assertEqual(json.loads(B.read(self.helper/'pro-config.json'))['max_api_requests'],60)
  self.entry.write_text('# next own native entry');m=json.loads((self.runtime/'PRO-RUNTIME.json').read_text());m['files'][self.entry.name]=B.sha(self.entry.read_bytes());self.put(self.runtime/'PRO-RUNTIME.json',m)
  self.tx().install(C.configure);self.assertEqual(json.loads(B.read(self.helper/'pro-config.json'))['max_api_requests'],60);self.preserve()
if __name__=='__main__':unittest.main()



