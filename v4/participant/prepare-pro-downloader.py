"""Local licensed DownloadManager reference + two original public npm resources.
No SDK copy/download, npm/script execution, account operation or daemon.
Only the installer wrapper calls provision with its verified BindingContinuation.
"""
import base64,contextlib,fcntl,hashlib,io,json,os,re,stat,tarfile,tempfile
from pathlib import Path
import portable_node
MANAGER='DownloadUI/src/main/download-manager.ts'
MANAGER_SHA='8fe88ee05ac91fa7e256be921b67e6fcb9396f337fed0a92f8ca12ea45e5c84e'
INVENTORY_SHA='7341217843184a92af65c4a7125094242d5fe52c48f035740e7ab62fb89f85ba'
SOURCE_FILES={MANAGER,'DownloadUI/package-lock.json','LICENSE','README.md'}
PACKAGES={'axios':('0.21.4','sha512-ut5vewkiu8jjGBdqpM44XxjuCjq9LAKeHVmoVfHVzy8eHgxxq8SbAVQNovDA8mVi05kP0Ea/n/UzcSHcTJQfNg=='),'follow-redirects':('1.15.9','sha512-gew4GsXizNgdoRyqmyfMHyAmXsZDk6mHkSxZFCzW9gwlbtOW44CDtYavM+y+72qD/Vq2l550kMF52DT8fOLJqQ==')}
RESOURCE='axios-0.21.4-fr-1.15.9'
PACKAGE={'name':'crowd-private-pro-downloader-deps','private':True,'version':'1.0.0','dependencies':{'axios':'0.21.4','follow-redirects':'1.15.9'}}
def url(name):return 'https://registry.npmjs.org/%s/-/%s-%s.tgz'%(name,name,PACKAGES[name][0])
def encoded(v):return json.dumps(v,sort_keys=True,separators=(',',':')).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def need(ok,code='downloader_dependency_invalid'):
 if not ok:raise ValueError(code)
def safe(path):
 p=Path(path);need(p.is_absolute() and p.resolve()==p and not p.is_symlink(),'downloader_path_invalid');return p

def stable(path,limit=8388608,private=False):
 p=safe(path);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 try:
  a=os.fstat(fd);need(stat.S_ISREG(a.st_mode) and a.st_uid==os.getuid() and not a.st_mode&(0o077 if private else 0o022) and a.st_nlink==1 and a.st_size<=limit,'downloader_file_invalid');raw=b''
  while len(raw)<=limit:
   block=os.read(fd,min(65536,limit+1-len(raw)))
   if not block:break
   raw+=block
  b=os.fstat(fd);need(len(raw)==a.st_size and (a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)==(b.st_ino,b.st_size,b.st_mtime_ns,b.st_ctime_ns),'downloader_file_changed');return raw
 finally:os.close(fd)
def sync(path):
 fd=os.open(path,os.O_RDONLY)
 try:os.fsync(fd)
 finally:os.close(fd)
def once_raw(path,raw):
 fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
 try:
  offset=0
  while offset<len(raw):
   n=os.write(fd,raw[offset:]);need(n>0,'downloader_short_write');offset+=n
  os.fsync(fd)
 finally:os.close(fd)
 sync(Path(path).parent)
def directory(path):
 p=safe(path)
 if not p.exists():p.mkdir(mode=0o700);sync(p.parent)
 need(p.is_dir() and p.stat().st_uid==os.getuid() and not p.stat().st_mode&0o077,'downloader_directory_invalid');return p

@contextlib.contextmanager
def locks(helper,session=None):
 fds=[]
 try:
  for p in [Path(helper)/'update.lock',Path(helper)/'pro.lock']+([Path(session)/'active.lock']if session else[]):
   fd=os.open(p,os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK);fds.append(fd);info=os.fstat(fd);need(stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid() and not info.st_mode&0o077,'downloader_lock_invalid');fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
  state=Path(helper)/'pro-state.json'
  if state.exists():
   host=json.loads(stable(state,65536,True));need(host.get('busy') is False and host.get('state') in {'stopped','complete','partial','source_failed','ready','not_ready'},'downloader_host_busy')
  yield
 finally:
  for fd in reversed(fds):os.close(fd)

