"""Seal existing setup tests and their explicit archived-fixture/current-preparer inputs."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import artifacts
import install

archived = ROOT / 'docs/assurance/operator-2-mechanical-native-v3/frozen-source'
names = set(install.kit_files(ROOT)) | {
    'docs/assurance/prepare-native-2-review-enforcement.py',
    'docs/assurance/test-native-setup-preflight-2.py'}
for name in [*install.kit_files(archived), '.agentic.json', '.git']:
    names.add(str((archived / name).relative_to(ROOT)))
for name in ('live_observer.py', 'behavior.py', 'live.json', 'delta.json'):
    names.add('docs/assurance/operator-2-report-contract/.ai/evals/checks/' + name)
qualified = artifacts.freeze(ROOT, ROOT, sorted(names))
with (ROOT / 'docs/assurance/native-codex-v6-setup-artifact.json').open('x') as stream:
    json.dump(qualified, stream, indent=2)
    stream.write('\n')
command = [sys.executable, str(ROOT / '.ai/scripts/artifacts.py'), 'run', '--bundle', qualified['bundle'],
    '--sha256', qualified['sha256'], '--timeout', '120', '--', sys.executable,
    '{artifact:docs/assurance/test-native-setup-preflight-2.py}']
result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=140)
with (ROOT / 'docs/assurance/native-codex-v6-setup-full.log').open('x') as stream:
    stream.write(result.stdout + result.stderr)
print(result.stdout + result.stderr)
raise SystemExit(result.returncode)
