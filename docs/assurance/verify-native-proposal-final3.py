"""Read-only final proposal audit; never invokes the authorized entrypoint or CLI."""
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import artifacts
import lifecycle

namespace = ROOT / 'docs/assurance/operator-2-mechanical-native-v3'
report = json.loads((namespace / 'preparation.json').read_text())
validation = json.loads((ROOT / 'docs/assurance/native-proposal-final3-validation.json').read_text())
artifact = validation['artifact']
artifacts.verify(Path(artifact['bundle']), artifact['sha256'])
spec = importlib.util.spec_from_file_location('prepared_runner_audit', ROOT / 'docs/assurance/run-native-2-review-enforcement.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
if lifecycle.tree_hash(ROOT) != report['source_tree'] or lifecycle.head_sha(ROOT) != report['source_head']:
    raise SystemExit('product source identity changed')
for name, expected in report['files'].items():
    runner.check_pin(ROOT / name, expected)
    runner.check_pin(Path(report['frozen_source']) / name, expected)
for name, expected in report['operator_inputs'].items():
    runner.check_pin(Path(name), expected)
for expected in report['binaries'].values():
    runner.check_pin(Path(expected['path']), expected)
if str(namespace / 'planned-commands.json') not in report['operator_inputs']:
    raise SystemExit('planned commands are not pinned')
commands = json.loads((namespace / 'planned-commands.json').read_text())
if set(commands) != {'claude', 'codex'}:
    raise SystemExit('unexpected attempt set')
for agent, command in commands.items():
    for option, expected in (('--scenario', 'control-delta'), ('--repeat', '1'), ('--timeout', '300'),
                             ('--max-agent-seconds', '300'), ('--max-wall-seconds', '330'),
                             ('--agent-id', agent)):
        if command.count(option) != 1 or command[command.index(option) + 1] != expected:
            raise SystemExit('unexpected frozen attempt option: ' + option)
    if command[-3:] != [sys.executable, str(namespace / 'native-launch.py'), agent]:
        raise SystemExit('unexpected native launcher')
    if any((namespace / name).exists() for name in (agent + '-started', agent + '-results.json')):
        raise SystemExit('an attempt has already been reserved or run')
if report['model_cells_launched'] or report['native_processes_launched'] or (namespace / 'retained').exists():
    raise SystemExit('proposal is not a fresh zero-native preparation')
if (validation['baseline']['exit'] or len(validation['controls']) != 2 or
        not all(item['killed'] and item['confirmed'] for item in validation['controls'])):
    raise SystemExit('operator policy/control proof incomplete')
result = {'source_tree': report['source_tree'], 'source_head': report['source_head'],
    'operator_artifact': artifact, 'all_source_operator_binary_command_pins': 'PASS',
    'fresh_attempts': True, 'Claude_Codex_app_server_processes': 0, 'model_calls': 0,
    'native_trust_and_capture': 'UNVERIFIED', 'requires_new_allocation_and_scoped_trust': True}
output = ROOT / 'docs/assurance/native-proposal-final3-verification.json'
with output.open('x') as stream:
    json.dump(result, stream, indent=2)
    stream.write('\n')
print('final proposal pins/commands/limits PASS; zero native attempts; trust and capture remain UNVERIFIED')
