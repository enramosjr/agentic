"""Inspect existing retry review artifacts/messages only; no execution or scoring changes."""
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('operator_observer', ROOT / 'docs/assurance/operator-2-retry/.ai/evals/checks/live_observer.py')
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)
name = sys.argv[1] if len(sys.argv) > 1 else 'real-agent-2-retry'
if name not in ('real-agent-2-retry', 'real-agent-2-report-contract'):
    raise SystemExit('unknown completed result name')
data = json.loads((ROOT / f'docs/assurance/{name}.json').read_text())
findings = []
for cell in data['attempts']:
    adapter = cell['observations']['adapter']
    parent = adapter['parent_session']
    project = re.sub(r'[^A-Za-z0-9]', '-', cell['workspace_directory'] + '/repo')
    transcript = Path('/home/enramosjr/.claude/projects') / project / (parent + '.jsonl')
    calls, reports, received = {}, [], []
    for line in transcript.read_text().splitlines():
        event = json.loads(line)
        content = event.get('message', {}).get('content')
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get('type') == 'tool_use':
                calls[block['id']] = block.get('name')
                params = block.get('input', {})
                if block.get('name') in ('Write', 'Edit') and 'review' in params.get('file_path', ''):
                    text = params.get('content') or params.get('new_string') or ''
                    if '## Verdict' in text:
                        reports.append({'tool': block['name'], 'path': params.get('file_path'),
                            'proposed_body_sha256': observer.report_hash(text), 'text': text})
            elif block.get('type') == 'tool_result' and calls.get(block.get('tool_use_id')) == 'Agent':
                received.append(block.get('content'))
    findings.append({'scenario': cell['scenario_id'], 'reviewer_observations': adapter['reviewers'],
        'parent_native_transcript': str(transcript), 'review_artifact_proposals': reports,
        'received_agent_results': received})
(ROOT / f'docs/assurance/{name}-review-binding.json').write_text(json.dumps(findings, indent=2) + '\n')
print(json.dumps(findings, indent=2))
