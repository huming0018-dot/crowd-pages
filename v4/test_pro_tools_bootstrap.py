"""Cold-Mac shell tests; no downloads or platform calls."""
from pathlib import Path
import json
import os
import platform
import subprocess
import tempfile
import unittest
ENTRY=Path(__file__).parent/'participant/bootstrap-pro-tools.command'
class BootstrapTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='cold Mac 工具 ');self.addCleanup(self.tmp.cleanup)
  self.home=Path(self.tmp.name).resolve();self.helper=self.home/'Library/Application Support/助手'
 def run_entry(self,*args):
  return subprocess.run(['/bin/sh',str(ENTRY),*args],env={'HOME':str(self.home),'PATH':'/usr/bin:/bin:/usr/sbin:/sbin'},capture_output=True,text=True,timeout=15)
 def test_help_without_tools_or_home_mutation(self):
  r=self.run_entry('--help');self.assertEqual(r.returncode,0,r.stderr);self.assertIn('--python-path',r.stdout);self.assertEqual(list(self.home.iterdir()),[])
 def test_external_hash_is_not_an_input(self):
  r=self.run_entry('--external-hash','a'*64);self.assertNotEqual(r.returncode,0);self.assertEqual(r.stdout,'');self.assertFalse(self.helper.exists())
 def test_check_missing_is_read_only(self):
  r=self.run_entry('--helper-root',str(self.helper),'--check','--python-path');self.assertNotEqual(r.returncode,0);self.assertIn('bootstrap_tools_missing',r.stderr);self.assertEqual(r.stdout,'');self.assertFalse(self.helper.exists())
 def test_relative_or_multiline_helper_rejected(self):
  for v in ('relative',str(self.helper)+'\nother',str(self.helper)+'\rother'):
   r=self.run_entry('--helper-root',v,'--check');self.assertNotEqual(r.returncode,0);self.assertIn('bootstrap_helper_invalid',r.stderr);self.assertEqual(r.stdout,'')
 def test_symlink_helper_rejected(self):
  target=self.home/'other';target.mkdir(mode=0o700);link=self.home/'link';link.symlink_to(target)
  r=self.run_entry('--helper-root',str(link),'--check');self.assertNotEqual(r.returncode,0);self.assertIn('bootstrap_helper_invalid',r.stderr);self.assertEqual(list(target.iterdir()),[])
 def test_public_helper_is_not_repaired(self):
  self.helper.mkdir(parents=True);self.helper.chmod(0o755)
  r=self.run_entry('--helper-root',str(self.helper),'--check');self.assertNotEqual(r.returncode,0);self.assertIn('bootstrap_helper_invalid',r.stderr);self.assertEqual(self.helper.stat().st_mode&0o777,0o755);self.assertEqual(list(self.helper.iterdir()),[])
 def test_unknown_intent_retained_without_retry(self):
  boot=self.helper/'bootstrap-tools';boot.mkdir(parents=True,mode=0o700);self.helper.chmod(0o700)
  intent=boot/'INTENT.json';intent.write_text('{"original":true}');intent.chmod(0o600)
  r=self.run_entry('--helper-root',str(self.helper),'--python-path');self.assertNotEqual(r.returncode,0);self.assertIn('bootstrap_attempt_unknown',r.stderr);self.assertEqual(r.stdout,'');self.assertEqual(intent.read_text(),'{"original":true}');self.assertEqual([p.name for p in boot.iterdir()],['INTENT.json'])
 def test_unknown_existing_boot_directory_is_never_adopted(self):
  boot=self.helper/'bootstrap-tools';boot.mkdir(parents=True,mode=0o700);self.helper.chmod(0o700)
  target=self.home/'retain';target.write_text('original')
  target_name='aarch64' if platform.machine()=='arm64' else 'x86_64'
  (boot/('uv-0.12.7-'+target_name+'-apple-darwin')).symlink_to(target)
  before=sorted(p.name for p in boot.iterdir())
  r=self.run_entry('--helper-root',str(self.helper),'--bootstrap-cache','/nonexistent-public-cache','--python-path');self.assertNotEqual(r.returncode,0);self.assertIn('bootstrap_attempt_unknown',r.stderr);self.assertEqual(r.stdout,'');self.assertEqual(target.read_text(),'original');self.assertEqual(sorted(p.name for p in boot.iterdir()),before)
 def test_record_without_fixed_archives_cannot_be_trusted(self):
  boot=self.helper/'bootstrap-tools';boot.mkdir(parents=True,mode=0o700);self.helper.chmod(0o700)
  record=boot/'TOOLS.json';record.write_text('{"schema":"crowd-pro-bootstrap-tools-v1"}');record.chmod(0o600)
  r=self.run_entry('--helper-root',str(self.helper),'--check','--python-path');self.assertNotEqual(r.returncode,0);self.assertEqual(r.stdout,'');self.assertFalse((boot/'archives').exists())
 def test_caller_record_and_changed_archive_cannot_execute_a_tool(self):
  boot=self.helper/'bootstrap-tools';archives=boot/'archives';archives.mkdir(parents=True,mode=0o700);self.helper.chmod(0o700);boot.chmod(0o700)
  (boot/'TOOLS.json').write_text('{"schema":"crowd-pro-bootstrap-tools-v1"}');(boot/'TOOLS.json').chmod(0o600)
  target='aarch64' if platform.machine()=='arm64' else 'x86_64'
  archive=archives/('uv-'+target+'-apple-darwin.tar.gz');archive.write_bytes(b'not the official release');archive.chmod(0o600)
  r=self.run_entry('--helper-root',str(self.helper),'--check','--python-path');self.assertNotEqual(r.returncode,0);self.assertIn('bootstrap_archive_changed',r.stderr);self.assertEqual(r.stdout,'');self.assertFalse((boot/'.verify').exists())
 def test_known_download_failure_reuses_only_verified_archives(self):
  boot=self.helper/'bootstrap-tools';archives=boot/'archives/20260825';archives.mkdir(parents=True,mode=0o700);self.helper.chmod(0o700);boot.chmod(0o700);archives.parent.chmod(0o700)
  (boot/'INTENT.json').write_text('{"original":true}');(boot/'INTENT.json').chmod(0o600)
  (boot/'DOWNLOAD-FAILED.json').write_text('{"state":"public_download_failed"}\n');(boot/'DOWNLOAD-FAILED.json').chmod(0o600)
  target='aarch64' if platform.machine()=='arm64' else 'x86_64';archive=boot/'archives'/('uv-'+target+'-apple-darwin.tar.gz');archive.write_bytes(b'corrupt cached archive');archive.chmod(0o600)
  r=self.run_entry('--helper-root',str(self.helper),'--python-path');self.assertNotEqual(r.returncode,0);self.assertIn('bootstrap_archive_changed',r.stderr);self.assertNotIn('bootstrap_attempt_unknown',r.stderr);self.assertEqual((boot/'INTENT.json').read_text(),'{"original":true}');self.assertEqual(r.stdout,'')

