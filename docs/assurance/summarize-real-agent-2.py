"""Bounded, redacted diagnosis of existing real-agent streams; no executions."""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import eval_results

name = sys.argv[1] if len(sys.argv) > 1 else 'real-agent-2'
if name not in ('real-agent-2', 'real-agent-2-retry', 'real-agent-2-report-contract'):
    raise SystemExit('unknown completed result name')
report = json.loads((ROOT / f'docs/assurance/{name}.json').read_text())
summaries = []
for cell in report['attempts']:
    session = cell['observations']['adapter']['parent_session']
    slug = re.sub(r'[^A-Za-z0-9]', '-', cell['workspace_directory'] + '/repo')
    path = Path('/home/enramosjr/.claude/projects') / slug / (session + '.jsonl')
    messages, denials, tools, hooks = [], [], [], []
    for line in path.read_text().splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind = event.get('type')
        if kind == 'assistant':
            for block in event.get('message', {}).get('content', []):
                if block.get('type') == 'text':
                    messages.append(block.get('text', ''))
                elif block.get('type') == 'tool_use':
                    tools.append({'name': block.get('name'), 'input': str(block.get('input'))[:600]})
        if kind == 'user' and isinstance(event.get('message', {}).get('content'), list):
            for block in event['message']['content']:
                if block.get('type') == 'tool_result' and block.get('is_error'):
                    denials.append(str(block.get('content'))[:1800])
        if kind == 'system' and event.get('subtype') == 'hook_response' and event.get('output'):
            hooks.append(str(event.get('output'))[:1200])
        if kind == 'attachment' and event.get('attachment', {}).get('type') == 'hook_success':
            attachment = event['attachment']
            if attachment.get('stdout'):
                hooks.append({'command': attachment.get('command'), 'exit': attachment.get('exitCode'),
                              'stdout': attachment['stdout'][:1200]})
    summary = {'scenario': cell['scenario_id'], 'status': cell['status'], 'stream': str(path),
               'assistant_text': messages[-5:], 'tool_calls': tools[-12:],
               'tool_errors': denials[-10:], 'hook_output': hooks[-8:]}
    summary = eval_results.sanitized(summary, [])
    summaries.append(summary)
output = ROOT / f'docs/assurance/{name}-diagnosis.json'
output.write_text(json.dumps(summaries, indent=2) + '\n')
print(json.dumps(summaries, indent=2))
