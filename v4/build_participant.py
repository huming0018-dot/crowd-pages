#!/usr/bin/env python3
"""Build the ordinary participant Mac installer from a reviewed extension ZIP."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def extension_files(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('duplicate archive entry')
        if any(PurePosixPath(n).is_absolute() or '..' in PurePosixPath(n).parts or '\\' in n for n in names):
            raise ValueError('unsafe archive path')
        if any((i.external_attr >> 16) & 0o170000 == 0o120000 for i in archive.infolist()):
            raise ValueError('symlink archive entry')
        if sum(i.file_size for i in archive.infolist()) > 16 * 1024 * 1024:
            raise ValueError('extension too large')
        files = {name: archive.read(name) for name in names if not name.endswith('/')}
    manifest = json.loads(files['manifest.json'])
    version = manifest.get('version', '')
    if not re.fullmatch(r'4\.2\.[0-9]{1,3}', version):
        raise ValueError('invalid participant version')
    if 'release.json' not in files:
        raise ValueError('release manifest required')
    return version, files


def pack(path, files):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 10, 14, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith('.command') or name == 'crowd-v4-participant-updater' else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    checksum = digest(path.read_bytes())
    path.with_suffix('.zip.sha256').write_text(checksum + '  ' + path.name + '\n')
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': checksum}


def build(extension, helper, output):
    extension, helper, output = Path(extension).resolve(), Path(helper).resolve(), Path(output).resolve()
    version, files = extension_files(extension)
    if set(subprocess.check_output(['lipo', '-archs', str(helper)], text=True).split()) != {'x86_64', 'arm64'}:
        raise ValueError('universal Mac helper required')
    subprocess.run(['codesign', '--verify', '--strict', str(helper)], check=True, capture_output=True)
    # The production helper enforces the original extension ID and exact capability shape.
    with tempfile.TemporaryDirectory(prefix='crowd-participant-package-') as temporary:
        directory = Path(temporary)
        for name, content in files.items():
            destination = directory / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        subprocess.run([str(helper), '--check-install', str(directory)], check=True, capture_output=True)
    archive_name = f'crowd-v{version}-participant-extension.zip'
    helper_name = 'crowd-v4-participant-updater'
    base = {
        helper_name: helper.read_bytes(),
        'reconnect.command': (ROOT / 'participant/reconnect.command').read_bytes(),
        'MIGRATION-README.md': (ROOT / 'participant/MIGRATION-README.md').read_bytes(),
    }
    base['MIGRATE-SHA256.txt'] = (digest(base[helper_name]) + '  ' + helper_name + '\n').encode()
    install = {**base, archive_name: extension.read_bytes()}
    install['install.command'] = (ROOT / 'participant/install.command').read_text().replace('@EXTENSION_ARCHIVE@', archive_name).encode()
    install['INSTALL-SHA256.txt'] = ''.join(digest(install[name]) + '  ' + name + '\n' for name in (archive_name, helper_name)).encode()
    result = {'version': version, 'extension_sha256': digest(extension.read_bytes()), 'helper_sha256': digest(helper.read_bytes()),
              'mac': pack(output, install),
              'reconnect': pack(output.with_name(f'crowd-v{version}-existing-helper-reconnect.zip'), base)}
    output.with_suffix('.build.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--extension', type=Path, required=True)
    parser.add_argument('--helper', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    options = parser.parse_args()
    print(json.dumps(build(options.extension, options.helper, options.output)))
