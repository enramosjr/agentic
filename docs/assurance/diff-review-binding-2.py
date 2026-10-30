"""Compare retained actual reviewer handbacks with successful artifact write payloads."""
import difflib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('binding_observer', ROOT / 'docs/assurance/operator-2-retry/.ai/evals/checks/live_observer.py')
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)
name = sys.argv[1] if len(sys.argv) > 1 else 'real-agent-2-retry'
if name not in ('real-agent-2-retry', 'real-agent-2-report-contract'):
    raise SystemExit('unknown completed result name')
diagnosis = json.loads((ROOT / f'docs/assurance/{name}-review-binding.json').read_text())
out = []
for item in diagnosis:
    text = item['received_agent_results'][0][0]['text']
    framed = text.split('The report follows:\n', 1)[1].split('\nagentId:', 1)[0]
    reviewer = '\n'.join(line[2:] if line.startswith('  ') else line for line in framed.splitlines()).strip() + '\n'
    events = [json.loads(line) for line in Path(item['parent_native_transcript']).read_text().splitlines()]
    calls, successful = {}, []
    for event in events:
        blocks = event.get('message', {}).get('content')
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if block.get('type') == 'tool_use':
                params = block.get('input', {})
                if block.get('name') in ('Write', 'Edit') and 'review' in params.get('file_path', ''):
                    calls[block['id']] = (block.get('name'), params)
            elif block.get('type') == 'tool_result' and block.get('tool_use_id') in calls and not block.get('is_error'):
                successful.append(calls[block['tool_use_id']])
    tool, params = successful[-1]
    artifact = params.get('content') or params.get('new_string')
    if artifact.startswith('---\n'):
        artifact = artifact[artifact.find('\n---', 4) + 4:]
    artifact = artifact.strip() + '\n'
    delta = ''.join(difflib.unified_diff(reviewer.splitlines(keepends=True), artifact.splitlines(keepends=True),
                                      fromfile='observed-reviewer-report', tofile='saved-artifact-body'))
    prefix = ROOT / 'docs/assurance' / (name + '-binding-' + item['scenario'])
    prefix.with_suffix('.diff').write_text(delta)
    observation = item['reviewer_observations'][0]
    body_match = artifact.endswith(reviewer)
    result = {'scenario': item['scenario'], 'observed_report_sha256': observation['report_sha256'],
        'observed_verdict': observation['verdict'], 'actual_handback_body_sha256': observer.report_hash(reviewer),
        'saved_artifact_body_sha256': observer.report_hash(artifact),
        'observed_hash_matches_unframed_report': observation['report_sha256'] == observer.report_hash(reviewer),
        'only_added_prefix': body_match, 'added_prefix': artifact[:-len(reviewer)] if body_match else None,
        'saved_artifact_reconstruction': 'final successful native ' + tool + ' payload; no post-run fixture edits',
        'native_transcript': item['parent_native_transcript'], 'diff': str(prefix.with_suffix('.diff')),
        'diff_excerpt': delta[:5000]}
    out.append(result)
(ROOT / f'docs/assurance/{name}-binding-diff.json').write_text(json.dumps(out, indent=2) + '\n')
report = json.loads((ROOT / f'docs/assurance/{name}.json').read_text())
summary = {'totals': report['totals'], 'qualification': report['qualification'], 'budget': report['budget'],
           'per_case_reasons': {c['scenario_id']: c['reasons'] for c in report['attempts']}, 'binding': out}
print(json.dumps(summary, indent=2))
