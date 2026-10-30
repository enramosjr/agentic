"""Prove the integration-safe report-only assertion detects invoking-source writes."""
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

with tempfile.TemporaryDirectory(dir=scratch.directory(ROOT)) as directory:
    root = Path(directory)
    scripts = root / '.ai/scripts'
    shutil.copytree(ROOT / '.ai/scripts', scripts, ignore=shutil.ignore_patterns('__pycache__'))
    for args in (['init', '-q'], ['add', '-A'], ['-c', 'user.name=Test', '-c', 'user.email=t@t',
                                            'commit', '-qm', 'fixture']):
        subprocess.run(['git', *args], cwd=root, check=True, capture_output=True)
    argv = [sys.executable, '-m', 'unittest', 'discover', '-s', str(scripts / 'tests'),
            '-p', 'test_assurance_measure.py', '-k', 'ReportOnlyTests']
    def run():
        return subprocess.run(argv, cwd=root, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                              capture_output=True, text=True, timeout=120)
    baseline = run()
    if baseline.returncode:
        raise SystemExit('copied baseline failed: ' + baseline.stderr[-1500:])
    path = scripts / 'assurance_measure.py'
    before = path.read_text()
    old = ('            only: Optional[tuple[str, ...]] = None) -> dict:\n'
           '    base = scratch.require_disk(base if base is not None else _base())\n')
    new = old + ('    protected = Path(__file__).with_name("assurance.py")\n'
                 '    protected.write_bytes(protected.read_bytes() + b"\\n# mutated by measurement\\n")\n')
    if before.count(old) != 1:
        raise SystemExit('mutation target count != 1')
    changed = before.replace(old, new)
    path.write_text(changed)
    confirmed = path.read_text() == changed and changed != before
    if not confirmed:
        raise SystemExit('mutation not confirmed')
    broken = run()
    killed = broken.returncode != 0 and 'AssertionError' in broken.stderr and 'assurance.py' in broken.stderr
    report = {'baseline_exit': baseline.returncode, 'confirmed': confirmed,
              'mutant_exit': broken.returncode, 'killed': killed, 'tail': broken.stderr[-1800:]}
    (ROOT / 'docs/assurance/mutation-measure-integration-2.json').write_text(json.dumps(report, indent=2) + '\n')
    print('measurement source-write mutant:', 'KILLED' if killed else 'SURVIVED')
    raise SystemExit(0 if killed else 1)
