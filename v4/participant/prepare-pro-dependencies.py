#!/usr/bin/env python3
"""Install only authorized local Pro projects using their unchanged official uv locks.

No SDK download, account operation, service startup, or settings/config mutation.
The installer hands a verified result to the existing configure-pro boundary.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import urllib.request
import portable_node
from urllib.parse import urlsplit

SCHEMA = 'crowd-pro-dependency-input-v1'
PROJECT_KEYS = {'root', 'commit', 'files', 'python', 'python_sha256'}
FILES = {'pyproject.toml', 'uv.lock', 'LICENSE', 'README.md'}
PROTOCOL = 'vox-acquisition-v1'


def need(ok, reason='dependency_input_invalid'):
    if not ok:
        raise ValueError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def read(path, limit=65536):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        s = os.fstat(fd)
        need(stat.S_ISREG(s.st_mode) and s.st_uid == os.getuid() and not s.st_mode & 0o077,
             'dependency_input_permissions')
        need(0 < s.st_size <= limit)
        raw = os.read(fd, limit + 1)
        a = os.fstat(fd)
        need(len(raw) == s.st_size and (s.st_size, s.st_mtime_ns, s.st_ctime_ns) ==
             (a.st_size, a.st_mtime_ns, a.st_ctime_ns))
        return raw
    finally:
        os.close(fd)


def write_once(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(encode(value)); f.flush(); os.fsync(f.fileno())
    fd = os.open(Path(path).parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def execute(argv, *, env, cwd, timeout=600):
    # Never include stdout/stderr in errors: package tools may print private URLs.
    with subprocess.Popen(argv, env=env, cwd=cwd, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, start_new_session=True) as child:
        try:
            stdout, _ = child.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.communicate()
            raise ValueError('dependency_command_timeout') from None
        need(child.returncode == 0, 'dependency_command_failed')
        need(len(stdout) <= 65536, 'dependency_output_invalid')
        return stdout


def environment():
    return {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'HOME': str(Path.home()),
            'PYTHONDONTWRITEBYTECODE': '1', 'UV_NO_PROGRESS': '1',
            'UV_PYTHON_DOWNLOADS': 'never', 'UV_KEYRING_PROVIDER': 'disabled'}


def regular(path, executable=False):
    path = Path(path)
    need(path.is_absolute() and path.resolve() == path and path.is_file())
    need(path.stat().st_uid == os.getuid() and not path.stat().st_mode & 0o022)
    if executable:
        need(os.access(path, os.X_OK))
    return path


def plan(descriptor, helper, run=execute):
    value = json.loads(read(descriptor))
    need(type(value) is dict and set(value) == {'schema', 'uv', 'uv_sha256', 'projects'})
    need(value['schema'] == SCHEMA and set(value['projects']) == {'pro', 'signer'})
    uv = regular(value['uv'], True)
    need(digest(uv.read_bytes()) == value['uv_sha256'], 'dependency_tool_changed')
    helper = Path(helper)
    need(helper.is_absolute() and helper.resolve() == helper and helper.is_dir())
    need(helper.stat().st_uid == os.getuid() and not helper.stat().st_mode & 0o077)
    env = environment()
    for name, project in value['projects'].items():
        need(type(project) is dict and set(project) == PROJECT_KEYS)
        source = Path(project['root'])
        need(source.is_absolute() and source.resolve() == source and source.is_dir())
        need(re.fullmatch('[a-f0-9]{40}', project['commit']) is not None)
        commit = run(['/usr/bin/git', '-C', str(source), 'rev-parse', 'HEAD'], env=env, cwd=source, timeout=10).decode().strip()
        need(commit == project['commit'], 'dependency_source_changed')
        dirty = run(['/usr/bin/git', '-C', str(source), 'status', '--porcelain', '--untracked-files=normal'], env=env, cwd=source, timeout=10)
        need(not dirty, 'dependency_source_changed')
        need(type(project['files']) is dict and set(project['files']) == FILES)
        for filename, expected in project['files'].items():
            path = regular(source / filename)
            need(digest(path.read_bytes()) == expected, 'dependency_source_changed')
        python = regular(project['python'], True)
        need(digest(python.read_bytes()) == project['python_sha256'], 'dependency_interpreter_changed')
        minor = 11 if name == 'pro' else 12
        run([str(python), '-I', '-B', '-c',
             'import sys;assert sys.version_info[0:2]==(3,%d)' % minor],
            env=env, cwd=source, timeout=15)
    # The path is final from the start: venvs are never renamed/copied after creation.
    key = digest(encode(value))
    return {'schema': 'crowd-pro-dependency-plan-v1', 'key': key, 'input': value,
            'target': str(helper / 'pro-environments' / key)}


def safe_directory(path):
    path = Path(path)
    if not path.exists():
        path.mkdir(mode=0o700)
    need(path.is_dir() and path.resolve() == path and path.stat().st_uid == os.getuid()
         and not path.stat().st_mode & 0o077, 'dependency_target_invalid')


def probes(p, run=execute):
    env = environment()
    for name, minor in [('pro', 11), ('signer', 12)]:
        root = p['input']['projects'][name]['root']
        python = Path(p['target']) / name / 'bin/python'
        # uv creates bin/python as a symlink to the explicitly pinned interpreter.
        need(python.is_file() and python.resolve() == Path(p['input']['projects'][name]['python']),
             'dependency_environment_missing')
        script = ('import sys,json;print(json.dumps({"version":list(sys.version_info[:2]),"prefix":sys.prefix}))')
        v = json.loads(run([str(python), '-I', '-B', '-c', script], env=env, cwd=root, timeout=15))
        need(v == {'version': [3, minor], 'prefix': str(Path(p['target']) / name)}, 'dependency_environment_invalid')
        if name == 'pro':
            caps = json.loads(run([str(python), '-B', str(Path(root) / 'main.py'), '--acquisition-capabilities'], env=env, cwd=root, timeout=15))
            need(type(caps) is dict and caps.get('schema_version') == PROTOCOL
                 and 'xhs' in caps.get('platforms', []), 'dependency_protocol_invalid')
        else:
            # No app import: app.py starts browser managers in its main path.
            run([str(python), '-I', '-B', '-c', 'import tornado.web,playwright.async_api,httpx,pydantic,execjs,xhshow'], env=env, cwd=root, timeout=15)


def signer_health(sign_url):
    # Diagnostic only: the caller supplies its validated original binding.
    try:
        url = urlsplit(sign_url)
        valid = (url.scheme == 'http' and url.hostname in ('127.0.0.1', 'localhost')
                 and url.port and not url.username and not url.password
                 and url.path in ('', '/') and not url.query and not url.fragment)
    except (TypeError, ValueError):
        valid = False
    need(valid, 'signer_binding_invalid')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(sign_url.rstrip('/') + '/signsrv/pong', timeout=3) as response:
        need(response.status == 200, 'signer_not_ready')
        raw = response.read(4097)
    need(len(raw) <= 4096, 'signer_not_ready')
    result = json.loads(raw)
    need(type(result) is dict and result.get('isok') is True and type(result.get('biz_code')) is int
         and result['biz_code'] == 0 and result.get('data') == {'message': 'pong'}, 'signer_not_ready')


def prepare(descriptor, helper, *, offline=False, run=execute):
    p = plan(descriptor, helper, run)
    helper = Path(helper)
    locks = []
    try:
        for name in ('update.lock', 'pro.lock'):
            fd = os.open(helper / name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            locks.append(fd); fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = helper / 'pro-state.json'
        if state.exists():
            need(json.loads(read(state)).get('busy') is False, 'dependency_host_busy')
        safe_directory(helper / 'pro-environments')
        target = Path(p['target'])
        if target.exists():
            safe_directory(target)
            receipt = json.loads(read(target / 'RESULT.json')) if (target / 'RESULT.json').exists() else None
            need(receipt == {'state': 'prepared', 'key': p['key'], 'offline': offline}, 'dependency_attempt_unknown')
            probes(p, run)
            portable_node.prepare(helper, offline=offline)
            return {'state': 'prepared', 'key': p['key'], 'python': str(target / 'pro/bin/python'), 'authenticated': False}
        safe_directory(target)
        write_once(target / 'INTENT.json', {'plan': p, 'offline': offline})
        # From here, any error preserves INTENT/no RESULT. Never resume an uncertain install.
        for name, project in p['input']['projects'].items():
            env = environment(); env['UV_PROJECT_ENVIRONMENT'] = str(target / name)
            argv = [p['input']['uv'], 'sync', '--frozen', '--no-config', '--no-python-downloads',
                    '--python', project['python'], '--project', project['root']]
            if offline:
                argv.append('--offline')
            try:
                run(argv, env=env, cwd=project['root'])
            except ValueError as error:
                if str(error) == 'dependency_command_failed':
                    raise ValueError('dependency_%s_sync_failed' % name) from None
                raise
            need(plan(descriptor, helper, run) == p, 'dependency_source_changed')
        portable_node.prepare(helper, offline=offline)
        probes(p, run)
        need(plan(descriptor, helper, run) == p, 'dependency_source_changed')
        write_once(target / 'RESULT.json', {'state': 'prepared', 'key': p['key'], 'offline': offline})
        return {'state': 'prepared', 'key': p['key'], 'python': str(target / 'pro/bin/python'), 'authenticated': False}
    finally:
        for fd in reversed(locks):
            os.close(fd)


def check(descriptor, helper, run=execute, health=None):
    p = plan(descriptor, helper, run)
    receipt = json.loads(read(Path(p['target']) / 'RESULT.json'))
    need(receipt.get('state') == 'prepared' and receipt.get('key') == p['key'], 'dependency_attempt_unknown')
    need(health is not None, 'signer_binding_required')
    probes(p, run); portable_node.check(helper); health()
    need(plan(descriptor, helper, run) == p, 'dependency_source_changed')
    return {'state': 'ready', 'key': p['key'], 'python': str(Path(p['target']) / 'pro/bin/python'), 'authenticated': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['plan', 'prepare', 'check'])
    parser.add_argument('--descriptor', type=Path, required=True)
    parser.add_argument('--helper-root', type=Path, default=Path.home() / 'Library/Application Support/CrowdV4Updater')
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    try:
        if args.action == 'plan':
            result = plan(args.descriptor, args.helper_root)
        elif args.action == 'prepare':
            result = prepare(args.descriptor, args.helper_root, offline=args.offline)
        else:
            result = check(args.descriptor, args.helper_root)
        print(json.dumps(result)); return 0
    except Exception as e:
        reason = str(e) if isinstance(e, ValueError) and re.fullmatch('[a-z_]{1,80}', str(e)) else 'dependency_prepare_failed'
        print(json.dumps({'state': 'not_ready', 'error': reason})); return 1


if __name__ == '__main__':
    sys.exit(main())
