"""Import-safe source acceptance dispatcher; local contracts cannot qualify hosting."""
from pathlib import Path
import subprocess
import sys


def main(argv=None):
    backend = Path(__file__).resolve().parents[3] / 'deploy/authority/tests/test_bootstrap_stage_contracts.py'
    if not backend.is_file():
        print('optional backend unavailable; hosted acceptance is unqualified and enforcement inactive', file=sys.stderr)
        return 2
    return subprocess.call([sys.executable, str(backend), *(sys.argv[1:] if argv is None else argv)])


if __name__ == '__main__':
    sys.exit(main())
