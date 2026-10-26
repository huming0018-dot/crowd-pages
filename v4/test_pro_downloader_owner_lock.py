"""Temp-only Owner scope + real AccountSessions.status/flock, no SDK/network calls.
Required CROWD_PRO_RUNTIME_FIXTURE: pinned own-code runtime with PRO-RUNTIME.json.
No real Owner state fixture; missing input fails. From v4:
python3 -B -m unittest test_pro_downloader_owner_lock
"""
import fcntl,importlib.util,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
BASE=Path(__file__).resolve().parent
PAGES=BASE;RUNTIME=Path(os.environ['CROWD_PRO_RUNTIME_FIXTURE'])
sys.path[:0]=[str(RUNTIME),str(PAGES/'participant')]
import pro_executor as pro
from account_sessions import AccountSessions

def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
M=load('g70_owner_test',PAGES/'participant/prepare-pro-downloader.py')
D=load('g70_owner_deps',PAGES/'participant/prepare-pro-dependencies.py')
C=load('g70_owner_continuation',PAGES/'participant/pro-binding-continuation.py')
class OwnerLock(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve();self.helper=self.root/'helper';self.helper.mkdir(mode=0o700);self.owner=self.root/'owner';self.owner.mkdir(mode=0o700);self.collector=self.root/'collector';self.collector.mkdir(mode=0o700)
  self.sid='11111111-1111-4111-8111-111111111111';self.session=self.collector/'sessions'/self.sid;self.session.mkdir(parents=True);self.account=self.collector/'accounts'/self.sid/'state.json';self.account.parent.mkdir(parents=True)
  for p in (self.helper/'update.lock',self.helper/'pro.lock',self.session/'active.lock'):p.touch(mode=0o600)
  self.put(self.helper/'pro-state.json',{'state':'stopped','busy':False});self.put(self.owner/'dashboard-config.json',{'collector_roots':[str(self.collector)]});self.put(self.collector/'pro-executor.json',{'root':str(self.root/'licensed-sdk'),'python':'/fixture/python'});self.put(self.session/'identity.json',{'platform':'xhs'});self.put(self.session/'pro-binding.json',{'platform':'xhs','client_id':'fixture-only','cookiebridge_url':'http://127.0.0.1:1','sign_url':'http://127.0.0.1:8990'})
  self.put(self.account,{'session_id':self.sid,'platform':'xhs','state':'authenticated','login_verified':True,'identity_status':'authenticated_self_id','account_ref':'a'*64,'generation':1})
  for target,value in [('task_installation',lambda *_:{'root':str(self.root/'licensed-sdk')}),('binding_for',lambda *_:json.loads((self.session/'pro-binding.json').read_bytes())),('bridge',lambda:type('Bridge',(),{'source_info':lambda _,p:{'commit':pro.PINNED_COMMIT,'dirty':False}})())]:
   x=patch.object(pro,target,value);x.start();self.addCleanup(x.stop)
  x=patch.object(M,'binding',return_value={'schema':'fixture-no-sdk-copy'});x.start();self.addCleanup(x.stop)
 def put(self,p,v):p.write_bytes(M.encoded(v));p.chmod(0o600)
 def context(self):return M.owner_context(D,None,self.helper,self.owner,RUNTIME,C.BindingContinuation,session_id=self.sid)
 def publish(self,ctx):return M._publish(D,None,self.helper,*ctx)
 def test_legitimate_owner_scope_publishes_under_real_session_lock(self):
  ctx=self.context();before=ctx[2]();self.assertFalse(AccountSessions(self.collector).status(self.sid,'xhs')['login_in_progress']);self.assertEqual(self.publish(ctx)['state'],'configured');self.assertEqual(ctx[2](),before);self.assertFalse(AccountSessions(self.collector).status(self.sid,'xhs')['login_in_progress'])
 def test_foreign_session_lock_before_context_refuses(self):
  with open(self.session/'active.lock','r+')as f:
   fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
   with self.assertRaisesRegex(ValueError,'identity_unverified'):self.context()
  self.assertFalse((self.collector/'pro-xhs-media.json').exists())
 def test_foreign_session_lock_after_context_refuses(self):
  ctx=self.context()
  with open(self.session/'active.lock','r+')as f:
   fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
   with self.assertRaises(BlockingIOError):self.publish(ctx)
  self.assertFalse((self.collector/'pro-xhs-media.json').exists())
 def test_account_change_after_precheck_refuses_before_publish(self):
  ctx=self.context();state=json.loads(self.account.read_bytes());state['generation']=2;self.put(self.account,state)
  with self.assertRaisesRegex(ValueError,'collector_changed'):self.publish(ctx)
  self.assertFalse((self.collector/'pro-xhs-media.json').exists())
 def test_pro_source_drift_still_refused_under_own_lock(self):
  ctx=self.context()
  with patch.object(pro,'bridge',return_value=type('Bridge',(),{'source_info':lambda _,p:{'commit':'0'*40,'dirty':False}})()):
   with self.assertRaisesRegex(ValueError,'pro_source_changed'):self.publish(ctx)
  self.assertFalse((self.collector/'pro-xhs-media.json').exists())
 def test_same_pinned_owner_binding_reuses_no_identity_write(self):
  ctx=self.context();before=ctx[2]();self.publish(ctx);self.assertEqual(self.publish(ctx),{'state':'verified','changed':False});self.assertEqual(ctx[2](),before)
if __name__=='__main__':unittest.main()
