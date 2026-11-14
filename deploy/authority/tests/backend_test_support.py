"""Source-only backend fixtures; this package is never exported to adopters."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
for directory in (ROOT / '.ai/scripts/tests', ROOT / '.ai/scripts', ROOT / 'deploy/authority'):
    sys.path.insert(0, str(directory))


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
