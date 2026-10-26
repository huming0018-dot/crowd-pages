"""Private dependency fixtures, no SDK vendoring or live account access.
Required: CROWD_PRO_DOWNLOADER=licensed checkout, CROWD_DOWNLOADER_ARCHIVES=JSON
mapping axios/follow-redirects to the original public SRI-verified cached tarballs.
Missing inputs fail. From v4: python3 -B -m unittest test_pro_downloader.
"""
import base64,hashlib,importlib.util,json,os,shutil,socket,sys,tempfile,unittest,uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
BASE=Path(__file__).resolve().parent;PAGES=BASE;sys.path[:0]=[str(PAGES/'participant'),str(PAGES)]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
D=load('g70_deps',PAGES/'participant/prepare-pro-dependencies.py');M=load('g70_media',PAGES/'participant/prepare-pro-downloader.py');W=load('g70_wrapper',PAGES/'participant/prepare-and-configure-pro.py')
import test_pro_dependencies as legacy
legacy.D=D;legacy.W=W
class Media(legacy.Dependencies):
 # Inherit fixture helpers, not old tests (run original unchanged separately).
 def setUp(self):
  super().setUp();self.network=patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN'));self.network.start();self.addCleanup(self.network.stop)
  for name in ('update.lock','pro.lock'):(self.helper/name).touch(mode=0o600)
  source=self.root/'licensed-downloader';(source/'DownloadUI/src/main').mkdir(parents=True)
  purchased=Path(os.environ['CROWD_PRO_DOWNLOADER'])
  for name in M.SOURCE_FILES:shutil.copyfile(purchased/name,source/name)
  self.value['downloader']={'root':str(source),'commit':'a'*40,'files':{n:M.sha((source/n).read_bytes())for n in M.SOURCE_FILES}};self.save()
  self.deps=SimpleNamespace(read=D.read,execute=self.transport,environment=D.environment)
  paths=json.loads(Path(os.environ['CROWD_DOWNLOADER_ARCHIVES']).read_text());self.archives={n:Path(p).read_bytes()for n,p in paths.items()}
  self.fetches=[]
  self.collector=self.root/'original-collector';(self.collector/'sessions').mkdir(parents=True);self.sid=str(uuid.uuid4());self.session=self.collector/'sessions'/self.sid;self.session.mkdir();(self.session/'active.lock').touch(mode=0o600)
  self.values={'root':str(self.collector),'python':str(self.binary),'mc_root':'/original/mc-fallback','session_id':self.sid,'max_api_requests':14,'purpose':'noncommercial_research'};self.write(self.settings,self.values)
  self.write(self.collector/'pro-executor.json',{'root':self.value['projects']['pro']['root'],'python':str(self.binary)});self.write(self.helper/'pro-config.json',self.values)
  self.config_bytes={p:p.read_bytes()for p in (self.settings,self.collector/'pro-executor.json',self.helper/'pro-config.json')}
 def write(self,p,v):p.write_bytes(D.encode(v));p.chmod(0o600)
 def fetch(self,url):
  self.fetches.append(url);name=next(n for n in M.PACKAGES if M.url(n)==url);return self.archives[name]
 def prepare_media(self):return M.prepare(self.deps,self.descriptor,self.helper,fetch=self.fetch)
 def continuation(self):
  return SimpleNamespace(settings=self.settings,original_raw=self.settings.read_bytes(),root=self.collector,session=self.session,plan={'input':self.value},scope=lambda:{'original-source':'unchanged'},idle=lambda:None)
 def assert_original(self):
  for p,v in self.config_bytes.items():self.assertEqual(p.read_bytes(),v)
 def test_optional_block_preserves_old_core_plan_and_target(self):
  new=D.plan(self.descriptor,self.helper,self.transport);self.value.pop('downloader');self.save();old=D.plan(self.descriptor,self.helper,self.transport);self.assertEqual(new,old)
 def test_source_plan_is_readonly(self):
  before=sorted(str(p)for p in self.helper.rglob('*'));M.plan(self.deps,self.descriptor,self.helper);self.assertEqual(before,sorted(str(p)for p in self.helper.rglob('*')))
 def test_two_official_archives_reconstruct_exact_53_any_device_prefix(self):
  result=self.prepare_media();target=Path(result['target']);files=M.inventory(target);self.assertEqual(len(files),53);self.assertEqual(M.sha(M.encoded(files)),M.INVENTORY_SHA);self.assertEqual(set(self.fetches),{M.url(n)for n in M.PACKAGES});self.assertNotIn('/Users/hubowen',str(target));self.assert_original()
 def test_existing_valid_resource_reused_without_fetch_or_install(self):
  target=self.helper/'pro-downloader-deps'/M.RESOURCE;target.mkdir(parents=True,mode=0o700)
  for name,raw in M.resources(self.archives).items():p=target/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
  self.assertFalse(self.prepare_media()['installed']);self.assertEqual(self.fetches,[])
 def test_wrong_archive_unknown_not_retried(self):
  with self.assertRaisesRegex(ValueError,'archive_changed'):M.prepare(self.deps,self.descriptor,self.helper,fetch=lambda _:b'bad')
  with self.assertRaisesRegex(ValueError,'attempt_unknown'):self.prepare_media()
  self.assertEqual(self.fetches,[])
 def test_existing_drift_does_not_repair(self):
  result=self.prepare_media();p=Path(result['target'])/'node_modules/axios/index.js';p.write_bytes(b'changed')
  with self.assertRaisesRegex(ValueError,'inventory_changed'):self.prepare_media()
  self.assertEqual(len(self.fetches),2)
 def test_bad_source_before_any_download(self):
  p=Path(self.value['downloader']['root'])/M.MANAGER;p.write_bytes(b'drift')
  with self.assertRaisesRegex(ValueError,'source_changed'):self.prepare_media()
  self.assertEqual(self.fetches,[])
 def test_wrong_lock_sri_not_guessed(self):
  p=Path(self.value['downloader']['root'])/'DownloadUI/package-lock.json';v=json.loads(p.read_bytes());v['packages']['node_modules/axios']['integrity']='wrong';p.write_text(json.dumps(v));self.value['downloader']['files']['DownloadUI/package-lock.json']=M.sha(p.read_bytes());self.save()
  with self.assertRaisesRegex(ValueError,'lock_changed'):self.prepare_media()
 def test_symlink_supplier_rejected(self):
  alias=self.root/'alias';alias.symlink_to(Path(self.value['downloader']['root']));self.value['downloader']['root']=str(alias);self.save()
  with self.assertRaisesRegex(ValueError,'path_invalid'):self.prepare_media()
 def test_native_provision_from_verified_collector_preserves_all_six_and_executor(self):
  self.prepare_media();result=M.provision(self.deps,self.descriptor,self.helper,self.continuation());self.assertTrue(result['changed']);v=json.loads((self.collector/'pro-xhs-media.json').read_bytes());self.assertEqual(set(v),{'schema','manager_path','manager_sha256','axios_root','axios_files'});self.assertEqual(len(v['axios_files']),53);self.assert_original();self.assertFalse(M.provision(self.deps,self.descriptor,self.helper,self.continuation())['changed'])
 def test_existing_foreign_binding_not_overwritten(self):
  self.prepare_media();p=self.collector/'pro-xhs-media.json';self.write(p,{'foreign':True});before=p.read_bytes()
  with self.assertRaisesRegex(ValueError,'binding_conflict'):M.provision(self.deps,self.descriptor,self.helper,self.continuation())
  self.assertEqual(p.read_bytes(),before)
 def test_unknown_cannot_change_descriptor_to_retry_binding(self):
  self.prepare_media();c=self.continuation();count=[0]
  def scope():count[0]+=1;return {'scope':count[0]}
  c.scope=scope
  with self.assertRaisesRegex(ValueError,'collector_changed'):M.provision(self.deps,self.descriptor,self.helper,c)
  with self.assertRaisesRegex(ValueError,'binding_unknown'):M.provision(self.deps,self.descriptor,self.helper,self.continuation())
  self.assertFalse((self.collector/'pro-xhs-media.json').exists());self.assert_original()
 def test_busy_host_no_binding(self):
  self.prepare_media();self.write(self.helper/'pro-state.json',{'state':'unknown','busy':False})
  with self.assertRaisesRegex(ValueError,'host_busy'):M.provision(self.deps,self.descriptor,self.helper,self.continuation())
  self.assertFalse((self.collector/'pro-xhs-media.json').exists())
 def test_no_check_creates_missing_resources(self):
  with self.assertRaisesRegex(ValueError,'resource_missing'):M.binding(self.deps,self.descriptor,self.helper)
  self.assertFalse((self.helper/'pro-downloader-deps').exists())
 def test_owner_root_must_be_registered_and_unambiguous(self):
  owner=self.root/'workbench';owner.mkdir(mode=0o700);self.write(owner/'dashboard-config.json',{'collector_roots':[],'preferred_session_by_platform':{'xhs':self.sid}})
  with self.assertRaisesRegex(ValueError,'owner_registry_invalid'):M.owner_context(self.deps,self.descriptor,self.helper,owner,self.root/'no-runtime',None)
 def test_wrapper_actually_consumes_optional_supplier_before_configure(self):
  self.prepare_media();events=[];c=self.continuation();c.signer_ready=lambda:events.append('signer');c.install=lambda configure:configure(None,None,None)
  facade=SimpleNamespace(read=D.read,prepare=lambda *_:{'python':str(self.binary),'key':'prepared'},plan=lambda *_:{'input':self.value},check=lambda *a,**kw:kw['health'](),execute=self.transport,environment=D.environment)
  def configure(*_):self.assertTrue((self.collector/'pro-xhs-media.json').exists());events.append('configure');return {'state':'current'}
  W.install(facade,configure,self.descriptor,self.settings,self.root/'runtime',self.helper,lambda *_:c);self.assertEqual(events,['signer','configure']);self.assert_original()
 def test_old_descriptor_wrapper_does_not_load_downloader(self):
  self.value.pop('downloader');self.save();c=self.continuation();c.signer_ready=lambda:None;c.install=lambda configure:configure(None,None,None)
  facade=SimpleNamespace(read=D.read,prepare=lambda *_:{},plan=lambda *_:{},check=lambda *a,**kw:kw['health']())
  with patch.object(W,'load',side_effect=AssertionError('old path must not import media')):self.assertEqual(W.install(facade,lambda *_:'old-original',self.descriptor,self.settings,self.root/'runtime',self.helper,lambda *_:c),'old-original')
# Keep old tests in their original files; only fixture inheritance here.
for name in list(legacy.Dependencies.__dict__):
 if name.startswith('test_')and name not in Media.__dict__:setattr(Media,name,None)
if __name__=='__main__':unittest.main()
