"""The shareable update must contain canonical code, never a private invitation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import zipfile

spec = importlib.util.spec_from_file_location('update', Path(__file__).with_name('build_update.py'))
update = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update)
source = Path(sys.argv[1])
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    a, b = temp/'a.zip', temp/'b.zip'
    assert update.build(source, a)['sha256'] == update.build(source, b)['sha256']
    with zipfile.ZipFile(source) as archive:
        original = {n: archive.read(n) for n in archive.namelist()}
    with zipfile.ZipFile(a) as archive:
        prefix = 'Mac众包更新/'
        for name, content in original.items():
            assert archive.read(prefix+'插件/'+name) == content, name
        config = archive.read(prefix+'插件/src/config.js').decode()
        values = json.loads(config.removeprefix('globalThis.CROWD_CONFIG = ').strip().removesuffix(';'))
        assert set(values) == {'url', 'key', 'portal'}
        assert b'--update-only' in archive.read(prefix+'更新.command')
        for row in archive.read(prefix+'SHA256SUMS.txt').decode().splitlines():
            digest, name = row.split('  ', 1)
            assert hashlib.sha256(archive.read(prefix+name)).hexdigest() == digest
    def rejected(files):
        with zipfile.ZipFile(b, 'w') as archive:
            for name, content in files.items():
                archive.writestr(name, content)
        try:
            update.build(b, a)
        except (ValueError, KeyError):
            return
        raise AssertionError('unsafe update accepted')
    rejected({**original, '../escape': b'bad'})
    rejected({**original, 'src/core.js': b'changed'})
    # Even with internally consistent hashes, a private invitation is rejected.
    conf = dict(values, trialInvite='a'*64)
    private = dict(original)
    private['src/config.js'] = ('globalThis.CROWD_CONFIG = '+json.dumps(conf)+';\n').encode()
    release = json.loads(private['release.json'])
    release['files']['src/config.js'] = hashlib.sha256(private['src/config.js']).hexdigest()
    private['release.json'] = json.dumps(release).encode()
    rejected(private)
    conf = dict(values, key='sb_secret_must_not_publish')
    private['src/config.js'] = ('globalThis.CROWD_CONFIG = '+json.dumps(conf)+';\n').encode()
    release['files']['src/config.js'] = hashlib.sha256(private['src/config.js']).hexdigest()
    private['release.json'] = json.dumps(release).encode()
    rejected(private)
print('PASS update package: reproducible, byte-identical canonical runtime, no invitation or enrollment credentials, file hashes, unsafe paths/tampering/private config rejected')
