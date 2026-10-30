"""Read-only input comparison; never relabel old execution as a new candidate run."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import artifacts
import lifecycle

old = json.loads((ROOT / 'docs/assurance/mechanical-review-artifact-2-final5.json').read_text())
manifest = artifacts.verify(Path(old['bundle']), old['sha256'])
changed = []
for name, expected in manifest['files'].items():
    path = artifacts.member(ROOT, name)
    current = {'sha256': artifacts.digest(path), 'executable': bool(path.stat().st_mode & 0o111)}
    if current != expected:
        changed.append({'path': name, 'before': expected, 'current': current})
report = {'current_source_tree': lifecycle.tree_hash(ROOT),
          'tested_source_tree': 'd9004a92fd67d8291856395496f3652ce13569635bf75bb67e3c2c91bcf7dce1',
          'original_bundle': old, 'changed_declared_files': changed,
          'new_tests_executed': 0, 'new_freeze_created': False,
          'ledger_reuse': {'initial_mutation_gate': 'RERUN last exit 1; original invalid classifications preserved',
                           'helper_gate': 'RERUN no --inputs and worktree changed'},
          'scope_note': 'Full KIT declared inputs include test_autonomy.py as copied installer payload. Old qualified artifact bytes differ from current tree; execution evidence remains bound to d9004a9. Runtime scripts, executed review test module and its imported helper dependencies are compared here, not rerun.'}
out = ROOT / 'docs/assurance/mechanical-input-comparison-2-final6.json'
with out.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({'current_source_tree': report['current_source_tree'], 'changed': changed,
                  'report': str(out)}, indent=2))
