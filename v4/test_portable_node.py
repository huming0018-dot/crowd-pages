import hashlib, importlib.util, io, json, os, sys, tarfile, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
PP=HERE/'participant'
MP=Path(os.environ.get('CROWD_MULTIPLATFORM_DIR',str(HERE.parents[1]/'crowd-kol/server/crowd/v4/multiplatform'))).resolve()
if not (MP/'portable_node.py').is_file():raise RuntimeError('required crowd-kol portable_node.py; set CROWD_MULTIPLATFORM_DIR or use adjacent repositories')
spec=importlib.util.spec_from_file_location('portable_node',MP/'portable_node.py')
N=importlib.util.module_from_spec(spec);spec.loader.exec_module(N)
def archive(node=b'fixture-node',extra=False):
 b=io.BytesIO()
 with tarfile.open(fileobj=b,mode='w:gz') as t:
  for name,data in [('bin/node',node),('LICENSE',b'Node license')]:
   q=tarfile.TarInfo('node-v22.23.2-darwin-arm64/'+name);q.size=len(data);q.mode=0o755 if name.endswith('node') else 0o644;t.addfile(q,io.BytesIO(data))
  if extra:
   q=tarfile.TarInfo('../escape');q.size=1;t.addfile(q,io.BytesIO(b'x'))
 return b.getvalue()
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.root.chmod(0o700)
  self.raw=archive();self.p=patch.dict(N.ARCHIVES,{'arm64':hashlib.sha256(self.raw).hexdigest()});self.p.start()
  self.p2=patch.object(N,'TRUSTED_ARM64_BINARY',hashlib.sha256(b'fixture-node').hexdigest());self.p2.start()
 def tearDown(self):self.p2.stop();self.p.stop();self.tmp.cleanup()
 def prepare(self):return N.prepare(self.root,arch='arm64',fetch=lambda u:self.raw)
 def test_prepare_check_and_old_path_not_used(self):
  p=self.prepare();self.assertEqual(p,N.check(self.root,arch='arm64'));self.assertNotIn('/Users/hubowen',str(p));self.assertEqual(p.read_bytes(),b'fixture-node')
 def test_repeated_prepared_no_fetch(self):
  p=self.prepare();self.assertEqual(N.prepare(self.root,arch='arm64',fetch=lambda u:self.fail('fetch replay')),p)
 def test_wrong_archive(self):
  with self.assertRaisesRegex(ValueError,'archive_changed'):N.prepare(self.root,arch='arm64',fetch=lambda u:b'bad')
 def test_unknown_once_no_retry(self):
  with self.assertRaises(OSError):N.prepare(self.root,arch='arm64',fetch=lambda u:(_ for _ in ()).throw(OSError('unknown')))
  with self.assertRaisesRegex(ValueError,'attempt_unknown'):self.prepare()
 def test_tampered_binary(self):
  p=self.prepare();p.write_bytes(b'changed')
  with self.assertRaisesRegex(ValueError,'binary_changed'):N.check(self.root,arch='arm64')
 def test_tampered_archive(self):
  p=self.prepare();(p.parent.parent/'archive.tar.gz').write_bytes(b'changed')
  with self.assertRaisesRegex(ValueError,'archive_changed'):N.check(self.root,arch='arm64')
 def test_wrong_arch(self):
  with self.assertRaisesRegex(ValueError,'architecture'):N.prepare(self.root,arch='linux')
 def test_symlink_target(self):
  self.prepare();p=N.target(self.root,'arm64');p.rename(self.root/'old');p.symlink_to(self.root/'old',target_is_directory=True)
  with self.assertRaises(ValueError):N.check(self.root,arch='arm64')
 def test_tar_escape(self):
  raw=archive(extra=True)
  with patch.dict(N.ARCHIVES,{'arm64':hashlib.sha256(raw).hexdigest()}),self.assertRaisesRegex(ValueError,'archive_member'):N.prepare(self.root,arch='arm64',fetch=lambda u:raw)
 def test_wrong_binary_original_trust(self):
  with patch.object(N,'TRUSTED_ARM64_BINARY','0'*64),self.assertRaisesRegex(ValueError,'binary_changed'):self.prepare()
 def test_offline_missing(self):
  with self.assertRaisesRegex(ValueError,'offline_missing'):N.prepare(self.root,arch='arm64',offline=True)
 def test_runtime_resolves_only_helper_layout(self):
  p=self.prepare();rt=self.root/'pro-runtime'/('a'*64);rt.mkdir(parents=True)
  self.assertEqual(N.from_runtime(rt,arch='arm64'),p)
  with self.assertRaisesRegex(ValueError,'runtime_layout'):N.from_runtime(self.root,arch='arm64')

