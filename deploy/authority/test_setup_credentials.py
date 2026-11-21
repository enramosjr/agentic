"""Actual private journals/RSA/vaults over native setup and Git API fixtures."""
import copy
import json
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

sys.path[:0] = [str(Path(__file__).resolve().parent / 'tests'),
               str(Path(__file__).resolve().parents[2] / '.ai/scripts')]
import test_authority_setup_owner as native
from test_authority_closed_artifacts import HistoricalAPI, locator
from test_authority_model_auth_store import AuthHost
from test_model_vault import fixture as vault_fixture
from trusted_ci_policy import Refusal
import authority_release
import bootstrap
import model_auth_store
import model_consent
import model_vault
import private_setup
import setup
import service


NAMES = tuple('AGENTIC_' + p.upper() + '_PRIVATE_KEY' for p in ('admin', 'reader', 'issuer', 'coding', 'merge')) + (
    'AGENTIC_MODEL_VAULT_KEY', 'AGENTIC_MODEL_DELIVERY_KEY')


class SetupCredentialContracts(unittest.TestCase):
    def setUp(self):
        parent = str(Path.home()) if os.name == 'nt' else '/tmp'
        temporary = tempfile.TemporaryDirectory(prefix='agentic-staging-fixture-', dir=parent)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.host, self.registry, make, self.operator, admin, preview, known, self.clock = native.fixture(
            credential_names=NAMES, host_type=AuthHost, embedded_identities=True)
        self.session = make()
        self.reader_names = {'UNRELATED_SECRET'}
        self.operator.pages = lambda route, collection: [{'name': v} for v in sorted(self.reader_names)]
        self.journal = private_setup.Store(self.root / 'staging')
        auth = model_auth_store.AuthStore(self.host, 'owner/authority', 456, 'a' * 40, session=self.session)
        self.consent = model_consent.Consent(auth, self.session, self.root / 'model', clock=lambda: self.clock[0])
        self.consent._begin('http://127.0.0.1:1455/auth/callback')
        body = copy.deepcopy(self.consent.document['value'])
        record, _, _ = vault_fixture()
        record['session_id'] = body['session_id']
        body['sealed_vault'] = model_vault.seal_record(record, body['keys']['vault'])
        body['attempt'].update(phase='installed', received_issued_client_id=record['identity']['client_id'])
        auth.initialize(body['sealed_vault'])
        self.consent._save(body)
        self.apps, self.public_keys = {}, {}
        for purpose, identity in self.session.identities['apps'].items():
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            self.apps[purpose] = dict(id=identity['id'], pem=key.private_bytes(serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode())
            self.public_keys[identity['id']] = key.public_key()
        self.writes = []
        outer = self
        class Gh:
            actor = 71
            lose_ack = False
            def api(self, route):
                outer.assertEqual(route, '/user')
                return dict(id=self.actor, type='User')
            def secret(self, repository, name, value):
                state = outer.journal.read()['value']
                outer.assertEqual(state['entries'][name]['phase'], 'write-started')
                outer.assertEqual(state['entries'][name]['value'], value)
                outer.assertEqual(repository, 'owner/authority')
                outer.writes.append(name)
                outer.reader_names.add(name)
                if self.lose_ack: raise OSError('synthetic lost secret write acknowledgement')
        self.gh = Gh()
        def app_api(app_id, pem):
            api = bootstrap.app_api(app_id, pem)
            jwt.decode(api.token, self.public_keys[app_id], algorithms=['RS256'], issuer=str(app_id))
            purpose = next(p for p, record in self.session.identities['apps'].items() if record['id'] == app_id)
            return native.AppAPI(self.registry.binding()['deployment'], self.session.identities, purpose)
        self.controller = setup.CredentialStaging(self.session, self.gh, self.journal,
            self.apps, self.consent, clock=lambda: self.clock[0], app_factory=app_api)

    def test_public_hold_precedes_all_io(self):
        with self.assertRaises(authority_release.Held): self.controller.run()
        self.assertIsNone(self.journal.read())
        self.assertEqual(self.writes, [])

    def test_workflow_dispatch_recovers_lost_ack_and_accepts_all_seven_real_proofs(self):
        import credential_workflow
        self.controller._stage()
        outer = self
        class Actions:
            proofs = []
            dispatched = 0
            locked = True
            def pages(self, route, collection):
                if collection == 'workflow_runs':
                    return [dict(self.proofs[0].run, event='workflow_dispatch', status='completed', conclusion='success')] if self.proofs else []
                if collection == 'jobs': return [p.job for p in self.proofs]
                if collection == 'artifacts': return [p.artifact for p in self.proofs]
                raise AssertionError(route)
            def get(self, route):
                if route.endswith('/rules/branches/main'):
                    return [dict(type=t, ruleset_id=81, ruleset_source_type='Repository',
                        ruleset_source='owner/authority') for t in ('update', 'deletion')] if self.locked else []
                if route.endswith('/rulesets/81'):
                    return dict(id=81, source_type='Repository', source='owner/authority', target='branch',
                        enforcement='active', bypass_actors=[], conditions=dict(ref_name=dict(include=['refs/heads/main'], exclude=[])),
                        rules=[dict(type='update', parameters=dict(update_allows_fetch_and_merge=False)), dict(type='deletion')])
                if route == '/repos/owner/authority' or '/git/ref/heads/' in route:
                    return outer.host.get(route)
                return self.proofs[0].get(route)
            def fetch(self, route, **kwargs):
                return next(p.raw for p in self.proofs if route.endswith('/' + str(p.artifact['id']) + '/zip'))
            def post(self, route, body):
                self.dispatched += 1
                outer.assertEqual(body['ref'], 'main')
                challenges = json.loads(body['inputs']['challenges'])
                outer.assertEqual(set(challenges), {setup._credential_purpose(n) for n in NAMES})
                for name in NAMES:
                    outer.clock[0] = 1001
                    outer.assertEqual(challenges[setup._credential_purpose(name)], outer.controller._challenge(name))
                    proof = outer.consumer(name)
                    proof.run.update(event='workflow_dispatch', status='completed', conclusion='success')
                    self.proofs.append(proof)
                raise OSError('synthetic dispatch acknowledgement lost')
        api = Actions()
        workflow = credential_workflow.CredentialWorkflow(self.controller, api,
            private_setup.Store(self.root / 'dispatch'), sleep=lambda _: None)
        with self.assertRaises(authority_release.Held): workflow.run()
        api.locked = False
        with self.assertRaisesRegex(Refusal, 'dispatch reference'): workflow._drive()
        self.assertEqual(api.dispatched, 0)
        api.locked = True
        with self.assertRaises(OSError): workflow._drive()
        self.assertEqual(api.dispatched, 1)
        result = workflow._drive()
        self.assertEqual(result['state'], 'credentials-verified')
        self.assertEqual(set(result['verified']), set(NAMES))
        self.assertEqual(api.dispatched, 1)
        self.assertFalse(result['enforcement_active'])
        self.assertEqual(workflow._drive(), result)
        api.proofs.append(api.proofs[0])
        with self.assertRaises(Refusal): workflow._drive()

    def test_unobserved_dispatch_times_out_without_replaying_unknown_post(self):
        import credential_workflow
        self.controller._stage()
        outer = self
        class Actions:
            dispatched = 0
            def pages(self, route, collection): return []
            def get(self, route):
                if route.endswith('/rules/branches/main'):
                    return [dict(type=t, ruleset_id=81, ruleset_source_type='Repository',
                        ruleset_source='owner/authority') for t in ('update', 'deletion')]
                if route.endswith('/rulesets/81'):
                    return dict(id=81, source_type='Repository', source='owner/authority', target='branch',
                        enforcement='active', bypass_actors=[], conditions=dict(ref_name=dict(include=['refs/heads/main'], exclude=[])),
                        rules=[dict(type='update', parameters=dict(update_allows_fetch_and_merge=False)), dict(type='deletion')])
                return outer.host.get(route)
            def post(self, route, body):
                self.dispatched += 1
                raise OSError('synthetic unknown request')
        api, ticks = Actions(), [0]
        def monotonic():
            ticks[0] += 301
            return ticks[0]
        workflow = credential_workflow.CredentialWorkflow(self.controller, api,
            private_setup.Store(self.root / 'dispatch'), sleep=lambda _: None, monotonic=monotonic)
        with self.assertRaises(OSError): workflow._drive()
        with self.assertRaisesRegex(Refusal, 'deadline'): workflow._drive()
        self.assertEqual(api.dispatched, 1)
        self.assertEqual(workflow.journal.read()['value']['phase'], 'dispatch-started')
        self.assertTrue(all(v['phase'] == 'acknowledged' for v in self.journal.read()['value']['entries'].values()))

    def test_exact_seven_values_are_durable_before_writes_and_ack_is_not_verification(self):
        result = self.controller._stage()
        self.assertEqual(set(self.writes), set(NAMES))
        self.assertEqual(result['state'], 'awaiting-consumer-verification')
        self.assertEqual(result['verified'], [])
        self.assertFalse(result['enforcement_active'])
        self.assertIn('UNRELATED_SECRET', self.reader_names)
        state = self.journal.read()['value']
        self.assertTrue(all(v['phase'] == 'acknowledged' for v in state['entries'].values()))
        model = self.consent.document['value']
        self.assertEqual(state['entries']['AGENTIC_MODEL_VAULT_KEY']['value'], model['keys']['vault'])
        self.assertEqual(state['entries']['AGENTIC_MODEL_DELIVERY_KEY']['value'], model['keys']['delivery'])
        self.assertEqual(state['model_vault'], model['sealed_vault'])
        rendered = json.dumps(result)
        for entry in state['entries'].values(): self.assertNotIn(entry['value'], rendered)
        before = list(self.writes)
        self.controller._stage()
        self.assertEqual(self.writes, before)

    def test_lost_ack_stays_unknown_and_present_secret_is_not_rewritten(self):
        self.gh.lose_ack = True
        with self.assertRaises(Refusal): self.controller._stage()
        self.assertEqual(len(self.writes), 1)
        state = self.journal.read()['value']
        self.assertEqual(state['entries'][self.writes[0]]['phase'], 'unknown')
        with self.assertRaises(Refusal): self.controller._stage()
        self.assertEqual(len(self.writes), 1)

    def test_native_consumer_staging_continues_other_intents_without_replaying_unknown_write(self):
        from unittest.mock import patch
        self.gh.lose_ack = True
        with self.assertRaises(Refusal): self.controller._stage()
        first = self.writes[0]
        self.gh.lose_ack = False
        with patch.object(authority_release, 'authorize'):
            result = self.controller.stage_for_consumers()
        self.assertEqual(len(self.writes), len(NAMES))
        self.assertEqual(self.writes.count(first), 1)
        self.assertEqual(self.journal.read()['value']['entries'][first]['phase'], 'unknown')
        self.assertEqual(result['verified'], [])
        self.assertEqual(result['state'], 'awaiting-consumer-verification')
        self.assertFalse(result['enforcement_active'])

    def test_unowned_secret_cli_identity_and_scope_changes_refuse_without_writes(self):
        self.reader_names.add(NAMES[0])
        with self.assertRaises(Refusal): self.controller._stage()
        self.reader_names.remove(NAMES[0])
        self.gh.actor = 999
        with self.assertRaises(Refusal): self.controller._stage()
        self.assertEqual(self.writes, [])

    def test_wrong_app_key_refuses_before_writes(self):
        self.apps['coding']['pem'] = self.apps['issuer']['pem']
        with self.assertRaises((Refusal, jwt.InvalidSignatureError)): self.controller._stage()
        self.assertEqual(self.writes, [])

    def test_boundary_expired_writer_identity_read_prevents_secret_write(self):
        original = self.gh.api
        deadline = self.registry.binding()['fence']['pending']['execution_deadline']
        def read(route):
            value = original(route)
            document = self.journal.read()
            if document is not None and any(entry['phase'] == 'write-started'
                    for entry in document['value']['entries'].values()):
                self.clock[0] = deadline
            return value
        self.gh.api = read
        with self.assertRaises(Refusal): self.controller._stage()
        self.assertEqual(self.writes, [])

    def test_boundary_case_insensitive_existing_secret_requires_repair(self):
        self.reader_names.add(NAMES[0].lower())
        with self.assertRaises(Refusal): self.controller._stage()
        self.assertEqual(self.writes, [])

    def consumer(self, name, wrong_value=None):
        challenge = self.controller._challenge(name)
        purpose = challenge['purpose']
        host = self.host
        class API(HistoricalAPI):
            def get(self, path):
                if path.endswith('/actions/runs/99'): return self.run
                if '/actions/' in path: return super().get(path)
                return host.get(path)
            def pages(self, path, collection):
                if path == '/installation/repositories': return host.pages(path, collection)
                return super().pages(path, collection)
        api = API('credential-proof', purpose)
        offset = NAMES.index(name)
        api.job['id'] += offset
        api.artifact['id'] += offset
        api.location = dict(locator(), job_id=api.job['id'], artifact_id=api.artifact['id'])
        api.fetch = lambda route, **kwargs: api.raw
        for value in (api.run, api.job, api.artifact['workflow_run']): value['head_sha'] = 'a' * 40
        api.job.update(status='in_progress', conclusion=None, started_at='1970-01-01T00:16:41Z')
        env = dict(GITHUB_REPOSITORY='owner/authority', GITHUB_REPOSITORY_ID='456', GITHUB_SHA='a' * 40,
            GITHUB_JOB=purpose + '_credential_proof', GITHUB_RUN_ID='99', GITHUB_RUN_ATTEMPT='1',
            GITHUB_TOKEN='SYNTHETIC-AUTHORITY-READ-ONLY')
        env[name] = wrong_value or self.journal.read()['value']['entries'][name]['value']
        uploaded = []
        def uploader(node, environment):
            self.assertEqual(node, 'synthetic-node')
            def upload(artifact_name, raw):
                self.assertEqual(artifact_name, 'credential-proof-' + purpose + '-1')
                self.assertNotIn(env[name].encode(), raw)
                uploaded.append(json.loads(raw))
                return api.location['artifact_id']
            return upload
        location = service._credential(env, challenge, 'synthetic-node', clock=lambda: self.clock[0],
            api_factory=lambda token: api, uploader_factory=uploader,
            consumer=lambda *args: setup._consume_credential(*args, app_factory=self.controller.app_factory))
        self.assertEqual(location, api.location)
        self.assertEqual(len(uploaded), 1)
        proof = uploaded[0]
        api.document = proof
        api.raw = api.archive(api.member)
        api.artifact['digest'] = 'sha256:' + hashlib.sha256(api.raw).hexdigest()
        api.artifact['created_at'] = '1970-01-01T00:16:42Z'
        api.job.update(status='completed', conclusion='success', completed_at='1970-01-01T00:16:42Z')
        self.clock[0] = 1003
        return api

    def test_each_pinned_consumer_proves_actual_value_before_verified_progress(self):
        self.controller._stage()
        for name in NAMES:
            api = self.consumer(name)
            self.controller._accept(name, api, api.location)
            self.clock[0] = 1001
        result = self.controller._stage()
        self.assertEqual(result['state'], 'credentials-verified')
        self.assertEqual(set(result['verified']), set(NAMES))
        self.assertEqual(len(self.writes), 7)
        self.assertFalse(result['enforcement_active'])

    def test_wrong_loaded_value_and_nonce_replay_cannot_verify(self):
        self.controller._stage()
        name = 'AGENTIC_MODEL_DELIVERY_KEY'
        api = self.consumer(name, model_vault.generate_keys()['delivery'])
        with self.assertRaises(Refusal): self.controller._accept(name, api, api.location)
        self.clock[0] = 1001
        api = self.consumer(name)
        api.document['challenge']['nonce'] = '0' * 64
        api.raw = api.archive(api.member)
        api.artifact['digest'] = 'sha256:' + hashlib.sha256(api.raw).hexdigest()
        with self.assertRaises(Refusal): self.controller._accept(name, api, api.location)

    def test_matching_consumer_recovers_unknown_write_without_rewriting(self):
        self.gh.lose_ack = True
        with self.assertRaises(Refusal): self.controller._stage()
        name = self.writes[0]
        api = self.consumer(name)
        self.controller._accept(name, api, api.location)
        self.assertEqual(self.journal.read()['value']['entries'][name]['phase'], 'verified')
        self.assertEqual(self.writes, [name])


if __name__ == '__main__': unittest.main()
