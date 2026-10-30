"""Local sealed operator policy proofs; no native processes or model inference."""
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import artifacts

OUT = ROOT / 'docs/assurance/native-proposal-controls-2-review-enforcement.json'
if OUT.exists():
    raise SystemExit('policy control evidence exists; preserve it')
NAMES = ['docs/assurance/' + name for name in (
    'native-launch-2-review-enforcement.py', 'run-native-2-review-enforcement.py',
    'test-native-preparation-2-review-enforcement.py')]
frozen = artifacts.freeze(ROOT, ROOT, NAMES)


def run(bundle, selector=None):
    command = [sys.executable, str(ROOT / '.ai/scripts/artifacts.py'), 'run',
        '--bundle', bundle['bundle'], '--sha256', bundle['sha256'], '--timeout', '30', '--',
        sys.executable, '{artifact:docs/assurance/test-native-preparation-2-review-enforcement.py}']
    if selector:
        command += ['TrustPolicyTests.' + selector]
    result = subprocess.run(command, capture_output=True, text=True, timeout=40)
    return {'command': command, 'exit': result.returncode, 'output': result.stdout + result.stderr}


baseline = run(frozen)
if baseline['exit'] or not re.search(r'^Ran 4 tests? in ', baseline['output'], re.M):
    raise SystemExit('sealed policy baseline failed or test count mismatched')
controls = []
for name, old, new, selector in (
    ('trusted-runtime-check-omitted', "if trusted and hook.get('trustStatus') != 'trusted':",
     'if False:', 'test_trust_requires_exact_native_definitions_and_actual_trusted_reply'),
    ('frozen-definition-check-omitted', 'if source not in expected or actual not in expected[source]:',
     'if False:', 'test_unknown_changed_disabled_and_malformed_handlers_refuse')):
    created = subprocess.run([sys.executable, str(ROOT / '.ai/scripts/artifacts.py'), 'variant',
        '--bundle', frozen['bundle'], '--sha256', frozen['sha256']], capture_output=True, text=True, check=True)
    variant = Path(json.loads(created.stdout)['variant'])
    target = variant / NAMES[0]
    original = target.read_text()
    if original.count(old) != 1:
        raise SystemExit('mutation target mismatch: ' + name)
    changed = original.replace(old, new)
    target.write_text(changed)
    confirmed = changed != original and target.read_text() == changed
    qualified = artifacts.freeze(ROOT, variant, NAMES)
    result = run(qualified, selector)
    valid = (re.search(r'^Ran 1 test in ', result['output'], re.M) and
        re.search(r'^AssertionError:', result['output'], re.M) and
        not re.search(r'^(?:ImportError|ModuleNotFoundError|SyntaxError):', result['output'], re.M))
    killed = bool(confirmed and result['exit'] != 0 and valid)
    controls.append({'name': name, 'confirmed': confirmed, 'artifact': qualified, 'killed': killed, **result})
artifacts.verify(Path(frozen['bundle']), frozen['sha256'])
OUT.write_text(json.dumps({'baseline_artifact': frozen, 'baseline': baseline,
    'controls': controls, 'native_processes_launched': 0, 'model_calls': 0}, indent=2) + '\n')
print('sealed operator baseline 4 PASS; controls ' + str(sum(item['killed'] for item in controls)) + '/2 killed')
raise SystemExit(0 if all(item['killed'] for item in controls) else 1)
