"""Fixed official Node resource for the existing participant dependency lifecycle.

No platform calls, daemon or private SDK. New runtime only; legacy NODE-SHA is untouched.
"""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import stat
import tarfile
import urllib.request

VERSION='v22.23.2'
ARCHIVES={
 'arm64':'61130f394c1630d211dd50aecc4353d379480f36d3ac913cd85dbba1aed585c6',
 'x64':'58e99022c2ff89395576cc7fd4d98cea24bb68081475d5f88b801ee8729fb026',
}
TRUSTED_ARM64_BINARY='18e387c90ab8a8400183e8bdd396376e1e875b91b4c874b894dcade7b35bf572'
MAX_ARCHIVE=80*1024*1024
MAX_FILE=160*1024*1024

def need(ok,reason='node_resource_invalid'):
 if not ok:raise ValueError(reason)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def architecture():
 need(platform.system()=='Darwin','node_architecture_unsupported')
 arch={'arm64':'arm64','x86_64':'x64'}.get(platform.machine())
 need(arch in ARCHIVES,'node_architecture_unsupported');return arch
def private_dir(path):
 path=Path(path);need(path.is_absolute() and path.resolve()==path and path.is_dir())
 s=path.stat();need(s.st_uid==os.getuid() and not s.st_mode&0o077)
 return path
def syncdir(path):
 fd=os.open(path,os.O_RDONLY)
 try:os.fsync(fd)
 finally:os.close(fd)
def once(path,raw,mode=0o600):
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
 with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 syncdir(path.parent)
def read(path,limit=MAX_FILE):
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 try:
  s=os.fstat(fd);need(stat.S_ISREG(s.st_mode) and s.st_uid==os.getuid() and not s.st_mode&0o022 and 0<s.st_size<=limit)
  with os.fdopen(fd,'rb',closefd=False) as f:raw=f.read(limit+1)
  e=os.fstat(fd);need(len(raw)==s.st_size and (s.st_size,s.st_mtime_ns,s.st_ctime_ns)==(e.st_size,e.st_mtime_ns,e.st_ctime_ns));return raw
 finally:os.close(fd)
def target(helper,arch):
 need(arch in ARCHIVES,'node_architecture_unsupported')
 return private_dir(helper)/'node-runtime'/('%s-darwin-%s'%(VERSION,arch))
def resource(raw,arch):
 need(sha(raw)==ARCHIVES[arch],'node_archive_changed')
 prefix='node-%s-darwin-%s/'%(VERSION,arch);files={}
 with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as t:
  for m in t:
   p=PurePosixPath(m.name)
   need(not p.is_absolute() and '..' not in p.parts and m.name.startswith(prefix.rstrip('/')),'node_archive_member_invalid')
   relative=m.name[len(prefix):] if m.name.startswith(prefix) else ''
   if relative in {'bin/node','LICENSE','NOTICE'}:
    need(m.isfile() and 0<m.size<=MAX_FILE and relative not in files,'node_archive_member_invalid')
    files[relative]=t.extractfile(m).read()
 need({'bin/node','LICENSE'}<=set(files),'node_archive_member_invalid')
 if arch=='arm64':need(sha(files['bin/node'])==TRUSTED_ARM64_BINARY,'node_binary_changed')
 return files
def contract(arch):return {'schema':'crowd-node-resource-v1','version':VERSION,'arch':arch,'archive_sha256':ARCHIVES[arch]}
def check(helper,*,arch=None):
 arch=arch or architecture();dest=target(helper,arch)
 private_dir(dest.parent);private_dir(dest);private_dir(dest/'bin')
 need(read(dest/'RESULT.json',4096)==json.dumps(contract(arch),sort_keys=True).encode(),'node_attempt_unknown')
 files=resource(read(dest/'archive.tar.gz',MAX_ARCHIVE),arch)
 for name,raw in files.items():need(read(dest/name)==raw,'node_binary_changed' if name=='bin/node' else 'node_license_changed')
 node=dest/'bin/node';need(os.access(node,os.X_OK));return node

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise ValueError('node_download_redirected')

def fetch(url):
 request=urllib.request.Request(url,headers={'User-Agent':'CrowdV4-node-dependency'})
 with urllib.request.build_opener(NoRedirect()).open(request,timeout=120) as response:
  need(response.url==url,'node_download_redirected');raw=response.read(MAX_ARCHIVE+1)
 need(len(raw)<=MAX_ARCHIVE,'node_archive_too_large');return raw

def prepare(helper,*,arch=None,offline=False,fetch=fetch):
 arch=arch or architecture();dest=target(helper,arch)
 if dest.exists():
  private_dir(dest)
  need((dest/'RESULT.json').exists(),'node_attempt_unknown');return check(helper,arch=arch)
 need(not offline,'node_offline_missing')
 if not dest.parent.exists():dest.parent.mkdir(mode=0o700);syncdir(dest.parent.parent)
 private_dir(dest.parent);dest.mkdir(mode=0o700);syncdir(dest.parent)
 once(dest/'INTENT.json',json.dumps(contract(arch),sort_keys=True).encode())
 # Unknown acquisition/install is durable. Only a complete RESULT permits reuse.
 name='node-%s-darwin-%s.tar.gz'%(VERSION,arch)
 raw=fetch('https://nodejs.org/download/release/%s/%s'%(VERSION,name));files=resource(raw,arch)
 once(dest/'archive.tar.gz',raw)
 (dest/'bin').mkdir(mode=0o700);syncdir(dest)
 for name,data in files.items():once(dest/name,data,0o700 if name=='bin/node' else 0o600)
 once(dest/'RESULT.json',json.dumps(contract(arch),sort_keys=True).encode())
 return check(helper,arch=arch)

def from_runtime(runtime,*,arch=None):
 runtime=Path(runtime)
 need(runtime.is_absolute() and runtime.resolve()==runtime,'node_runtime_layout_invalid')
 if runtime.parent.name=='pro-runtime' and len(runtime.name)==64 and all(c in '0123456789abcdef' for c in runtime.name):
  helper=runtime.parent.parent
 elif (tuple(runtime.parts[-4:])==('server','crowd','v4','multiplatform')
       or (runtime.name=='pro-runtime' and runtime.parent.name=='.crowd-support')):
  # Owner checkout and verified installer preconfigure use the same per-user resource.
  # It never resolves a browser-provided path or falls back to legacy NODE-SHA.
  helper=Path.home()/'Library/Application Support/CrowdV4Updater'
 else:raise ValueError('node_runtime_layout_invalid')
 return check(helper,arch=arch)
