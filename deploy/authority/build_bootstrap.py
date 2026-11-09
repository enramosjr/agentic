"""Build a deterministic, minimal maintainer preflight candidate (not a release)."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.ai' / 'scripts'))
from trusted_ci_policy import Refusal, require
import build_runtime

FILES = tuple(dict.fromkeys(build_runtime.FILES + (
    'deploy/authority/operator_setup.py',
    'deploy/authority/build_runtime.py',
    'deploy/authority/bootstrap_stage.py',
    '.ai/trusted-ci/authority-v2.yml',
    '.ai/trusted-ci/authority-v2-recovery.yml',
    '.ai/docs/trusted-ci-bootstrap-preflight.md',
)))


def build(root, output):
    root, output = Path(root).resolve(), Path(output)
    require(not output.exists(), 'bundle output already exists; refusing to overwrite')
    inputs = {}
    for name in FILES:
        path = root / name
        require(path.is_file() and not path.is_symlink(), 'plain bundle source required: ' + name)
        try:
            path.resolve().relative_to(root)
        except ValueError:
            raise Refusal('bundle source escapes trusted root') from None
        raw = path.read_bytes()
        require(len(raw) <= 1024 * 1024, 'bundle source exceeds limit')
        inputs[name] = raw
    manifest = {'schema_version': 1, 'kind': 'maintainer-bootstrap-preflight',
                'enforcement_qualified': False,
                'files': {name: hashlib.sha256(raw).hexdigest() for name, raw in inputs.items()}}
    inputs['bundle-manifest.json'] = (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode='w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(inputs.items()):
            entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100444 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, raw)
    raw = buffer.getvalue()
    with output.open('xb') as stream:
        stream.write(raw)
    return {'kind': manifest['kind'], 'path': str(output.resolve()),
            'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
            'enforcement_qualified': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(build(Path(__file__).resolve().parents[2], args.output), sort_keys=True))
        return 0
    except (Refusal, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
