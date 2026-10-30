"""Confirmed broken variants of increment 2, in independent throwaway copies."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import scratch

MUTATIONS = [
    ('gate-omitted', 'lifecycle.py',
     'problem = assurance.gate_problem(root, state, record_path(root, state).parent, tree)',
     'problem = None', 'test_unverified_blocks'),
    ('status-allowed', 'assurance.py',
     "FAILING = ('STALE', 'FAILED', 'UNVERIFIED', 'INVALID')",
     "FAILING = ('STALE', 'FAILED', 'INVALID')", 'test_unverified_blocks'),
    ('head-baseline', 'assurance.py',
     "chosen = touched(root, state.get('head'), obligations, operated)",
     "chosen = touched(root, 'HEAD', obligations, operated)", 'test_all_path_states'),
    ('block-omitted', 'assurance.py',
     'or baseline.get((o.capability, o.id)) != o.block_sha256',
     'or False', 'test_blocks_unrelated'),
    ('delta-omitted', 'assurance.py',
     "chosen = touched(root, state.get('head'), obligations, operated)",
     "chosen = touched(root, state.get('head'), obligations, ())", 'test_operated_id'),
    ('git-swallowed', 'assurance.py',
     "if result.returncode:\n            raise ValueError('assurance selection failed:",
     "if False:\n            raise ValueError('assurance selection failed:",
     'test_git_errors'),
    ('normalized-baseline', 'assurance.py', 'result = _git(root, *args, binary=True)',
     'result = _git(root, *args)', 'test_unchanged_crlf'),
    ('risk-waiver', 'assurance.py',
     'results = [evaluate(root, o, items, tree) for o in chosen]',
     'results = [evaluate(root, o, items, tree) for o in chosen if not o.risk]', 'test_risk_and_attestation'),
    ('inexact-argv', 'lifecycle.py', 'and obligation.manual is None and list(obligation.argv) == argv)',
     'and obligation.manual is None)', 'test_different_command'),
    ('wrong-scope', 'lifecycle.py', 'globs = obligation.evidence_globs\n',
     'globs = []\n', 'test_matching_add'),
    ('post-run-inputs', 'lifecycle.py',
     "snapshot.update(exit=entry['exit'], duration=round(durations[rid], 3), at=now())",
     "snapshot.update(exit=entry['exit'], duration=round(durations[rid], 3), tree=tree_hash(root), "
     "inputs_sha256=ledger.inputs_digest(root, snapshot['inputs']))\n"
     "            if snapshot['inputs']:\n"
     "                snapshot['input_files'] = ledger.inputs_snapshot(root, snapshot['inputs'])",
     'test_self_modified'),
    ('start-timestamp', 'lifecycle.py',
     "snapshot.update(exit=entry['exit'], duration=round(durations[rid], 3), at=now())",
     "snapshot.update(exit=entry['exit'], duration=round(durations[rid], 3))", 'test_later_completed'),
    ('duplicate-execution', 'lifecycle.py',
     '            result = subprocess.run(argv, cwd=root, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, errors="replace", timeout=args.timeout)',
     '            subprocess.run(argv, cwd=root, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, errors="replace", timeout=args.timeout)\n'
     '            result = subprocess.run(argv, cwd=root, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, errors="replace", timeout=args.timeout)',
     'test_matching_add'),
    ('failure-as-pass', 'lifecycle.py', "snapshot.update(exit=entry['exit'],",
     'snapshot.update(exit=0,', 'test_failed_unlaunchable'),
    ('reload-omitted', 'lifecycle.py',
     '        state = evidence_state(root, state)\n        for entry in results:',
     '        for entry in results:', 'test_nested_run'),
]


def attempt(item):
    name, module, old, new, selected = item
    with tempfile.TemporaryDirectory(dir=scratch.directory(ROOT)) as directory:
        root = Path(directory)
        scripts = root / '.ai/scripts'
        shutil.copytree(ROOT / '.ai/scripts', scripts, ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy2(ROOT / '.ai/lifecycle.md', root / '.ai/lifecycle.md')
        subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
        confirmed = False
        if module:
            path = scripts / module
            text = path.read_text()
            if text.count(old) != 1:
                return {'name': name, 'error': 'mutation match count != 1', 'killed': False}
            changed = text.replace(old, new)
            path.write_text(changed)
            confirmed = path.read_text() == changed and changed != text
            if not confirmed:
                return {'name': name, 'error': 'mutation not confirmed', 'killed': False}
        argv = [sys.executable, '-m', 'unittest', 'discover', '-s', str(scripts / 'tests'),
                '-p', 'test_assurance_gate.py']
        if selected:
            argv += ['-k', selected]
        result = subprocess.run(argv, cwd=root, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                                capture_output=True, text=True, timeout=180)
        output = result.stdout + result.stderr
        valid = 'Ran 0 tests' not in output and 'ImportError' not in output and 'SyntaxError' not in output
        return {'name': name, 'confirmed': confirmed, 'exit': result.returncode,
                'killed': valid and result.returncode != 0,
                'tail': output[-2500:]}


requested = set(sys.argv[1:])
variants = [item for item in MUTATIONS if not requested or item[0] in requested]
if requested - {item[0] for item in variants}:
    raise SystemExit('unknown mutation name')
baseline = attempt(('baseline', None, '', '', 'TouchedScopeTests' if requested else None))
if baseline['exit'] != 0:
    print(json.dumps(baseline, indent=2))
    raise SystemExit('copied baseline failed; mutation evidence invalid')
with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(attempt, variants))
filename = 'mutations-2-targeted.json' if requested else 'mutations-2.json'
(ROOT / 'docs/assurance' / filename).write_text(json.dumps(results, indent=2) + '\n')
for result in results:
    print(result['name'], 'KILLED' if result['killed'] else 'INVALID/SURVIVED', result.get('error', ''))
raise SystemExit(0 if all(result['killed'] for result in results) else 1)
