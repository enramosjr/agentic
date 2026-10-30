"""Summarize previously recorded local Codex capability responses; no native process."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
out = ROOT / 'docs/assurance/codex-capability-scope-2'
report = json.loads((out / 'report.json').read_text())
response = json.loads((out / 'responses.json').read_text())
hook_groups = report['hooks_list']['data']
hooks = []
for group in hook_groups:
    for hook in group.get('hooks', []):
        if 'hook-probe.py' in hook.get('command', ''):
            hooks.append(hook)
thread_schema = json.loads((out / 'schema/v2/ThreadReadResponse.json').read_text())
properties = thread_schema['definitions']['Thread']['properties']
fields = ['parentThreadId', 'agentRole', 'model', 'reasoningEffort', 'cliVersion']
summary = {'native_initialize': next(item['result'] for item in response if item.get('id') == 1),
    'schema_hook_events': next(item['events'] for item in report['schema_facts'] if 'events' in item),
    'configured_probe_hooks': hooks,
    'hook_group_errors': [group.get('errors', []) for group in hook_groups],
    'thread_read_identity_field_schemas': {field: properties[field] for field in fields},
    'actual_model_thread_calls': 0, 'trust_bypass_used': False,
    'request_methods': [request['method'] for request in json.loads((out / 'requests.json').read_text())],
    'boundary': 'schema/config acceptance only, no native subagent event-fire or populated reviewer payload proof'}
(out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
