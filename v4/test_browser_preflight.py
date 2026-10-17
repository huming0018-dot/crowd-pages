"""Run the actual macOS JXA preflight against isolated Chrome metadata only."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

EXTENSION_ID = 'licijehcpohikchlnkbpjdjdfkcocndg'
KEY = 'dGVzdA=='
SOURCE = Path(__file__).parent / 'participant/browser-preflight.js'


def run_case(name, expected, setup):
    with tempfile.TemporaryDirectory(prefix='crowd-browser-preflight-') as tmp:
        base = Path(tmp)
        root = base / 'Chrome'
        native = base / 'original-source'
        root.mkdir()
        native.mkdir()
        (native / 'manifest.json').write_text(json.dumps({'version': '4.2.60', 'key': KEY}))
        script = base / 'check.js'
        script.write_text(SOURCE.read_text().replace('@EXTENSION_KEY@', KEY))
        native_arg = setup(base, root, native)
        before = {str(p.relative_to(base)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in base.rglob('*') if p.is_file() and not p.is_symlink()}
        result = subprocess.run(['/usr/bin/osascript', '-l', 'JavaScript', str(script), str(root), native_arg],
                                capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, (name, result.stderr)
        assert result.stdout.strip() == expected, (name, result.stdout, result.stderr)
        after = {str(p.relative_to(base)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in base.rglob('*') if p.is_file() and not p.is_symlink()}
        assert before == after, name + ': changed metadata'
        print('PASS', name, expected)


def registered(root, source, version='4.2.60', profile='Default', filename='Secure Preferences', key=KEY):
    folder = root / profile
    folder.mkdir(exist_ok=True)
    path = folder / filename
    path.write_text(json.dumps({'null_chrome_field': None, 'extensions': {'settings': {
        EXTENSION_ID: {'path': str(source), 'state': 0, 'manifest': {'version': version, 'key': key}}
    }}}))
    return path


run_case('fresh-no-profiles', 'clear', lambda b, r, n: '')
run_case('empty-profile-with-json-null', 'clear', lambda b, r, n:
         ((r/'Default').mkdir(), (r/'Default/Preferences').write_text('{"nothing": null}'), '')[-1])
run_case('compatible-existing', 'compatible_registered', lambda b, r, n: (registered(r, n), str(n))[1])
run_case('disabled-v3-without-helper', 'legacy_browser_extension', lambda b, r, n:
         (registered(r, n, '3.5.1'), '')[1])
run_case('v3-after-native-install', 'legacy_browser_extension', lambda b, r, n:
         (registered(r, n, '3.5.1'), str(n))[1])
run_case('other-profile-v3', 'legacy_browser_extension', lambda b, r, n:
         (registered(r, n), registered(r, n, '3.5.1', profile='Profile 2'), str(n))[-1])
run_case('registered-no-helper', 'browser_reconnect_required', lambda b, r, n: (registered(r, n), '')[1])
run_case('different-helper-directory', 'browser_reconnect_required', lambda b, r, n:
         (registered(r, n), str(b/'new-location'))[1])
run_case('malformed-json', 'browser_inventory_unavailable', lambda b, r, n:
         ((r/'Default').mkdir(), (r/'Default/Preferences').write_text('{broken'), '')[-1])
run_case('missing-source', 'browser_inventory_unavailable', lambda b, r, n:
         (registered(r, b/'missing'), str(n))[1])
run_case('wrong-key', 'browser_inventory_unavailable', lambda b, r, n:
         (registered(r, n, key='d3Jvbmc='), str(n))[1])
run_case('changed-disk-version', 'browser_inventory_unavailable', lambda b, r, n:
         (registered(r, n, '4.2.58'), str(n))[1])
run_case('invalid-extensions-shape', 'browser_inventory_unavailable', lambda b, r, n:
         ((r/'Default').mkdir(), (r/'Default/Preferences').write_text('{"extensions": []}'), '')[-1])
run_case('symlink-preferences', 'browser_inventory_unavailable', lambda b, r, n:
         (registered(r, n), (r/'Default/Preferences').symlink_to(r/'Default/Secure Preferences'), str(n))[-1])
run_case('broken-symlink-preferences', 'browser_inventory_unavailable', lambda b, r, n:
         ((r/'Default').mkdir(), (r/'Default/Preferences').symlink_to(b/'missing'), '')[-1])
run_case('other-profile-symlink', 'browser_inventory_unavailable', lambda b, r, n:
         (registered(b, n, '3.5.1', profile='external'), (r/'WorkProfile').symlink_to(b/'external'), '')[-1])
run_case('root-has-regular-files', 'clear', lambda b, r, n:
         ((r/'Local State').write_text('{}'), (r/'SingletonLock').symlink_to(b/'not-present'), '')[-1])
run_case('v3-source-with-no-cached-manifest', 'legacy_browser_extension', lambda b, r, n:
         (registered(r, n), (r/'Default/Secure Preferences').write_text(json.dumps({'extensions':{'settings':{EXTENSION_ID:{'path':str(n)}}}})),
          (n/'manifest.json').write_text(json.dumps({'version':'3.5.1','key':KEY})), '')[-1])
run_case('conflicting-preference-source', 'browser_reconnect_required', lambda b, r, n:
         (registered(r, n), (b/'other').mkdir(), (b/'other/manifest.json').write_text((n/'manifest.json').read_text()), registered(r,b/'other',filename='Preferences'), str(n))[-1])
run_case('relative-packed-source-no-helper', 'browser_reconnect_required', lambda b, r, n:
         ((r/'Default/Extensions'/EXTENSION_ID/'4.2.60_0').mkdir(parents=True),
          (r/'Default/Extensions'/EXTENSION_ID/'4.2.60_0/manifest.json').write_text((n/'manifest.json').read_text()),
          registered(r, Path(EXTENSION_ID)/'4.2.60_0'), '')[-1])
print('PASS 20 actual JXA cases; no browser launched; all fixture bytes preserved')
