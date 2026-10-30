"""Report retained v4 native evidence only; no additional runtime/model calls."""
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
namespace = ROOT / 'docs/assurance/operator-2-mechanical-native-v4'
report = {'source_tree': 'a9e58f56be695f860d87a470fdf18b038e698c18a5982703bab939b088e7f409',
          'command': ['python3', '.ai/scripts/lifecycle.py', 'run', 'assurance-2-real-agent',
                      '--timeout', '670', '--', 'python3', 'docs/assurance/run-native-2-review-enforcement.py',
                      '--authorized-allocation-and-scoped-trust'],
          'executions': 1, 'exit': 1, 'namespace': str(namespace),
          'limits': {'agent_seconds': 600, 'campaign_wall_seconds': 660, 'per_cell_seconds': 300},
          'agents': {}, 'charged_agent_seconds': 0, 'retries': 0,
          'source_edits': False, 'persistent_trust_changes_by_validator': False,
          'strict_results_check': 'Both failed: unqualified provenance/execution and unobserved attempt identity.',
          'behavioral_proof': 'Absent: neither delegated a reviewer, converged, recorded native Review or reached Verify.',
          'root_cause': 'After fixture Git metadata relocation, inherited runtime scratch paths still traverse repo/.git/okf-scratch; repo/.git is a file. Claude settings startup and Codex command sandbox refuse ENOTDIR.',
          'outer_log': str(ROOT / 'docs/assurance/mechanical-native-2-v4.log'),
          'outer_exit_file': str(ROOT / 'docs/assurance/mechanical-native-2-v4.log.exit')}
for agent in ('claude', 'codex'):
    path = namespace / (agent + '-results.json')
    value = json.loads(path.read_text())
    capture = namespace / 'retained' / agent / 'live-capture'
    events_path = capture / 'events.jsonl'
    events = [json.loads(line) for line in events_path.read_text().splitlines()] if events_path.exists() else []
    preflight_path = capture / 'preflight.json'
    preflight = json.loads(preflight_path.read_text()) if preflight_path.exists() else None
    stream_path = capture / 'native-stream.jsonl'
    messages, usage = [], None
    for line in stream_path.read_text().splitlines():
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if item.get('type') == 'item.completed' and item.get('item', {}).get('type') == 'agent_message':
            messages.append(item['item']['text'])
        if item.get('type') == 'turn.completed':
            usage = item.get('usage')
    report['agents'][agent] = {'results': str(path), 'totals': value['totals'],
        'qualification': value['qualification'], 'budget': value['budget'],
        'attempts': [{key: attempt[key] for key in ('attempt_id', 'status', 'phase', 'elapsed_seconds',
                    'charged_seconds', 'reserved_seconds', 'exit_code', 'reasons', 'observations')}
                    for attempt in value['attempts']],
        'raw_stream': str(stream_path), 'event_counts': dict(collections.Counter(e['event'] for e in events)),
        'native_sessions': sorted({event['session'] for event in events}),
        'observed_callback_models': sorted({event['model'] for event in events if event.get('model')}),
        'preflight': {'path': str(preflight_path), 'exact_handlers': len(preflight['handlers']),
                      'configuration_sha256': preflight['configuration_sha256'],
                      'meaning': 'Written only after native handler trust/configuration assertions passed; not reviewer event proof.'}
                      if preflight else {'available': False},
        'final_assistant_message': messages[-1] if messages else None, 'native_usage': usage}
    report['charged_agent_seconds'] += value['budget']['charged_seconds']
out = ROOT / 'docs/assurance/mechanical-native-2-v4-report.json'
with out.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({'report': str(out), 'exit': report['exit'],
                  'charged_agent_seconds': report['charged_agent_seconds'],
                  'events': {key: value['event_counts'] for key, value in report['agents'].items()}}, indent=2))
