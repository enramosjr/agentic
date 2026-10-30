"""Hash exact known v7 proof files before/after local source repair; never edit evidence."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/assurance'
BEFORE = BASE / 'native-codex-v7-help-fix-preservation-before.json'
AFTER = BASE / 'native-codex-v7-help-fix-preservation-after.json'


def snapshot(path):
    if not path.resolve().is_relative_to(ROOT) or path.is_symlink():
        raise SystemExit('refuse nonlocal or symlink evidence path: ' + str(path))
    if not path.exists():
        return {'exists': False}
    if not path.is_file():
        raise SystemExit('expected exact evidence file: ' + str(path))
    return {'exists': True, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'mode': oct(stat.S_IMODE(path.stat().st_mode)), 'bytes': path.stat().st_size}


def main():
    if sys.argv[1:] == ['before']:
        report_path = BASE / 'mechanical-native-2-codex-v7-report.json'
        report = json.loads(report_path.read_text())
        namespace = BASE / 'operator-2-mechanical-codex-v7'
        retained = namespace / 'retained/codex'
        mechanical = retained / 'mechanical-capture'
        journal_path = mechanical / 'journal/journal.json'
        journal = json.loads(journal_path.read_text())
        capture = mechanical / 'journal/captures' / journal['interval']['id']
        paths = [report_path, BASE / 'mechanical-native-2-codex-v7-report.md',
                 Path(report['outer_log']), Path(report['outer_exit_file']), Path(report['results']),
                 Path(report['raw_stream']), Path(report['raw_events']),
                 Path(report['preflight']['path']), retained / 'qualified-final-state.json',
                 retained / 'relocation.json', mechanical / 'saved-review.md',
                 mechanical / 'lifecycle-state.json', mechanical / 'expectation.json', journal_path,
                 capture / 'capture.json', capture / 'completion.json', capture / 'publication.json']
        files = {str(path.relative_to(ROOT)): snapshot(path) for path in paths}
        value = {'created_at': datetime.now(timezone.utc).isoformat(),
                 'tested_product_tree': report['source_tree'], 'files': files,
                 'preservation_scope': 'Exact known original result/outer/raw/qualified state/report/journal/capture files only; no recursive filesystem discovery, edits, rescoring or native queries.'}
        with BEFORE.open('x') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')
        print(json.dumps({'before_manifest': str(BEFORE), 'file_count': len(files),
                          'existing_files': sum(item['exists'] for item in files.values()),
                          'sha256': hashlib.sha256(BEFORE.read_bytes()).hexdigest()}, indent=2))
        return 0
    if sys.argv[1:] == ['after']:
        original = json.loads(BEFORE.read_text())
        current = {name: snapshot(ROOT / name) for name in original['files']}
        changed = [name for name, expected in original['files'].items() if current[name] != expected]
        value = {'created_at': datetime.now(timezone.utc).isoformat(), 'before_manifest': str(BEFORE),
                 'before_manifest_sha256': hashlib.sha256(BEFORE.read_bytes()).hexdigest(),
                 'files': current, 'changed': changed, 'unchanged': not changed,
                 'native_queries': 0, 'evidence_edits': False}
        with AFTER.open('x') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')
        print(json.dumps({'after_manifest': str(AFTER), 'unchanged': not changed,
                          'file_count': len(current), 'changed': changed}, indent=2))
        return int(bool(changed))
    raise SystemExit('usage: preserve-native-codex-v7-help-fix.py before|after')


if __name__ == '__main__':
    raise SystemExit(main())
