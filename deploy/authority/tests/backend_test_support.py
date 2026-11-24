"""Source-only backend fixtures; this package is never exported to adopters."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
for directory in (ROOT / '.ai/scripts/tests', ROOT / '.ai/scripts', ROOT / 'deploy/authority'):
    sys.path.insert(0, str(directory))


import copy
import marshal

_ATOMS = (str, int, float, bool, bytes, type(None))
_CONTAINERS = (dict, list, tuple)
_deepcopy = copy.deepcopy


def fast_copy(value):
    """Independent copy of a JSON-shaped fixture document, far faster than deepcopy.

    Fixture fakes copy on every read and the documents grow with each case, so deepcopy's
    memo bookkeeping dominates the native suites. A marshal round trip copies plain
    dict/list/tuple/str/int/float/bool/bytes/None trees in C, keeping container types and shared
    substructure like deepcopy; anything else (subclasses, other objects) takes the Python walk,
    which falls back to deepcopy for what it cannot copy itself."""
    kind = type(value)
    if kind in _ATOMS:
        return value
    if kind in _CONTAINERS:
        try:
            return marshal.loads(marshal.dumps(value))
        except ValueError:
            pass
    if kind is dict:
        return {key: fast_copy(item) for key, item in value.items()}
    if kind is list:
        return [fast_copy(item) for item in value]
    if kind is tuple:
        return tuple(fast_copy(item) for item in value)
    return _deepcopy(value)


def _fast_deepcopy(value, memo=None, *args):
    """Test-suite `copy.deepcopy`: plain document trees copy through `fast_copy`; everything else,
    and any call that passes a memo, is the standard library deepcopy."""
    if memo is None and not args and type(value) in _CONTAINERS:
        return fast_copy(value)
    return _deepcopy(value, memo, *args)


copy.deepcopy = _fast_deepcopy


def config(adapter='aws'):
    return dict(adapter=adapter, deployment='agentic-123', authority='owner/authority',
                branch='main', account=('123456789012' if adapter == 'aws' else
                 '11111111-2222-3333-4444-555555555555'), region=('us-east-2' if adapter == 'aws' else 'eastus'))


class LocalSession:
    """Explicit API-fixture capability only; never remote authorization evidence."""
    def __init__(self, journal=None):
        self.journal = journal
        self.effects = []

    def require_effect(self, action, scope):
        self.effects.append((action, scope))

    def write_configuration(self, expected, value):
        self.journal.write(expected, value)

    def allow_software_revision(self, repository, branch, revision):
        self.effects.append(('software-revision', revision))
