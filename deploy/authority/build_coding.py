"""Export an explicit held worker image context; never build/pull/run an image."""
import argparse
import hashlib
import json
from pathlib import Path
import stat
import sys

sys.path[:0] = [str(Path(__file__).resolve().parent),
                str(Path(__file__).resolve().parents[2] / '.ai/scripts')]
from codex_harness import profile
from trusted_ci_policy import Refusal, loads, require

FILES = tuple('.ai/scripts/' + name for name in (
    'authority_release.py', 'authority_protocol.py', 'trusted_ci_policy.py', 'trusted_ci_sandbox.py', 'trusted_ci_github.py',
)) + tuple('deploy/authority/' + name for name in (
    'coding_stdio.py', 'coding_worker.py', 'coding_transport.py', 'codex_harness.py', 'model_bridge.py',
    'model_relay.py', 'model_vault.py', 'submission.py',
))
MAX_BINARY = 256 * 1024 * 1024


def plain(path, directory=False):
    value = path.lstat()
    require(not path.is_symlink() and not getattr(value, 'st_file_attributes', 0) & 0x400 and
            (stat.S_ISDIR(value.st_mode) if directory else stat.S_ISREG(value.st_mode)), 'plain build input/output required')
    return value


def binary_digest(path):
    size = plain(path).st_size
    require(4 <= size <= MAX_BINARY, 'bounded Linux harness binary required')
    fingerprint = hashlib.sha256()
    with path.open('rb') as stream:
        require(stream.read(4) == b'\x7fELF', 'Linux ELF harness required')
        stream.seek(0)
        total = 0
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            total += len(chunk)
            require(total <= MAX_BINARY, 'harness changed or exceeds limit')
            fingerprint.update(chunk)
    require(total == size, 'harness changed during read')
    return fingerprint.hexdigest()


def build(root, deployment, binary, destination):
    resources = profile(deployment)
    root, binary, destination = Path(root).resolve(), Path(binary), Path(destination)
    require(binary_digest(binary) == resources['codex_sha'], 'harness does not match approved binary pin')
    require(not destination.exists() and not destination.is_symlink(), 'fresh worker build context required')
    plain(destination.parent, directory=True)
    inputs = {}
    for name in FILES:
        source = root / name
        require(source.resolve().is_relative_to(root) and plain(source).st_size <= 1024 * 1024,
                'bounded trusted worker source required')
        inputs[name] = source.read_bytes()
    setup = ('import os; os.chmod("/opt/agentic/bin/codex",0o555); '
        'os.makedirs("/work",exist_ok=True); os.makedirs("/home/agentic",exist_ok=True); '
        'os.chown("/home/agentic",65534,65534); os.chmod("/home/agentic",0o700)')
    copies = ''.join('COPY ' + json.dumps([name, '/opt/agentic/' + name]) + '\n'
                     for name in (*FILES, 'bin/codex', 'coding-manifest.json'))
    recipe = ('FROM ' + deployment['policy']['image'] + '\nUSER 0:0\n' + copies + 'RUN ' +
        json.dumps(['python3', '-I', '-c', setup]) + '\nUSER 65534:65534\nWORKDIR /work\nENTRYPOINT ' +
        json.dumps(['python3', '-I', '/opt/agentic/deploy/authority/coding_stdio.py']) + '\n')
    inputs['Containerfile'] = recipe.encode()
    destination.mkdir(mode=0o700)
    for name, raw in inputs.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as output: output.write(raw)
        target.chmod(0o444)
    target = destination / 'bin/codex'
    target.parent.mkdir()
    with binary.open('rb') as source, target.open('xb') as output:
        total, fingerprint = 0, hashlib.sha256()
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            total += len(chunk)
            require(total <= MAX_BINARY, 'harness exceeds build context limit')
            output.write(chunk)
            fingerprint.update(chunk)
    require(fingerprint.hexdigest() == resources['codex_sha'], 'harness changed during context export')
    target.chmod(0o555)
    hashes = {name:hashlib.sha256(raw).hexdigest() for name,raw in inputs.items()}
    hashes['bin/codex'] = fingerprint.hexdigest()
    manifest = dict(schema_version=2, kind='held-coding-context', base_image=deployment['policy']['image'],
        codex_sha256=resources['codex_sha'], codex_version=resources['codex_version'],
        files=hashes, image_built=False, enforcement_active=False)
    with (destination / 'coding-manifest.json').open('x', encoding='utf-8') as output:
        json.dump(manifest, output, sort_keys=True, allow_nan=False)
    return dict(path=str(destination.resolve()), image_built=False, enforcement_active=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deployment', required=True, type=Path)
    parser.add_argument('--binary', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        with args.deployment.open('rb') as stream: d = loads(stream.read(1024 * 1024 + 1))
        print(json.dumps(build(Path(__file__).resolve().parents[2], d, args.binary, args.output), sort_keys=True))
        return 0
    except (Refusal, OSError, ValueError):
        print('coding context export refused; no image built', file=sys.stderr)
        return 1


if __name__ == '__main__': sys.exit(main())
