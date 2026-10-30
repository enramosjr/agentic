"""Verify final10's sealed inputs against delivery without rerunning runtime checks."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import artifacts

bundle = Path('/home/enramosjr/Projects/agentic/.git/okf-scratch/qualified-sp1dk82n')
pin = 'fe2fcdd5eb9ac87a368b0c0073d202b0928d84e1ec54cb1cb82574be236853c0'
manifest = artifacts.verify(bundle, pin)
changed = []
for name, expected in manifest['files'].items():
    path = ROOT / name
    if (hashlib.sha256(path.read_bytes()).hexdigest() != expected['sha256']
            or bool(path.stat().st_mode & 0o111) != expected['executable']):
        changed.append(name)
cleanup = '.ai/scripts/tests/test_assurance_gate.py'
if changed != [cleanup]:
    raise AssertionError(changed)
base_changes = subprocess.check_output(['git', 'diff', '--name-status',
    '9efcfb7939cd6818f28caab48d3dadf4b2d69f4a', 'c19c77c', '--'], cwd=ROOT, text=True).strip()
if base_changes != 'D\t.github/rulesets/main.json':
    raise AssertionError(base_changes)
test = (ROOT / cleanup).read_bytes()
original = (bundle / cleanup).read_bytes()
if original != test + b'\n' or ast.dump(ast.parse(test)) != ast.dump(ast.parse(original)):
    raise AssertionError('trailing blank line changes test syntax')
report = {'sealed_input_count': len(manifest['files']), 'changed_sealed_inputs': changed,
          'other_sealed_inputs_identical': True,
          'artifact_sha256': pin, 'upstream_changes': base_changes,
          'test_assurance_gate_cleanup': 'single trailing blank line; identical AST',
          'boundary': 'Existing runtime results retain original provenance; this is source-equivalence proof, not a new test PASS.'}
with (ROOT / 'docs/assurance/delivery-2-source-scope-proof.json').open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps(report))
