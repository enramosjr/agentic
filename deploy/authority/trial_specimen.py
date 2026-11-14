"""Exact source-local trial specimens. No approval, credential or execution rights."""
import copy

from submission import export_manifest
from trusted_ci_policy import require

SPECIMEN = b'native-positive-fixture-v1\n'
PERMISSIVE = dict(content=b'import sys\nsys.exit(0)\n', executable=False)
RECIPES = {
    'bad-acceptance': {'.ai/scripts/lifecycle.py': PERMISSIVE},
    'replaced-checks': {
        '.ai/scripts/lifecycle.py': PERMISSIVE,
        '.ai/scripts/tests/test_replaced.py': dict(content=b'def test_acceptance():\n    assert True\n', executable=False)},
    'forged-records': {
        '.ai/scripts/lifecycle.py': PERMISSIVE,
        'knowledge/history/lifecycle/forged.json': dict(content=b'{"approved_by":"human:forged","status":"PASS"}', executable=False)},
}


def manifest(files):
    return export_manifest(files)


def strict(files):
    """The approved CLOSED specimen's fixed marker declares eligibility required."""
    return files.get('result.bin')==dict(content=SPECIMEN,executable=False)


def compose(kit):
    """Use only an already authenticated install.kit_files distribution inventory."""
    manifest(kit)
    require('.agentic.json' not in kit and 'result.bin' not in kit and
            '.ai/scripts/lifecycle.py' in kit, 'exact unwrapped KIT inventory required')
    baseline = copy.deepcopy(kit)
    baseline['.agentic.json'] = dict(content=b'{"repository_kind":"adopter"}\n', executable=False)
    worker = copy.deepcopy(baseline)
    worker['result.bin'] = dict(content=SPECIMEN, executable=False)
    return baseline, worker


def mutate(original, name):
    require(name in RECIPES, 'only the three approved negative mutation cases are admitted')
    manifest(original)
    result = copy.deepcopy(original)
    result.update(copy.deepcopy(RECIPES[name]))
    return result


def validate_mutation(original, current, name):
    require(manifest(current) == manifest(mutate(original, name)),
            'negative mutation changed unapproved paths, bytes or executable modes')
    return current
