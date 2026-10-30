"""Report completed one-shot Codex v6 evidence; no native queries or rescore."""
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
namespace = ROOT / 'docs/assurance/operator-2-mechanical-codex-v6'
result_path = namespace / 'codex-results.json'
value = json.loads(result_path.read_text())
capture = namespace / 'retained/codex/live-capture'
stream_path = capture / 'native-stream.jsonl'
messages, command_results, native_errors, usage = [], [], [], None
for line in stream_path.read_text().splitlines():
    try:
        item = json.loads(line)
    except ValueError:
        if 'ERROR' in line or 'refused' in line or 'blocked' in line:
            native_errors.append(line)
        continue
    if item.get('type') == 'item.completed':
        completed = item.get('item', {})
        if completed.get('type') == 'agent_message':
            messages.append(completed.get('text'))
        if completed.get('type') == 'command_execution':
            command_results.append({key: completed.get(key) for key in ('command', 'exit_code', 'status', 'aggregated_output')})
    if item.get('type') == 'turn.completed':
        usage = item.get('usage')
events_path = capture / 'events.jsonl'
events = [json.loads(line) for line in events_path.read_text().splitlines()] if events_path.exists() else []
def read_if(path):
    return json.loads(path.read_text()) if path.exists() else None
mechanical = namespace / 'retained/codex/mechanical-capture'
state = read_if(mechanical / 'lifecycle-state.json')
journal = read_if(mechanical / 'journal/journal.json')
preflight = read_if(capture / 'preflight.json')
report = {'source_tree': '5d42a15c9fb995ce09703be0121c5b31e6dd387e93d8733b8cc7dd34f0189516',
    'command': ['python3', '.ai/scripts/lifecycle.py', 'run', 'assurance-2-real-agent', '--timeout', '340',
                '--', 'python3', 'docs/assurance/run-native-2-mechanical-codex-v6.py',
                '--authorized-allocation-and-scoped-trust'],
    'executions': 1, 'outer_exit': 1, 'results': str(result_path),
    'outer_log': str(ROOT / 'docs/assurance/mechanical-native-2-codex-v6.log'),
    'outer_exit_file': str(ROOT / 'docs/assurance/mechanical-native-2-codex-v6.log.exit'),
    'limits': {'agent_seconds': 300, 'campaign_wall_seconds': 330},
    'totals': value['totals'], 'qualification': value['qualification'], 'budget': value['budget'],
    'attempts': [{key: attempt.get(key) for key in ('attempt_id', 'status', 'phase', 'started_at', 'ended_at',
                'elapsed_seconds', 'reserved_seconds', 'charged_seconds', 'exit_code', 'reasons')}
                for attempt in value['attempts']],
    'event_counts': dict(collections.Counter(event['event'] for event in events)),
    'native_sessions': sorted({event['session'] for event in events}),
    'callback_models': sorted({event['model'] for event in events if event.get('model')}),
    'final_assistant_message': messages[-1] if messages else None, 'native_usage': usage,
    'native_errors': native_errors, 'last_command_results': command_results[-5:],
    'lifecycle_state': state, 'journal': journal,
    'preflight': {'path': str(capture / 'preflight.json'), 'exact_handlers': len(preflight['handlers']),
                  'configuration_sha256': preflight['configuration_sha256']} if preflight else None,
    'prepared_branch_receipt': read_if(namespace / 'retained/codex/relocation.json'),
    'qualified_final_state': read_if(namespace / 'retained/codex/qualified-final-state.json'),
    'raw_stream': str(stream_path), 'raw_events': str(events_path),
    'retries': 0, 'extra_native_queries': 0, 'source_edits': False,
    'evidence_boundary': 'Unchanged strict evaluator reports ERROR/unqualified. Raw callback/model/configuration evidence is partial and cannot establish a passing native reviewer/canonical report/fresh Verify claim.'}
out = ROOT / 'docs/assurance/mechanical-native-2-codex-v6-report.json'
with out.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({key: report[key] for key in ('outer_exit', 'totals', 'budget', 'attempts', 'event_counts',
    'native_sessions', 'final_assistant_message', 'native_errors', 'preflight', 'qualified_final_state')}, indent=2))
