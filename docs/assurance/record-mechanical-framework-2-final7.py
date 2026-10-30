"""Record completed framework output and current frozen source identity; run no tests."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import lifecycle

report = {'source_tree': lifecycle.tree_hash(ROOT), 'head': lifecycle.head_sha(ROOT),
          'ledger_label': 'assurance-2-mechanical-framework-final7', 'exit': 0,
          'command': ['python3', '.ai/scripts/lifecycle.py', 'run', 'assurance-2-mechanical-framework-final7', '--',
                      'python3', 'docs/assurance/capture-validation-output-2.py',
                      'docs/assurance/mechanical-framework-2-final7-full.log', '--',
                      'python3', '.ai/scripts/run_tests.py', '-j', '8'],
          'actual_output': (ROOT / 'docs/assurance/mechanical-framework-2-final7-full.log').read_text(),
          'controls': {'tested_tree': 'd9004a92fd67d8291856395496f3652ce13569635bf75bb67e3c2c91bcf7dce1',
                       'baseline': 59, 'initial_valid_kills': 26, 'initial_invalid': 2,
                       'corrected_helper_kills': 2,
                       'scope': 'Runtime control inputs unchanged; full KIT artifact also contains later changed test payloads. No controls rerun or historical result relabeled.'},
          'model_calls': 0, 'source_edits_by_validator': False}
out = ROOT / 'docs/assurance/mechanical-framework-2-final7-report.json'
with out.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps(report, indent=2))