def plan(deps,descriptor,helper,run=None):
 value=json.loads(deps.read(descriptor));block=value.get('downloader')
 if block is None:return None
 need(type(block) is dict and set(block)=={'root','commit','files'} and type(block['files']) is dict and set(block['files'])==SOURCE_FILES)
 root=safe(block['root']);need(root.is_dir() and re.fullmatch('[a-f0-9]{40}',block['commit']) is not None)
 run=run or deps.execute;env=deps.environment()
 need(run(['/usr/bin/git','-C',str(root),'rev-parse','HEAD'],env=env,cwd=root,timeout=10).decode().strip()==block['commit'],'downloader_source_changed')
 need(not run(['/usr/bin/git','-C',str(root),'status','--porcelain','--untracked-files=normal'],env=env,cwd=root,timeout=10),'downloader_source_changed')
 for name,expected in block['files'].items():need(re.fullmatch('[a-f0-9]{64}',expected) is not None and sha(stable(root/name))==expected,'downloader_source_changed')
 need(block['files'][MANAGER]==MANAGER_SHA,'downloader_manager_changed')
 lock=json.loads(stable(root/'DownloadUI/package-lock.json'))
 for name,(version,sri)in PACKAGES.items():
  row=lock['packages']['node_modules/'+name];need(row['version']==version and row['integrity']==sri,'downloader_lock_changed')
 helper=safe(helper);need(helper.is_dir() and helper.stat().st_uid==os.getuid() and not helper.stat().st_mode&0o077,'downloader_directory_invalid')
 return {'source':block,'target':str(helper/'pro-downloader-deps'/RESOURCE),'manager':str(root/MANAGER)}

def unpack(name,raw):
 version,sri=PACKAGES[name];need(len(raw)<=8388608 and 'sha512-'+base64.b64encode(hashlib.sha512(raw).digest()).decode()==sri,'downloader_archive_changed');result={};total=0
 with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz')as tar:
  for item in tar:
   parts=Path(item.name).parts
   need(parts and parts[0]=='package' and not any(x in ('..','')for x in parts) and not item.name.startswith('/'),'downloader_archive_path')
   if item.isdir():continue
   need(item.isfile() and len(parts)>1 and not item.issym() and not item.islnk() and 0<=item.size<=8388608,'downloader_archive_path')
   namepath='node_modules/'+name+'/'+'/'.join(parts[1:]);need(namepath not in result and len(result)<200,'downloader_archive_path');total+=item.size;need(total<=8388608,'downloader_archive_size')
   data=tar.extractfile(item).read(8388609);need(len(data)==item.size,'downloader_archive_size');result[namepath]=data
 return result

def resources(raws):
 result={}
 for name in PACKAGES:result.update(unpack(name,raws[name]))
 lock={'lockfileVersion':3,'requires':True,'packages':{}}
 for name,(version,sri)in PACKAGES.items():
  row={'version':version,'resolved':url(name),'integrity':sri}
  if name=='axios':row.update(license='MIT',dependencies={'follow-redirects':'^1.14.0'})
  else:row.update(funding=[{'type':'individual','url':'https://github.com/sponsors/RubenVerborgh'}],license='MIT',engines={'node':'>=4.0'},peerDependenciesMeta={'debug':{'optional':True}})
  lock['packages']['node_modules/'+name]=row
 result['package.json']=json.dumps(PACKAGE).encode();result['node_modules/.package-lock.json']=(json.dumps(lock,indent=2)+'\n').encode()
 need(sha(encoded({n:sha(raw)for n,raw in result.items()}))==INVENTORY_SHA,'downloader_inventory_changed');return result

