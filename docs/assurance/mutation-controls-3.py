"""Confirmed, isolated assertion controls for increment 3; no native evaluations."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

root = Path.cwd()
scripts = root / '.ai/scripts'
sys.path.insert(0, str(scripts))
sys.path.insert(0, str(scripts / 'tests'))
import disk_tmp

controls = [
    ('containment', 'assurance.py',
     'if not target.is_relative_to(bundle.resolve()) or not target.is_relative_to(root):', 'if False:',
     'ReferenceTests.test_duplicates_late_lines_and_escaping_symlink'),
    ('manual-metadata', 'assurance.py',
     'return dataclasses.replace(obligation, governed_by=metadata)\n',
     'return obligation if obligation.manual is not None else dataclasses.replace(obligation, governed_by=metadata)\n',
     'ReportTests.test_governance_on_every_status_preserves_existing_fields'),
    ('implicit-input', 'assurance.py',
     'return dataclasses.replace(obligation, governed_by=metadata)\n',
     "return dataclasses.replace(obligation, governed_by=metadata, globs=(*obligation.globs, metadata['document']))\n",
     'FreshnessTests.test_adr_is_an_input_only_when_explicitly_declared'),
    ('invalid-delta-evidence', 'lifecycle.py',
     'if (obligation and obligation.declared and not obligation.invalid\n',
     'if (obligation and obligation.declared\n',
     'IntegrationTests.test_invalid_delta_publishes_no_requirement_evidence'),
]
report = {'source': {}, 'controls': [], 'operator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
for file in ('assurance.py', 'lifecycle.py', 'assurance_architecture_demo.py', 'tests/test_assurance_architecture.py'):
    report['source'][file] = hashlib.sha256((scripts / file).read_bytes()).hexdigest()
environment = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
with tempfile.TemporaryDirectory(prefix='architecture-controls-') as temporary:
    copy_root = Path(temporary) / 'kit'
    shutil.copytree(root / '.ai', copy_root / '.ai', ignore=shutil.ignore_patterns('__pycache__'))
    copied = copy_root / '.ai/scripts'
    command = [sys.executable, str(copied / 'tests/test_assurance_architecture.py')]
    baseline = subprocess.run(command + [control[4] for control in controls], cwd=copy_root,
                              env=environment, capture_output=True, text=True, timeout=120)
    report['baseline_exit'] = baseline.returncode
    if baseline.returncode:
        raise SystemExit('control harness baseline failed: ' + baseline.stdout + baseline.stderr)
    for name, file, original, replacement, test in controls:
        path = copied / file
        text = path.read_text()
        if text.count(original) != 1:
            raise SystemExit(f'{name}: mutation anchor is not unique')
        variant = text.replace(original, replacement)
        path.write_text(variant)
        if path.read_text() != variant or variant == text:
            raise SystemExit(f'{name}: mutation was not confirmed')
        try:
            result = subprocess.run(command + [test], cwd=copy_root, env=environment,
                                    capture_output=True, text=True, timeout=120)
            output = result.stdout + result.stderr
            killed = result.returncode != 0 and test.split('.')[-1] in output and (
                'FAIL:' in output or 'ERROR:' in output)
            report['controls'].append({'name': name, 'test': test, 'confirmed': True,
                                       'variant_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                       'exit': result.returncode, 'killed': killed, 'output': output})
        finally:
            path.write_text(text)
        if not killed:
            raise SystemExit(f'{name}: control survived or failed outside its assertion')
report['disabled-checker'] = 'Covered by ConstraintFlowTests.test_disabled_checker_cannot_pass_the_demo; bytes confirmed before execution.'
(root / 'docs/assurance/mutations-3.json').write_text(json.dumps(report, indent=2) + '\n')
print('baseline PASS; 4/4 confirmed source controls KILLED; disabled-checker control is in acceptance')
