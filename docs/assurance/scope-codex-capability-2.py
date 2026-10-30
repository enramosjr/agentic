"""No-model installed Codex hook/schema qualification for scoping only."""
import json
from pathlib import Path
import selectors
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/assurance/codex-capability-scope-2'
if OUT.exists():
    raise SystemExit('scope evidence already exists; do not overwrite')
OUT.mkdir()
fixture = OUT / 'fixture'
fixture.mkdir()
handler = OUT / 'hook-probe.py'
handler.write_text('print("{}")\n')
schema = OUT / 'schema'
generated = subprocess.run(['codex', 'app-server', 'generate-json-schema', '--experimental', '--out', str(schema)],
                           cwd=fixture, capture_output=True, text=True, timeout=30)
(OUT / 'schema-generation.log').write_text(generated.stdout + generated.stderr)
if generated.returncode:
    raise SystemExit('installed schema generation failed')

def toml(value):
    if isinstance(value, dict):
        return '{' + ','.join(json.dumps(key) + '=' + toml(item) for key, item in value.items()) + '}'
    if isinstance(value, list):
        return '[' + ','.join(toml(item) for item in value) + ']'
    return json.dumps(value)

command = str(Path(sys.executable)) + ' ' + str(handler)
hooks = {event: [{'hooks': [{'type': 'command', 'command': command, 'timeout': 5}]}]
         for event in ('SubagentStart', 'SubagentStop')}
argv = ['codex']
for event, groups in hooks.items():
    argv += ['-c', 'hooks.' + event + '=' + toml(groups)]
argv += ['-c', 'analytics.enabled=false', 'app-server', '--strict-config']
(OUT / 'command.json').write_text(json.dumps(argv, indent=2) + '\n')
responses, requests = [], []
error = None
with (OUT / 'app-server.stderr').open('w') as stderr:
    server = subprocess.Popen(argv, cwd=fixture, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr)
    buffer = bytearray()
    deadline = time.monotonic() + 20
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(server.stdout, selectors.EVENT_READ)
            def request(index, method, params):
                nonlocal_placeholder = None
                payload = {'id': index, 'method': method, 'params': params}
                requests.append(payload)
                server.stdin.write((json.dumps(payload) + '\n').encode())
                server.stdin.flush()
                while time.monotonic() < deadline:
                    while b'\n' in buffer:
                        line, _, rest = buffer.partition(b'\n')
                        buffer[:] = rest
                        message = json.loads(line)
                        responses.append(message)
                        if message.get('id') == index:
                            if 'error' in message:
                                raise ValueError(json.dumps(message['error']))
                            return message['result']
                    if not selector.select(max(0, deadline - time.monotonic())):
                        break
                    chunk = server.stdout.read1(16384)
                    if not chunk:
                        raise ValueError('native app-server closed before response')
                    buffer.extend(chunk)
                    if len(buffer) > 1024 * 1024:
                        raise ValueError('native response output cap exceeded')
                raise ValueError('native metadata deadline expired')
            initialization = request(1, 'initialize', {'clientInfo': {'name': 'assurance_scope_readonly', 'version': '1'},
                'capabilities': {'experimentalApi': True}})
            server.stdin.write(b'{"method":"initialized"}\n')
            server.stdin.flush()
            listed = request(2, 'hooks/list', {'cwds': [str(fixture)]})
            config = request(3, 'config/read', {'cwd': str(fixture), 'includeLayers': False})
    except Exception as caught:
        error = str(caught)
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
(OUT / 'requests.json').write_text(json.dumps(requests, indent=2) + '\n')
(OUT / 'responses.json').write_text(json.dumps(responses, indent=2) + '\n')
schema_facts = []
identity_names = {'parentThreadId', 'agentRole', 'model', 'reasoningEffort', 'cliVersion',
                  'agentId', 'agentType', 'agent_id', 'agent_type', 'last_assistant_message', 'agent_transcript_path'}
for path in sorted(schema.rglob('*.json')):
    value = json.loads(path.read_text())
    def inspect(node, pointer=''):
        if isinstance(node, dict):
            values = node.get('enum')
            if isinstance(values, list) and any(item in ('subagentStart', 'subagentStop', 'SubagentStart', 'SubagentStop') for item in values):
                schema_facts.append({'file': path.relative_to(schema).as_posix(), 'pointer': pointer, 'events': values})
            props = node.get('properties', {})
            found = sorted(set(props) & identity_names) if isinstance(props, dict) else []
            if found and ('Thread' in path.name or 'Hook' in path.name):
                schema_facts.append({'file': path.relative_to(schema).as_posix(), 'pointer': pointer, 'identity_fields': found})
            for key, child in node.items():
                inspect(child, pointer + '/' + key)
        elif isinstance(node, list):
            for index, child in enumerate(node):
                inspect(child, pointer + '/' + str(index))
    inspect(value)
(OUT / 'schema-facts.json').write_text(json.dumps(schema_facts, indent=2) + '\n')
report = {'scope': 'installed schema/event acceptance only; no model/provider inference or reviewer event-fire claim',
    'allowed_methods_only': all(item['method'] in ('initialize', 'hooks/list', 'config/read') for item in requests),
    'model_or_thread_calls': 0, 'trust_bypass_used': False, 'global_config_modified': False,
    'protocol_error': error, 'schema_generated': generated.returncode == 0, 'schema_facts': schema_facts,
    'hooks_list': listed if error is None else None,
    'active_hook_config': config.get('config', {}).get('hooks') if error is None else None,
    'boundary': 'actual subagent firing, payload population and report capture require separately authorized live evaluation'}
(OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
raise SystemExit(0 if error is None else 1)
