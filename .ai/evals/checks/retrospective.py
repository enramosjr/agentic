"""Frozen assertions for actual closure and observation reuse by an agent."""
import json
from pathlib import Path
import subprocess
import sys


root = Path(sys.argv[-1])
assert (root / 'app.py').read_text() == '# Read the input value.\nprint(input())\n'
blocked = (root / 'missing-retrospective.txt').read_text().lower()
assert 'retrospect' in blocked and ('required' in blocked or 'requires' in blocked)
records = list((root / 'knowledge/history/lifecycle').glob('*.json'))
assert records, 'no durable lifecycle records'
for path in records:
    record = json.loads(path.read_text())
    if 'verify' not in record.get('stages', {}):
        continue
    closure = record.get('retrospective', {})
    assert closure.get('outcome') == 'observations', 'no observation closure'
    selected = closure.get('lessons', [])
    assert selected, 'closure selected no lessons'
    lesson = record['lessons'][selected[0] - 1]
    assert 'missing-retrospective.txt' in lesson['evidence']
    assert lesson['text'] == 'Retrospective closure must precede Verify even for small tasks.'
    reference = path.relative_to(root).as_posix() + '#' + str(selected[0])
    output = (root / 'observations.txt').read_text()
    assert reference in output and lesson['text'] in output and lesson['evidence'] in output
    assert 'advisory' in output.lower()
    result = subprocess.run([sys.executable, '.ai/scripts/lifecycle.py', 'observations',
                             '--query', 'retrospective'], cwd=root, text=True,
                            capture_output=True, check=True)
    assert result.stdout == output, 'saved retrieval differs from public command'
    break
else:
    raise AssertionError('no verified retrospective task')
