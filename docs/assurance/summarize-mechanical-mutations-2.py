"""Summarize the completed immutable-artifact controls without rerunning tests."""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
suffix = {'--final': '-final', '--final2': '-final2', '--final3': '-final3', '--final4': '-final4', '--final5': '-final5', '--final8': '-final8', '--final9': '-final9', '--final10': '-final10'}.get(sys.argv[1] if len(sys.argv) == 2 else '', '')
report = json.loads((ROOT / f'docs/assurance/mechanical-review-mutations-2{suffix}.json').read_text())
matched = re.findall(r'Ran (\d+) tests?', report['baseline']['output'])
summary = {'source_tree': report['source_tree'], 'artifact_bundle': report['artifact']['bundle'],
    'artifact_sha256': report['artifact']['sha256'], 'declared_files': len(report['artifact']['files']),
    'baseline_exit': report['baseline']['exit'], 'baseline_valid': report['baseline']['valid'],
    'baseline_test_count': int(matched[-1]) if matched else None,
    'total': report['total'], 'killed': report['killed'], 'model_calls': report['model_calls'],
    'controls': [{'name': item['name'], 'confirmed': item['confirmed'], 'killed': item['killed'],
        'valid': item.get('valid'), 'exit': item.get('exit'), 'test': item['test'],
        'variant_sha256': item['variant_artifact']['sha256']} for item in report['controls']]}
(ROOT / f'docs/assurance/mechanical-review-mutations-2{suffix}-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
for item in report['controls']:
    if not item['killed']:
        print(json.dumps({key: value for key, value in item.items() if key in ('name', 'confirmed', 'valid', 'exit', 'output', 'error')}, indent=2))