def inventory(target):
 target=safe(target);need(target.is_dir(),'downloader_resource_missing');directory(target);files={}
 for p in target.rglob('*'):
  safe(p);need(p.stat().st_uid==os.getuid() and not p.stat().st_mode&0o022,'downloader_file_invalid')
  if p.is_file():files[str(p.relative_to(target))]=sha(stable(p))
  else:need(p.is_dir(),'downloader_file_invalid')
 need(sha(encoded(files))==INVENTORY_SHA,'downloader_inventory_changed');return files

def prepare(deps,descriptor,helper,*,fetch=portable_node.fetch,run=None):
 p=plan(deps,descriptor,helper,run)
 if p is None:return {'state':'not_requested'}
 helper=safe(helper);target=Path(p['target']);attempt=helper/'pro-downloader-attempts'/RESOURCE
 with locks(helper):
  if attempt.exists() and not (attempt/'RESULT.json').exists():raise ValueError('downloader_attempt_unknown')
  if target.exists():inventory(target);return {'state':'verified','target':str(target),'installed':False}
  directory(helper/'pro-downloader-deps');directory(helper/'pro-downloader-attempts');directory(attempt)
  once_raw(attempt/'INTENT.json',encoded({'resource':RESOURCE,'inventory_sha256':INVENTORY_SHA,'retry_unknown_forbidden':True}))
  raw=resources({name:fetch(url(name))for name in PACKAGES});need(plan(deps,descriptor,helper,run)==p,'downloader_source_changed');directory(target)
  for name,data in raw.items():
   path=target/name
   for parent in reversed(path.relative_to(target).parents):
    if str(parent)!='.':directory(target/parent)
   once_raw(path,data)
  inventory(target);need(plan(deps,descriptor,helper,run)==p,'downloader_source_changed')
  once_raw(attempt/'RESULT.json',encoded({'state':'prepared','inventory_sha256':INVENTORY_SHA}));return {'state':'prepared','target':str(target),'installed':True}

def binding(deps,descriptor,helper,run=None):
 p=plan(deps,descriptor,helper,run);need(p is not None,'downloader_descriptor_required');files=inventory(Path(p['target']))
 return {'schema':'crowd-pro-xhs-download-manager-v1','manager_path':p['manager'],'manager_sha256':MANAGER_SHA,'axios_root':p['target'],'axios_files':files}

def _publish(deps,descriptor,helper,root,session,scope,idle):
 desired=encoded(binding(deps,descriptor,helper));destination=root/'pro-xhs-media.json';evidence=Path(helper)/'pro-downloader-bindings'/sha(str(root).encode())
 with locks(helper,session):
  idle();protected=scope()
  if evidence.exists() and not (evidence/'RESULT.json').exists():raise ValueError('downloader_binding_unknown')
  if destination.exists():need(deps.read(destination)==desired,'downloader_binding_conflict');return {'state':'verified','changed':False}
  directory(Path(helper)/'pro-downloader-bindings');directory(evidence)
  once_raw(evidence/'INTENT.json',encoded({'root_sha256':sha(str(root).encode()),'before':None,'after_sha256':sha(desired),'source_scope':protected,'retry_unknown_forbidden':True}))
  need(scope()==protected,'downloader_collector_changed');need(encoded(binding(deps,descriptor,helper))==desired,'downloader_source_changed')
  fd,temp=tempfile.mkstemp(prefix='.pro-xhs-media-',dir=root)
  try:
   with os.fdopen(fd,'wb')as f:need(f.write(desired)==len(desired),'downloader_short_write');f.flush();os.fsync(f.fileno())
   os.link(temp,destination);sync(root)
  finally:os.unlink(temp)
  need(deps.read(destination)==desired and scope()==protected,'downloader_collector_changed')
  once_raw(evidence/'RESULT.json',encoded({'state':'configured','config_sha256':sha(desired),'source_started':False}));return {'state':'configured','changed':True}

