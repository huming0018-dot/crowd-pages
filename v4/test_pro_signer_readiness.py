import json,sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import test_pro_binding_continuation as T
B,W,C,load,HERE=T.B,T.W,T.C,T.load,T.HERE
D=load('deps_readiness', HERE/'participant/prepare-pro-dependencies.py')

class Readiness(unittest.TestCase):
 setUp=T.Binding.setUp
 put=T.Binding.put
 tx=T.Binding.tx
 preserve=T.Binding.preserve
 def test_original_nondefault_binding_not_hardcoded(self):
  self.put(self.session/'pro-binding.json',{'platform':'xhs','client_id':'original-client','cookiebridge_url':'http://127.0.0.1:8274','sign_url':'http://127.0.0.1:8990'})
  class Response:
   status=200
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def read(self,n):return b'{"isok":true,"biz_code":0,"data":{"message":"pong"}}'
  calls=[]
  with patch.object(D.urllib.request,'build_opener',return_value=SimpleNamespace(open=lambda url,**kw:(calls.append(url)or Response()))):
   D.signer_health('http://127.0.0.1:8990')
  self.assertEqual(calls,['http://127.0.0.1:8990/signsrv/pong'])
 def test_validate_only_not_idle_pong_before_pointer_transaction(self):
  value=json.loads((self.session/'pro-binding.json').read_bytes());value['sign_url']='http://127.0.0.1:8990';self.put(self.session/'pro-binding.json',value);self.protected[str(self.session/'pro-binding.json')]=(self.session/'pro-binding.json').read_bytes()
  signer=self.base/'signer';signer.mkdir();python=self.base/'sign-python';python.write_text('fixture');python.chmod(0o700)
  self.put(self.root/'pro-signer.json',{'python':str(python),'source_root':str(signer)})
  wrapper=self.runtime/'pro_signer_server.py';wrapper.write_text('# fixture pinned wrapper')
  mf=json.loads((self.runtime/'PRO-RUNTIME.json').read_bytes());mf['files'][wrapper.name]=B.sha(wrapper.read_bytes());self.put(self.runtime/'PRO-RUNTIME.json',mf)
  self.plan['input']['projects']['signer']={'root':str(signer)}
  calls=[]
  def execute(argv,**kw):
   if 'pro_signer_server.py' in str(argv):
    calls.append(argv);self.assertNotIn('--serve',argv);self.assertFalse((self.helper/'pro-binding-continuations').exists())
    return b'{"ok":true,"validate_only":true,"listening":false,"source_requests":0,"browser_started":false,"platforms":["xhs","dy","zhihu"]}'
   return self.deps.execute_original(argv,**kw)
  self.deps.execute_original=self.deps.execute;self.deps.execute=execute
  tx=self.tx();tx.signer_ready();self.assertEqual(len(calls),1)
  tx.install(C.configure);self.preserve()
 def test_invalid_urls_no_request(self):
  for url in ['http://example.com:8990','http://127.0.0.1:8990/x','http://u:p@127.0.0.1:8990','http://127.0.0.1:8990/?x=1','http://[::1]:8990','http://localhost','https://localhost:8990']:
   with self.subTest(url=url),patch.object(D.urllib.request,'build_opener') as op,self.assertRaisesRegex(ValueError,'signer_binding_invalid'):D.signer_health(url)
   op.assert_not_called()

 def test_wrapper_uses_owned_installation_validation_not_listener(self):
  calls=[]
  deps=SimpleNamespace(prepare=lambda*a:self.prepared,read=lambda p:p.read_bytes(),plan=lambda*a:self.plan,
       check=lambda*a,health=None:(calls.append('check'),health()),need=B.need)
  tx=SimpleNamespace(signer_ready=lambda:calls.append('validate_only'),install=lambda config:(calls.append('install')or {'configured':True}))
  W.install(deps,C.configure,None,self.settings,self.runtime,self.helper,lambda*a:tx)
  self.assertEqual(calls,['check','validate_only','install'])
 def test_missing_signer_descriptor_refused_before_intent(self):
  v=json.loads((self.session/'pro-binding.json').read_bytes());v['sign_url']='http://127.0.0.1:8990';self.put(self.session/'pro-binding.json',v)
  tx=self.tx()
  with self.assertRaisesRegex(ValueError,'signer_installation_required'):tx.signer_ready()
  self.assertFalse((self.helper/'pro-binding-continuations').exists())
 def test_foreign_pong_and_network_error_not_ready(self):
  class Response:
   status=200
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def read(self,n):return b'{"isok":true,"biz_code":false,"data":{"message":"pong"}}'
  with patch.object(D.urllib.request,'build_opener',return_value=SimpleNamespace(open=lambda*a,**k:Response())),self.assertRaisesRegex(ValueError,'signer_not_ready'):
   D.signer_health('http://127.0.0.1:8990')

 def fixture_signer(self):
  value=json.loads((self.session/'pro-binding.json').read_bytes());value['sign_url']='http://127.0.0.1:8990';self.put(self.session/'pro-binding.json',value)
  signer=self.base/'signer';signer.mkdir();python=self.base/'sign-python';python.write_text('fixture');python.chmod(0o700)
  self.put(self.root/'pro-signer.json',{'python':str(python),'source_root':str(signer)})
  wrapper=self.runtime/'pro_signer_server.py';wrapper.write_text('# fixture pinned wrapper')
  mf=json.loads((self.runtime/'PRO-RUNTIME.json').read_bytes());mf['files'][wrapper.name]=B.sha(wrapper.read_bytes());self.put(self.runtime/'PRO-RUNTIME.json',mf)
  self.plan['input']['projects']['signer']={'root':str(signer)}
  return self.tx()
 def test_validate_failure_no_pointer_or_intent_write(self):
  tx=self.fixture_signer();before=(self.root/'pro-executor.json').read_bytes()
  self.deps.execute=lambda*a,**kw:(_ for _ in ()).throw(ValueError('dependency_command_failed'))
  with self.assertRaisesRegex(ValueError,'signer_validation_failed'):tx.signer_ready()
  self.assertFalse((self.helper/'pro-binding-continuations').exists());self.assertEqual((self.root/'pro-executor.json').read_bytes(),before);self.assertFalse((self.helper/'pro-config.json').exists())
 def test_descriptor_drift_after_validation_rejects_before_intent(self):
  tx=self.fixture_signer()
  self.deps.execute=lambda*a,**kw:b'{"ok":true,"validate_only":true,"listening":false,"source_requests":0,"browser_started":false,"platforms":["xhs","dy","zhihu"]}'
  tx.signer_ready();self.put(self.root/'pro-signer.json',{'python':'/foreign','source_root':'/foreign'})
  with self.assertRaisesRegex(ValueError,'scope_changed'):tx.install(C.configure)
  self.assertFalse((self.helper/'pro-binding-continuations').exists())
 def test_wrong_source_or_managed_port_reject_no_command(self):
  tx=self.fixture_signer();calls=[];self.deps.execute=lambda*a,**kw:calls.append(a)
  self.put(self.root/'pro-signer.json',{'python':str(self.newpython),'source_root':'/foreign'})
  with self.assertRaisesRegex(ValueError,'signer_source_changed'):tx.signer_ready()
  value=json.loads((self.session/'pro-binding.json').read_bytes());value['sign_url']='http://127.0.0.1:8989';self.put(self.session/'pro-binding.json',value)
  with self.assertRaisesRegex(ValueError,'signer_binding_invalid'):tx.signer_ready()
  self.assertEqual(calls,[])
 def test_validate_response_typed_no_listener_or_source(self):
  tx=self.fixture_signer()
  for change in [{'listening':True},{'source_requests':1},{'source_requests':False},{'browser_started':True},{'ok':1}]:
   value={'ok':True,'validate_only':True,'listening':False,'source_requests':0,'browser_started':False,'platforms':['xhs','dy','zhihu'],**change}
   self.deps.execute=lambda*a,**kw:json.dumps(value).encode()
   with self.subTest(change=change),self.assertRaisesRegex(ValueError,'signer_validation_failed'):tx.signer_ready()
  self.assertFalse((self.helper/'pro-binding-continuations').exists())

 def test_selected_python_same_path_drift_rejects_before_intent(self):
  tx=self.fixture_signer()
  self.deps.execute=lambda*a,**kw:b'{"ok":true,"validate_only":true,"listening":false,"source_requests":0,"browser_started":false,"platforms":["xhs","dy","zhihu"]}'
  tx.signer_ready();descriptor=json.loads((self.root/'pro-signer.json').read_bytes());Path(descriptor['python']).write_text('changed same path')
  with self.assertRaisesRegex(ValueError,'scope_changed'):tx.install(C.configure)
  self.assertFalse((self.helper/'pro-binding-continuations').exists())
 def test_selected_python_drift_after_write_restores_known_pointers(self):
  tx=self.fixture_signer();original=self.deps.execute;old=(self.root/'pro-executor.json').read_bytes()
  def run(argv,**kw):
   if 'pro_signer_server.py' in str(argv):return b'{"ok":true,"validate_only":true,"listening":false,"source_requests":0,"browser_started":false,"platforms":["xhs","dy","zhihu"]}'
   selected=json.loads((self.root/'pro-signer.json').read_bytes());Path(selected['python']).write_text('drift at last local probe')
   return original(argv,**kw)
  self.deps.execute=run;tx.signer_ready()
  with self.assertRaisesRegex(ValueError,'scope_changed'):tx.install(C.configure)
  self.assertEqual((self.root/'pro-executor.json').read_bytes(),old);self.assertFalse((self.helper/'pro-config.json').exists());self.assertTrue((tx.evidence/'ROLLBACK.json').exists());self.assertFalse((tx.evidence/'RESULT.json').exists())

if __name__=='__main__':unittest.main()
