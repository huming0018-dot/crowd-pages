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


def install(deps, configure, descriptor, settings, runtime, helper):
    # Dependency work does not modify settings, SDK files, account data or adapter pointers.
    prepared = deps.prepare(descriptor, helper)
    values = json.loads(deps.read(settings))
    plan = deps.plan(descriptor, helper)
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
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    deps = load('pro_dependencies', base / 'prepare-pro-dependencies.py')
    try:
        original = load('pro_configure', base / 'configure-pro.py')
        result = install(deps, original.configure, args.descriptor, args.settings, args.runtime, args.helper_root)
        print(json.dumps(result)); return 0
    except FileNotFoundError:
        print(json.dumps({'state': 'not_ready', 'error': 'dependency_binding_required'})); return 1
    except Exception as error:
        reason = str(error) if isinstance(error, ValueError) and deps.re.fullmatch('[a-z_]{1,80}', str(error)) else 'dependency_prepare_failed'
        print(json.dumps({'state': 'not_ready', 'error': reason})); return 1


if __name__ == '__main__':
    sys.exit(main())