def provision(deps,descriptor,helper,continuation):
 # Native root comes ONLY from the existing verified six-setting continuation.
 settings=Path(continuation.settings);before=deps.read(settings);values=json.loads(before);root=safe(values['root']);need(root==continuation.root and before==continuation.original_raw,'downloader_collector_changed')
 need(set(values)=={'python','root','mc_root','session_id','max_api_requests','purpose'},'downloader_collector_changed')
 ex_before=deps.read(root/'pro-executor.json');ex=json.loads(ex_before);need(set(ex)=={'root','python'} and ex['root']==continuation.plan['input']['projects']['pro']['root'],'downloader_collector_changed')
 config=Path(helper)/'pro-config.json';cfg_before=deps.read(config)if config.exists()else None
 if cfg_before is not None:need(json.loads(cfg_before).get('root')==str(root) and json.loads(cfg_before).get('session_id')==values['session_id'],'downloader_collector_changed')
 def scope():
  need(deps.read(settings)==before and deps.read(root/'pro-executor.json')==ex_before and (deps.read(config)if config.exists()else None)==cfg_before,'downloader_collector_changed')
  return {**continuation.scope(),str(settings):sha(before),str(root/'pro-executor.json'):sha(ex_before),str(config):sha(cfg_before)if cfg_before else None}
 return _publish(deps,descriptor,helper,root,continuation.session,scope,continuation.idle)

def owner_context(deps,descriptor,helper,owner_root,runtime,continuation_type,*,session_id=None):
 # Local operator only: same existing registry/preferred-session selection as dashboard.
 import sys,uuid
 from types import SimpleNamespace
 owner=safe(owner_root);config=owner/'dashboard-config.json';raw=deps.read(config);value=json.loads(raw)
 registered=value.get('collector_roots',[]);preferred=session_id if session_id is not None else value.get('preferred_session_by_platform',{}).get('xhs')
 need(type(registered) is list and all(type(p)is str for p in registered) and type(preferred)is str,'downloader_owner_registry_invalid')
 try:valid=str(uuid.UUID(preferred))==preferred
 except (ValueError,TypeError,AttributeError):valid=False
 need(valid,'downloader_owner_registry_invalid')
 roots=list(dict.fromkeys([owner/'collector',*[safe(p)for p in registered]]));matches=[r for r in roots if (r/'sessions'/preferred).is_dir()and not (r/'sessions'/preferred).is_symlink()];need(len(matches)==1,'downloader_owner_registry_invalid');root=matches[0];session=root/'sessions'/preferred
 runtime=safe(runtime);manifest=json.loads(stable(runtime/'PRO-RUNTIME.json',1048576));need(set(manifest)=={'schema','files'}and manifest['schema']=='crowd-participant-pro-runtime-v1'and type(manifest['files'])is dict and 1<=len(manifest['files'])<=128,'downloader_runtime_invalid')
 for name,expected in manifest['files'].items():need(type(name)is str and Path(name).name==name and sha(stable(runtime/name))==expected,'downloader_runtime_changed')
 need(all(name in manifest['files']for name in ('pro_executor.py','account_sessions.py','mc_runner.py')),'downloader_runtime_invalid')
 # Run reader in the caller's already-pinned runtime; no Application construction.
 sys.path.insert(0,str(runtime))
 try:
  import pro_executor as pro
  from account_sessions import AccountSessions
  import account_sessions,mc_runner
  need(Path(mc_runner.__file__).resolve()==runtime/'mc_runner.py','downloader_runtime_module_changed')
  need(Path(pro.__file__).resolve()==runtime/'pro_executor.py' and Path(account_sessions.__file__).resolve()==runtime/'account_sessions.py','downloader_runtime_module_changed')
 finally:sys.path.pop(0)
 paths=[config,root/'pro-executor.json',session/'identity.json',session/'pro-binding.json',root/'accounts'/preferred/'state.json']
 def snapshot():return {str(p):sha(stable(p,65536,True))for p in paths}
 expected=snapshot()
 # status probes active.lock: validate before owning it, then pin the exact metadata.
 state=AccountSessions(root).status(preferred,'xhs');need(state.get('state')in ('authenticated','resumed') and state.get('login_verified')is True and state.get('identity_status')=='authenticated_self_id' and type(state.get('generation'))is int and re.fullmatch('[a-f0-9]{64}',state.get('account_ref',''))and state.get('login_in_progress')is False,'downloader_owner_identity_unverified')
 need(snapshot()==expected,'downloader_collector_changed')
 def scope():
  need(deps.read(config)==raw,'downloader_owner_registry_changed');chosen=pro.task_installation(root,{'source_executor':'pro'});pro.binding_for(root,{'session_id':preferred,'platform':'xhs'})
  info=pro.bridge().source_info(Path(chosen['root']));need(info.get('commit')==pro.PINNED_COMMIT and not info.get('dirty'),'downloader_pro_source_changed')
  current=snapshot();need(current==expected,'downloader_collector_changed');return current
 ctx=SimpleNamespace(root=root,helper=Path(helper));scope();return root,session,scope,lambda:continuation_type.idle(ctx)

