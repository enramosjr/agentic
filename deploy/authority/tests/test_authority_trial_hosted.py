"""Real native setup/dispatch to a fresh hosted admission without native journals."""
import backend_test_support
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import app_proofs
import model_vault
import service
import trial_admission
import test_authority_trial_workflow as workflow
from test_authority_closed_artifacts import HistoricalAPI
from trusted_ci_github import HostRefusal
from trusted_ci_policy import Refusal, digest


@unittest.skipIf(workflow.staging.handoff.preparation.jwt is None, 'optional model-auth cryptography environment required')
class Hosted(unittest.TestCase):
    fixture = workflow.staging.handoff.Publication.fixture
    prepared = workflow.staging.Delegation.prepared
    connected = workflow.Dispatch.connected

    def configured(self):
        controller, native, reg, origin, clock, handshake, dispatched, published = self.connected()
        bound = controller.run('prompt')
        scoped = controller.staging.token_factory(reg.api.secrets['AGENTIC_TRIAL_ORIGIN_TOKEN'])
        class OriginReader:
            token = reg.api.secrets['AGENTIC_TRIAL_ORIGIN_TOKEN']
            def get(self, route): return origin.api.get(route)
            def pages(self, *args): return scoped.pages(*args)
            def fetch(self, *args, **kwargs): return scoped.fetch(*args, **kwargs)
        origin.reader = OriginReader()
        api, d = reg.api, reg.read()
        jobs, artifacts = [handshake.job], [(handshake.artifact, handshake.raw)]
        get, pages, fetch = api.get, api.pages, api.fetch
        def source_tree(route):
            value = get(route)
            if route.startswith('/repos/owner/trial/git/trees/'):
                value = dict(value, sha=route.split('/git/trees/')[1].split('?')[0])
            return value
        api.get = source_tree
        api.pages = lambda route, collection=None: copy.deepcopy(jobs) if '/runs/100/' in route and collection == 'jobs' else (
            copy.deepcopy([a for a, _ in artifacts]) if '/runs/100/' in route and collection == 'artifacts' else pages(route, collection))
        def read_transport(route, **kwargs):
            if '/actions/artifacts/' in route:
                return next(raw for a, raw in artifacts if route.endswith('/' + str(a['id']) + '/zip'))
            if route.startswith('/repos/owner/trial/git/blobs/'): return api.get(route)
            return fetch(route, **kwargs)
        api.fetch = read_transport
        def job(name, identity):
            value = dict(id=identity, run_id=100, head_sha=d['policy']['workflow_sha'], name=name,
                         status='in_progress', conclusion=None, started_at='1970-01-01T00:16:43Z')
            jobs.append(value)
            return value
        def upload(role, key, producer):
            def invoke(name, raw):
                a = HistoricalAPI()
                a.document = json.loads(raw)
                a.raw = a.archive(role + '.json')
                a.artifact.update(id=1000 + len(artifacts), name=name, created_at='1970-01-01T00:16:43Z')
                a.artifact['workflow_run'].update(id=100, repository_id=702, head_repository_id=702, head_sha=d['policy']['workflow_sha'])
                a.artifact['digest'] = 'sha256:' + hashlib.sha256(a.raw).hexdigest()
                artifacts.append((a.artifact, a.raw))
                producer.update(status='completed', conclusion='success', completed_at='1970-01-01T00:16:44Z')
                clock[0] = 1004
                return a.artifact['id']
            return invoke
        task = dict(task_id=bound['task_id'], run_id=100, attempt=1, deadline=bound['expires'], purpose='qualification')
        env = dict(GITHUB_REPOSITORY='owner/trial-authority', GITHUB_REPOSITORY_ID='702', GITHUB_RUN_ID='100',
                   GITHUB_RUN_ATTEMPT='1', GITHUB_SHA=d['policy']['workflow_sha'], GITHUB_JOB='model_auth', GITHUB_TOKEN='fixture-actions-read')
        model_job = job('model authorization', 801)
        env.update({k:api.secrets[k] for k in ('AGENTIC_MODEL_VAULT_KEY', 'AGENTIC_MODEL_DELIVERY_KEY')})
        clock[0] = 1003
        model = service._model_authorization(env, task, 'fixture-node', clock=native.clock,
            api_factory=lambda token:api, uploader_factory=lambda node, environment:upload('model-lease', task['task_id'], model_job))
        proofs = {}
        identities = app_proofs.load_identities(d)
        from test_authority_app_proofs import AppAPI
        class OwnApp(AppAPI):
            def get(self, path):
                if path == '/repos/owner/trial-authority/installation' and self.purpose in ('coding', 'issuer', 'merge'):
                    raise HostRefusal(404)
                return super().get(path)
            def post(self, path, body):
                if body['repository_ids'] == [702] and self.purpose in ('coding', 'merge'):
                    raise HostRefusal(422, 'repository_scope')
                return super().post(path, body)
        for index, purpose in enumerate(app_proofs.PERMISSIONS):
            producer = job('proof (' + purpose + ')', 810 + index)
            root = OwnApp(d, identities, purpose)
            value = app_proofs.prove(root, api, d, identities, purpose, reg.binding()['branch_head'], 1003, root.token_api)
            artifact_id = upload('proof', purpose, producer)('proof-' + purpose + '-1', json.dumps(value).encode())
            proofs[purpose] = dict(run_id=100, attempt=1, job_id=producer['id'], artifact_id=artifact_id)
        parent = job('hosted qualification', 820)
        env = {k:v for k, v in env.items() if k.startswith('GITHUB_')}
        env['GITHUB_JOB'] = 'qualification'
        hint = dispatched[0]['inputs']['handoff']
        return native, reg, origin, clock, env, hint, model, proofs, api.secrets['AGENTIC_MODEL_DELIVERY_KEY'], jobs, artifacts

    def admit(self, f, prompt='prompt'):
        native, reg, origin, clock, env, hint, model, proofs, key, *_ = f
        return trial_admission.Admission.hosted(reg, origin.reader, reg.api, native.api,
            Path('/fresh-hosted-purpose'), native.clock, env, hint, prompt, model, proofs, key, native.store)

    def test_authenticated_native_handoff_admits_without_native_provision_or_session_in_job(self):
        f = self.configured()
        c = self.admit(f)
        self.assertIsNone(c.provision)
        self.assertEqual(c.intent['task']['purpose'], 'qualification')
        self.assertEqual(c.intent['execution']['run_id'], 100)
        self.assertFalse(c.intent['hosted_qualified'])
        files = __import__('submission').read_export(c.capture_source())
        self.assertEqual(files['.github/CODEOWNERS']['content'], b'* @maintainer\n')
        for key in ('AGENTIC_MODEL_VAULT_KEY', 'AGENTIC_MODEL_DELIVERY_KEY', 'AGENTIC_TRIAL_ORIGIN_TOKEN'):
            self.assertNotIn(f[1].api.secrets[key], str(c.document))

    def test_native_prompt_run_fence_and_closed_producer_substitution_refuse(self):
        for fault in ('prompt', 'run', 'fence', 'proof'):
            f = self.configured()
            if fault == 'run': f[4]['GITHUB_RUN_ID'] = '101'
            if fault == 'fence': f[2].api.refs['main'] = '9' * 40
            if fault == 'proof': f[10][-1][0]['digest'] = 'sha256:' + '0' * 64
            with self.subTest(fault=fault), self.assertRaises(Refusal):
                self.admit(f, 'changed prompt' if fault == 'prompt' else 'prompt')

    def test_same_scope_unconsumed_origin_capability_cannot_replace_exact_token(self):
        f = self.configured()
        f[2].reader.token = 'different-unconsumed-original-reader-token'
        with self.assertRaises(Refusal): self.admit(f)
