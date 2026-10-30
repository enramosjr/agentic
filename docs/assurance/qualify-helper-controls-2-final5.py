"""Retain complete diagnostics for the two existing sealed helper mutants only."""
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import artifacts
import lifecycle

original = json.loads((ROOT / 'docs/assurance/mechanical-review-mutations-2-final5.json').read_text())
out = ROOT / 'docs/assurance/mechanical-helper-controls-2-final5.json'
if out.exists() or lifecycle.tree_hash(ROOT) != original['source_tree']:
    raise SystemExit('refuse existing helper report or changed source candidate')
expected = {
    'snapshot-policy-and-history-comparison-omitted': 'self.assertNotEqual(snapshot(), before)',
    'snapshot-blanket-capture-exclusion': 'self.assertNotEqual(snapshot(), policy)',
}
results = []
for item in original['controls']:
    if item['name'] not in expected:
        continue
    qualified = item['variant_artifact']
    artifacts.verify(Path(qualified['bundle']), qualified['sha256'])
    if not item['confirmed']:
        raise SystemExit('unconfirmed helper mutation')
    process = subprocess.run(item['command'], cwd=ROOT, capture_output=True, text=True, timeout=140)
    output = process.stdout + process.stderr
    log = ROOT / ('docs/assurance/' + item['name'] + '-2-final5-full.log')
    with log.open('x') as stream:
        stream.write(output)
    # Match actual exception/result lines, never source-code text embedded in a dictionary repr.
    valid = (bool(re.search(r'^Ran 1 test in ', output, re.M))
             and not re.search(r'^(?:ImportError|ModuleNotFoundError|SyntaxError):', output, re.M)
             and bool(re.search(r'^FAILED \(failures=1\)$', output, re.M)))
    killed = (process.returncode != 0 and valid
              and bool(re.search(r'^AssertionError:', output, re.M))
              and expected[item['name']] in output.split('AssertionError:', 1)[0])
    prefix = output.split('AssertionError:', 1)[0]
    results.append({'name': item['name'], 'confirmed': True, 'artifact': qualified,
                    'command': item['command'], 'exit': process.returncode, 'valid': valid,
                    'killed': killed, 'assertion': expected[item['name']], 'traceback': prefix[-2500:],
                    'full_output': str(log)})
    print(item['name'], 'KILLED' if killed else 'INVALID/SURVIVED', flush=True)
report = {'source_tree': original['source_tree'], 'baseline_reused': True, 'baseline_test_count': 59,
          'original_report_preserved': True, 'controls': results, 'total': len(results),
          'killed': sum(item['killed'] for item in results), 'model_calls': 0}
out.write_text(json.dumps(report, indent=2) + '\n')
raise SystemExit(0 if len(results) == 2 and all(item['killed'] for item in results) else 1)
