"""Controlled subscription-profile app-server protocol, not isolation proof.

Use only inside an admitted, pinned OCI worker. Its supervisor must enforce the
task deadline and confirm termination/cleanup. The inference relay owns upstream
OAuth credentials; this worker receives only a task-scoped capability.

Protocol/profile references:
https://learn.chatgpt.com/docs/app-server
https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server
"""
import json
import re

from authority_protocol import fingerprint, validate_deployment
from trusted_ci_policy import Refusal, loads, require

MAX_LINE, MAX_STREAM, MAX_MESSAGES = 1024 * 1024, 32 * 1024 * 1024, 10000


def profile(deployment):
    d = validate_deployment(deployment)
    r = d['resources']
    require(r.get('model_auth') == 'chatgpt-plan', 'ChatGPT-plan profile required; no billing fallback')
    require(isinstance(r.get('model_id'), str) and re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,199}', r['model_id']) and
            fingerprint(r.get('codex_sha')) and isinstance(r.get('codex_version'), str) and
            re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?', r['codex_version']) and
            isinstance(r.get('coding_image'), str) and
            re.fullmatch('[A-Za-z0-9._/:-]+@sha256:[0-9a-f]{64}', r['coding_image']),
            'approved model and pinned harness/image required')
    return r


def command(deployment, bridge_port):
    profile(deployment)
    require(type(bridge_port) is int and 1024 <= bridge_port <= 65535, 'worker loopback bridge port required')
    settings = [
        'model_provider="agentic_chatgpt_plan"',
        'model_providers.agentic_chatgpt_plan.name="AGENTIC ChatGPT plan"',
        'model_providers.agentic_chatgpt_plan.base_url="http://127.0.0.1:' + str(bridge_port) + '/v1"',
        'model_providers.agentic_chatgpt_plan.env_key="AGENTIC_MODEL_CAP"',
        'model_providers.agentic_chatgpt_plan.wire_api="responses"',
        'model_providers.agentic_chatgpt_plan.requires_openai_auth=false',
        'model_providers.agentic_chatgpt_plan.supports_websockets=false',
    ]
    return ['/opt/agentic/bin/codex', 'app-server', '--listen', 'stdio://',
            *(part for value in settings for part in ('-c', value))]


def environment(task_capability):
    require(isinstance(task_capability, str) and re.fullmatch(r'agentic-task\.[0-9a-f]{64}', task_capability),
            'task-only inference capability required')
    # Never inherit the parent environment, user HOME, browser or native auth cache.
    return {'HOME': '/home/agentic', 'CODEX_HOME': '/home/agentic/.codex',
            'PATH': '/opt/agentic/bin:/usr/local/bin:/usr/bin:/bin', 'AGENTIC_MODEL_CAP': task_capability}


def conversation(reader, writer, deployment, prompt):
    """Drive bounded JSONL I/O. A completed RPC is not a qualification receipt."""
    r = profile(deployment)
    require(isinstance(prompt, str) and 0 < len(prompt.encode('utf-8')) <= 64 * 1024,
            'bounded nonempty task prompt required')
    received, count, notifications = 0, 0, []

    def send(method, params, identity=None):
        value = {'method': method, 'params': params}
        if identity is not None:
            value['id'] = identity
        writer.write((json.dumps(value, allow_nan=False) + '\n').encode())
        writer.flush()

    def read():
        nonlocal received, count
        raw = reader.readline(MAX_LINE + 1)
        received += len(raw)
        count += 1
        require(raw and raw.endswith(b'\n') and len(raw) <= MAX_LINE and
                received <= MAX_STREAM and count <= MAX_MESSAGES, 'incomplete or oversized app-server protocol')
        value = loads(raw)
        require(isinstance(value, dict), 'app-server object message required')
        require(not ('id' in value and 'method' in value), 'interactive app-server requests are not admitted')
        return value

    def response(identity):
        while True:
            value = read()
            if 'id' in value:
                require(type(value['id']) is int and value['id'] == identity and 'error' not in value and
                        isinstance(value.get('result'), dict), 'app-server request failed or response identity differs')
                return value['result']
            require(isinstance(value.get('method'), str) and isinstance(value.get('params'), dict),
                    'malformed app-server notification')
            notifications.append(value)

    def identifier(value):
        require(isinstance(value, str) and 0 < len(value) <= 200 and not any(ord(c) < 32 for c in value),
                'app-server execution identity required')
        return value

    def execution_identity(result, key):
        value = result.get(key)
        require(isinstance(value, dict), 'malformed app-server execution object')
        return identifier(value.get('id'))

    send('initialize', {'clientInfo': {'name': 'agentic', 'title': 'AGENTIC authority',
                                      'version': deployment['policy']['workflow_sha']}}, 1)
    response(1)
    send('initialized', {})
    send('thread/start', {'model': r['model_id'], 'cwd': '/work/project', 'approvalPolicy': 'never',
                          'sandbox': 'workspace-write', 'serviceName': 'agentic'}, 2)
    thread = execution_identity(response(2), 'thread')
    send('turn/start', {'threadId': thread, 'model': r['model_id'], 'cwd': '/work/project',
        'input': [{'type': 'text', 'text': prompt}], 'approvalPolicy': 'never',
        # The admitted OCI container enforces filesystem/network controls. This
        # avoids asking the unprivileged worker to create another OS sandbox.
        'sandboxPolicy': {'type': 'externalSandbox', 'networkAccess': 'restricted'}}, 3)
    turn = execution_identity(response(3), 'turn')
    while True:
        value = notifications.pop(0) if notifications else read()
        require('id' not in value, 'unexpected app-server response after turn start')
        require(isinstance(value.get('method'), str) and isinstance(value.get('params'), dict),
                'malformed app-server notification')
        if value.get('method') != 'turn/completed':
            continue
        params = value.get('params', {})
        outcome = params.get('turn', {})
        require(isinstance(outcome, dict), 'malformed app-server completion object')
        require(params.get('threadId') == thread and outcome.get('id') == turn and
                outcome.get('status') == 'completed' and outcome.get('error') is None,
                'exact Codex turn did not complete successfully')
        return {'kind': 'codex-protocol-result', 'thread_id': thread, 'turn_id': turn,
                'model_id': r['model_id'], 'model_execution_qualified': False}