if os.environ.get('CROWD_BOOTSTRAP_VERIFIED_FIXTURE'):
 class InstalledBootstrapTests(unittest.TestCase):
  def setUp(self):
   self.helper=Path(os.environ['CROWD_BOOTSTRAP_VERIFIED_FIXTURE']).resolve();self.boot=self.helper/'bootstrap-tools'
   self.value=json.loads((self.boot/'TOOLS.json').read_bytes());self.sign=Path(self.value['signer_python']['path'])
  def check(self):
   return subprocess.run(['/bin/sh',str(ENTRY),'--helper-root',str(self.helper),'--check','--python-path'],env={'HOME':str(self.helper.parents[2]),'PATH':'/usr/bin:/bin:/usr/sbin:/sbin'},capture_output=True,text=True,timeout=60)
  def test_reuse_is_local_and_preserves_receipts(self):
   files=[self.boot/'TOOLS.json',self.boot/'PROOF.json',*self.boot.glob('archives/**/*.gz')];before=[(p.read_bytes(),p.stat().st_mtime_ns) for p in files]
   r=self.check();self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(r.stdout,str(self.sign)+'\n');self.assertEqual(before,[(p.read_bytes(),p.stat().st_mtime_ns) for p in files])
  def test_stdlib_byte_change_is_rejected(self):
   p=self.sign.parent.parent/'lib/python3.12/abc.py';raw=p.read_bytes()
   try:p.write_bytes(raw+b'\n# changed\n');r=self.check();self.assertNotEqual(r.returncode,0);self.assertEqual(r.stdout,'')
   finally:p.write_bytes(raw)
  def test_added_file_is_rejected(self):
   p=self.sign.parent.parent/'lib/python3.12/unexpected.py'
   try:p.write_text('raise RuntimeError("must not run")');r=self.check();self.assertNotEqual(r.returncode,0);self.assertEqual(r.stdout,'')
   finally:p.unlink()
  def test_symlink_change_is_rejected(self):
   p=self.sign.parent/'python';target=os.readlink(p)
   try:p.unlink();p.symlink_to('python3.12' if target!='python3.12' else 'python3');r=self.check();self.assertNotEqual(r.returncode,0);self.assertEqual(r.stdout,'')
   finally:p.unlink();p.symlink_to(target)
  def test_forged_record_is_rejected(self):
   p=self.boot/'TOOLS.json';raw=p.read_bytes()
   try:v=json.loads(raw);v['uv']['sha256']='a'*64;p.write_text(json.dumps(v));r=self.check();self.assertNotEqual(r.returncode,0);self.assertEqual(r.stdout,'')
   finally:p.write_bytes(raw)
  def test_partial_receipt_never_resumes(self):
   p=self.boot/'TOOLS.json';saved=self.boot/'TOOLS.saved';p.rename(saved)
   try:r=self.check();self.assertNotEqual(r.returncode,0);self.assertIn('bootstrap_attempt_unknown',r.stderr);self.assertEqual(r.stdout,'')
   finally:saved.rename(p)
  def test_python_root_permissions_are_verified(self):
   p=self.sign.parent.parent;mode=p.stat().st_mode&0o777
   try:p.chmod(0o777);r=self.check();self.assertNotEqual(r.returncode,0);self.assertEqual(r.stdout,'')
   finally:p.chmod(mode)
if __name__=='__main__':unittest.main()
