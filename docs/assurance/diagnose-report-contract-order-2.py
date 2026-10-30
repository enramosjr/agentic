"""Read completed report-contract native logs to pin convergence mutations by session."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
result = json.loads((ROOT / 'docs/assurance/real-agent-2-report-contract.json').read_text())
diagnoses = json.loads((ROOT / 'docs/assurance/real-agent-2-report-contract-review-binding.json').read_text())
out = []
for cell, diagnosis in zip(result['attempts'], diagnoses):
    parent_path = Path(diagnosis['parent_native_transcript'])
    reviewer = cell['observations']['adapter']['reviewers'][0]
    child_path = parent_path.with_suffix('') / 'subagents' / ('agent-' + reviewer['session'] + '.jsonl')
    sequence = []
    for label, path in (('parent', parent_path), ('reviewer', child_path)):
        seen = set()
        for line in path.read_text().splitlines():
            event = json.loads(line)
            blocks = event.get('message', {}).get('content')
            if not isinstance(blocks, list):
                continue
            for block in blocks:
                if block.get('type') != 'tool_use' or block['id'] in seen:
                    continue
                seen.add(block['id'])
                params = block.get('input', {})
                if block.get('name') == 'Bash':
                    command = params.get('command', '')
                    if any(word in command for word in ('lifecycle.py converge', 'lifecycle.py stage review',
                                                       'lifecycle.py stage verify')):
                        sequence.append({'session': label, 'at': event.get('timestamp'), 'command': command})
    sequence.sort(key=lambda item: item['at'] or '')
    out.append({'scenario': cell['scenario_id'], 'reviewer_transcript': str(child_path),
        'before_pins': reviewer['before'], 'after_pins': reviewer['after'],
        'reviewed_pins': reviewer['reviewed'], 'observed_writes': reviewer['writes'],
        'final_convergence_digest': cell['observations'].get('convergence_digest'),
        'command_chronology': sequence})
(ROOT / 'docs/assurance/real-agent-2-report-contract-order.json').write_text(json.dumps(out, indent=2) + '\n')
print(json.dumps(out, indent=2))
