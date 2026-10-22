#!/usr/bin/env python3
"""Offline own-code packaging, never reads SDK/account/root data or downloads dependencies."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
ASSETS={'SIGN-SOURCE-SHA.json','DEPENDENCIES.json','DEPENDENCY-SHA.json','NODE-SHA.json'}
RESOURCES={'pro_xhs_download.mjs'}
EXCLUDED={'probe_pro_ks_sdk.py'}  # Explicit offline SDK test, not an installed runtime entry.
NATIVE={'participant_native_rpc.py','participant_pro_native.py'}
def assemble(source,output,pins):
 source=Path(source).resolve();output=Path(output)
 raw=subprocess.check_output(['git','-C',str(source),'ls-files','--full-name','--',str(source)],text=True)
 names={Path(n).name for n in raw.splitlines() if Path(n).parent.name=='multiplatform' and Path(n).name not in EXCLUDED and ((n.endswith('.py') and not Path(n).name.startswith('test_')) or Path(n).name in ASSETS|RESOURCES)}|NATIVE
 if not {'mc_runner.py','participant_pro.py','participant_pro_hooks.py'}<=names or not ASSETS<=names or not 1<=len(names)<=128:raise ValueError('own_runtime_manifest_invalid')
 expected=json.loads(Path(pins).read_bytes())
 if type(expected) is not dict or not NATIVE|{'mc_runner.py','participant_pro.py','participant_pro_hooks.py'} <= set(expected):raise ValueError('final_source_pins_required')
 files={}
 for name in sorted(names):
  if not ((re.fullmatch('[a-z][a-z0-9_]*[.]py',name) and not name.startswith('test_')) or name in ASSETS|RESOURCES):raise ValueError('own_runtime_manifest_invalid')
  if name in RESOURCES and name not in expected:raise ValueError('own_runtime_resource_pin_required')
  f=source/name
  if f.is_symlink() or not f.is_file():raise ValueError('own_runtime_source_invalid')
  b=f.read_bytes();h=hashlib.sha256(b).hexdigest()
  if name in expected and h!=expected[name]:raise ValueError('final_source_pin_changed')
  files[name]=(b,h)
 if not set(expected)<=set(files):raise ValueError('final_source_pin_missing')
 output.mkdir(mode=0o700,parents=False,exist_ok=False)
 for name,(b,h) in files.items():(output/name).write_bytes(b);(output/name).chmod(0o600)
 manifest={'schema':'crowd-participant-pro-runtime-v1','files':{name:h for name,(b,h) in files.items()}}
 (output/'PRO-RUNTIME.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n');(output/'PRO-RUNTIME.json').chmod(0o600)
 return {'state':'prepared','files':len(files),'manifest_sha256':hashlib.sha256((output/'PRO-RUNTIME.json').read_bytes()).hexdigest()}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--pins',type=Path,required=True);a=p.parse_args();print(json.dumps(assemble(a.source,a.output,a.pins)))