def provision_owner(deps,descriptor,helper,owner_root,runtime,continuation_type,*,session_id=None):
 root,session,scope,idle=owner_context(deps,descriptor,helper,owner_root,runtime,continuation_type,session_id=session_id)
 return _publish(deps,descriptor,helper,root,session,scope,idle)

if __name__=='__main__':
 import argparse,importlib.util
 def load(name,file):
  spec=importlib.util.spec_from_file_location(name,file);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
 parser=argparse.ArgumentParser(description='Local operator only; no extension/native action.')
 parser.add_argument('action',choices=['plan','check','owner-check','owner-provision'])
 parser.add_argument('--descriptor',type=Path,required=True);parser.add_argument('--helper-root',type=Path,required=True)
 parser.add_argument('--owner-root',type=Path);parser.add_argument('--runtime',type=Path);parser.add_argument('--session-id')
 args=parser.parse_args();base=Path(__file__).resolve().parent
 try:
  deps=load('downloader_core_dependencies',base/'prepare-pro-dependencies.py')
  if args.action=='plan':result=plan(deps,args.descriptor,args.helper_root)
  elif args.action=='check':result={'state':'verified','manager_sha256':binding(deps,args.descriptor,args.helper_root)['manager_sha256'],'inventory_sha256':INVENTORY_SHA}
  else:
   need(args.owner_root is not None and args.runtime is not None,'downloader_owner_registry_required')
   continuation=load('downloader_original_continuation',base/'pro-binding-continuation.py')
   if args.action=='owner-check':
    root,session,scope,idle=owner_context(deps,args.descriptor,args.helper_root,args.owner_root,args.runtime,continuation.BindingContinuation,session_id=args.session_id);idle();scope();need(deps.read(root/'pro-xhs-media.json')==encoded(binding(deps,args.descriptor,args.helper_root)),'downloader_binding_conflict');result={'state':'verified','source_started':False}
   else:
    # Explicit operator mutation, never invoked by plan/check or from task messages.
    prepare(deps,args.descriptor,args.helper_root);result=provision_owner(deps,args.descriptor,args.helper_root,args.owner_root,args.runtime,continuation.BindingContinuation,session_id=args.session_id)
  print(json.dumps(result))
 except Exception as error:
  reason=str(error)if isinstance(error,ValueError)and re.fullmatch('[a-z_]{1,80}',str(error))else'downloader_dependency_failed'
  print(json.dumps({'state':'not_ready','error':reason}));raise SystemExit(1)
