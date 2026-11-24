"""Real encrypted rotation over Git/API fixtures; no OAuth/model/provider calls."""
import copy
from pathlib import Path
import sys
import time
import unittest

from cryptography.fernet import Fernet

sys.path[:0] = [str(Path(__file__).resolve().parents[2] / '.ai/scripts'),
               str(Path(__file__).resolve().parents[2] / '.ai/scripts/tests'),
               str(Path(__file__).resolve().parent / 'tests')]
from test_authority_model_auth_store import AuthHost, InitialSession
from test_model_vault import fixture as vault_fixture
from trusted_ci_policy import Refusal, digest
import authority_release
import model_auth
import model_auth_store
import model_vault


class AuthReader:
    def __init__(self): self.calls = 0
    def get(self, path):
        self.calls += 1
        if path.endswith('/actions/runs/99'):
            return dict(path='.github/workflows/authority.yml', workflow_id=33, repository={'id': 456},
                head_sha='a' * 40, run_attempt=1, event='workflow_dispatch', head_branch='main')
        if path.endswith('/actions/workflows/33'):
            return dict(id=33, path='.github/workflows/authority.yml')
        raise AssertionError(path)
    def pages(self, path, collection):
        self.calls += 1
        if path.endswith('/runs/99/attempts/1/jobs'):
            return [dict(id=800, run_id=99, head_sha='a' * 40, name='model authorization', status='in_progress', conclusion=None)]
        raise AssertionError(path)


class Provider:
    def __init__(self):
        self.calls, self.after = 0, None
        self.response = dict(access_token='SYNTHETIC-ROTATED-ACCESS', refresh_token='SYNTHETIC-ROTATED-REFRESH',
                             token_type='bearer', expires_in=3600)
    def refresh(self, record):
        self.calls += 1
        if self.after: self.after()
        if isinstance(self.response, Exception): raise self.response
        return copy.deepcopy(self.response)


def fixture(needs_refresh=True):
    record, b, task = vault_fixture()
    b['deployment']['policy']['workflow_sha'] = 'a' * 40
    b['deployment_digest'] = digest(b['deployment'])
    if needs_refresh: record['credentials']['access_expires'] = 1600
    keys = model_vault.generate_keys()
    host = AuthHost()
    store = model_auth_store.AuthStore(host, 'owner/authority', 456, 'a' * 40,
        admitted_owner=dict(workflow_sha='a' * 40, run_id=99, attempt=1), session=InitialSession())
    store.initialize(model_vault.seal_record(record, keys['vault']))
    host.writes.clear()
    class Registry:
        def __init__(self): self.reads = 0
        def binding(self):
            self.reads += 1
            return copy.deepcopy(b)
    registry, reader, provider = Registry(), AuthReader(), Provider()
    env = dict(GITHUB_REPOSITORY_ID='456', GITHUB_SHA='a' * 40, GITHUB_RUN_ID='99', GITHUB_RUN_ATTEMPT='1', GITHUB_JOB='model_auth')
    controller = model_auth.Controller(registry, reader, store, env, keys['vault'], keys['delivery'],
                                       provider=provider, clock=lambda: 1500)
    return controller, host, store, provider, keys, b, task, registry, reader


