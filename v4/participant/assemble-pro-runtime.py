#!/usr/bin/env python3
"""Offline own-code packaging, never reads SDK/account/root data or downloads dependencies."""
import argparse,ast,hashlib,json,re,subprocess,zipfile
from pathlib import Path
ASSETS={'SIGN-SOURCE-SHA.json','DEPENDENCIES.json','DEPENDENCY-SHA.json','NODE-SHA.json','PRO-LOCAL-SOURCE-PINS.json'}
RESOURCES={'pro_xhs_download.mjs'}
EXCLUDED={'probe_pro_ks_sdk.py'}  # Explicit offline SDK test, not an installed runtime entry.
NATIVE={'participant_native_rpc.py','participant_pro_native.py','pro_source_artifact.py'}
BASELINE_SHA256='c381679fa39e4b93011235894bb87427da672985363533d963275deb768be9ae'
BASELINE_MANIFEST_SHA256='597b61fe8b1a86d9514175f9ba6fa508f69cb6ee4442bda9855f45b7bf50f81c'

def source_info_bytes(raw):
 lines=raw.splitlines(keepends=True);tree=ast.parse(raw)
 matches=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='source_info']
 if len(matches)!=1 or matches[0].decorator_list:raise ValueError('source_info_invalid')
 node=matches[0];return b''.join(lines[node.lineno-1:node.end_lineno]),lines,node

def write_runtime(output,files,provenance=None):
 output=Path(output);output.mkdir(mode=0o700,parents=False,exist_ok=False)
 for name,(b,h) in files.items():(output/name).write_bytes(b);(output/name).chmod(0o600)
 manifest={'schema':'crowd-participant-pro-runtime-v1','files':{name:h for name,(b,h)in files.items()}}
 (output/'PRO-RUNTIME.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n');(output/'PRO-RUNTIME.json').chmod(0o600)
 return {'state':'prepared','files':len(files),'manifest_sha256':hashlib.sha256((output/'PRO-RUNTIME.json').read_bytes()).hexdigest(),**({'provenance':provenance}if provenance else{})}

def baseline_runtime(source,output,pins,baseline,source_info_sha256):
 baseline=Path(baseline);source=Path(source)
 if baseline.is_symlink()or hashlib.sha256(baseline.read_bytes()).hexdigest()!=BASELINE_SHA256:raise ValueError('baseline_package_changed')
 files={}
 with zipfile.ZipFile(baseline)as archive:
  names=archive.namelist();manifests=[n for n in names if n.endswith('/PRO-RUNTIME.json')]
  if len(names)!=len(set(names))or len(manifests)!=1:raise ValueError('baseline_package_changed')
  raw=archive.read(manifests[0])
  if hashlib.sha256(raw).hexdigest()!=BASELINE_MANIFEST_SHA256:raise ValueError('baseline_package_changed')
  metadata=json.loads(raw)
  if set(metadata)!={'schema','files'}or metadata['schema']!='crowd-participant-pro-runtime-v1'or len(metadata['files'])!=126:raise ValueError('baseline_package_changed')
  prefix=Path(manifests[0]).parent
  for name,pin in metadata['files'].items():
   if Path(name).name!=name:raise ValueError('baseline_package_changed')
   item=archive.getinfo(str(prefix/name))
   if item.file_size>16*1024*1024:raise ValueError('baseline_package_changed')
   blob=archive.read(item)
   if hashlib.sha256(blob).hexdigest()!=pin:raise ValueError('baseline_package_changed')
   files[name]=blob
 path=source/'mc_runner.py'
 if path.is_symlink()or not path.is_file():raise ValueError('own_runtime_source_invalid')
 replacement,_,_=source_info_bytes(path.read_bytes())
 if hashlib.sha256(replacement).hexdigest()!=source_info_sha256:raise ValueError('source_info_pin_changed')
 old=files['mc_runner.py'];prior,lines,node=source_info_bytes(old)
 files['mc_runner.py']=b''.join(lines[:node.lineno-1])+replacement+b''.join(lines[node.end_lineno:])
 ast.parse(files['mc_runner.py'])
 additions={}
 for name in ('pro_source_artifact.py','PRO-LOCAL-SOURCE-PINS.json'):
  path=source/name
  if path.is_symlink()or not path.is_file():raise ValueError('own_runtime_source_invalid')
  files[name]=path.read_bytes();additions[name]=hashlib.sha256(files[name]).hexdigest()
 expected=json.loads(Path(pins).read_bytes())
 if type(expected)is not dict or set(expected)!=set(files)or len(files)!=128:raise ValueError('complete_runtime_pin_required')
 if any(hashlib.sha256(blob).hexdigest()!=expected[name]for name,blob in files.items()):raise ValueError('final_source_pin_changed')
 provenance={'source_selection':'frozen_native126_source_info_only','baseline_package_sha256':BASELINE_SHA256,
  'baseline_manifest_sha256':BASELINE_MANIFEST_SHA256,'baseline_preserved_files':125,
  'baseline_mc_runner_sha256':hashlib.sha256(old).hexdigest(),'baseline_source_info_sha256':hashlib.sha256(prior).hexdigest(),
  'source_info_sha256':source_info_sha256,'mc_runner_sha256':expected['mc_runner.py'],'additions':additions}
 return write_runtime(output,{name:(blob,expected[name])for name,blob in sorted(files.items())},provenance)

def assemble(source,output,pins,*,baseline=None,source_info_sha256=None):
 source=Path(source).resolve();output=Path(output)
 if baseline is not None:return baseline_runtime(source,output,pins,baseline,source_info_sha256)
 if source_info_sha256 is not None:raise ValueError('baseline_required')
 raw=subprocess.check_output(['git','-C',str(source),'ls-files','--full-name','--',str(source)],text=True)
 names={Path(n).name for n in raw.splitlines() if Path(n).parent.name=='multiplatform' and Path(n).name not in EXCLUDED and ((n.endswith('.py') and not Path(n).name.startswith('test_')) or Path(n).name in ASSETS|RESOURCES)}|NATIVE
 if not {'mc_runner.py','participant_pro.py','participant_pro_hooks.py'}<=names or not ASSETS<=names or not 1<=len(names)<=128:raise ValueError('own_runtime_manifest_invalid')
 expected=json.loads(Path(pins).read_bytes())
 if type(expected) is not dict or not NATIVE|{'mc_runner.py','participant_pro.py','participant_pro_hooks.py'} <= set(expected):raise ValueError('final_source_pins_required')
 files={}
 for name in sorted(names):
  if not ((re.fullmatch('[a-z][a-z0-9_]*[.]py',name) and not name.startswith('test_')) or name in ASSETS|RESOURCES):raise ValueError('own_runtime_manifest_invalid')
  if (name in RESOURCES or name=='PRO-LOCAL-SOURCE-PINS.json') and name not in expected:raise ValueError('own_runtime_resource_pin_required')
  f=source/name
  if f.is_symlink() or not f.is_file():raise ValueError('own_runtime_source_invalid')
  b=f.read_bytes();h=hashlib.sha256(b).hexdigest()
  if name in expected and h!=expected[name]:raise ValueError('final_source_pin_changed')
  files[name]=(b,h)
 if not set(expected)<=set(files):raise ValueError('final_source_pin_missing')
 return write_runtime(output,files)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--pins',type=Path,required=True);p.add_argument('--baseline',type=Path);p.add_argument('--source-info-sha256');a=p.parse_args();print(json.dumps(assemble(a.source,a.output,a.pins,baseline=a.baseline,source_info_sha256=a.source_info_sha256)))
