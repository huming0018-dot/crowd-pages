"""Local explicit installer continuation; never a native/extension command.

Existing settings are evidence, not overwritten. The original configure-pro dual
locks surround this transaction and its original config writer.
"""
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import sqlite3
import stat
import tempfile


def need(ok, code='dependency_binding_invalid'):
    if not ok:
        raise ValueError(code)


def encoded(value):
    return json.dumps(value, sort_keys=True).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    path = Path(path)
    need(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)))
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_uid == os.getuid() and not a.st_mode & 0o077 and 0 < a.st_size <= 65536)
        raw = os.read(fd, 65537); b = os.fstat(fd)
        need(len(raw) == a.st_size and (a.st_ino, a.st_size, a.st_mtime_ns, a.st_ctime_ns) == (b.st_ino, b.st_size, b.st_mtime_ns, b.st_ctime_ns))
        return raw
    finally:
        os.close(fd)


def once(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        need(stream.write(raw) == len(raw), 'dependency_binding_short_write'); stream.flush(); os.fsync(stream.fileno())
    sync(Path(path).parent)


def sync(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def replace(path, before, after):
    current = read(path) if path.exists() else None
    need(current == before, 'dependency_binding_cas_changed')
    if after is None:
        path.unlink(); sync(path.parent); return
    fd, temp = tempfile.mkstemp(prefix='.binding-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            need(stream.write(after) == len(after), 'dependency_binding_short_write'); stream.flush(); os.fsync(stream.fileno())
        need((read(path) if path.exists() else None) == before, 'dependency_binding_cas_changed')
        os.replace(temp, path); sync(path.parent)
    finally:
        if os.path.exists(temp): os.unlink(temp)


def signer_python_pin(path):
    resolved = Path(path).resolve(strict=True)
    fd = os.open(resolved, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid()
             and not before.st_mode & 0o022 and before.st_mode & 0o111
             and 0 < before.st_size <= 64 * 1024 * 1024, 'signer_python_invalid')
        digest = hashlib.sha256(); total = 0
        while True:
            block = os.read(fd, 65536)
            if not block: break
            total += len(block); need(total <= before.st_size, 'signer_python_changed')
            digest.update(block)
        after = os.fstat(fd)
        need(total == before.st_size and (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
             == (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'signer_python_changed')
        return str(resolved), digest.hexdigest()
    finally:
        os.close(fd)


class BindingContinuation:
    def __init__(self, deps, prepared, plan, settings, runtime, helper, *, max_api_requests=None):
        need(max_api_requests is None or type(max_api_requests) is int and 1 <= max_api_requests <= 100, 'operator_capacity_invalid')
        self.operator_max_api_requests = max_api_requests
        self.deps, self.prepared, self.plan = deps, prepared, plan
        self.settings, self.runtime, self.helper = Path(settings), Path(runtime).resolve(), Path(helper)
        self.original_raw = read(self.settings); self.original = json.loads(self.original_raw)
        need(set(self.original) == {'python', 'root', 'mc_root', 'session_id', 'max_api_requests', 'purpose'})
        pro_source = plan['input']['projects']['pro']['root']  # mc_root remains the original MC fallback.
        self.values = {**self.original, 'python': prepared['python']}
        if max_api_requests is not None: self.values['max_api_requests'] = max_api_requests
        self.root = Path(self.original['root']); self.session = self.root/'sessions'/self.original['session_id']
        self.executor = self.root/'pro-executor.json'; self.config = self.helper/'pro-config.json'
        self.executor_before = read(self.executor)
        need(json.loads(self.executor_before) in ({'root': pro_source, 'python': self.original['python']}, {'root': pro_source, 'python': prepared['python']}), 'dependency_binding_source_changed')
        self.executor_after = encoded({'root': pro_source, 'python': prepared['python']})
        self.config_before = read(self.config) if self.config.exists() else None
        if self.config_before is not None:
            old = json.loads(self.config_before)
            need(json.loads(self.executor_before).get('python') == old.get('python'), 'dependency_binding_source_changed')
            need(set(old) == set(self.original)|{'schema', 'entry', 'entry_sha256'}
                 and all(type(old[k]) is type(v) and old[k] == v for k,v in self.original.items() if k not in {'python','max_api_requests'})
                 and old['python'] in {self.original['python'],prepared['python']}
                 and type(old['max_api_requests']) is int and 1 <= old['max_api_requests'] <= 100, 'dependency_binding_scope_changed')
            # Installed capacity is durable current configuration, not an old task budget.
            # Omitting a new operator override preserves it on every later upgrade.
            if max_api_requests is None: self.values['max_api_requests'] = old['max_api_requests']
        manifest = json.loads((self.runtime/'PRO-RUNTIME.json').read_bytes())
        files = manifest['files']
        self.runtime_files = files
        need(manifest.get('schema') == 'crowd-participant-pro-runtime-v1' and set(manifest) == {'schema','files'} and type(files) is dict and 1 <= len(files) <= 128)
        for name, expected in files.items():
            need(type(name) is str and '/' not in name and not (self.runtime/name).is_symlink() and sha((self.runtime/name).read_bytes()) == expected, 'dependency_runtime_changed')
        key = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        entry = self.helper/'pro-runtime'/key/'participant_pro_native.py'
        self.expected = encoded({'schema': 'crowd-participant-pro-install-v1', **self.values, 'entry': str(entry), 'entry_sha256': files[entry.name]})
        self.evidence = self.helper/'pro-binding-continuations'/sha(encoded({'input':prepared['key'],'runtime':key,'settings':sha(self.original_raw), **({'max_api_requests':self.values['max_api_requests']} if max_api_requests is not None or self.values['max_api_requests'] != self.original['max_api_requests'] else {})}))
        self.completed = (self.evidence/'RESULT.json').exists()
        self.derived = self.evidence/'derived-settings.json'
        self.lock = None

    def matches(self, existing):
        return (self.config_before is not None and existing == json.loads(self.config_before)) or any(all(type(existing[k]) is type(v) and existing[k] == v for k,v in values.items()) for values in (self.original,self.values))

    def scope(self):
        need(read(self.settings) == self.original_raw, 'dependency_binding_scope_changed')
        identity = self.session/'identity.json'; binding = self.session/'pro-binding.json'
        need(json.loads(read(identity)) == {'platform': 'xhs'}, 'dependency_binding_scope_changed')
        # Reuse installed account/provider validation. No bridge HTTP or login.
        import sys
        sys.path.insert(0, str(self.runtime))
        try:
            from pro_executor import binding_for
            from account_sessions import safe_account_ref, _original_profile_reference
            value = binding_for(self.root, {'session_id': self.original['session_id'], 'platform': 'xhs'})
            need(set(value) == {'platform','client_id','cookiebridge_url','sign_url'}, 'dependency_binding_scope_changed')
            account = self.root/'accounts'/self.original['session_id']/'state.json'
            state = json.loads(read(account))
            need(state.get('session_id') == self.original['session_id'] and state.get('platform') == 'xhs' and type(state.get('account_ref')) is str and re.fullmatch('[a-f0-9]{64}',state['account_ref']) is not None, 'dependency_binding_principal_required')
            need(state.get('state') not in {'account_changed','identity_unverified','checking'}, 'dependency_binding_principal_required')
            profile = self.session/'browser_data'
            need(profile.is_dir() and (not profile.is_symlink() or _original_profile_reference(self.session,'xhs')), 'dependency_binding_profile_invalid')
            paths = [identity, binding, account]
            signer = self.root/'pro-signer.json'
            if signer.exists(): paths.append(signer)
            host_identity = self.helper/'config.json'
            if host_identity.exists(): paths.append(host_identity)
            marker = self.session/'browser-profile-reference.json'
            if marker.exists(): paths.append(marker)
            protected = {str(p): sha(read(p)) for p in paths}
            if signer.exists():
                selected = json.loads(read(signer))
                try:
                    resolved, digest = signer_python_pin(selected['python'])
                except OSError:
                    raise ValueError('dependency_binding_scope_changed') from None
                protected['selected_signer_python:' + resolved] = digest
            return protected
        finally:
            sys.path.pop(0)

    def signer_ready(self):
        # Signer is owned per source run, so an idle installation has no listener.
        self.idle()
        before = self.scope()
        binding = json.loads(read(self.session/'pro-binding.json'))
        need(binding['sign_url'].rstrip('/') == 'http://127.0.0.1:8990', 'signer_binding_invalid')
        descriptor_path = self.root/'pro-signer.json'
        try:
            descriptor_raw = read(descriptor_path)
        except FileNotFoundError:
            raise ValueError('signer_installation_required') from None
        descriptor = json.loads(descriptor_raw)
        need(type(descriptor) is dict and set(descriptor) == {'python','source_root'}, 'signer_installation_invalid')
        source = self.plan['input']['projects']['signer']['root']
        need(descriptor['source_root'] == source, 'signer_source_changed')
        python = Path(descriptor['python'])
        need(python.is_absolute() and python.is_file() and os.access(python, os.X_OK), 'signer_installation_invalid')
        wrapper = self.runtime/'pro_signer_server.py'
        need(wrapper.is_file() and not wrapper.is_symlink()
             and sha(wrapper.read_bytes()) == self.runtime_files.get(wrapper.name), 'signer_installation_invalid')
        try:
            raw = self.deps.execute([str(python), '-B', str(wrapper), '--source-root', source],
                                    env=self.deps.environment(), cwd=self.root, timeout=30)
            result = json.loads(raw)
        except (ValueError, OSError):
            raise ValueError('signer_validation_failed') from None
        need(result == {'ok':True,'validate_only':True,'listening':False,'source_requests':0,
                        'browser_started':False,'platforms':['xhs','dy','zhihu']}
             and all(type(result[k]) is type(v) for k,v in {'ok':True,'validate_only':True,
                        'listening':False,'source_requests':0,'browser_started':False}.items()),
             'signer_validation_failed')
        need(read(descriptor_path) == descriptor_raw and self.scope() == before, 'dependency_binding_scope_changed')
        self.signer_scope = before

    def idle(self):
        state = self.helper/'pro-state.json'
        if state.exists():
            host = json.loads(read(state))
            need(host.get('busy') is False and host.get('state') in {'stopped','complete','partial','source_failed','ready','not_ready'}, 'dependency_host_busy')
        for path in (self.root/'runs').glob('*/status.json'):
            need(json.loads(read(path)).get('state') in {'completed','failed','stopped','login_required'}, 'dependency_source_active')
        db = self.root/'cloud-outbox/outbox.sqlite3'
        if db.exists():
            with sqlite3.connect(db.as_uri()+'?mode=ro', uri=True) as connection:
                tables = {r[0] for r in connection.execute("select name from sqlite_master where type='table'")}
                if 'participant_delivery' in tables:
                    need(connection.execute("select count(*) from participant_delivery where state != 'delivered'").fetchone()[0] == 0, 'dependency_native_pending')
                if 'participant_runs' in tables:
                    need(connection.execute("select count(*) from participant_runs where state not in ('complete','stopped','source_failed')").fetchone()[0] == 0, 'dependency_native_pending')

    def install(self, configure):
        # This stage contains only derived settings, before-images, and once evidence.
        self.idle(); self.protected = self.scope()
        need(not hasattr(self, 'signer_scope') or self.signer_scope == self.protected, 'dependency_binding_scope_changed')
        base = self.evidence.parent
        if not base.exists(): base.mkdir(mode=0o700)
        need(base.resolve() == base and base.stat().st_uid == os.getuid() and not base.stat().st_mode & 0o077)
        if self.evidence.exists():
            need(self.completed, 'dependency_binding_attempt_unknown')
            need(json.loads(read(self.evidence/'INTENT.json')).get('scope') == self.protected, 'dependency_binding_scope_changed')
            result = json.loads(read(self.evidence/'RESULT.json'))
            need(result == {'state':'configured','authenticated':False,'executor_sha256':sha(self.executor_after),'config_sha256':sha(self.expected)}, 'dependency_binding_attempt_unknown')
            need(read(self.executor) == self.executor_after and read(self.config) == self.expected and read(self.derived) == encoded(self.values), 'dependency_binding_cas_changed')
            return configure(self.runtime, self.derived, self.helper, continuation=self)
        self.evidence.mkdir(mode=0o700)
        once(self.derived, encoded(self.values))
        once(self.evidence/'settings.before.json', self.original_raw)
        once(self.evidence/'executor.before.json', self.executor_before)
        if self.config_before is not None: once(self.evidence/'config.before.json', self.config_before)
        return configure(self.runtime, self.derived, self.helper, continuation=self)

    def __enter__(self):
        path = self.session/'active.lock'
        fd = os.open(path, os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK, 0o600)
        self.lock = fd
        try:
            need(stat.S_ISREG(os.fstat(fd).st_mode) and os.fstat(fd).st_uid == os.getuid(), 'dependency_session_lock_invalid')
            fcntl.flock(fd, fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.idle(); need(self.scope() == self.protected, 'dependency_binding_scope_changed')
            need((read(self.config) if self.config.exists() else None) == self.config_before, 'dependency_binding_cas_changed')
            if self.completed:
                need(read(self.executor) == self.executor_after and read(self.config) == self.expected, 'dependency_binding_cas_changed')
                return self
            once(self.evidence/'INTENT.json', encoded({'schema':'crowd-pro-binding-continuation-v1','input_key':self.prepared['key'],'before_settings_sha256':sha(self.original_raw),'executor_before_sha256':sha(self.executor_before),'executor_after_sha256':sha(self.executor_after),'config_before_sha256':sha(self.config_before) if self.config_before else None,'config_after_sha256':sha(self.expected),'scope':self.protected, **({'operator_max_api_requests':self.operator_max_api_requests} if self.operator_max_api_requests is not None else {})}))
            replace(self.executor, self.executor_before, self.executor_after)
            return self
        except BaseException:
            os.close(fd); self.lock = None; raise

    def __exit__(self, typ, error, traceback):
        try:
            if typ is None:
                try:
                    need(read(self.executor) == self.executor_after and read(self.config) == self.expected and self.scope() == self.protected, 'dependency_binding_verify_failed')
                    # Same reader as NativeService HELLO; only local early-exit probe.
                    script = 'import sys,json;sys.path.insert(0,sys.argv[1]);from participant_pro_native import installation_ready;installation_ready(json.load(open(sys.argv[2])))'
                    self.deps.execute([self.values['python'],'-B','-c',script,str(self.runtime),str(self.config)], env=self.deps.environment(), cwd=self.root, timeout=30)
                    self.idle(); need(self.scope() == self.protected, 'dependency_binding_scope_changed')
                    need(read(self.executor) == self.executor_after and read(self.config) == self.expected, 'dependency_binding_verify_failed')
                    if self.completed: return False
                    once(self.evidence/'RESULT.json', encoded({'state':'configured','authenticated':False,'executor_sha256':sha(self.executor_after),'config_sha256':sha(self.expected)}))
                    return False
                except BaseException as verification:
                    error = verification
            # Restore only our exact expected writes; foreign/uncertain state is held.
            try:
                current = read(self.config) if self.config.exists() else None
                need(current in (self.config_before, self.expected), 'dependency_binding_rollback_unknown')
                current_executor = read(self.executor)
                need(current_executor in (self.executor_before, self.executor_after), 'dependency_binding_rollback_unknown')
                if current != self.config_before: replace(self.config, current, self.config_before)
                if current_executor != self.executor_before: replace(self.executor, current_executor, self.executor_before)
                once(self.evidence/'ROLLBACK.json', encoded({'state':'restored_before','source_started':False}))
            except BaseException:
                raise ValueError('dependency_binding_rollback_unknown') from None
            if typ is None: raise error
            return False
        finally:
            if self.lock is not None: os.close(self.lock); self.lock = None
