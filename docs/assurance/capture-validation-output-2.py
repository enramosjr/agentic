"""Capture every byte from a local check; preserve its exact exit status."""
from pathlib import Path
import subprocess
import sys

log = Path(sys.argv[1])
if log.exists():
    raise SystemExit('refuse to overwrite retained validation output')
if sys.argv[2:3] != ['--'] or not sys.argv[3:]:
    raise SystemExit('usage: capture-validation-output-2.py LOG -- COMMAND ...')
with log.open('x') as stream:
    result = subprocess.run(sys.argv[3:], stdout=stream, stderr=subprocess.STDOUT)
print(f'full output: {log}; exit={result.returncode}', flush=True)
raise SystemExit(result.returncode)
