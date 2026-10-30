"""Summarize actual successful one-shot v7 output and retained binding; no native calls."""
from pathlib import Path

previous = Path(__file__).with_name('record-mechanical-native-2-codex-v6.py')
program = previous.read_text()
program = program.replace('operator-2-mechanical-codex-v6', 'operator-2-mechanical-codex-v7')
program = program.replace('mechanical-native-2-codex-v6', 'mechanical-native-2-codex-v7')
program = program.replace('run-native-2-mechanical-codex-v6.py', 'run-native-2-mechanical-codex-v7.py')
program = program.replace('5d42a15c9fb995ce09703be0121c5b31e6dd387e93d8733b8cc7dd34f0189516',
                          'b0a6231f497622bd2243ab5118fae636860f33ec2f3529a949ed3f19c7ca7bf7')
program = program.replace("'outer_exit': 1", "'outer_exit': 0")
program = program.replace("'evidence_boundary': 'Unchanged strict evaluator reports ERROR/unqualified. Raw callback/model/configuration evidence is partial and cannot establish a passing native reviewer/canonical report/fresh Verify claim.'",
                          "'evidence_boundary': 'Actual strict selected control-delta PASS on current frozen source/operator; this one scenario is not the full baseline or delivery/overall Verify authorization.'")
marker = "out = ROOT / 'docs/assurance/mechanical-native-2-codex-v7-report.json'"
if program.count(marker) != 1:
    raise SystemExit('preserved report marker drift')
binding = '''
import sys
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import review_guard
qualified = report['qualified_final_state']
if not qualified or not value['qualification']['qualified'] or value['totals']['PASS'] != 1:
    raise SystemExit('actual completed v7 report is not qualified PASS')
saved = mechanical / 'saved-review.md'
expected = qualified['native_review']['report_sha256']
captured_hash = review_guard.report_hash(journal['interval']['report'])
saved_hash = review_guard.report_hash(saved.read_text())
if expected != captured_hash or expected != saved_hash:
    raise SystemExit('actual saved/captured/native receipt report hashes disagree')
report['strict_results_check'] = 'PASS (executed within guarded allocation)'
report['report_binding'] = {'expected_sha256': expected, 'captured_sha256': captured_hash,
                            'saved_sha256': saved_hash, 'matches': True,
                            'native_review': qualified['native_review'],
                            'pins': journal['interval']['pins'],
                            'interval_phase': journal['interval']['phase'],
                            'verify': qualified['verify']}
'''
program = program.replace(marker, binding + '\n' + marker)
program = program.replace("'native_sessions', 'final_assistant_message', 'native_errors', 'preflight', 'qualified_final_state')",
                          "'native_sessions', 'final_assistant_message', 'native_errors', 'preflight', 'qualified_final_state', 'report_binding')")
exec(compile(program, str(previous), 'exec'), globals())
