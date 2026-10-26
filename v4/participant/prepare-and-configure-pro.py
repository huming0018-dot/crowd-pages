#!/usr/bin/env python3
"""Fixed local installer entry, never callable from extension/native messages."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def install(deps, configure, descriptor, settings, runtime, helper, continuation_factory=None, *, max_api_requests=None):
    deps.need(max_api_requests is None or type(max_api_requests) is int and 1 <= max_api_requests <= 100, 'operator_capacity_invalid')
    # Dependency work does not modify settings, SDK files, account data or adapter pointers.
    prepared = deps.prepare(descriptor, helper)
    if not Path(settings).exists() and not Path(settings).is_symlink():
        deps.need(max_api_requests is None, 'operator_capacity_requires_continuation')
        return {**prepared, 'state': 'prepared_unbound', 'configured': False,
                'authenticated': False, 'local_account_binding_required': True}
    values = json.loads(deps.read(settings))
    plan = deps.plan(descriptor, helper)
    if continuation_factory is not None:
        continuation = continuation_factory(deps, prepared, plan, settings, runtime, helper, **({'max_api_requests':max_api_requests} if max_api_requests is not None else {}))
        deps.check(descriptor, helper, health=continuation.signer_ready)
        if 'downloader' in json.loads(deps.read(descriptor)):
            media = load('pro_downloader_dependencies', Path(__file__).with_name('prepare-pro-downloader.py'))
            media.prepare(deps, descriptor, helper)
            media.provision(deps, descriptor, helper, continuation)
        result = continuation.install(configure)
        return {**result, **({'max_api_requests':max_api_requests} if max_api_requests is not None else {})}
    deps.need(max_api_requests is None, 'operator_capacity_requires_continuation')
    deps.need(values.get('python') == prepared['python'] and
              values.get('mc_root') == plan['input']['projects']['pro']['root'],
              'dependency_binding_migration_required')
    deps.check(descriptor, helper)
    # Original configure retains dual locks, manifest verification, six-binding equality.
    return configure(runtime, settings, helper)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--descriptor', type=Path, required=True)
    parser.add_argument('--settings', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--helper-root', type=Path, required=True)
    parser.add_argument('--max-api-requests', type=int, help='Explicit operator capacity for this new installation configuration (1..100); old task budgets unchanged')
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    deps = load('pro_dependencies', base / 'prepare-pro-dependencies.py')
    try:
        if not args.descriptor.exists() and not args.descriptor.is_symlink():
            deps.need(args.descriptor == args.helper_root/'pro-dependency-settings.json', 'dependency_input_invalid')
            args.descriptor = deps.discover(args.helper_root)
        original = load('pro_configure', base / 'configure-pro.py')
        continuation = load('pro_binding_continuation', base / 'pro-binding-continuation.py')
        result = install(deps, original.configure, args.descriptor, args.settings, args.runtime, args.helper_root, continuation.BindingContinuation, max_api_requests=args.max_api_requests)
        print(json.dumps(result))
        if result.get('state') == 'prepared_unbound':
            print('Pro 依赖已准备；尚未绑定本机登录，当前不能采集。', file=sys.stderr)
        return 0
    except FileNotFoundError:
        print(json.dumps({'state': 'not_ready', 'error': 'dependency_binding_required'})); return 1
    except Exception as error:
        reason = str(error) if isinstance(error, ValueError) and deps.re.fullmatch('[a-z_]{1,80}', str(error)) else 'dependency_prepare_failed'
        print(json.dumps({'state': 'not_ready', 'error': reason})); return 1


if __name__ == '__main__':
    sys.exit(main())
