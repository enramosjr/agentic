"""Bounded isolated increment 5 controls; never mutate the source checkout."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / '.ai/scripts'
sys.path.insert(0, str(SCRIPTS / 'tests'))
import disk_tmp  # noqa: E402,F401


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(root, classes):
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
    result = subprocess.run([sys.executable, str(root / '.ai/scripts/tests/test_assurance_inputs.py'), *classes],
                            cwd=root, env=env, capture_output=True, text=True, timeout=120)
    return {'command': classes, 'exit': result.returncode, 'output': (result.stdout + result.stderr)[-9000:]}


def copy_source(root):
    target = root / '.ai/scripts'
    (target / 'tests').mkdir(parents=True)
    for path in SCRIPTS.glob('*.py'):
        shutil.copy2(path, target / path.name)
    for name in ('test_assurance_inputs.py', 'test_run_tests.py', 'disk_tmp.py'):
        shutil.copy2(SCRIPTS / 'tests' / name, target / 'tests' / name)
    shutil.copy2(ROOT / '.ai/lifecycle.md', root / '.ai/lifecycle.md')


report = {'operator_sha256': digest(Path(__file__)),
          'source_sha256': {str(p.relative_to(ROOT)): digest(p) for p in
                            (SCRIPTS / 'assurance_inputs.py', SCRIPTS / 'tests/test_assurance_inputs.py',
                             SCRIPTS / 'tests/test_run_tests.py')}, 'controls': []}
with tempfile.TemporaryDirectory() as name:
    base = Path(name)
    original = base / 'baseline'
    copy_source(original)
    report['baseline'] = run(original, ['DependencyCoverageTests', 'ProfileTests', 'EndToEndTests'])
    assert report['baseline']['exit'] == 0, report['baseline']
    for variant in ('missing-runner', 'missing-helper', 'empty-discovery', 'loose-command'):
        root = base / variant
        copy_source(root)
        path = root / '.ai/scripts/assurance_inputs.py'
        text = path.read_text()
        if variant in ('missing-runner', 'missing-helper'):
            item = '.ai/scripts/run_tests.py' if variant == 'missing-runner' else '.ai/scripts/tests/disk_tmp.py'
            if variant == 'missing-runner':
                old, new = "'.ai/scripts/scratch.py', '.ai/scripts/run_tests.py'", "'.ai/scripts/scratch.py'"
            else:
                old, new = "'.ai/scripts/tests/test_run_tests.py', '.ai/scripts/tests/disk_tmp.py',", "'.ai/scripts/tests/test_run_tests.py',"
            assert text.count(old) == 1
            text = text.replace(old, new)
            text = ''.join(line for line in text.splitlines(keepends=True) if not line.startswith('        ' + repr(item) + ':'))
            classes = ['DependencyCoverageTests']
        elif variant == 'loose-command':
            old, new = "p['argv'] == list(argv)", "p['argv'][:3] == list(argv)[:3]"
            assert text.count(old) == 1
            text = text.replace(old, new)
            classes = ['ProfileTests']
        else:
            path = root / '.ai/scripts/tests/test_run_tests.py'
            text = path.read_text()
            old, new = 'class RunnerTests(unittest.TestCase):', 'class RunnerChecks:'
            assert text.count(old) == 1
            text = text.replace(old, new)
            classes = ['EndToEndTests']
        before = digest(path)
        path.write_text(text)
        assert old not in path.read_text() and new in path.read_text() and digest(path) != before
        result = run(root, classes)
        result.update({'name': variant, 'confirmed': True, 'before_sha256': before, 'after_sha256': digest(path)})
        result['killed'] = result['exit'] != 0 and 'FAILED (failures=' in result['output']
        if variant == 'empty-discovery':
            result['killed'] = result['killed'] and 'empty discovery cannot verify the pilot' in result['output']
        report['controls'].append(result)
report['passed'] = all(c['killed'] for c in report['controls'])
(ROOT / 'docs/assurance/mutations-5-reviewed.json').write_text(json.dumps(report, indent=2) + '\n')
print('baseline PASS; confirmed controls killed: ' + str(sum(c['killed'] for c in report['controls'])) + '/4')
raise SystemExit(0 if report['passed'] else 1)
