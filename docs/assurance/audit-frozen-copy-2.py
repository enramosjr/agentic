"""Audit preserved bytes and modes of the disposable real-evaluation source snapshot."""
import hashlib
import json
from pathlib import Path
import stat

ROOT = Path(__file__).resolve().parents[2]
operator = ROOT / 'docs/assurance/operator-2'
manifest = json.loads((operator / 'frozen-copy.json').read_text())
frozen = Path(manifest['path'])
modes = {}
for name, expected in manifest['files'].items():
    source, target = ROOT / name, frozen / name
    source_digest = hashlib.sha256(source.read_bytes()).hexdigest()
    target_digest = hashlib.sha256(target.read_bytes()).hexdigest()
    source_mode, target_mode = stat.S_IMODE(source.stat().st_mode), stat.S_IMODE(target.stat().st_mode)
    if source_digest != expected or target_digest != expected or source_mode != target_mode:
        raise SystemExit('frozen source mismatch: ' + name)
    modes[name] = oct(source_mode)
(operator / 'frozen-copy-audit.json').write_text(json.dumps({'source_tree': manifest['source_tree'],
    'frozen_commit': manifest['commit'], 'bytes_and_modes_equal': True, 'count': len(modes), 'modes': modes}, indent=2) + '\n')
print(f'frozen copy audit: PASS ({len(modes)} identical file contents and modes)')