class CallerTests(unittest.TestCase):
 def test_prepare_check_actual_dependency_caller(self):
  sys.path.insert(0,str(PP))
  try:
   spec=importlib.util.spec_from_file_location('deps',PP/'prepare-pro-dependencies.py');d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
  finally:sys.path.pop(0)
  with tempfile.TemporaryDirectory() as tmp:
   helper=Path(tmp).resolve();helper.chmod(0o700);dest=helper/'pro-environments'/'fixed';dest.mkdir(parents=True);dest.chmod(0o700);dest.parent.chmod(0o700)
   p={'target':str(dest),'key':'a'*64};(dest/'RESULT.json').write_text(json.dumps({'state':'prepared','key':p['key'],'offline':False}));(dest/'RESULT.json').chmod(0o600)
   calls=[]
   with patch.object(d,'plan',return_value=p),patch.object(d,'probes'),patch.object(d.portable_node,'prepare',side_effect=lambda *a,**k:calls.append('prepare')),patch.object(d.portable_node,'check',side_effect=lambda *a,**k:calls.append('check')):
    d.prepare(None,helper);d.check(None,helper,health=lambda:calls.append('health'))
   self.assertEqual(calls,['prepare','check','health'])
 def test_wrapper_and_builder_real_call_sites(self):
  import ast
  tree=ast.parse((MP/'pro_signer_server.py').read_text());fn=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='build_application')
  nodes=ast.walk(fn)
  self.assertTrue(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='from_runtime' for n in nodes))
  self.assertNotIn("'NODE-SHA.json'",ast.get_source_segment((MP/'pro_signer_server.py').read_text(),fn))
  self.assertIn("pro_files['portable_node.py'] = pro_files['pro-runtime/portable_node.py']",(PP.parent/'build_participant.py').read_text())

class PackageMechanicsTests(unittest.TestCase):
 def test_builder_packages_identical_module_and_checksums(self):
  import zipfile
  s=importlib.util.spec_from_file_location('builder',PP.parent/'build_participant.py');b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
  b.ROOT=PP.parent
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);runtime=root/'runtime';runtime.mkdir();files={'participant_pro_native.py':b'# fixture entry','portable_node.py':(MP/'portable_node.py').read_bytes()}
   for name,raw in files.items():(runtime/name).write_bytes(raw)
   (runtime/'PRO-RUNTIME.json').write_text(json.dumps({'schema':'crowd-participant-pro-runtime-v1','files':{k:hashlib.sha256(v).hexdigest() for k,v in files.items()}}))
   extension=root/'extension.zip';extension.write_bytes(b'fixture extension');helper=root/'helper';helper.write_bytes(b'fixture helper')
   with patch.object(b,'extension_files',return_value=('4.2.101',{'manifest.json':b'{"key":"YWJj"}'})),patch.object(b.subprocess,'check_output',return_value='arm64 x86_64'),patch.object(b.subprocess,'run'):
    result=b.build(extension,helper,root/'out.zip',runtime)
   with zipfile.ZipFile(root/'out.zip') as z:
    top=z.read('.crowd-support/portable_node.py');nested=z.read('.crowd-support/pro-runtime/portable_node.py')
    self.assertEqual(top,nested);self.assertEqual(top,files['portable_node.py'])
    checks=z.read('.crowd-support/INSTALL-SHA256.txt').decode()
    self.assertIn(hashlib.sha256(top).hexdigest()+'  portable_node.py',checks)
    self.assertIn(hashlib.sha256(top).hexdigest()+'  pro-runtime/portable_node.py',checks)

class ClosureTests(unittest.TestCase):
 setUp=Tests.setUp
 tearDown=Tests.tearDown
 def test_owner_uses_fixed_per_user_resource(self):
  home=self.root/'home';helper=home/'Library/Application Support/CrowdV4Updater';helper.mkdir(parents=True);helper.chmod(0o700)
  node=N.prepare(helper,arch='arm64',fetch=lambda u:self.raw)
  runtime=self.root/'repo/server/crowd/v4/multiplatform';runtime.mkdir(parents=True)
  with patch.object(N.Path,'home',return_value=home):self.assertEqual(N.from_runtime(runtime,arch='arm64'),node)
 def test_managed_wrapper_pin_closure(self):
  import ast
  tree=ast.parse((MP/'managed_pro_signer.py').read_text())
  actual=next(n.value.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SERVER_SHA' for t in n.targets))
  self.assertEqual(actual,hashlib.sha256((MP/'pro_signer_server.py').read_bytes()).hexdigest())

class PackageLayout(unittest.TestCase):
 setUp=Tests.setUp
 tearDown=Tests.tearDown
 def test_installer_preconfigure_wrapper_layout(self):
  home=self.root/'home';helper=home/'Library/Application Support/CrowdV4Updater';helper.mkdir(parents=True);helper.chmod(0o700)
  node=N.prepare(helper,arch='arm64',fetch=lambda u:self.raw)
  runtime=self.root/'installer/.crowd-support/pro-runtime';runtime.mkdir(parents=True)
  with patch.object(N.Path,'home',return_value=home):self.assertEqual(N.from_runtime(runtime,arch='arm64'),node)

if __name__=='__main__':unittest.main()
