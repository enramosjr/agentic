"""Seal the changed generic operator inputs and run existing local policy regressions once."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import artifacts
import install

names = sorted(set(install.kit_files(ROOT)) | {
    'docs/assurance/native-launch-2-review-enforcement.py',
    'docs/assurance/run-native-2-review-enforcement.py',
    'docs/assurance/prepare-native-2-review-enforcement.py',
    'docs/assurance/test-native-preparation-2-review-enforcement.py'})
qualified = artifacts.freeze(ROOT, ROOT, names)
out = ROOT / 'docs/assurance/native-codex-v6-policy-artifact.json'
with out.open('x') as stream:
    json.dump(qualified, stream, indent=2)
    stream.write('\n')
command = [sys.executable, str(ROOT / '.ai/scripts/artifacts.py'), 'run', '--bundle', qualified['bundle'],
           '--sha256', qualified['sha256'], '--timeout', '120', '--', sys.executable,
           '{artifact:docs/assurance/test-native-preparation-2-review-enforcement.py}']
result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=140)
with (ROOT / 'docs/assurance/native-codex-v6-policy-full.log').open('x') as stream:
    stream.write(result.stdout + result.stderr)
print(result.stdout + result.stderr)
raise SystemExit(result.returncode)
