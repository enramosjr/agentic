"""Confirm new local prebranch tests reject three sealed broken operator variants."""
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import artifacts

parent = json.loads((ROOT / 'docs/assurance/native-codex-v6-local-artifact.json').read_text())
controls = [
    ('prebranch-omitted', '    if branch:\n        import lifecycle',
     '    if False:\n        import lifecycle', 'test_prebranch_preserves_head_tree_index_commits_and_cleanliness'),
    ('existing-session-accepted', "        if value.get('sessions') or lifecycle.load(root) is not None:",
     '        if False:', 'test_observed_session_refuses'),
    ('wrong-agent-accepted', "        if agent != 'codex' or branch != 'codex/named-greeting':",
     '        if False:', 'test_wrong_agent_refuses'),
]
results = []
for name, old, new, test in controls:
    created = subprocess.run([sys.executable, str(ROOT / '.ai/scripts/artifacts.py'), 'variant',
        '--bundle', parent['bundle'], '--sha256', parent['sha256']], cwd=ROOT,
        capture_output=True, text=True, check=True)
    variant = Path(json.loads(created.stdout)['variant'])
    path = variant / 'docs/assurance/native-launch-2-review-enforcement.py'
    original = path.read_text()
    if original.count(old) != 1:
        raise SystemExit('mutation target drift: ' + name)
    changed = original.replace(old, new)
    path.write_text(changed)
    confirmed = path.read_text() == changed and changed != original
    qualified = artifacts.freeze(ROOT, variant, parent['files'])
    command = [sys.executable, str(ROOT / '.ai/scripts/artifacts.py'), 'run', '--bundle', qualified['bundle'],
        '--sha256', qualified['sha256'], '--timeout', '120', '--', sys.executable,
        '{artifact:docs/assurance/test-native-prebranch-2-v6.py}', 'PrebranchTests.' + test]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=140)
    output = result.stdout + result.stderr
    log = ROOT / ('docs/assurance/native-codex-v6-' + name + '.log')
    with log.open('x') as stream:
        stream.write(output)
    valid = bool(re.search(r'^Ran 1 test in ', output, re.M)) and not re.search(
        r'^(?:ImportError|ModuleNotFoundError|SyntaxError):', output, re.M)
    killed = confirmed and valid and result.returncode != 0 and bool(re.search(r'^AssertionError:', output, re.M))
    results.append({'name': name, 'artifact': qualified, 'confirmed': confirmed, 'valid': valid,
                    'killed': killed, 'exit': result.returncode, 'command': command, 'output': str(log)})
    print(name, 'KILLED' if killed else 'INVALID/SURVIVED')
artifacts.verify(Path(parent['bundle']), parent['sha256'])
report = {'parent': parent, 'controls': results, 'total': 3, 'killed': sum(item['killed'] for item in results),
          'native_calls': 0, 'model_calls': 0}
out = ROOT / 'docs/assurance/native-codex-v6-local-mutations.json'
with out.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
raise SystemExit(0 if report['killed'] == 3 else 1)
