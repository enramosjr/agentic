"""Complete local policy proof; retain the earlier redundant-guard mutation result."""
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import artifacts

OUT = ROOT / 'docs/assurance/native-proposal-copy-control-2.json'
if OUT.exists():
    raise SystemExit('copy-control result exists; preserve it')
prior = json.loads((ROOT / 'docs/assurance/native-proposal-controls-2-review-enforcement.json').read_text())
frozen = prior['baseline_artifact']
artifacts.verify(Path(frozen['bundle']), frozen['sha256'])
if prior['baseline']['exit'] or not prior['controls'][0]['killed']:
    raise SystemExit('prior exact baseline/strict-trust proof unavailable')
created = subprocess.run([sys.executable, str(ROOT / '.ai/scripts/artifacts.py'), 'variant',
    '--bundle', frozen['bundle'], '--sha256', frozen['sha256']], capture_output=True, text=True, check=True)
variant = Path(json.loads(created.stdout)['variant'])
name = 'docs/assurance/native-launch-2-review-enforcement.py'
target = variant / name
original = target.read_text()
old = "state = copy.deepcopy(preflight.get('_configuration', {}).get('hooks', {}).get('state', {}))"
new = "state = preflight.get('_configuration', {}).get('hooks', {}).get('state', {})"
if original.count(old) != 1:
    raise SystemExit('copy mutation target mismatch')
changed = original.replace(old, new)
target.write_text(changed)
confirmed = changed != original and target.read_text() == changed
qualified = artifacts.freeze(ROOT, variant, frozen['files'])
command = [sys.executable, str(ROOT / '.ai/scripts/artifacts.py'), 'run',
    '--bundle', qualified['bundle'], '--sha256', qualified['sha256'], '--timeout', '30', '--',
    sys.executable, '{artifact:docs/assurance/test-native-preparation-2-review-enforcement.py}',
    'TrustPolicyTests.test_overlay_preserves_existing_state_without_editing_discovery']
result = subprocess.run(command, capture_output=True, text=True, timeout=40)
output = result.stdout + result.stderr
killed = bool(confirmed and result.returncode and re.search(r'^Ran 1 test in ', output, re.M)
              and re.search(r'^AssertionError:', output, re.M))
OUT.write_text(json.dumps({'artifact': qualified, 'command': command, 'confirmed': confirmed,
    'exit': result.returncode, 'output': output, 'killed': killed,
    'baseline_reused': frozen, 'strict_trust_control_reused': prior['controls'][0],
    'prior_redundant_definition_guard_control': 'retained not killed; other completeness checks still refuse',
    'native_processes_launched': 0, 'model_calls': 0}, indent=2) + '\n')
print('policy baseline4 and strict-trust kill reused; discovery-copy mutation ' + ('KILLED' if killed else 'INVALID/SURVIVED'))
raise SystemExit(0 if killed else 1)
