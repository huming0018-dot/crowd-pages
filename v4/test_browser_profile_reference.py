"""Migration-pinned original browser_data only; actual JXA, isolated metadata, no browser."""
from pathlib import Path
import json,hashlib,shutil,subprocess,tempfile,sys,uuid
SOURCE=Path(__file__).parent/'participant/browser-preflight.js';KEY='dGVzdA==';ID='licijehcpohikchlnkbpjdjdfkcocndg'
def case(name,expected,change=lambda e:None):
 with tempfile.TemporaryDirectory(prefix='profile-reference-',dir=Path.home()/'Library/Caches')as tmp:
  b=Path(tmp).resolve();daily=b/'Chrome';daily.mkdir();native=b/'registered';native.mkdir();sid=str(uuid.uuid4());session=b/'collector/sessions'/sid;session.mkdir(parents=True);original=b/'original/sessions'/sid;target=original/'browser_data/xhs_bridge_profile';(target/'Default').mkdir(parents=True)
  nm={'version':'4.2.101','key':KEY,'permissions':['storage','webNavigation','nativeMessaging'],'host_permissions':['https://www.xiaohongshu.com/*','https://m.xiaohongshu.com/*']};(native/'manifest.json').write_text(json.dumps(nm))
  (target/'Default/Secure Preferences').write_text(json.dumps({'extensions':{'settings':{ID:{'path':str(native)}}}}))
  identity=b'{"platform":"xhs"}';binding=b'{"platform":"xhs","client_id":"original","cookiebridge_url":"http://127.0.0.1:2333","sign_url":"http://127.0.0.1:8990"}'
  for root in [session,original]:
   (root/'identity.json').write_bytes(identity);(root/'pro-binding.json').write_bytes(binding)
  (session/'browser_data').symlink_to(original/'browser_data',target_is_directory=True)
  marker=session/'browser-profile-reference.json';value={'schema':'crowd-pro-original-browser-profile-v1','session_id':sid,'platform':'xhs','browser_data':str(original/'browser_data'),'identity_sha256':hashlib.sha256(identity).hexdigest(),'binding_sha256':hashlib.sha256(binding).hexdigest()};marker.write_text(json.dumps(value));marker.chmod(0o600)
  settings=b/'pro-install-settings.json';settings.write_text(json.dumps({'python':sys.executable,'root':str(session.parent.parent),'mc_root':str(b),'session_id':sid,'max_api_requests':14,'purpose':'noncommercial_research'}));settings.chmod(0o600)
  config=b/'config.json';config.write_text(json.dumps({'directory':str(native),'extension_key':KEY}));config.chmod(0o600)
  env=locals();change(env);script=b/'check.js';script.write_text(SOURCE.read_text().replace('@EXTENSION_KEY@',KEY))
  before={str(p.relative_to(b)):hashlib.sha256(p.read_bytes()).hexdigest()for p in b.rglob('*')if p.is_file()and not p.is_symlink()}
  r=subprocess.run(['/usr/bin/osascript','-l','JavaScript',str(script),str(daily),str(native),str(settings),str(config)],capture_output=True,text=True,timeout=20)
  assert r.returncode==0 and r.stdout.strip()==expected,(name,r.stdout,r.stderr)
  after={str(p.relative_to(b)):hashlib.sha256(p.read_bytes()).hexdigest()for p in b.rglob('*')if p.is_file()and not p.is_symlink()};assert before==after,name
  print('PASS',name,expected)
def mutate(e,key,value):
 d=json.loads(e['marker'].read_text());d[key]=value;e['marker'].write_text(json.dumps(d))
case('authorized-original-reference','compatible_registered')
case('marker-missing','browser_inventory_unavailable',lambda e:e['marker'].unlink())
case('marker-public','browser_inventory_unavailable',lambda e:e['marker'].chmod(0o644))
case('marker-wrong-schema','browser_inventory_unavailable',lambda e:mutate(e,'schema','other'))
case('marker-wrong-session','browser_inventory_unavailable',lambda e:mutate(e,'session_id',str(uuid.uuid4())))
case('marker-wrong-platform','browser_inventory_unavailable',lambda e:mutate(e,'platform','dy'))
case('marker-extra-field','browser_inventory_unavailable',lambda e:mutate(e,'unexpected',True))
case('marker-wrong-identity-hash','browser_inventory_unavailable',lambda e:mutate(e,'identity_sha256','0'*64))
case('marker-wrong-binding-hash','browser_inventory_unavailable',lambda e:mutate(e,'binding_sha256','0'*64))
case('current-binding-drift','browser_inventory_unavailable',lambda e:(e['session']/'pro-binding.json').write_text('{}'))
case('original-binding-drift','browser_inventory_unavailable',lambda e:(e['original']/'pro-binding.json').write_text('{}'))
case('original-identity-drift','browser_inventory_unavailable',lambda e:(e['original']/'identity.json').write_text('{"platform":"dy"}'))
case('current-identity-drift','browser_inventory_unavailable',lambda e:(e['session']/'identity.json').write_text('{"platform":"dy"}'))
case('marker-wrong-target','browser_inventory_unavailable',lambda e:mutate(e,'browser_data',str(e['b']/'wrong/sessions'/e['sid']/'browser_data')))
case('unmarked-original-link','browser_inventory_unavailable',lambda e:mutate(e,'browser_data',str(e['original']/'browser_data/..'/'browser_data')))
def symlink_marker(e):
 other=e['b']/'marker-copy';other.write_bytes(e['marker'].read_bytes());other.chmod(0o600);e['marker'].unlink();e['marker'].symlink_to(other)
case('marker-symlink','browser_inventory_unavailable',symlink_marker)
def symlink_binding(e):
 p=e['session']/'pro-binding.json';p.unlink();p.symlink_to(e['original']/'pro-binding.json')
case('identity-binding-symlink','browser_inventory_unavailable',symlink_binding)
def symlink_bridge(e):
 other=e['original']/'other-profile';e['target'].rename(other);e['target'].symlink_to(other,target_is_directory=True)
case('bridge-profile-symlink','browser_inventory_unavailable',symlink_bridge)
def symlink_session(e):
 old=e['session'];other=e['b']/'other-session';old.rename(other);old.symlink_to(other,target_is_directory=True)
case('session-directory-symlink','browser_inventory_unavailable',symlink_session)
def legacy(e):
 ext=e['b']/'legacy';ext.mkdir();(ext/'manifest.json').write_text(json.dumps({'key':KEY,'version':'3.5.2','permissions':[]}));profile=e['daily']/'Default';profile.mkdir();(profile/'Preferences').write_text(json.dumps({'extensions':{'settings':{ID:{'path':str(ext)}}}}))
case('legacy-daily-risk-not-exempted','legacy_browser_extension',legacy)
print('PASS 20 original-profile-reference JXA cases; no browser launched or metadata changed')
