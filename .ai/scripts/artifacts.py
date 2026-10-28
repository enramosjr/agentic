#!/usr/bin/env python3
"""Seal declared files for acceptance; mutation variants never modify qualified copies."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

import scratch
import timed_check


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def member(root, name):
    value = PurePosixPath(name)
    if (not name or value.is_absolute() or '..' in value.parts or '\\' in name
            or value.as_posix() != name or name == 'manifest.json'):
        raise ValueError(f'unsafe artifact path: {name}')
    path = root
    for part in value.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError(f'artifact symlink refused: {name}')
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'unsafe artifact path: {name}')
    if not path.is_file():
        raise ValueError(f'artifact file missing: {name}')
    return path


def verify(bundle, pin):
    if not re.fullmatch(r'[0-9a-f]{64}', pin) or bundle.is_symlink():
        raise ValueError('invalid artifact pin or bundle')
    manifest = bundle / 'manifest.json'
    if manifest.is_symlink() or digest(manifest) != pin:
        raise ValueError('artifact manifest hash mismatch')
    data = json.loads(manifest.read_text())
    if data.get('schema_version') != 1 or not isinstance(data.get('files'), dict) or not data['files']:
        raise ValueError('invalid artifact manifest')
    for name, expected in data['files'].items():
        path = member(bundle, name)
        if digest(path) != expected['sha256'] or bool(path.stat().st_mode & 0o111) != expected['executable']:
            raise ValueError(f'artifact hash mismatch: {name}')
    actual = set()
    for path in bundle.rglob('*'):
        if path.is_symlink():
            raise ValueError('artifact symlink refused')
        if path.is_file():
            actual.add(path.relative_to(bundle).as_posix())
    if actual != set(data['files']) | {'manifest.json'}:
        raise ValueError('artifact file membership changed')
    return data


def freeze(repo, root, names):
    sources = {name: member(root, name) for name in names}
    if len(sources) != len(names):
        raise ValueError('duplicate artifact file')
    bundle = Path(tempfile.mkdtemp(prefix='qualified-', dir=scratch.directory(repo)))
    files = {}
    try:
        for name, source in sources.items():
            target = bundle / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            executable = bool(source.stat().st_mode & 0o111)
            target.chmod(0o555 if executable else 0o444)
            files[name] = {'sha256': digest(target), 'executable': executable}
        manifest = bundle / 'manifest.json'
        manifest.write_text(json.dumps({'schema_version': 1, 'files': files}, sort_keys=True) + '\n')
        pin = digest(manifest)
        manifest.chmod(0o444)
        for path in sorted(bundle.rglob('*'), key=lambda p: len(p.parts), reverse=True):
            if path.is_dir():
                path.chmod(0o555)
        bundle.chmod(0o555)
        verify(bundle, pin)
        return {'bundle': str(bundle), 'sha256': pin, 'files': sorted(files)}
    except BaseException:
        writable(bundle)
        shutil.rmtree(bundle)
        raise


def writable(root):
    for path in [root, *root.rglob('*')]:
        path.chmod(0o755 if path.is_dir() or path.stat().st_mode & 0o111 else 0o644)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('freeze')
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--file', action='append', required=True)
    for name in ('verify', 'run', 'variant'):
        p = sub.add_parser(name)
        p.add_argument('--bundle', type=Path, required=True)
        p.add_argument('--sha256', required=True)
        if name == 'run':
            p.add_argument('--timeout', type=float, default=600)
            p.add_argument('argv', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        repo = Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True).strip())
        if args.action == 'freeze':
            print(json.dumps(freeze(repo, args.root.resolve(), args.file)))
            return 0
        data = verify(args.bundle, args.sha256)
        if args.action == 'verify':
            print('artifact: PASS (declared files only)')
            return 0
        if args.action == 'variant':
            variant = Path(tempfile.mkdtemp(prefix='mutation-', dir=scratch.directory(repo))) / 'files'
            shutil.copytree(args.bundle, variant)
            writable(variant)
            print(json.dumps({'variant': str(variant), 'qualified': False, 'parent_sha256': args.sha256}))
            return 0
        command, referenced = [], False
        for arg in args.argv[1:] if args.argv[:1] == ['--'] else args.argv:
            def replace(match):
                nonlocal referenced
                name = match[1]
                if name not in data['files']:
                    raise ValueError(f'undeclared artifact: {name}')
                referenced = True
                return str(member(args.bundle.resolve(), name))
            command.append(re.sub(r'\{artifact:([^}]+)\}', replace, arg))
        if not command or not referenced:
            raise ValueError('acceptance must reference a declared {artifact:PATH}')
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            raise ValueError('artifact timeout must be positive and finite')
        build = tempfile.mkdtemp(prefix='acceptance-build-', dir=scratch.directory(repo))
        env = scratch.environment(repo)
        env.update(CARGO_TARGET_DIR=build, AGENTIC_BUILD_DIR=build)
        try:
            if os.name == 'posix':
                result = timed_check.run(command, label='artifact-acceptance', cwd=repo, env=env,
                                         timeout_seconds=args.timeout)
            else:
                result = subprocess.run(command, cwd=repo, env=env, timeout=args.timeout)
        finally:
            verify(args.bundle, args.sha256)
        return result.returncode
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f'artifact: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