class ModelAuthContracts(unittest.TestCase):
    def test_fixed_service_composes_registry_auth_owner_and_encrypted_upload(self):
        import json
        import registry as registry_backend
        import service
        from test_authority_app_proofs import identities
        controller, host, store, provider, keys, b, task, _, reader = fixture(False)
        d = copy.deepcopy(b['deployment'])
        d['policy']['merge_actors'] = [19]
        records = identities(d)
        d['resources'].update(identity_record=json.dumps(records, sort_keys=True, separators=(',', ':')),
                              identity_digest=digest(records))
        registry = registry_backend.Registry(host, dict(schema_version=2, repository='owner/authority',
            repository_id=456, registry_branch='agentic-registry'))
        registry.write(None, d)
        class API:
            def get(self, route): return reader.get(route) if '/actions/' in route else host.get(route)
            def pages(self, route, collection): return reader.pages(route, collection) if '/actions/' in route else host.pages(route, collection)
            def post(self, route, body): return host.post(route, body)
            def patch(self, route, body): return host.patch(route, body)
        uploaded = []
        def upload_factory(node, environment):
            def upload(name, raw):
                self.assertEqual(name, 'model-lease-' + task['task_id'] + '-1')
                uploaded.append(json.loads(raw))
                return 555
            return upload
        env = dict(controller.environment, GITHUB_REPOSITORY='owner/authority', GITHUB_TOKEN='SYNTHETIC-AUTH-WRITER',
            AGENTIC_MODEL_VAULT_KEY=keys['vault'], AGENTIC_MODEL_DELIVERY_KEY=keys['delivery'])
        request = dict(schema_version=2,task=task,source_base='a'*40,prompt='Reviewed task',
            configuration_revision=registry.binding()['configuration_revision'],deployment_digest=digest(d))
        location = service._authorize_task_request(env, request, 'synthetic-node', clock=lambda:1500,
            api_factory=lambda token:API(), uploader_factory=upload_factory, provider=provider)
        self.assertEqual(location, dict(run_id=99, attempt=1, job_id=800, artifact_id=555))
        lease = model_vault.open_lease(uploaded[0]['ciphertext'], keys['delivery'], registry.binding(), task, 1501)
        self.assertEqual(lease['access_token'], 'SYNTHETIC-ACCESS-ONLY')
        self.assertEqual(provider.calls, 0)
        from unittest.mock import patch
        stale = dict(request, deployment_digest='f'*64)
        with patch.object(service,'_model_authorization',side_effect=AssertionError('must reject before model authorization')):
            with self.assertRaises(Refusal): service._authorize_task_request(env,stale,'synthetic-node',clock=lambda:1500,
                api_factory=lambda token:API(),uploader_factory=upload_factory,provider=provider)

    def test_encrypted_delivery_is_uploaded_by_auth_job_and_authenticated_before_opening(self):
        import hashlib
        import json
        from unittest.mock import patch
        from test_authority_closed_artifacts import HistoricalAPI
        controller, host, store, provider, keys, b, task, _, _ = fixture(False)
        uploaded = []
        def upload(name, raw):
            self.assertEqual(name, 'model-lease-' + task['task_id'] + '-1')
            self.assertNotIn(b'SYNTHETIC-ACCESS', raw)
            self.assertNotIn(b'SYNTHETIC-REFRESH', raw)
            uploaded.append(json.loads(raw))
            return 555
        location = controller._produce(task, upload)
        self.assertEqual(location, dict(run_id=99, attempt=1, job_id=800, artifact_id=555))
        api = HistoricalAPI('model-lease', task['task_id'])
        api.job.update(id=800, started_at='1970-01-01T00:24:59Z', completed_at='1970-01-01T00:25:02Z')
        api.artifact['created_at'] = '1970-01-01T00:25:01Z'
        for row in (api.run, api.job, api.artifact['workflow_run']): row['head_sha'] = 'a' * 40
        api.document = uploaded[0]
        api.raw = api.archive(api.member)
        api.artifact['digest'] = 'sha256:' + hashlib.sha256(api.raw).hexdigest()
        delivered = model_vault.read_delivery(api, b, task, location, keys['delivery'], 1503)
        self.assertEqual(delivered['access_token'], 'SYNTHETIC-ACCESS-ONLY')
        self.assertNotIn('refresh_token', delivered)
        api.job['name'] = 'task (' + task['task_id'] + ')'
        with patch.object(model_vault, 'open_lease', side_effect=AssertionError('must authenticate before decrypting')):
            with self.assertRaises(Refusal): model_vault.read_delivery(api, b, task, location, keys['delivery'], 1503)

    def test_public_hold_precedes_key_validation_registry_and_provider_access(self):
        controller, host, store, provider, keys, b, task, registry, reader = fixture()
        with self.assertRaises(authority_release.Held): controller.run(task)
        self.assertEqual(registry.reads, 0)
        self.assertEqual(reader.calls, 0)
        self.assertEqual(provider.calls, 0)
        self.assertEqual(host.writes, [])

    def test_existing_access_is_delivered_without_redeeming_or_mutating_refresh_state(self):
        controller, host, store, provider, keys, b, task, _, _ = fixture(False)
        result = controller._lease(task)
        lease = model_vault.open_lease(result['ciphertext'], keys['delivery'], b, task, 1500)
        self.assertEqual(lease['access_token'], 'SYNTHETIC-ACCESS-ONLY')
        self.assertEqual(provider.calls, 0)
        self.assertEqual(host.writes, [])
        self.assertFalse(result['model_execution_qualified'])

    def test_one_refresh_persists_complete_rotation_before_access_delivery(self):
        controller, host, store, provider, keys, b, task, _, _ = fixture()
        before = copy.deepcopy(b)
        result = controller._lease(task)
        after = store.read()['state']
        expected = {k: after['vault'][k] for k in model_vault.BINDING_FIELDS}
        record = model_vault.open_record(after['vault'], keys['vault'], expected)
        lease = model_vault.open_lease(result['ciphertext'], keys['delivery'], b, task, 1500)
        self.assertEqual(provider.calls, 1)
        self.assertIsNone(after['pending'])
        self.assertEqual(record['generation'], 2)
        self.assertEqual(record['credentials']['refresh_token'], 'SYNTHETIC-ROTATED-REFRESH')
        self.assertEqual(record['credentials']['access_token'], lease['access_token'])
        self.assertEqual(record['credentials']['id_token'], 'SYNTHETIC-ID-TOKEN')
        self.assertEqual(record['credentials']['scopes'], ['chatgpt.tokens.use.direct', 'offline_access', 'resource.invoke'])
        self.assertEqual(b, before)  # Routine renewal does not rotate deployment/check context.

    def test_received_invalid_or_unknown_response_stays_pending_without_second_post(self):
        for defect in ('replacement', 'scope-expansion', 'scope-loss', 'expiry', 'id-token', 'network', 'token-type', 'null-scope'):
            f = fixture()
            controller, host, store, provider, keys, b, task, _, _ = f
            if defect == 'replacement': provider.response.pop('refresh_token')
            if defect == 'scope-expansion': provider.response['scope'] = 'chatgpt.tokens.use.direct offline_access resource.invoke expanded'
            if defect == 'scope-loss': provider.response['scope'] = 'offline_access resource.invoke'
            if defect == 'expiry': provider.response['expires_in'] = True
            if defect == 'id-token': provider.response['id_token'] = 'malformed.signature'
            if defect == 'network': provider.response = Refusal('synthetic unknown provider completion')
            if defect == 'token-type': provider.response['token_type'] = 'not-bearer'
            if defect == 'null-scope': provider.response['scope'] = None
            with self.subTest(defect=defect), self.assertRaises(Refusal): controller._lease(task)
            self.assertIsNotNone(store.read()['state']['pending'])
            with self.assertRaises(Refusal): controller._lease(task)
            self.assertEqual(provider.calls, 1)

    def test_lost_completion_ack_does_not_repeat_refresh_or_deliver_unpersisted_tokens(self):
        controller, host, store, provider, keys, b, task, _, _ = fixture()
        provider.after = lambda: setattr(host, 'lose_ack', True)
        result = controller._lease(task)
        self.assertEqual(provider.calls, 1)
        self.assertIsNone(store.read()['state']['pending'])
        self.assertEqual(model_vault.open_lease(result['ciphertext'], keys['delivery'], b, task, 1500)['auth_generation'], 2)

    def test_wrong_job_token_scope_client_or_shared_keys_refuse_before_grant(self):
        for defect in ('job', 'scope', 'client', 'keys'):
            controller, host, store, provider, keys, b, task, _, _ = fixture()
            if defect == 'job': controller.environment['GITHUB_JOB'] = 'coding_task'
            if defect == 'scope': host.visible = [123, 456]
            if defect == 'client':
                b['deployment']['resources']['model_client'] = 'foreign-client'
                b['deployment_digest'] = digest(b['deployment'])
            if defect == 'keys': controller._delivery_key = controller._vault_key
            with self.subTest(defect=defect), self.assertRaises(Refusal): controller._lease(task)
            self.assertEqual(provider.calls, 0)
            self.assertEqual(host.writes, [])


if __name__ == '__main__':
    unittest.main()
