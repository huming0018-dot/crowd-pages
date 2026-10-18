"""Real JXA isolated-profile reconnect regression; no browser/credentials/actions."""
from pathlib import Path
import hashlib,json,subprocess,sys,tempfile,uuid
SOURCE=Path(__file__).parent/'participant/browser-preflight.js';KEY='dGVzdA==';ID='licijehcpohikchlnkbpjdjdfkcocndg'
def case(name,expected,change=lambda env:None):
 with tempfile.TemporaryDirectory(prefix='registered-profile-test-') as d:
  b=Path(d);daily=b/'Chrome';daily.mkdir();native=b/'registered';native.mkdir();legacy=b/'legacy';legacy.mkdir();sid=str(uuid.uuid4());collector=b/'collector';session=collector/'sessions'/sid;target=session/'browser_data/xhs_bridge_profile';target.mkdir(parents=True)
  nm={'version':'4.2.93','key':KEY,'permissions':['storage','webNavigation','nativeMessaging'],'host_permissions':['https://www.xiaohongshu.com/*','https://m.xiaohongshu.com/*']};lm={'version':'3.5.3','key':KEY,'permissions':['storage','alarms','unlimitedStorage','notifications'],'host_permissions':['https://www.xiaohongshu.com/*']}
  (native/'manifest.json').write_text(json.dumps(nm));(legacy/'manifest.json').write_text(json.dumps(lm));(session/'identity.json').write_text(json.dumps({'platform':'xhs'}))
  def register(root,source):
   (root/'Default').mkdir(exist_ok=True);(root/'Default/Secure Preferences').write_text(json.dumps({'extensions':{'settings':{ID:{'path':str(source)}}}}))
  register(daily,legacy);register(target,native)
  settings=b/'pro-install-settings.json';settings.write_text(json.dumps({'python':sys.executable,'root':str(collector),'mc_root':str(b),'session_id':sid,'max_api_requests':14,'purpose':'noncommercial_research'}));settings.chmod(0o600)
  config=b/'config.json';config.write_text(json.dumps({'directory':str(native),'extension_key':KEY}));config.chmod(0o600)
  env=locals();change(env);script=b/'check.js';script.write_text(SOURCE.read_text().replace('@EXTENSION_KEY@',KEY))
  before={str(p.relative_to(b)):hashlib.sha256(p.read_bytes()).hexdigest() for p in b.rglob('*') if p.is_file() and not p.is_symlink()}
  args=[str(daily),str(native),str(settings),str(config)]
  r=subprocess.run(['/usr/bin/osascript','-l','JavaScript',str(script),*args],capture_output=True,text=True,timeout=20)
  assert r.returncode==0 and r.stdout.strip()==expected,(name,r.stdout,r.stderr)
  after={str(p.relative_to(b)):hashlib.sha256(p.read_bytes()).hexdigest() for p in b.rglob('*') if p.is_file() and not p.is_symlink()};assert before==after,name
  print('PASS',name,expected)
def manifest(e,**kw):
 p=e['legacy']/'manifest.json';m=json.loads(p.read_text());m.update(kw);p.write_text(json.dumps(m))
case('registered93-isolated-plus-passive-daily353','compatible_registered')
case('daily-native-conflict','legacy_browser_extension',lambda e:manifest(e,permissions=['nativeMessaging']))
case('daily-optional-native-conflict','legacy_browser_extension',lambda e:manifest(e,optional_permissions=['nativeMessaging']))
case('daily-external-bridge-conflict','legacy_browser_extension',lambda e:manifest(e,externally_connectable={'matches':['https://example.com/*']}))
case('daily-unknown-legacy-not-exempt','legacy_browser_extension',lambda e:manifest(e,version='3.5.2'))
case('private-settings-required','browser_inventory_unavailable',lambda e:e['settings'].chmod(0o644))
case('wrong-session-platform','browser_inventory_unavailable',lambda e:(e['session']/'identity.json').write_text('{"platform":"dy"}'))
case('target-must-be-registered','browser_inventory_unavailable',lambda e:(e['target']/'Default/Secure Preferences').write_text('{}'))
case('helper-directory-must-match','browser_inventory_unavailable',lambda e:e['config'].write_text(json.dumps({'directory':str(e['legacy']),'extension_key':KEY})))
case('daily-target-registration-cannot-be-exempt','browser_reconnect_required',lambda e:e['register'](e['daily'],e['native']))
case('missing-identity','browser_inventory_unavailable',lambda e:(e['session']/'identity.json').unlink())
case('daily-malformed-still-refused','browser_inventory_unavailable',lambda e:(e['daily']/'Default/Secure Preferences').write_text('{broken'))
print('PASS 12 bound-profile JXA cases; no bytes changed')
