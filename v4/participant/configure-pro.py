#!/usr/bin/env python3
"""Local installer: own adapter only; licensed SDK and binding are never downloaded/copied.
A local installation operator supplies settings, never a browser/native message.
"""
import argparse,fcntl,hashlib,json,os,re,shutil,stat,sys,tempfile,uuid
from pathlib import Path
FIELDS={'python','root','mc_root','session_id','max_api_requests','purpose'}
def need(ok):
 if not ok:raise ValueError('pro_not_ready')
def private(p):
 p=Path(p);s=p.lstat();need(stat.S_ISREG(s.st_mode) and s.st_uid==os.getuid() and stat.S_IMODE(s.st_mode)==0o600 and not p.is_symlink());return p

def configure(runtime,settings,helper):
 runtime=Path(runtime).resolve();helper=Path(helper)
 need(helper.is_absolute() and helper.resolve()==helper and helper.is_dir() and helper.stat().st_uid==os.getuid())
 values=json.loads(private(settings).read_bytes());need(set(values)==FIELDS)
 need(values['purpose']=='noncommercial_research' and type(values['max_api_requests']) is int and 1<=values['max_api_requests']<=100)
 need(str(uuid.UUID(values['session_id']))==values['session_id'])
 for k in ('python','root','mc_root'):
  p=Path(values[k]);need(p.is_absolute() and p.exists())
 need(os.access(values['python'],os.X_OK))
 # Presence is not an authentication claim. Python hello performs original binding/readiness checks.
 need((Path(values['mc_root'])/'media_platform/xhs').is_dir())
 manifest=json.loads((runtime/'PRO-RUNTIME.json').read_bytes());need(manifest.get('schema')=='crowd-participant-pro-runtime-v1' and set(manifest)=={'schema','files'})
 files=manifest['files'];need(type(files) is dict and 'participant_pro_native.py' in files and len(files)<=128)
 for name,h in files.items():
  need(type(name) is str and '/' not in name and ((name.endswith('.py') and not name.startswith('test_')) or name in {'SIGN-SOURCE-SHA.json','DEPENDENCIES.json','DEPENDENCY-SHA.json','NODE-SHA.json'}))
  p=runtime/name;need(not p.is_symlink() and p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==h)
 fingerprint=hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 lock=os.open(helper/'update.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
 try:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  prolock=os.open(helper/'pro.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
  try:
   fcntl.flock(prolock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   old=helper/'pro-state.json'
   if old.exists():need(json.loads(private(old).read_bytes()).get('busy') is False)
   # Bootstrap may update only own-code entry/hash; original six bindings are immutable.
   destination=helper/'pro-config.json';previous=None;existing=None
   if destination.exists():
    previous=private(destination).read_bytes();existing=json.loads(previous)
    need(type(existing) is dict and set(existing)==FIELDS|{'schema','entry','entry_sha256'} and existing['schema']=='crowd-participant-pro-install-v1')
    need(all(type(existing[k]) is type(values[k]) and existing[k]==values[k] for k in FIELDS))
    oldentry=Path(existing['entry']);need(oldentry.is_absolute() and oldentry.resolve()==oldentry and oldentry.is_file() and oldentry.stat().st_uid==os.getuid())
    need(type(existing['entry_sha256']) is str and re.fullmatch('[a-f0-9]{64}',existing['entry_sha256']) and hashlib.sha256(oldentry.read_bytes()).hexdigest()==existing['entry_sha256'])
   base=helper/'pro-runtime';base.mkdir(mode=0o700,exist_ok=True);need(base.resolve()==base and base.stat().st_uid==os.getuid())
   target=base/fingerprint
   if not target.exists():
    stage=Path(tempfile.mkdtemp(prefix='.stage-',dir=base))
    try:
     for name in files:(stage/name).write_bytes((runtime/name).read_bytes());(stage/name).chmod(0o600)
     (stage/'PRO-RUNTIME.json').write_bytes((runtime/'PRO-RUNTIME.json').read_bytes());(stage/'PRO-RUNTIME.json').chmod(0o600)
     os.rename(stage,target)
    finally:
     if stage.exists():shutil.rmtree(stage)
   need(target.resolve()==target and target.is_dir() and target.stat().st_uid==os.getuid())
   for name,h in files.items():need(not (target/name).is_symlink() and hashlib.sha256((target/name).read_bytes()).hexdigest()==h)
   entry=target/'participant_pro_native.py'
   config={'schema':'crowd-participant-pro-install-v1',**values,'entry':str(entry),'entry_sha256':files[entry.name]}
   encoded=json.dumps(config,sort_keys=True).encode()
   if existing is not None:
    if existing==config:return {'state':'current','configured':True}
    backup=helper/('pro-config.before-'+hashlib.sha256(previous).hexdigest()+'.json')
    if backup.exists():need(private(backup).read_bytes()==previous)
    else:
     fd=os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
     with os.fdopen(fd,'wb') as f:f.write(previous);f.flush();os.fsync(f.fileno())
    fd,temporary=tempfile.mkstemp(prefix='.pro-config-',dir=helper)
    try:
     with os.fdopen(fd,'wb') as f:f.write(encoded);f.flush();os.fsync(f.fileno())
     need(private(destination).read_bytes()==previous)
     os.replace(temporary,destination)
    finally:
     if os.path.exists(temporary):os.unlink(temporary)
    result='upgraded'
   else:
    fd=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as f:f.write(encoded);f.flush();os.fsync(f.fileno())
    result='configured'
   fd=os.open(helper,os.O_RDONLY)
   try:os.fsync(fd)
   finally:os.close(fd)
   return {'state':result,'configured':True}
  finally:os.close(prolock)
 finally:os.close(lock)

def main():
 p=argparse.ArgumentParser();p.add_argument('--runtime',type=Path,required=True);p.add_argument('--settings',type=Path,required=True);p.add_argument('--helper-root',type=Path,default=Path.home()/'Library/Application Support/CrowdV4Updater');a=p.parse_args()
 try:print(json.dumps(configure(a.runtime,a.settings,a.helper_root)))
 except Exception:print(json.dumps({'state':'not_ready','error':'pro_not_ready'}));return 1
 return 0
if __name__=='__main__':sys.exit(main())
