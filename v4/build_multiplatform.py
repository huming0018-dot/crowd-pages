#!/usr/bin/env python3
"""Build the local Owner workbench from committed Crowd runtime files only."""
import argparse
import hashlib
import io
from pathlib import Path
import subprocess
import tarfile
import zipfile


SOURCE_DIR = Path('server/crowd/v4/multiplatform')
METADATA = {
    'BRIDGE-DEPENDENCIES.lock', 'DEPENDENCIES.json', 'DEPENDENCY-SHA.json',
    'NODE-SHA.json', 'PRO-LOCAL-SOURCE-PINS.json', 'SIGN-SOURCE-SHA.json',
    'capability-ledger.json',
}
REQUIRED = {
    'dashboard.py', 'dashboard.html', 'mc_runner.py', 'cloud_sync.py',
    'owner_tasks.py', 'account_sessions.py', 'run_diagnostics.py',
    'install_machine_node.py', 'prepare_machine_node.py',
    '打开工作台.command', 'README.md',
    'analysis-ui.js', 'owner-ui.js', 'results-ui.js', 'media-ui.js',
    'accounts-ui.js', 'cloud-ui.js', 'fleet-ui.js',
    'node-capabilities-ui.js', 'knowledge-ui.js',
}


def runtime_file(name):
    if name.startswith('test_') or name.endswith(('_test.py', '_test.js', '_test.mjs')):
        return False
    if name.endswith('.py'):
        return not name.startswith('probe_')
    return name.endswith(('.js', '.mjs')) or name in METADATA | {'dashboard.html', '打开工作台.command', 'README.md'}


def committed_files(source, revision):
    source = source.resolve()
    repo = Path(subprocess.check_output(['git', '-C', str(source), 'rev-parse', '--show-toplevel'], text=True).strip()).resolve()
    if source.relative_to(repo) != SOURCE_DIR:
        raise ValueError('source must be the Crowd multiplatform directory')
    commit = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', '--verify', revision + '^{commit}'], text=True).strip()
    archive = subprocess.check_output(['git', '-C', str(repo), 'archive', '--format=tar', commit, str(SOURCE_DIR)])
    files = {}
    with tarfile.open(fileobj=io.BytesIO(archive)) as tree:
        for item in tree:
            path = Path(item.name)
            if not item.isfile() or path.parent != SOURCE_DIR or not runtime_file(path.name):
                continue
            files[path.name] = tree.extractfile(item).read()
    missing = REQUIRED - files.keys()
    if missing:
        raise ValueError('missing committed runtime files: ' + ', '.join(sorted(missing)))
    return commit, files


def build(source, output, revision='HEAD'):
    commit, files = committed_files(source, revision)
    files['SOURCE-COMMIT.txt'] = (commit + '\n').encode()
    files['SHA256SUMS.txt'] = ''.join(
        hashlib.sha256(data).hexdigest() + '  ' + name + '\n'
        for name, data in sorted(files.items())
    ).encode()
    output = Path(output)
    checksum = output.with_suffix('.zip.sha256')
    if output.exists() or checksum.exists():
        raise FileExistsError('package or checksum already exists')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x') as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo('多平台采集/' + name, (2026, 10, 28, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith('.command') else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    with checksum.open('x') as stream:
        stream.write(digest + '  ' + output.name + '\n')
    print(digest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--revision', default='HEAD')
    args = parser.parse_args()
    build(args.source, args.output, args.revision)
