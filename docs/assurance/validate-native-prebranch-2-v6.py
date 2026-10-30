"""Seal and exercise only the local prebranch proof; no native launch or model calls."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import artifacts

names = sorted(str(path.relative_to(ROOT)) for path in (ROOT / '.ai/scripts').glob('*.py'))
names += ['docs/assurance/native-launch-2-review-enforcement.py',
          'docs/assurance/run-native-2-mechanical-codex-v6.py',
          'docs/assurance/test-native-prebranch-2-v6.py']
qualified = artifacts.freeze(ROOT, ROOT, names)
out = ROOT / 'docs/assurance/native-codex-v6-local-artifact.json'
with out.open('x') as stream:
    json.dump(qualified, stream, indent=2)
    stream.write('\n')
command = [sys.executable, str(ROOT / '.ai/scripts/artifacts.py'), 'run', '--bundle', qualified['bundle'],
           '--sha256', qualified['sha256'], '--timeout', '120', '--', sys.executable,
           '{artifact:docs/assurance/test-native-prebranch-2-v6.py}']
result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=140)
log = ROOT / 'docs/assurance/native-codex-v6-local-full.log'
with log.open('x') as stream:
    stream.write(result.stdout + result.stderr)
print(result.stdout + result.stderr)
raise SystemExit(result.returncode)
