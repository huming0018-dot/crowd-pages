"""Actual zsh entry/reconnect + actual JXA; temporary HOME and helper/UI stubs only.
--package permits replay of saved old public installer without installing it.
"""
import argparse,hashlib,json,os,re,subprocess,sys,tempfile,zipfile,time
from pathlib import Path
ROOT=Path(__file__).parent;KEY='dGVzdA==';ID='licijehcpohikchlnkbpjdjdfkcocndg'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def case(mode,package=None,reconnect_package=False):
 with tempfile.TemporaryDirectory(prefix='participant-chain-',dir=Path.home()) as tmp:
  b=Path(tmp).resolve();home=b/'home';support=b/'package/.crowd-support';support.mkdir(parents=True);tools=b/'tools';tools.mkdir();calls=b/'helper-calls';opens=b/'ui-calls'
  scripts=['install.command','reconnect.command','browser-preflight.js','browser-preflight.command']
  for n in scripts:
   if package:
    with zipfile.ZipFile(package) as z:
     name='.crowd-support/'+n
     if name not in z.namelist():continue
     data=z.read(name).decode()
   else:
    f=ROOT/'participant'/n
    if not f.exists():continue
    data=f.read_text()
   if n.endswith('.js'):data=re.sub("var expectedKey = '[^']+';","var expectedKey = '"+KEY+"';",data)
   (support/n).write_text(data);(support/n).chmod(0o755)
  # Explicit host/UI transports only are stubbed; preflight JXA and shell nesting remain real.
  for name,body in {'sw_vers':'echo 14.0','PlistBuddy':'echo 141.0','open':'echo open >> "$UI_CALLS"; exit 0'}.items():
   f=tools/name;f.write_text('#!/bin/zsh\n'+body+'\n');f.chmod(0o755)
  chrome=home/'Applications/Google Chrome.app';chrome.mkdir(parents=True)
  for n in ['install.command','reconnect.command']:
   p=support/n;s=p.read_text().replace('/usr/bin/open',str(tools/'open')).replace('/usr/bin/sw_vers',str(tools/'sw_vers')).replace('/usr/libexec/PlistBuddy',str(tools/'PlistBuddy')).replace("'/Applications/Google Chrome.app'", "'"+str(chrome)+"'")
   p.write_text(s)
  if not reconnect_package:
   install_text=(support/'install.command').read_text()
   assert install_text.index('--check-install') < install_text.index('  configure_pro_if_present') < install_text.index('if ! ./reconnect.command')
  source=home/'Library/Application Support/CrowdParticipantExtension';source.mkdir(parents=True)
  (source/'manifest.json').write_text(json.dumps({'version':'4.2.93','key':KEY,'permissions':['storage','nativeMessaging','webNavigation'],'host_permissions':['https://www.xiaohongshu.com/*','https://m.xiaohongshu.com/*']}))
  helperhome=home/'Library/Application Support/CrowdV4Updater';helperhome.mkdir(parents=True)
  (helperhome/'config.json').write_text(json.dumps({'directory':str(source),'extension_key':KEY}));(helperhome/'config.json').chmod(0o600)
  collector=b/'collector';session=collector/'sessions/903d6888-6397-426c-a5e4-8080597c7101';target=session/'browser_data/xhs_bridge_profile';target.mkdir(parents=True);(session/'identity.json').write_text('{"platform":"xhs"}')
  settings=helperhome/'pro-install-settings.json';settings.write_text(json.dumps({'python':sys.executable,'root':str(collector),'mc_root':str(b),'session_id':session.name,'max_api_requests':14,'purpose':'noncommercial_research'}));settings.chmod(0o600)
  daily=home/'Library/Application Support/Google/Chrome';daily.mkdir(parents=True);legacy=b/'legacy';legacy.mkdir();(legacy/'manifest.json').write_text(json.dumps({'version':'3.5.3','key':KEY,'permissions':['storage','alarms']}))
  def register(root,src):
   (root/'Default').mkdir(exist_ok=True);(root/'Default/Secure Preferences').write_text(json.dumps({'extensions':{'settings':{ID:{'path':str(src)}}}}))
  register(daily,legacy);register(target,source)
  if mode=='missing_target':(target/'Default/Secure Preferences').write_text('{}')
  if mode=='native_conflict':(legacy/'manifest.json').write_text(json.dumps({'version':'3.5.3','key':KEY,'permissions':['nativeMessaging']}))
  if mode=='poll_lock':
   # Real current helper holds update.lock through bootstrap; scheduled poll may
   # acquire it immediately after install returns and before outer configure.
   (b/'media_platform/xhs').mkdir(parents=True)
   binding=session/'pro-binding.json';binding.write_text('{"platform":"xhs","client_id":"fixture","cookiebridge_url":"http://127.0.0.1:8274","sign_url":"http://127.0.0.1:5005"}')
   (support/'configure-pro.py').write_bytes((ROOT/'participant/configure-pro.py').read_bytes())
   rt=support/'pro-runtime';rt.mkdir();e=rt/'participant_pro_native.py';e.write_text('# own fixture entry\n');(rt/'PRO-RUNTIME.json').write_text(json.dumps({'schema':'crowd-participant-pro-runtime-v1','files':{e.name:digest(e)}}))
  h=support/'crowd-v4-participant-updater';h.write_text('#!/bin/zsh\nprint -r -- "$1" >> "$HELPER_CALLS"\nexit 0\n');h.chmod(0o755)
  if mode=='poll_lock':
   poll=b/'poll.py';poll.write_text("import fcntl,os,sys,time\nf=open(sys.argv[1],'a');fcntl.flock(f,fcntl.LOCK_EX);open(sys.argv[2],'w').write('ready');time.sleep(2)\n")
   helpercode=b/'helper.py';helpercode.write_text("import fcntl,os,subprocess,sys,time\nfrom pathlib import Path\na=sys.argv[1];open(os.environ['HELPER_CALLS'],'a').write(a+'\\n')\nif a=='--reconnect':\n lock=Path(os.environ['HOME'])/'Library/Application Support/CrowdV4Updater/update.lock';f=open(lock,'a');fcntl.flock(f,fcntl.LOCK_EX)\n ready=Path(os.environ['POLL_READY']);p=subprocess.Popen([sys.executable,os.environ['POLL_SCRIPT'],str(lock),str(ready)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,close_fds=True)\n f.close()\n end=time.monotonic()+3\n while not ready.exists() and time.monotonic()<end:time.sleep(0.01)\n assert ready.exists()\n")
   h.write_text('#!/bin/zsh\nexec '+json.dumps(sys.executable)+' '+json.dumps(str(helpercode))+' "$@"\n')
  # Keep only own-fixture files: configuration not attempted, and no source SDK exists.
  (support/'MIGRATE-SHA256.txt').write_text(''.join(digest(support/n)+'  '+n+'\n' for n in ['crowd-v4-participant-updater','browser-preflight.js','reconnect.command']+(['browser-preflight.command'] if (support/'browser-preflight.command').exists() else [])))
  (support/'INSTALL-SHA256.txt').write_text(''.join(digest(f)+'  '+f.name+'\n' for f in support.iterdir() if f.is_file() and f.name not in ('MIGRATE-SHA256.txt','INSTALL-SHA256.txt')))
  entry=b/'package/开始安装.command';entry.write_bytes((ROOT/'participant/start.command').read_bytes());entry.chmod(0o755)
  protected=[source/'manifest.json',helperhome/'config.json',daily/'Default/Secure Preferences',target/'Default/Secure Preferences',session/'identity.json',legacy/'manifest.json'];before={str(f):digest(f) for f in protected}
  env={**os.environ,'HOME':str(home),'HELPER_CALLS':str(calls),'UI_CALLS':str(opens),'POLL_SCRIPT':str(b/'poll.py'),'POLL_READY':str(b/'poll-ready')}
  p=subprocess.run(['/bin/zsh',str(entry)],env=env,capture_output=True,text=True,timeout=30)
  actual=calls.read_text().splitlines() if calls.exists() else []
  expected=(['--reconnect'] if reconnect_package else ['--check-install','--reconnect']) if mode in ('success','poll_lock') else []
  assert p.returncode==(0 if mode in ('success','poll_lock') else 1) and actual==expected,(mode,p.returncode,actual,p.stdout,p.stderr)
  assert {str(f):digest(f) for f in protected}==before
  if mode=='poll_lock':
   config=helperhome/'pro-config.json'
   assert config.exists(),('self-created RunAtLoad poll lock prevented own-runtime configuration',p.stdout,p.stderr)
   prepared=json.loads(config.read_bytes());original=json.loads(settings.read_bytes());assert all(prepared[k]==v for k,v in original.items())
   assert (session/'pro-binding.json').read_text()=='{"platform":"xhs","client_id":"fixture","cookiebridge_url":"http://127.0.0.1:8274","sign_url":"http://127.0.0.1:5005"}'
   time.sleep(2.1);print('PASS bootstrap poll may hold lock after reconnect; existing SDK/settings unchanged; configure already complete');return
  assert not (helperhome/'pro-config.json').exists()
  # Standalone internal reconnect entry must select identical preflight arguments.
  if calls.exists():calls.unlink()
  p=subprocess.run(['/bin/zsh',str(support/'reconnect.command')],env=env,capture_output=True,text=True,timeout=30)
  actual=calls.read_text().splitlines() if calls.exists() else []
  assert p.returncode==(0 if mode in ('success','poll_lock') else 1) and actual==(['--reconnect'] if mode in ('success','poll_lock') else []),(mode,'standalone',actual,p.stdout,p.stderr)
  assert {str(f):digest(f) for f in protected}==before
  print('PASS actual nested install + standalone reconnect',mode,'exact helper calls',expected)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--package',type=Path);p.add_argument('--reconnect-package',action='store_true');p.add_argument('--lock-race',action='store_true');a=p.parse_args()
 for mode in (['poll_lock'] if a.lock_race else ['success','missing_target','native_conflict']):case(mode,a.package,a.reconnect_package)
