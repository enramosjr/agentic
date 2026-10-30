"""Record completed local final10 gates and unchanged v7 evidence; run no checks."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import lifecycle

BASE = ROOT / 'docs/assurance'
summary = json.loads((BASE / 'mechanical-review-mutations-2-final10-summary.json').read_text())
preserved = json.loads((BASE / 'native-codex-v7-help-fix-preservation-after.json').read_text())
output = (BASE / 'mechanical-framework-2-final10-full.log').read_text()
count = re.search(r'Ran (\d+) tests in ([\d.]+)s with (\d+) workers: OK', output)
if not count or int((BASE / 'mechanical-framework-2-final10.log.exit').read_text()) != 0:
    raise SystemExit('completed fullgate is not passing')
tree = lifecycle.tree_hash(ROOT)
if tree != summary['source_tree'] or not preserved['unchanged']:
    raise SystemExit('source drift or native evidence preservation failure')
state = lifecycle.load(ROOT)
entries = {entry['label']: entry for entry in state['ledger'] if entry['label'] in
           ('assurance-2-mechanical-mutations-final10', 'assurance-2-mechanical-framework-final10')}
report = {'created_at': datetime.now(timezone.utc).isoformat(), 'source_tree': tree,
          'baseline_tests': summary['baseline_test_count'], 'controls': summary['total'],
          'controls_killed': summary['killed'], 'artifact_bundle': summary['artifact_bundle'],
          'artifact_sha256': summary['artifact_sha256'], 'declared_files': summary['declared_files'],
          'framework': {'exit': 0, 'actual_output': output, 'tests': int(count[1]),
                        'seconds': float(count[2]), 'workers': int(count[3])},
          'ledger_entries': entries,
          'native_v7_preservation': {'files': len(preserved['files']), 'unchanged': True,
              'comparison_at': preserved['created_at'], 'changed': preserved['changed'],
              'before_manifest_sha256': preserved['before_manifest_sha256'],
              'after_manifest': str(BASE / 'native-codex-v7-help-fix-preservation-after.json')},
          'native_calls': 0, 'model_calls': 0, 'new_attempt_preparation': False,
          'source_edits_by_validator': False, 'historical_evidence_edits': False}
with (BASE / 'mechanical-validation-2-final10-report.json').open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({key: report[key] for key in ('created_at', 'source_tree', 'baseline_tests', 'controls',
                  'controls_killed', 'framework', 'native_v7_preservation')}, indent=2))
