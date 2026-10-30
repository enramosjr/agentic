"""Summarize immutable one-shot native allocation results without any new launch."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
namespace = ROOT / 'docs/assurance/operator-2-mechanical-native-v3'
report = {'source_tree': 'a9e58f56be695f860d87a470fdf18b038e698c18a5982703bab939b088e7f409',
          'command': ['python3', '.ai/scripts/lifecycle.py', 'run', 'assurance-2-real-agent',
                      '--timeout', '670', '--', 'python3', 'docs/assurance/run-native-2-review-enforcement.py',
                      '--authorized-allocation-and-scoped-trust'],
          'executions': 1, 'exit': 1, 'namespace': str(namespace),
          'limits': {'agent_seconds': 600, 'campaign_wall_seconds': 660, 'per_cell_seconds': 300},
          'agents': {}, 'charged_agent_seconds': 0,
          'native_trust_preflight': 'Not reached; launcher never invoked. No actual response available.',
          'behavioral_proof': 'Unavailable; both attempts failed during evaluator setup.',
          'cause': "Prepared --checks-dir points to an operator directory missing delta.json, required by control-delta. Both reports say unknown operator check ID 'delta'.",
          'integrity_check': 'Both results-check --require-real --campaign-complete commands failed; reports explicitly unqualified. Additional diagnostics require the baseline two configurations/16 scenarios/three repeats; no scope expansion was made.',
          'retries': 0, 'source_edits': False, 'persistent_trust_changes': False,
          'outer_log': str(ROOT / 'docs/assurance/mechanical-native-2-v3.log'),
          'outer_exit_file': str(ROOT / 'docs/assurance/mechanical-native-2-v3.log.exit')}
for agent in ('claude', 'codex'):
    path = namespace / (agent + '-results.json')
    value = json.loads(path.read_text())
    attempts = value['attempts']
    report['agents'][agent] = {'results': str(path), 'totals': value['totals'],
        'qualification': value['qualification'], 'budget': value['budget'],
        'attempts': [{key: attempt[key] for key in ('attempt_id', 'status', 'phase', 'elapsed_seconds',
                    'charged_seconds', 'reserved_seconds', 'launch_intent', 'process_supervision', 'reasons',
                    'observations')} for attempt in attempts]}
    report['charged_agent_seconds'] += value['budget']['charged_seconds']
out = ROOT / 'docs/assurance/mechanical-native-2-v3-report.json'
with out.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({'report': str(out), 'exit': report['exit'],
                  'charged_agent_seconds': report['charged_agent_seconds'],
                  'agents': {key: value['totals'] for key, value in report['agents'].items()}}, indent=2))
