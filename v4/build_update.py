#!/usr/bin/env python3
"""Build an existing-participant update; no invite, enrollment or browser policy changes."""
import argparse
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

ROOT = Path(__file__).resolve().parent

def build(source, output):
    with zipfile.ZipFile(source) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or any(PurePosixPath(n).is_absolute() or '..' in PurePosixPath(n).parts or '\\' in n for n in names):
            raise ValueError('Unsafe archive')
        files = {n: archive.read(n) for n in names}
    release = json.loads(files['release.json'])
    manifest = json.loads(files['manifest.json'])
    version = manifest['version']
    if release.get('repository') != 'huming0018-dot/crawler-extension' or release.get('protocol') != 'crowd_v4' or release['version'] != version or not re.fullmatch(r'4\.\d+\.\d+', version):
        raise ValueError('Wrong source')
    if set(files) != set(release['files']) | {'release.json'} or any(hashlib.sha256(files[n]).hexdigest() != h for n, h in release['files'].items()):
        raise ValueError('Integrity mismatch')
    config = files['src/config.js'].decode()
    conf = json.loads(config.removeprefix('globalThis.CROWD_CONFIG = ').strip().removesuffix(';'))
    if set(conf) != {'url', 'key', 'portal'} or release.get('configuration_mode') == 'private_invite' or 'update_url' in manifest:
        raise ValueError('Only the public-config canonical source may be distributed')
    key = conf['key']
    if key.startswith('eyJ'):
        payload = key.split('.')[1]
        if json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload)%4))).get('role') != 'anon':
            raise ValueError('Public key only')
    elif not key.startswith('sb_publishable_'):
        raise ValueError('Public key only')
    worker = 'src/background_v' + version.replace('.', '_') + '.js'
    if manifest['background'] != {'service_worker': worker} or worker not in files:
        raise ValueError('Worker mismatch')
    launcher = (ROOT / 'crowd-extension-mac.command').read_bytes()
    wrapper = b'#!/bin/bash\nset -euo pipefail\nkit_dir=$(cd "$(dirname "$0")" && pwd)\nexec /bin/bash "$kit_dir/prepare.command" --update-only\n'
    guide = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>众包插件更新 {version}</title>
<h1>更新已有插件至 {version}</h1><p>只用于之前已参加的原 Mac、Chrome/Edge 和个人资料。无需 Codex、不重新报名、不卸载。</p>
<ol><li>运行本包更新命令，自动找到并更新原插件文件。</li><li>在自动打开的扩展管理页，点击本插件的刷新图标。</li><li>打开原插件，确认 {version}，点击继续采集。若要求登录小红书或处理验证，请本人处理后继续。</li></ol>
<p>本包不含邀请、密码或参与身份。身份与进度保存在浏览器原插件存储，更新不删除。若未找到原 v4 安装会退出，不替用户创建新身份。</p>
<p>本版修复网页脚本接入时机和导航后恢复，重试保留上一轮诊断；保留访问预算及风控暂停。中台负责检查新版诊断和实际回传；固定页面测试已通过，真实平台验收仍在进行。本次不扩大招募。</p></html>'''
    payload = {'插件/' + n: b for n, b in files.items()}
    payload.update({'prepare.command': launcher, '更新.command': wrapper, '先打开安装说明.html': guide.encode()})
    payload['SHA256SUMS.txt'] = ''.join(hashlib.sha256(b).hexdigest() + '  ' + n + '\n' for n, b in sorted(payload.items())).encode()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(payload.items()):
            item = zipfile.ZipInfo('Mac众包更新/' + name, (2026, 10, 8, 0, 0, 0))
            item.create_system = 3
            item.external_attr = (0o100755 if name.endswith('.command') else 0o100644) << 16
            item.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(item, data)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(digest + '  ' + output.name + '\n')
    return {'version': version, 'sha256': digest, 'bytes': output.stat().st_size, 'mode': 'existing_participant_update'}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output)))
