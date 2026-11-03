"""Repair only Git newline-converted, cryptographically pinned source oracles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from compatibility_baselines import MANIFEST_SHA256

RELATIVE = '.ai/scripts/tests/fixtures/qualification-baselines'


def restore(root: Path, *, manifest_sha: str = MANIFEST_SHA256) -> int:
    root = root.resolve()

    def blob(name):
        return subprocess.check_output(['git', '-C', str(root), 'cat-file', 'blob',
                                        f'HEAD:{RELATIVE}/{name}'])

    manifest = blob('manifest.json')
    if hashlib.sha256(manifest).hexdigest() != manifest_sha:
        raise ValueError('committed baseline manifest does not match its independent pin')
    expected = {'manifest.json': manifest}
    for item in json.loads(manifest)['sources']:
        name = item['file']
        if Path(name).name != name:
            raise ValueError('baseline path must be local')
        data = blob(name)
        if hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError(f'committed baseline hash mismatch: {name}')
        header = b'blob ' + str(len(data)).encode() + b'\0'
        if hashlib.sha1(header + data).hexdigest() != item['git_blob']:
            raise ValueError(f'committed baseline Git identity mismatch: {name}')
        expected[name] = data
    changes = []
    for name, data in expected.items():
        path = root / RELATIVE / name
        current = path.read_bytes()
        if current == data:
            continue
        if current.replace(b'\r\n', b'\n') != data:
            raise ValueError(f'baseline has edits beyond Git newline conversion: {name}')
        changes.append((path, data))
    # Validate every pin and every current file before the first mutation.
    for path, data in changes:
        path.write_bytes(data)
    return len(changes)


if __name__ == '__main__':
    print(f'restored {restore(Path(__file__).resolve().parents[3])} pinned baseline file(s)')
