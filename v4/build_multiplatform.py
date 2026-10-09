#!/usr/bin/env python3
"""Package only Crowd's local workbench; external MediaCrawler is not bundled."""
import argparse
import hashlib
from pathlib import Path
import zipfile


def build(source, output):
    names = ('mc_runner.py', 'dashboard.py', 'dashboard.html', '打开工作台.command', 'README.md')
    files = {name: (source / name).read_bytes() for name in names}
    files['SHA256SUMS.txt'] = ''.join(
        hashlib.sha256(data).hexdigest() + '  ' + name + '\n'
        for name, data in sorted(files.items())
    ).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w') as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo('多平台采集/' + name, (2026, 10, 9, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith('.command') else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(digest + '  ' + output.name + '\n')
    print(digest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.output)
