#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import importlib.util,json,hashlib,pathlib,sys,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('bootstrap',root/'build_bootstrap.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
source,helper=map(pathlib.Path,sys.argv[1:])
with tempfile.TemporaryDirectory() as d:
    a=pathlib.Path(d)/'a.zip';b=pathlib.Path(d)/'b.zip'
    assert m.build(source,helper,a)['sha256']==m.build(source,helper,b)['sha256']
    with zipfile.ZipFile(a) as z,zipfile.ZipFile(source) as original:
        prefix='Mac众包更新/'
        for n in original.namelist():assert z.read(prefix+'插件/'+n)==original.read(n)
        assert 'nativeMessaging' in json.loads(z.read(prefix+'插件/manifest.json'))['permissions']
        assert z.read(prefix+'updater/crowd-v4-updater')==helper.read_bytes()
        assert (z.getinfo(prefix+'updater/crowd-v4-updater').external_attr>>16)&0o111
        for line in z.read(prefix+'SHA256SUMS.txt').decode().splitlines():
            digest,name=line.split('  ',1);assert hashlib.sha256(z.read(prefix+name)).hexdigest()==digest
        assert b'--install' in z.read(prefix+'prepare.command')
print('PASS bootstrap: deterministic archive, canonical runtime, universal executable, executable bit and all file hashes')
