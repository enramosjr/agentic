"""Final declared-file operator proof, independent of ignored-file reuse inventory."""
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import artifacts

OUT = ROOT / 'docs/assurance/native-proposal-final3-validation.json'
if OUT.exists():
    raise SystemExit('final operator evidence exists; preserve it')
names = ['docs/assurance/' + name for name in (
    'native-launch-2-review-enforcement.py', 'run-native-2-review-enforcement.py',
    'prepare-native-2-review-enforcement.py', 'test-native-preparation-2-review-enforcement.py')]
frozen = artifacts.freeze(ROOT, ROOT, names)


def invoke(bundle, test=None):
    command = [sys.executable, str(ROOT / '.ai/scripts/artifacts.py'), 'run',
        '--bundle', bundle['bundle'], '--sha256', bundle['sha256'], '--timeout', '30', '--',
        sys.executable, '{artifact:docs/assurance/test-native-preparation-2-review-enforcement.py}']
    if test:
        command.append('TrustPolicyTests.' + test)
    result = subprocess.run(command, capture_output=True, text=True, timeout=40)
    return {'command': command, 'exit': result.returncode, 'output': result.stdout + result.stderr}


baseline = invoke(frozen)
if baseline['exit'] or not re.search(r'^Ran 9 tests in ', baseline['output'], re.M):
    raise SystemExit('final sealed operator baseline failed or count mismatched')
controls = []
for label, old, new, test in (
    ('trusted-runtime-check-omitted', "if trusted and hook.get('trustStatus') != 'trusted':",
     'if False:', 'test_trust_requires_exact_native_definitions_and_actual_trusted_reply'),
    ('native-discovery-mutated', "state = copy.deepcopy(preflight.get('_configuration', {}).get('hooks', {}).get('state', {}))",
     "state = preflight.get('_configuration', {}).get('hooks', {}).get('state', {})",
     'test_overlay_preserves_existing_state_without_editing_discovery')):
    created = subprocess.run([sys.executable, str(ROOT / '.ai/scripts/artifacts.py'), 'variant',
        '--bundle', frozen['bundle'], '--sha256', frozen['sha256']], capture_output=True, text=True, check=True)
    variant = Path(json.loads(created.stdout)['variant'])
    target = variant / names[0]
    original = target.read_text()
    if original.count(old) != 1:
        raise SystemExit('final control target mismatch: ' + label)
    changed = original.replace(old, new)
    target.write_text(changed)
    confirmed = changed != original and target.read_text() == changed
    qualified = artifacts.freeze(ROOT, variant, names)
    result = invoke(qualified, test)
    semantic = re.search(r'^AssertionError:', result['output'], re.M)
    valid = re.search(r'^Ran 1 test in ', result['output'], re.M) and not re.search(
        r'^(?:ImportError|ModuleNotFoundError|SyntaxError):', result['output'], re.M)
    controls.append({'name': label, 'confirmed': confirmed, 'artifact': qualified,
        'killed': bool(confirmed and result['exit'] and semantic and valid), **result})
artifacts.verify(Path(frozen['bundle']), frozen['sha256'])
OUT.write_text(json.dumps({'artifact': frozen, 'baseline': baseline, 'controls': controls,
    'Claude_Codex_app_server_processes': 0, 'model_calls': 0,
    'scope': 'local Git/Python/mocked policy and retention; native qualification remains unverified'}, indent=2) + '\n')
print('final declared-file operator baseline9 PASS; confirmed controls ' + str(sum(item['killed'] for item in controls)) + '/2 killed')
raise SystemExit(0 if all(item['killed'] for item in controls) else 1)
