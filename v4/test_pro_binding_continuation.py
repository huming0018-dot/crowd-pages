"""Temp-only original configure/metadata reader; no SDK HTTP, native IPC or UI."""
import hashlib,importlib.util,json,os,sqlite3,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
HERE=Path(__file__).resolve().parent
MP=Path(os.environ.get('CROWD_MULTIPLATFORM_DIR', str(HERE.parents[1]/'crowd-kol/server/crowd/v4/multiplatform')))
sys.path.insert(0,str(MP))
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
B=load('continuation',HERE/'participant/pro-binding-continuation.py');C=load('configure',HERE/'participant/configure-pro.py');W=load('wrapper',HERE/'participant/prepare-and-configure-pro.py')
class Binding(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name).resolve();self.helper=self.base/'helper';self.helper.mkdir(mode=0o700);self.root=self.base/'collector';self.root.mkdir();self.session_id='11111111-1111-4111-8111-111111111111';self.session=self.root/'sessions'/self.session_id;self.session.mkdir(parents=True);(self.session/'browser_data').mkdir();(self.session/'browser_data/keep').write_text('profile metadata, no credentials');self.sdk=self.base/'licensed';(self.sdk/'media_platform/xhs').mkdir(parents=True)
  self.oldpython=self.base/'old-python';self.oldpython.write_text('old');self.oldpython.chmod(0o700);self.newpython=self.base/'new-python';self.newpython.write_text('new');self.newpython.chmod(0o700)
  self.values={'python':str(self.oldpython),'root':str(self.root),'mc_root':str(self.sdk),'session_id':self.session_id,'max_api_requests':14,'purpose':'noncommercial_research'}
  self.settings=self.helper/'pro-install-settings.json';self.put(self.settings,self.values);self.put(self.root/'pro-executor.json',{'root':str(self.sdk),'python':str(self.oldpython)});self.put(self.session/'identity.json',{'platform':'xhs'});self.put(self.session/'pro-binding.json',{'platform':'xhs','client_id':'original-client','cookiebridge_url':'http://127.0.0.1:8274','sign_url':'http://127.0.0.1:8989'});self.account=self.root/'accounts'/self.session_id/'state.json';self.account.parent.mkdir(parents=True);self.put(self.account,{'session_id':self.session_id,'platform':'xhs','account_ref':'a'*64,'state':'authenticated','generation':3})
  self.runtime=self.base/'own-runtime';self.runtime.mkdir();self.entry=self.runtime/'participant_pro_native.py';self.entry.write_text('# own fixture entry\n');self.put(self.runtime/'PRO-RUNTIME.json',{'schema':'crowd-participant-pro-runtime-v1','files':{self.entry.name:B.sha(self.entry.read_bytes())}})
  self.calls=[]
  def execute(argv,**kw):
   self.calls.append(argv)
   import pro_executor
   value=pro_executor.task_installation(self.root,{'source_executor':'pro'});self.assertEqual(value,{'root':str(self.sdk),'python':str(self.newpython)});self.assertEqual(pro_executor.binding_for(self.root,{'session_id':self.session_id,'platform':'xhs'})['client_id'],'original-client')
   return b''
  self.deps=SimpleNamespace(execute=execute,environment=lambda:{})
  self.prepared={'key':'b'*64,'python':str(self.newpython)};self.plan={'input':{'projects':{'pro':{'root':str(self.sdk)}}}}
  self.protected={str(p):p.read_bytes()for p in [self.settings,self.account,self.session/'identity.json',self.session/'pro-binding.json',self.session/'browser_data/keep']}
 def put(self,p,v):p.write_bytes(B.encoded(v));p.chmod(0o600)
 def tx(self):return B.BindingContinuation(self.deps,self.prepared,self.plan,self.settings,self.runtime,self.helper)
 def preserve(self):self.assertEqual({p:Path(p).read_bytes()for p in self.protected},self.protected)
 def test_original_wrapper_red_contract(self):
  deps=SimpleNamespace(prepare=lambda*a:self.prepared,read=lambda p:p.read_bytes(),plan=lambda*a:self.plan,need=B.need,check=lambda*a:None)
  with self.assertRaisesRegex(ValueError,'dependency_binding_migration_required'):W.install(deps,C.configure,None,self.settings,self.runtime,self.helper)
  self.assertFalse((self.helper/'pro-config.json').exists());self.preserve()
 def test_new_config_double_reader_same_python_preserves_identity(self):
  tx=self.tx();r=tx.install(C.configure);self.assertTrue(r['configured']);self.assertEqual(len(self.calls),1);self.assertEqual(json.loads(B.read(self.root/'pro-executor.json'))['python'],str(self.newpython));self.assertEqual(json.loads(B.read(self.helper/'pro-config.json'))['python'],str(self.newpython));self.assertEqual(json.loads(B.read(tx.evidence/'RESULT.json'))['authenticated'],False);self.preserve()
 def test_existing_config_continues_original_scope(self):
  C.configure(self.runtime,self.settings,self.helper);before=B.read(self.helper/'pro-config.json');tx=self.tx();tx.install(C.configure);self.assertEqual(B.read(tx.evidence/'config.before.json'),before);self.assertEqual(json.loads(B.read(self.helper/'pro-config.json'))['session_id'],self.session_id);self.preserve()
 def test_same_success_idempotent_no_rewrite(self):
  self.tx().install(C.configure);p=self.helper/'pro-config.json';inode=p.stat().st_ino;self.tx().install(C.configure);self.assertEqual(p.stat().st_ino,inode);self.preserve()
 def test_wrong_executor_source_and_foreign_config_reject(self):
  self.put(self.root/'pro-executor.json',{'root':'/foreign','python':str(self.oldpython)})
  with self.assertRaisesRegex(ValueError,'source_changed'):self.tx()
  self.put(self.root/'pro-executor.json',{'root':str(self.sdk),'python':str(self.oldpython)});C.configure(self.runtime,self.settings,self.helper);v=json.loads(B.read(self.helper/'pro-config.json'));v['session_id']='22222222-2222-4222-8222-222222222222';self.put(self.helper/'pro-config.json',v)
  with self.assertRaisesRegex(ValueError,'scope_changed'):self.tx()
  self.preserve()
 def test_wrong_principal_and_identity_reject_before_intent(self):
  v=json.loads(B.read(self.account));v['account_ref']=None;self.put(self.account,v)
  with self.assertRaisesRegex(ValueError,'principal_required'):self.tx().install(C.configure)
  self.assertFalse((self.helper/'pro-binding-continuations').exists())
  self.put(self.account,json.loads(self.protected[str(self.account)]));self.put(self.session/'identity.json',{'platform':'bili'})
  with self.assertRaisesRegex(ValueError,'scope_changed'):self.tx().install(C.configure)
 def test_active_session_and_native_unknown_reject(self):
  import fcntl
  p=self.session/'active.lock';p.touch();f=p.open('r+');fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
  try:
   with self.assertRaises(BlockingIOError):self.tx().install(C.configure)
  finally:f.close()
  self.assertEqual(json.loads(B.read(self.root/'pro-executor.json'))['python'],str(self.oldpython));self.preserve()
  db=self.root/'cloud-outbox/outbox.sqlite3';db.parent.mkdir();conn=sqlite3.connect(db);conn.execute('create table participant_runs(state text)');conn.execute("insert into participant_runs values('source_unknown')");conn.commit();conn.close()
  with self.assertRaisesRegex(ValueError,'native_pending'):self.tx().install(C.configure)
 def test_busy_host_reject_no_mutation(self):
  self.put(self.helper/'pro-state.json',{'busy':True,'state':'unknown'})
  with self.assertRaisesRegex(ValueError,'host_busy'):self.tx().install(C.configure)
  self.preserve();self.assertFalse((self.helper/'pro-config.json').exists())
 def test_busy_false_unknown_still_denied(self):
  self.put(self.helper/'pro-state.json',{'busy':False,'state':'unknown'})
  with self.assertRaisesRegex(ValueError,'host_busy'):self.tx().install(C.configure)
  self.preserve();self.assertFalse((self.helper/'pro-config.json').exists())
 def test_config_write_failure_rolls_back_both_known_pointers(self):
  old=B.read(self.root/'pro-executor.json');real=C.os.open
  def fail(path,*a,**kw):
   if Path(path)==self.helper/'pro-config.json':raise OSError('simulated write failure')
   return real(path,*a,**kw)
  tx=self.tx()
  with patch.object(C.os,'open',side_effect=fail),self.assertRaises(OSError):tx.install(C.configure)
  self.assertEqual(B.read(self.root/'pro-executor.json'),old);self.assertFalse((self.helper/'pro-config.json').exists());self.assertTrue((tx.evidence/'ROLLBACK.json').exists());self.assertFalse((tx.evidence/'RESULT.json').exists());self.preserve()
  with self.assertRaisesRegex(ValueError,'attempt_unknown'):self.tx().install(C.configure)
 def test_postverify_failure_restores_existing_config(self):
  C.configure(self.runtime,self.settings,self.helper);old=B.read(self.helper/'pro-config.json');exec_old=B.read(self.root/'pro-executor.json');self.deps.execute=lambda*a,**k:(_ for _ in()).throw(ValueError('local_probe_failed'));tx=self.tx()
  with self.assertRaisesRegex(ValueError,'local_probe_failed'):tx.install(C.configure)
  self.assertEqual(B.read(self.helper/'pro-config.json'),old);self.assertEqual(B.read(self.root/'pro-executor.json'),exec_old);self.preserve()
 def test_foreign_write_held_unknown_not_overwritten(self):
  def execute(*a,**kw):self.put(self.root/'pro-executor.json',{'root':'/foreign','python':'/foreign'});raise ValueError('unexpected')
  self.deps.execute=execute;tx=self.tx()
  with self.assertRaisesRegex(ValueError,'rollback_unknown'):tx.install(C.configure)
  self.assertEqual(json.loads(B.read(self.root/'pro-executor.json'))['root'],'/foreign');self.assertFalse((tx.evidence/'RESULT.json').exists());self.assertFalse((tx.evidence/'ROLLBACK.json').exists());self.preserve()
 def test_scope_change_before_commit_rejects(self):
  tx=self.tx();real=C.configure
  def mutate(*a,**kw):
   v=json.loads(B.read(self.account));v['account_ref']='c'*64;self.put(self.account,v);return real(*a,**kw)
  with self.assertRaisesRegex(ValueError,'scope_changed'):tx.install(mutate)
  self.assertEqual(json.loads(B.read(self.root/'pro-executor.json'))['python'],str(self.oldpython));self.assertFalse((self.helper/'pro-config.json').exists())
 def test_result_write_failure_is_not_ready_and_rolls_back(self):
  tx=self.tx();original=B.once
  def fail(path,raw):
   if Path(path).name=='RESULT.json':raise OSError('terminal disk full')
   return original(path,raw)
  old=B.read(self.root/'pro-executor.json')
  with patch.object(B,'once',side_effect=fail),self.assertRaises(OSError):tx.install(C.configure)
  self.assertEqual(B.read(self.root/'pro-executor.json'),old);self.assertFalse((self.helper/'pro-config.json').exists());self.assertFalse((tx.evidence/'RESULT.json').exists());self.preserve()
 def test_unknown_run_and_missing_profile_reject(self):
  status=self.root/'runs'/'run'/'status.json';status.parent.mkdir(parents=True);self.put(status,{'state':'interrupted_unknown'})
  with self.assertRaisesRegex(ValueError,'source_active'):self.tx().install(C.configure)
  status.unlink();(self.session/'browser_data/keep').unlink();(self.session/'browser_data').rmdir()
  with self.assertRaisesRegex(ValueError,'profile_invalid'):self.tx().install(C.configure)
 def test_identity_drift_during_probe_rolls_back_not_ready(self):
  original=self.deps.execute
  def mutate(*a,**kw):
   r=original(*a,**kw);self.put(self.account,{**json.loads(B.read(self.account)),'account_ref':'c'*64});return r
  self.deps.execute=mutate;tx=self.tx()
  with self.assertRaisesRegex(ValueError,'scope_changed'):tx.install(C.configure)
 def test_inconsistent_before_double_pointer_refuses(self):
  C.configure(self.runtime,self.settings,self.helper);self.put(self.root/'pro-executor.json',{'root':str(self.sdk),'python':str(self.newpython)})
  with self.assertRaisesRegex(ValueError,'source_changed'):self.tx()
 def test_completed_attempt_cannot_accept_changed_principal(self):
  self.tx().install(C.configure);value=json.loads(B.read(self.account));value['account_ref']='c'*64;self.put(self.account,value)
  with self.assertRaisesRegex(ValueError,'scope_changed'):self.tx().install(C.configure)
 def test_real_source_split_preserves_original_fallback_and_uses_selected_pro(self):
  fallback=self.base/'original-media-crawler';(fallback/'media_platform/xhs').mkdir(parents=True)
  self.values['mc_root']=str(fallback);self.put(self.settings,self.values);self.protected[str(self.settings)]=self.settings.read_bytes()
  before=self.settings.read_bytes();tx=self.tx();tx.install(C.configure)
  self.assertEqual(self.settings.read_bytes(),before)
  self.assertEqual(json.loads(B.read(self.root/'pro-executor.json'))['root'],str(self.sdk))
  self.assertEqual(json.loads(B.read(self.helper/'pro-config.json'))['mc_root'],str(fallback))
  self.preserve()
 def test_real_source_split_foreign_selected_source_still_refused(self):
  fallback=self.base/'original-media-crawler';(fallback/'media_platform/xhs').mkdir(parents=True)
  self.values['mc_root']=str(fallback);self.put(self.settings,self.values)
  self.put(self.root/'pro-executor.json',{'root':str(fallback),'python':str(self.oldpython)})
  with self.assertRaisesRegex(ValueError,'source_changed'):self.tx()
  self.assertFalse((self.helper/'pro-binding-continuations').exists())

if __name__=='__main__':unittest.main()
