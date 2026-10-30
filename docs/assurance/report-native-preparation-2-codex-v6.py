"""Audit locally frozen v6 proposal pins and summarize proof; never launch native tools."""
import hashlib
import json
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import artifacts

namespace = ROOT / 'docs/assurance/operator-2-mechanical-codex-v6'
preparation = json.loads((namespace / 'preparation.json').read_text())
def pin(path):
    return {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'mode': oct(stat.S_IMODE(path.stat().st_mode))}
for name, expected in preparation['files'].items():
    if pin(ROOT / name) != expected or pin(Path(preparation['frozen_source']) / name) != expected:
        raise SystemExit('source drift: ' + name)
for name, expected in preparation['operator_inputs'].items():
    if pin(Path(name)) != expected:
        raise SystemExit('operator drift: ' + name)
for expected in preparation['binaries'].values():
    if pin(Path(expected['path'])) != {key: expected[key] for key in ('sha256', 'mode')}:
        raise SystemExit('installed binary drift')
local = json.loads((ROOT / 'docs/assurance/native-codex-v6-local-artifact.json').read_text())
artifacts.verify(Path(local['bundle']), local['sha256'])
mutants = json.loads((ROOT / 'docs/assurance/native-codex-v6-local-mutations.json').read_text())
report = {'source_tree': preparation['source_tree'], 'namespace': str(namespace), 'pin_audit': 'PASS',
          'future_command': ['python3', '.ai/scripts/lifecycle.py', 'run', 'assurance-2-real-agent', '--timeout', '340',
                             '--', 'python3', 'docs/assurance/run-native-2-mechanical-codex-v6.py',
                             '--authorized-allocation-and-scoped-trust'],
          'allocation': preparation['limits'], 'prepared_branch': preparation['prepared_branch'],
          'runner_pin': pin(ROOT / 'docs/assurance/run-native-2-mechanical-codex-v6.py'),
          'launcher_pin': pin(namespace / 'native-launch.py'),
          'planned_commands_pin': pin(namespace / 'planned-commands.json'),
          'preparation_pin': pin(namespace / 'preparation.json'),
          'local_artifact': local, 'local_test_output': (ROOT / 'docs/assurance/native-codex-v6-local-full.log').read_text(),
          'local_mutations': {'total': mutants['total'], 'killed': mutants['killed'],
                              'report': str(ROOT / 'docs/assurance/native-codex-v6-local-mutations.json')},
          'setup': json.loads((namespace / 'setup-preflight.json').read_text()),
          'evaluation_started': (namespace / 'codex-started').exists(),
          'evaluation_result_exists': (namespace / 'codex-results.json').exists(),
          'native_preflight_calls': 0, 'model_calls': 0, 'fresh_human_allocation_required': True,
          'trust_boundary': 'Normal invocation-local project and exact-handler trust; workspace-write/never unchanged. Native hook trust/callback/reviewer/model proof remains unverified until a separately approved actual evaluation.'}
out = ROOT / 'docs/assurance/native-codex-v6-preparation-report.json'
with out.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({key: report[key] for key in ('source_tree', 'pin_audit', 'allocation', 'runner_pin',
                  'launcher_pin', 'planned_commands_pin', 'preparation_pin', 'evaluation_started',
                  'evaluation_result_exists', 'native_preflight_calls', 'model_calls')}, indent=2))
