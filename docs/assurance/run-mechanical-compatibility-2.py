"""Scoped existing-path compatibility checks only; no model calls or full framework gate."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import lifecycle

FILES = ('test_install.py', 'test_ledger.py', 'test_completion.py', 'test_artifacts.py',
         'test_autonomy_validation.py', 'test_pr_sync.py')
started_tree = lifecycle.tree_hash(ROOT)


def check(name):
    label = 'assurance-2-compat-' + name.removeprefix('test_').removesuffix('.py').replace('_', '-')
    reuse = subprocess.run([sys.executable, '.ai/scripts/lifecycle.py', 'reuse', label], cwd=ROOT,
                           capture_output=True, text=True, timeout=30)
    if reuse.returncode == 0:
        return {'module': name, 'label': label, 'reused': True, 'exit': 0, 'output': reuse.stdout}
    command = [sys.executable, '.ai/scripts/lifecycle.py', 'run', label, '--',
               sys.executable, '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests', '-p', name]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=300)
    output = result.stdout + result.stderr
    (ROOT / 'docs/assurance' / (label + '.log')).write_text(output)
    match = re.search(r' tree=([0-9a-f]+)', output)
    return {'module': name, 'label': label, 'command': command, 'reuse': reuse.stdout.strip(),
            'exit': result.returncode, 'recorded_tree': match[1] if match else None, 'output': output}


with ThreadPoolExecutor(max_workers=3) as executor:
    results = list(executor.map(check, FILES))
report = {'source_head': lifecycle.head_sha(ROOT), 'start_tree': started_tree,
          'end_tree': lifecycle.tree_hash(ROOT), 'scope': 'six existing compatibility modules only',
          'model_calls': 0, 'results': results}
(ROOT / 'docs/assurance/mechanical-compatibility-2.json').write_text(json.dumps(report, indent=2) + '\n')
for item in results:
    print(item['module'], 'PASS' if item['exit'] == 0 else 'FAIL', item.get('recorded_tree', 'REUSED'))
    if item['exit']:
        print(item['output'])
raise SystemExit(0 if all(item['exit'] == 0 for item in results) else 1)
