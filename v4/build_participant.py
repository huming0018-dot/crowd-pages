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
R3_BASE_EXTENSION_SHA256 = '0f65751fd0c3be90c4af6c8e434aa4a628d5c27af7e0ae47c25668686c08cc57'
R3_BASE_MIGRATION_PROFILE = ('r3-base-helper-v1 channel-participants-base.json '
    'b653d69911655b1294e3ef7f63c18f229ba13b864a205bb2609d838412d91988 '
    'db457d8604f9902c687c82ffc15d7af01eea3e2b289ca32ab60fd8c1b979b187')


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
            info.external_attr = (0o100755 if name.endswith('.command') or PurePosixPath(name).name == 'crowd-v4-participant-updater' else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    checksum = digest(path.read_bytes())
    path.with_suffix('.zip.sha256').write_text(checksum + '  ' + path.name + '\n')
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': checksum}


def build(extension, helper, output, pro_runtime=None, r3_base_migration=False, fixture_only=False, fresh_only=False):
    extension, helper, output = Path(extension).resolve(), Path(helper).resolve(), Path(output).resolve()
    version, files = extension_files(extension)
    helper_bytes = helper.read_bytes()
    if fixture_only and not r3_base_migration:
        raise ValueError('fixture-only package requires R3 base migration')
    testing_helper = b'CROWD_TEST_INSTALL_HOME' in helper_bytes
    if testing_helper != fixture_only:
        raise ValueError('TESTING helper requires --fixture-only' if testing_helper else 'fixture package requires a TESTING helper')
    if fresh_only:
        release = json.loads(files['release.json'])
        if (r3_base_migration or pro_runtime is not None or release.get('profile') != 'participant'
                or release.get('execution_engine') != 'crowd-base-dom-v1'
                or b'channel-participants-base.json' not in helper_bytes
                or b'crowd-base-dom-v1' not in helper_bytes):
            raise ValueError('fresh base package requires current base extension and helper without Pro runtime')
    if r3_base_migration:
        if pro_runtime is not None or version != '4.2.94' or digest(extension.read_bytes()) != R3_BASE_EXTENSION_SHA256:
            raise ValueError('R3 base migration requires exact frozen extension and no Pro runtime')
    if set(subprocess.check_output(['lipo', '-archs', str(helper)], text=True).split()) != {'x86_64', 'arm64'}:
        raise ValueError('universal Mac helper required')
    subprocess.run(['codesign', '--verify', '--strict', str(helper)], check=True, capture_output=True)
    if r3_base_migration and subprocess.check_output([str(helper), '--migration-profile'], text=True).strip() != R3_BASE_MIGRATION_PROFILE + (' testing' if fixture_only else ' release'):
        raise ValueError('helper is not pinned R3 base migration')
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
    # Reconnect ZIPs omit runtime; capability belongs to their checksum-pinned helper.
    supports_pro = all(verb in helper_bytes for verb in (b'pro_hello', b'pro_start', b'pro_status', b'pro_stop'))
    if fresh_only and supports_pro:
        raise ValueError('fresh base package cannot use a Pro helper')
    native_protocol = 'participant_pro_v2' if supports_pro else 'ota_only'
    extension_key = json.loads(files['manifest.json']).get('key', '')
    if not re.fullmatch(r'[A-Za-z0-9+/=]+', extension_key):
        raise ValueError('participant manifest key required')
    base = {
        helper_name: helper_bytes,
        'reconnect.command': (ROOT / 'participant/reconnect.command').read_text().replace('@NATIVE_PROTOCOL@', native_protocol).replace('@R3_BASE_MIGRATION@', str(r3_base_migration).lower()).replace('@FIXTURE_ONLY@', str(fixture_only).lower()).encode(),
        'browser-preflight.command': (ROOT / 'participant/browser-preflight.command').read_bytes(),
        'MIGRATION-README.md': (ROOT / 'participant/MIGRATION-README.md').read_bytes(),
        'browser-preflight.js': (ROOT / 'participant/browser-preflight.js').read_text().replace('@EXTENSION_KEY@', extension_key).encode(),
    }
    if fresh_only:
        base['reconnect.command'] = "#!/bin/zsh\nprint '此包仅供全新安装，已有安装请联系邀请人接续。'\nexit 1\n".encode()
    # Optional own-code runtime. Licensed SDK, venv, profiles and bindings stay local.
    pro_files = {}
    if pro_runtime is not None:
        runtime = Path(pro_runtime).resolve()
        metadata = json.loads((runtime / 'PRO-RUNTIME.json').read_bytes())
        if set(metadata) != {'schema', 'files'} or metadata['schema'] != 'crowd-participant-pro-runtime-v1':
            raise ValueError('invalid Pro own-runtime manifest')
        names = metadata['files']
        if not isinstance(names, dict) or not 1 <= len(names) <= 128 or 'participant_pro_native.py' not in names:
            raise ValueError('incomplete Pro own-runtime manifest')
        for name, expected in names.items():
            if not ((re.fullmatch(r'[a-z][a-z0-9_]*[.]py', name) and not name.startswith('test_')) or name in {'SIGN-SOURCE-SHA.json','DEPENDENCIES.json','DEPENDENCY-SHA.json','NODE-SHA.json','PRO-LOCAL-SOURCE-PINS.json','pro_xhs_download.mjs'}):
                raise ValueError('own runtime modules and resources only')
            path = runtime / name
            if path.is_symlink() or not path.is_file() or digest(path.read_bytes()) != expected:
                raise ValueError('Pro own-runtime hash mismatch')
            pro_files['pro-runtime/' + name] = path.read_bytes()
        pro_files['pro-runtime/PRO-RUNTIME.json'] = (runtime / 'PRO-RUNTIME.json').read_bytes()
        pro_files['portable_node.py'] = pro_files['pro-runtime/portable_node.py']
        pro_files['PRO-LOCAL-SOURCE-PINS.json'] = pro_files['pro-runtime/PRO-LOCAL-SOURCE-PINS.json']
        pro_files['configure-pro.py'] = (ROOT / 'participant/configure-pro.py').read_bytes()
        for name in ('bootstrap-pro-tools.command', 'prepare-pro-dependencies.py', 'prepare-and-configure-pro.py', 'prepare-pro-downloader.py', 'pro-binding-continuation.py'):
            pro_files[name] = (ROOT / 'participant' / name).read_bytes()
    base['MIGRATE-SHA256.txt'] = ''.join(digest(base[name]) + '  ' + name + '\n' for name in (helper_name, 'browser-preflight.js', 'browser-preflight.command', 'reconnect.command')).encode()
    install = {**base, **pro_files, archive_name: extension.read_bytes()}
    install['install.command'] = (ROOT / 'participant/install.command').read_text().replace('@EXTENSION_ARCHIVE@', archive_name).replace('@NATIVE_PROTOCOL@', native_protocol).replace('@R3_BASE_MIGRATION@', str(r3_base_migration).lower()).replace('@FIXTURE_ONLY@', str(fixture_only).lower()).replace('@FRESH_ONLY@', str(fresh_only).lower()).encode()
    install['INSTALL-SHA256.txt'] = ''.join(digest(install[name]) + '  ' + name + '\n' for name in (archive_name, helper_name, 'browser-preflight.js', 'browser-preflight.command', 'reconnect.command', 'install.command', *sorted(pro_files))).encode()
    guide = (ROOT / 'participant/安装说明.html').read_text().replace('@VERSION@', version)
    if fresh_only:
        guide = guide.replace('已有标准安装会自动接续，不需要重装扩展。', '本包仅用于全新安装；发现旧安装会停止。').replace('已有标准参与者安装会接续原目录和身份。', '本包发现已有标准参与者安装会拒绝覆盖，并保留原目录和身份。')
    errors = {
        'os': ('这台 Mac 的系统版本还不够', '本包需要 macOS 14 或更新系统。此次未安装，请先更新系统或联系邀请人。'),
        'chrome': ('请先安装或更新 Google Chrome', '没有安装 Chrome：先从 <a href="https://www.google.com/chrome/" rel="noreferrer" target="_blank">Google 官网下载安装</a>。已经安装：打开 Chrome 菜单中的“关于 Google Chrome”完成更新，需达到120或更新版本。完成后重新双击“开始安装.command”。'),
        'integrity': ('安装包没有完整解压，或校验未通过', '重新从邀请人提供的地址下载，完整解压整个包。不要移动其中单个文件；原安装未覆盖。'),
        'existing': ('找到了原安装，需要先接续', '原目录和更新助手记录不完整。为保护原身份，本次没有覆盖。请把终端最后的提示交给邀请人核对。'),
        'incompatible': ('原版本需要使用对应的更新方式', '原扩展的权限或文件与标准参与者版不兼容（例如旧 KOL 版）。已经保留原样，请联系邀请人；不要卸载或清数据。'),
        'busy': ('这次还没有完成安装或接续', '可能仍在采集、更新或等待系统确认。请保留终端最后的错误文字，等原任务空闲后重试；仍失败则联系邀请人。'),
        'browser-legacy': ('Chrome 中已有旧版众包插件，先保留它', '旧版仍可能有任务或待回传记录。本次没有覆盖，也没有迁移旧身份。请把此提示交给邀请人安全接续；不要卸载旧插件、删除数据或另行报名。'),
        'browser-existing': ('Chrome 原插件需要接续原目录', '浏览器登记的插件目录与更新助手不一致。已保留原样，请联系邀请人核对；不要重新加载另一个目录。'),
        'browser-unknown': ('需要先确认 Chrome 原来的安装', '无法安全读取原安装信息。本次没有安装或接续，请把此提示交给邀请人；不要清空浏览器、卸载插件或重复报名。'),
    }
    def render(mode, error=None):
        title, message = errors.get(error, ('先看安装窗口最后一条提示', '原资料保留。请把最后的错误文字交给邀请人，按原因处理。'))
        return guide.replace('@MODE@', mode).replace('@ERROR_MESSAGE@', title).replace('@ERROR_NEXT@', message).encode()
    entry = (ROOT / 'participant/start.command').read_bytes()
    # Keep one visible executable entry; signed extension/helper bytes stay intact.
    instructions = (ROOT / 'participant/安装说明.md').read_text().replace('@VERSION@', version)
    if fresh_only:
        instructions = instructions.replace('已有标准参与者安装会自动接续。', '本包只用于全新参与者；已有标准参与者安装会拒绝覆盖并保留原身份。').replace('Pro 采集还需要本设备已有合法 SDK 和账号绑定。安装器会按官方锁文件准备已配置的依赖；缺失时明确显示未就绪，不替换原账号。依赖安装完成不代表已经登录或开始采集。', '本基础包不需要 Pro SDK、账号绑定或额外依赖。基础正文能力仍须本人完成 Chrome 加载与登录后才可使用。')
    visible = {'开始安装.command': entry, '安装说明.html': render('intro'),
               '安装说明.md': instructions.encode()}
    support = {name + '.html': render(mode) for name, mode in
               [('new', 'new'), ('existing', 'existing'), ('help', 'help')]}
    support.update({'help-' + code + '.html': render('help', code) for code in errors})
    install.update(support)
    # The small legacy reconnect ZIP also gets one entrance, but never installs a new identity.
    reconnect = {**base, **support}
    reconnect['install.command'] = ("#!/bin/zsh\nprint '此包仅供隔离验收，不能在参与者电脑上安装。'\nexit 1\n" if fixture_only else
        "#!/bin/zsh\nset -eu\nPACKAGE_DIR=\"${0:A:h}\"\ncd \"$PACKAGE_DIR\"\n"
        "if ./reconnect.command; then /usr/bin/open \"$PACKAGE_DIR/existing.html\" || true; "
        "else /usr/bin/open \"$PACKAGE_DIR/help.html\" || true; exit 1; fi\n").encode()
    source_files = ['build_participant.py', 'participant/install.command', 'participant/browser-preflight.js', 'participant/browser-preflight.command', 'participant/reconnect.command',
                    'participant/configure-pro.py', 'participant/bootstrap-pro-tools.command', 'participant/prepare-pro-dependencies.py', 'participant/prepare-and-configure-pro.py', 'participant/prepare-pro-downloader.py', 'participant/pro-binding-continuation.py', 'participant/start.command', 'participant/安装说明.html', 'participant/安装说明.md', 'participant/MIGRATION-README.md']
    provenance = {'package_revision': 4 if r3_base_migration else 3, 'version': version, 'extension_sha256': digest(extension.read_bytes()), 'native_protocol': native_protocol,
                  'helper_sha256': digest(helper.read_bytes()), 'pro_runtime_files': {name: digest(data) for name, data in pro_files.items()},
                  'source_sha256': {name: digest((ROOT / name).read_bytes()) for name in source_files}}
    if fresh_only:
        provenance['install_scope'] = 'fresh_base_only'
    if r3_base_migration:
        provenance['migration_profile'] = 'r3-base-helper-v1'
        provenance['fixture_only'] = fixture_only
    install['package-source.json'] = (json.dumps(provenance, ensure_ascii=False, indent=2) + '\n').encode()
    reconnect['package-source.json'] = install['package-source.json']
    wrap = lambda contents: {**visible, **{'.crowd-support/' + name: data for name, data in contents.items()}}
    reconnect_name = output.stem + '-reconnect.zip' if r3_base_migration else f'crowd-v{version}-existing-helper-reconnect.zip'
    result = {**provenance, 'mac': pack(output, wrap(install))}
    if not fresh_only:
        result['reconnect'] = pack(output.parent / '.internal' / reconnect_name, wrap(reconnect))
    output.with_suffix('.build.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--extension', type=Path, required=True)
    parser.add_argument('--helper', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pro-runtime', type=Path)
    parser.add_argument('--r3-base-migration', action='store_true')
    parser.add_argument('--fixture-only', action='store_true')
    parser.add_argument('--fresh-only', action='store_true')
    options = parser.parse_args()
    print(json.dumps(build(options.extension, options.helper, options.output, options.pro_runtime,
        options.r3_base_migration, options.fixture_only, options.fresh_only)))
