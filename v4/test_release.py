"""Offline: cross-repository package integrity, candidate isolation and safe paths."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import zipfile

def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

if len(sys.argv)!=2:raise SystemExit('Usage: python3 v4/test_release.py /path/to/crawler-extension/v4')
ext=Path(sys.argv[1]).resolve();build=load('candidate_build',ext/'build.py');kit=load('candidate_kit',Path(__file__).with_name('build_trial.py'))
pilot={'invite':'a'*64,'expires_at':'2099-01-01T00:00:00+00:00','max_people':1,'quota_day':2}
with tempfile.TemporaryDirectory() as directory:
 tmp=Path(directory);one=tmp/'one.zip';two=tmp/'two.zip';out=tmp/'trial.zip'
 assert build.build(one)['sha256']==build.build(two)['sha256'],'same canonical inputs produce identical bytes'
 result=kit.write_kit(one,pilot,out);assert result['device_acceptance'] is False
 with zipfile.ZipFile(one) as z:raw={n:z.read(n) for n in z.namelist()}
 with zipfile.ZipFile(out) as z:
  prefix='Mac轻量内测/'
  manifest=json.loads(z.read(prefix+'插件/manifest.json'));version=manifest['version'];worker=manifest['background']['service_worker']
  assert worker=='src/background_v'+version.replace('.','_')+'.js'
  assert 'update_url' not in manifest,'private v4 must never attach to legacy update channel'
  assert z.read(prefix+'插件/src/background.js')==(ext/'src/background.js').read_bytes()
  assert b"importScripts('background.js')" in z.read(prefix+'插件/'+worker)
  assert f"VERSION = '{version}'" in z.read(prefix+'插件/src/core.js').decode()
  assert version in z.read(prefix+'先打开安装说明.html').decode()
  release=json.loads(z.read(prefix+'插件/release.json'))
  assert release['protocol']=='crowd_v4' and release['configuration_mode']=='private_invite'
  for n,digest in release['files'].items():assert hashlib.sha256(z.read(prefix+'插件/'+n)).hexdigest()==digest,n
  for line in z.read(prefix+'SHA256SUMS.txt').decode().splitlines():
   digest,n=line.split('  ',1);assert hashlib.sha256(z.read(prefix+n)).hexdigest()==digest,n
  assert (z.getinfo(prefix+'双击开始安装.command').external_attr>>16)&0o111
 def rejected(files):
  with zipfile.ZipFile(two,'w') as z:
   for n,data in files.items():z.writestr(n,data)
  try:kit.write_kit(two,pilot,out)
  except (ValueError,KeyError):return
  raise AssertionError('unsafe or tampered source was accepted')
 rejected({**raw,'../outside':'bad'})
 rejected({**raw,worker:b'wrong runtime'})
 changed=json.loads(raw['manifest.json']);changed['version']='4.9.9'
 rejected({**raw,'manifest.json':json.dumps(changed).encode()})
 print('PASS release: reproducible canonical source, versioned worker, unchanged identity, invite-only config mutation, all hashes, guide version, no legacy update channel, tamper/path rejection')
