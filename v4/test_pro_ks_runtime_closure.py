"""Only own modules in temp Git; no SDK/source/install. python -B -m unittest test_pro_ks_runtime_closure"""
import hashlib,importlib.util,json,subprocess,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('ks_runtime_assembler',HERE/'participant/assemble-pro-runtime.py');A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)
class Closure(unittest.TestCase):
 def source(self,root,ks=True,tracked=True):
  repo=root/'repo';source=repo/'multiplatform';source.mkdir(parents=True);names=A.NATIVE|A.ASSETS|A.RESOURCES|{'mc_runner.py','participant_pro.py','participant_pro_hooks.py','pro_executor.py','portable_node.py'}
  if ks:names|={'pro_ks_entry.py','pro_ks_adapter.py'}
  for n in names:(source/n).write_bytes(b'VALUE=1\n'if n.endswith('.py')else b'{}')
  (source/'probe_pro_ks_sdk.py').write_text("raise RuntimeError('explicit offline test only; never runtime')\n")
  subprocess.run(['git','init','-q',str(repo)],check=True);subprocess.run(['git','-C',str(repo),'add','.'],check=True)
  if ks and not tracked:subprocess.run(['git','-C',str(repo),'rm','--cached','-q','multiplatform/pro_ks_entry.py','multiplatform/pro_ks_adapter.py'],check=True)
  pins={n:hashlib.sha256((source/n).read_bytes()).hexdigest()for n in names};pin=root/'pins.json';pin.write_text(json.dumps(pins));return source,pin,pins
 def test_two_KS_modules_exact_probe_excluded(self):
  with tempfile.TemporaryDirectory()as temp:
   r=Path(temp);s,p,pins=self.source(r);out=r/'runtime';A.assemble(s,out,p);self.assertEqual(json.loads((out/'PRO-RUNTIME.json').read_bytes())['files'],pins);self.assertFalse((out/'probe_pro_ks_sdk.py').exists());self.assertTrue(all((out/n).read_bytes()==(s/n).read_bytes()for n in ('pro_ks_entry.py','pro_ks_adapter.py')))
 def test_untracked_KS_with_explicit_fullpins_refuses_before_output(self):
  with tempfile.TemporaryDirectory()as temp:
   r=Path(temp);s,p,_=self.source(r,tracked=False)
   with self.assertRaisesRegex(ValueError,'final_source_pin_missing'):A.assemble(s,r/'runtime',p)
   self.assertFalse((r/'runtime').exists())
 def test_changed_KS_pin_refuses_before_output(self):
  with tempfile.TemporaryDirectory()as temp:
   r=Path(temp);s,p,_=self.source(r);(s/'pro_ks_adapter.py').write_text('CHANGED=1\n')
   with self.assertRaisesRegex(ValueError,'final_source_pin_changed'):A.assemble(s,r/'runtime',p)
   self.assertFalse((r/'runtime').exists())
 def test_legacy_without_KS_preserves_all_existing_names(self):
  with tempfile.TemporaryDirectory()as temp:
   r=Path(temp);s,p,pins=self.source(r,ks=False);A.assemble(s,r/'runtime',p);self.assertEqual(json.loads((r/'runtime/PRO-RUNTIME.json').read_bytes())['files'],pins)
if __name__=='__main__':unittest.main()
