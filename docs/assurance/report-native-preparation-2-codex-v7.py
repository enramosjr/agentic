"""Audit no-model v7 proposal and scoped unchanged operator evidence without reruns."""
import ast
import hashlib
import json
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import artifacts

namespace = ROOT / 'docs/assurance/operator-2-mechanical-codex-v7'
preparation = json.loads((namespace / 'preparation.json').read_text())
def pin(path):
    return {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'mode': oct(stat.S_IMODE(path.stat().st_mode))}
for name, expected in preparation['files'].items():
    if pin(ROOT / name) != expected or pin(Path(preparation['frozen_source']) / name) != expected:
        raise SystemExit('current/frozen source drift: ' + name)
for name, expected in preparation['operator_inputs'].items():
    if pin(Path(name)) != expected:
        raise SystemExit('operator drift: ' + name)
for expected in preparation['binaries'].values():
    if pin(Path(expected['path'])) != {key: expected[key] for key in ('sha256', 'mode')}:
        raise SystemExit('installed binary drift')
old_runner = (ROOT / 'docs/assurance/run-native-2-mechanical-codex-v6.py').read_bytes()
new_runner = (ROOT / 'docs/assurance/run-native-2-mechanical-codex-v7.py').read_bytes()
normalized = new_runner.replace(b'operator-2-mechanical-codex-v7', b'operator-2-mechanical-codex-v6')
if old_runner != normalized or ast.dump(ast.parse(old_runner)) != ast.dump(ast.parse(normalized)):
    raise SystemExit('namespace-normalized runner mismatch')
reused = []
for suffix, count in (('local', 8), ('policy', 10), ('setup', 2)):
    artifact = json.loads((ROOT / ('docs/assurance/native-codex-v6-' + suffix + '-artifact.json')).read_text())
    manifest = artifacts.verify(Path(artifact['bundle']), artifact['sha256'])
    changed = []
    for name, old in manifest['files'].items():
        current = ROOT / name
        if artifacts.digest(current) != old['sha256'] or bool(current.stat().st_mode & 0o111) != old['executable']:
            changed.append(name)
    operator_changed = [name for name in changed if name.startswith('docs/assurance/') and
                        'operator-2-mechanical-native-v3/frozen-source/' not in name]
    if operator_changed:
        raise SystemExit('old local operator proof inputs changed: ' + ', '.join(operator_changed))
    reused.append({'suite': suffix, 'old_test_count': count, 'artifact': artifact,
                   'changed_declared_source_payloads': changed, 'changed_operator_inputs': operator_changed,
                   'boundary': 'Original sealed run stays bound to original full manifest. Operator/guarded runner/prebranch/trust/setup-test code is unchanged; current review_native payload differs and is covered by current focused/framework and fresh setup evidence. This is scoped prior operator-policy evidence, not an exact-current-manifest rerun.'})
setup = json.loads((namespace / 'setup-preflight.json').read_text())
if setup['setup'] != 'PASS' or setup['agent_processes'] or setup['model_calls']:
    raise SystemExit('fresh selected current-KIT setup is not passing/no-model')
report = {'source_tree': preparation['source_tree'], 'namespace': str(namespace), 'pin_audit': 'PASS',
          'future_command': ['python3', '.ai/scripts/lifecycle.py', 'run', 'assurance-2-real-agent', '--timeout', '340',
                             '--', 'python3', 'docs/assurance/run-native-2-mechanical-codex-v7.py',
                             '--authorized-allocation-and-scoped-trust'],
          'allocation': preparation['limits'], 'prepared_branch': preparation['prepared_branch'],
          'runner_pin': pin(ROOT / 'docs/assurance/run-native-2-mechanical-codex-v7.py'),
          'launcher_pin': pin(namespace / 'native-launch.py'),
          'planned_commands_pin': pin(namespace / 'planned-commands.json'),
          'preparation_pin': pin(namespace / 'preparation.json'),
          'runner_equivalence': preparation['runner_namespace_equivalence'],
          'prior_local_operator_evidence': reused, 'fresh_current_KIT_setup': setup,
          'current_local_baseline': {'tests': 66, 'controls_killed': 37,
              'summary': str(ROOT / 'docs/assurance/mechanical-review-mutations-2-final9-summary.json')},
          'current_fullframework_output': (ROOT / 'docs/assurance/mechanical-framework-2-final9-full.log').read_text(),
          'evaluation_started': (namespace / 'codex-started').exists(),
          'evaluation_result_exists': (namespace / 'codex-results.json').exists(),
          'native_preflight_calls': 0, 'model_calls': 0, 'fresh_human_allocation_required': True,
          'trust_boundary': 'Normal invocation-local project/exact-handler trust, workspace-write/never/prebranch unchanged. Actual native trust/callback/reviewer/Verify proof remains pending separate approval and execution.'}
out = ROOT / 'docs/assurance/native-codex-v7-preparation-report.json'
with out.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({key: report[key] for key in ('source_tree', 'pin_audit', 'allocation', 'runner_pin',
                  'launcher_pin', 'planned_commands_pin', 'preparation_pin', 'evaluation_started',
                  'evaluation_result_exists', 'native_preflight_calls', 'model_calls')}, indent=2))
