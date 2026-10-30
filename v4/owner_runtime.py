"""Validate a prepared CPython tree; never fetch or install dependencies."""
import json
import os
from pathlib import Path
import subprocess
import tempfile


PROBE = '''import bz2, ctypes, hashlib, http.server, json, lzma, platform, sqlite3, ssl, sys, zlib
c = sqlite3.connect(':memory:')
assert c.execute('select 42').fetchone() == (42,)
ssl.create_default_context()
assert lzma.decompress(lzma.compress(b'owner')) == b'owner'
assert bz2.decompress(bz2.compress(b'owner')) == b'owner'
print(json.dumps({'implementation': platform.python_implementation(),
 'version': platform.python_version(), 'architecture': platform.machine(),
 'system': platform.system(), 'prefix': sys.prefix, 'base_prefix': sys.base_prefix}))
'''


def prepared_runtime(runtime, architecture):
    if runtime is None:
        raise ValueError('standalone package requires --runtime')
    if architecture not in ('arm64', 'x86_64'):
        raise ValueError('explicit macOS architecture required: arm64 or x86_64')
    root = Path(runtime).resolve()
    if not root.is_dir() or not (root / 'bin/python3').is_file():
        raise ValueError('incomplete runtime: bin/python3 missing')
    files = {}
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if relative.as_posix() == 'lib/python3.12/lib-dynload/.empty':
            continue  # Upstream empty build placeholder, not needed at runtime.
        if path.suffix in {'.pyc', '.pyo'}:
            raise ValueError('runtime contains bytecode cache: ' + str(relative))
        if any(part in {'site-packages', '__pycache__', '.git', '.cache'} or part.startswith('.')
               for part in relative.parts):
            raise ValueError('unexpected runtime content: ' + str(relative))
        if path.is_symlink():
            if not path.resolve().is_relative_to(root) or not path.is_file():
                raise ValueError('runtime symlink must target an internal regular file: ' + str(relative))
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError('runtime contains non-file: ' + str(relative))
        # Normalize internal interpreter aliases to one regular executable in the zip.
        if relative.parts[0] == 'bin' and relative.as_posix() != 'bin/python3':
            if path.samefile(root / 'bin/python3'):
                continue
            raise ValueError('unexpected runtime executable: ' + str(relative))
        # Accept only interpreter, stdlib/dynamic libraries and licensing files.
        license_file = path.name.upper().startswith(('LICENSE', 'COPYING', 'NOTICE'))
        if not (relative.parts[0] == 'lib' or
                (relative.parts[0] == 'bin' and path.name.startswith('python3')) or license_file):
            raise ValueError('unexpected runtime file: ' + str(relative))
        files[relative.as_posix()] = (path.read_bytes(), 0o755 if os.access(path, os.X_OK) else 0o644)
    if not any(Path(name).name.upper().startswith(('LICENSE', 'COPYING')) for name in files):
        raise ValueError('runtime Python license missing')
    if not any(name.startswith('lib/python3.') and '/encodings/' in name for name in files):
        raise ValueError('incomplete runtime: standard library missing')
    if not files['bin/python3'][1] & 0o111:
        raise ValueError('runtime bin/python3 is not executable')
    # Probe the exact bytes to be packaged after relocation, with no Python environment.
    with tempfile.TemporaryDirectory(prefix='owner relocated runtime ') as temp:
        relocated = Path(temp) / 'runtime with spaces'
        for name, (data, mode) in files.items():
            target = relocated / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(mode)
        home = Path(temp) / 'empty-home'
        home.mkdir()
        try:
            result = subprocess.run([str(relocated / 'bin/python3'), '-I', '-S', '-c', PROBE],
                                    env={'HOME': str(home), 'PATH': '/nonexistent'}, cwd=temp,
                                    capture_output=True, text=True, timeout=30, check=True)
            metadata = json.loads(result.stdout)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            raise ValueError('runtime relocation/stdlib probe failed: ' + str(exc)) from exc
        if (metadata.get('implementation') != 'CPython' or metadata.get('system') != 'Darwin'
                or metadata.get('architecture') != architecture):
            raise ValueError('runtime architecture/platform mismatch: ' + str(metadata))
        if any(Path(metadata[key]).resolve() != relocated.resolve() for key in ('prefix', 'base_prefix')):
            raise ValueError('runtime still depends on original Python prefix')
        metadata.pop('prefix')
        metadata.pop('base_prefix')
    return files, metadata
