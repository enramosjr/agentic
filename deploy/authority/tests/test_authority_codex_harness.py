"""Protocol/config fixtures only: not an actual supported-model qualification."""
import backend_test_support
import io
import json
import unittest

from test_authority_protocol import deployment
from trusted_ci_policy import Refusal
import codex_harness


def configured():
    d = deployment()
    d['resources'].update(model_auth='chatgpt-plan', model_id='fixture-model', codex_version='1.2.3',
        codex_sha='a' * 64, coding_image='registry.example/coding@sha256:' + 'b' * 64)
    return d


def messages(status='completed', thread='thread-1', turn='turn-1'):
    return [
        {'id': 1, 'result': {}},
        {'id': 2, 'result': {'thread': {'id': 'thread-1'}}},
        {'method': 'turn/started', 'params': {'threadId': 'thread-1', 'turn': {'id': 'turn-1'}}},
        {'id': 3, 'result': {'turn': {'id': 'turn-1', 'status': 'inProgress'}}},
        {'method': 'turn/completed', 'params': {'threadId': thread,
            'turn': {'id': turn, 'status': status, 'error': None}}},
    ]


def run(values):
    reader = io.BytesIO(b''.join((json.dumps(v) + '\n').encode() for v in values))
    writer = io.BytesIO()
    result = codex_harness.conversation(reader, writer, configured(), 'Implement the reviewed fixture task')
    return result, [json.loads(line) for line in writer.getvalue().splitlines()]


class CodexHarnessContracts(unittest.TestCase):
    def test_controlled_provider_uses_task_capability_without_upstream_or_github_credentials(self):
        d = configured()
        argv = codex_harness.command(d, 8123)
        env = codex_harness.environment('agentic-task.' + 'c' * 64)
        self.assertEqual(argv[:4], ['/opt/agentic/bin/codex', 'app-server', '--listen', 'stdio://'])
        self.assertIn('model_providers.agentic_chatgpt_plan.base_url="http://127.0.0.1:8123/v1"', argv)
        self.assertIn('model_providers.agentic_chatgpt_plan.requires_openai_auth=false', argv)
        self.assertEqual(set(env), {'HOME', 'CODEX_HOME', 'PATH', 'AGENTIC_MODEL_CAP'})
        self.assertNotIn('GITHUB_TOKEN', env)
        for secret in ('sk-project-upstream', 'oauth.access.token', 'PRIVATE KEY'):
            with self.subTest(secret=secret), self.assertRaises(Refusal):
                codex_harness.environment(secret)

    def test_full_handshake_and_exact_completed_turn_are_required(self):
        result, sent = run(messages())
        self.assertEqual(result['thread_id'], 'thread-1')
        self.assertEqual(result['turn_id'], 'turn-1')
        self.assertFalse(result['model_execution_qualified'])
        self.assertEqual([v['method'] for v in sent], ['initialize', 'initialized', 'thread/start', 'turn/start'])
        self.assertEqual(sent[2]['params']['model'], 'fixture-model')
        self.assertEqual(sent[2]['params']['cwd'], '/work/project')
        self.assertEqual(sent[3]['params']['cwd'], '/work/project')
        self.assertEqual(sent[3]['params']['approvalPolicy'], 'never')
        self.assertEqual(sent[3]['params']['sandboxPolicy'], {'type': 'externalSandbox', 'networkAccess': 'restricted'})

    def test_early_completed_notification_is_bound_to_the_returned_turn(self):
        values = messages()
        values[-1], values[-2] = values[-2], values[-1]
        result, _ = run(values)
        self.assertEqual(result['turn_id'], 'turn-1')

    def test_failure_interruption_wrong_ids_eof_and_server_requests_are_refused(self):
        for values in [messages('failed'), messages('interrupted'), messages(thread='other'),
                       messages(turn='other'), messages()[:-1],
                       [{'id': 1, 'error': {'message': 'SYNTHETIC-UPSTREAM-SECRET'}}],
                       [{'id': 99, 'method': 'item/commandExecution/requestApproval', 'params': {}}]]:
            with self.subTest(values=values), self.assertRaises(Refusal) as error:
                run(values)
            self.assertNotIn('SYNTHETIC-UPSTREAM-SECRET', str(error.exception))

    def test_malformed_nested_protocol_objects_fail_closed(self):
        for index, value in [(1, {'id': 2, 'result': {'thread': None}}),
                             (3, {'id': 3, 'result': {'turn': []}}),
                             (4, {'method': 'turn/completed', 'params': None}),
                             (4, {'method': 'turn/completed', 'params': {'threadId': 'thread-1', 'turn': None}})]:
            values = messages()
            values[index] = value
            with self.subTest(index=index, value=value), self.assertRaises(Refusal):
                run(values)

    def test_profile_narrowing_unpinned_runtime_or_injected_endpoint_is_refused(self):
        for key, value in [('model_auth', 'api-key'), ('coding_image', 'latest'),
                           ('codex_sha', 'unknown'), ('model_id', 'model; command')]:
            d = configured()
            d['resources'][key] = value
            with self.subTest(key=key), self.assertRaises(Refusal):
                codex_harness.command(d, 8123)
        for port in (True, 0, 80, 65536, '8123;exec'):
            with self.subTest(port=port), self.assertRaises(Refusal):
                codex_harness.command(configured(), port)


if __name__ == '__main__':
    unittest.main()
