"""Summarize retained v5 outcomes and bindings, making no runtime/model calls."""
import collections
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import review_guard

namespace = ROOT / 'docs/assurance/operator-2-mechanical-native-v5'
report = {'source_tree': 'a9e58f56be695f860d87a470fdf18b038e698c18a5982703bab939b088e7f409',
          'command': ['python3', '.ai/scripts/lifecycle.py', 'run', 'assurance-2-real-agent',
                      '--timeout', '670', '--', 'python3', 'docs/assurance/run-native-2-review-enforcement.py',
                      '--authorized-allocation-and-scoped-trust'],
          'executions': 1, 'exit': 1, 'namespace': str(namespace),
          'limits': {'agent_seconds': 600, 'campaign_wall_seconds': 660, 'per_cell_seconds': 300},
          'agents': {}, 'charged_agent_seconds': 0, 'retries': 0,
          'source_edits': False, 'persistent_trust_changes_by_validator': False,
          'strict_results_check': {'claude': 'PASS', 'codex': 'FAIL: unqualified execution/provenance'},
          'codex_actual_blocker': 'Native-stream line65: lifecycle PreToolUse refused git switch -c named-greeting: Git metadata owner is unsupported or ambiguous; use an ordinary checkout/index.',
          'codex_launcher_stderr_limit': 'Native stream retains the CLI final message, not launcher stderr. Evaluator excerpt truncates first4096bytes; launch control/output was cleaned. No exact final launcher refusal text can be quoted from retained output.',
          'outer_log': str(ROOT / 'docs/assurance/mechanical-native-2-v5.log'),
          'outer_exit_file': str(ROOT / 'docs/assurance/mechanical-native-2-v5.log.exit')}
for agent in ('claude', 'codex'):
    result_path = namespace / (agent + '-results.json')
    value = json.loads(result_path.read_text())
    retained = namespace / 'retained' / agent
    capture = retained / 'live-capture'
    event_path = capture / 'events.jsonl'
    events = [json.loads(line) for line in event_path.read_text().splitlines()] if event_path.exists() else []
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
    mechanical = retained / 'mechanical-capture'
    state = json.loads((mechanical / 'lifecycle-state.json').read_text())
    journal = json.loads((mechanical / 'journal/journal.json').read_text())
    qualified_path = retained / 'qualified-final-state.json'
    qualified = json.loads(qualified_path.read_text()) if qualified_path.exists() else None
    saved = mechanical / 'saved-review.md'
    binding = None
    if qualified:
        expected = qualified['native_review']['report_sha256']
        binding = {'native_review': qualified['native_review'], 'verify': qualified['verify'],
                   'saved_body_sha256': review_guard.report_hash(saved.read_text()),
                   'captured_body_sha256': review_guard.report_hash(journal['interval']['report']),
                   'expected_body_sha256': expected, 'interval_phase': journal['interval']['phase'],
                   'interval_pins': journal['interval']['pins'],
                   'qualified_final_state': str(qualified_path)}
        binding['body_hashes_match'] = expected == binding['saved_body_sha256'] == binding['captured_body_sha256']
    report['agents'][agent] = {'results': str(result_path), 'totals': value['totals'],
        'qualification': value['qualification'], 'budget': value['budget'],
        'attempts': [{key: attempt[key] for key in ('attempt_id', 'status', 'phase', 'elapsed_seconds',
                    'charged_seconds', 'reserved_seconds', 'exit_code', 'reasons')} for attempt in value['attempts']],
        'observed_model': value['provenance']['agent']['observed_model'],
        'event_counts': dict(collections.Counter(event['event'] for event in events)),
        'native_sessions': sorted({event['session'] for event in events}),
        'preflight': {'path': str(preflight_path), 'exact_handlers': len(preflight['handlers']),
                      'configuration_sha256': preflight['configuration_sha256'],
                      'meaning': 'Written after native trusted-handler/configuration assertions; separate from reviewer event proof.'}
                      if preflight else {'separate_preflight_file': False},
        'final_assistant_message': messages[-1] if messages else None, 'native_usage': usage,
        'lifecycle_stages': list(state.get('stages', {})), 'native_registered_sessions': journal['sessions'],
        'writers_at_retention': journal['writers'], 'interval_phase': (journal.get('interval') or {}).get('phase'),
        'journal_request': journal.get('request'), 'mechanical_binding': binding,
        'raw_stream': str(stream_path), 'raw_events': str(event_path), 'retained_state': str(mechanical)}
    report['charged_agent_seconds'] += value['budget']['charged_seconds']
out = ROOT / 'docs/assurance/mechanical-native-2-v5-report.json'
with out.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({'report': str(out), 'exit': report['exit'], 'charged_agent_seconds': report['charged_agent_seconds'],
                  'agents': {key: {'totals': value['totals'], 'budget': value['budget'], 'callbacks': value['event_counts'],
                                  'binding_hashes_match': (value['mechanical_binding'] or {}).get('body_hashes_match')}
                             for key, value in report['agents'].items()}}, indent=2))
