"""Local browser callbacks and real issuer signatures; no OpenAI/GitHub calls."""
import copy
import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit

sys.path[:0] = [str(Path(__file__).resolve().parents[2] / '.ai/scripts'),
               str(Path(__file__).resolve().parents[2] / '.ai/scripts/tests'),
               str(Path(__file__).resolve().parent / 'tests')]
from test_authority_model_auth_store import AuthHost
from test_authority_registry import coordinates, intent
import test_model_oidc
from trusted_ci_policy import Refusal, digest
from configuration import ConfigurationSession
import authority_release
import model_auth_store
import model_consent
import model_vault
import private_setup
import registry


class ModelConsentContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls): test_model_oidc.ModelOIDCContracts.setUpClass()

    def setUp(self):
        parent = str(Path.home()) if os.name == 'nt' else '/tmp'
        self.temporary = tempfile.TemporaryDirectory(prefix='agentic-consent-fixture-', dir=parent)
        self.addCleanup(self.temporary.cleanup)
        self.now = int(time.time())
        self.issuer = test_model_oidc.ModelOIDCContracts()
        self.issuer.setUp()
        self.host = AuthHost()
        self.registry = registry.Registry(self.host, coordinates())
        d = intent()
        d.update(state='setup', expires=self.now + 3600)
        self.registry.write(None, d)
        b = self.registry.binding()
        scope = {'credentials': ['owner/authority:model-vault']}
        owner = dict(workflow_sha='a' * 40, run_id=99, attempt=1)
        op = dict(kind='configuration', operation_id='1' * 32, scope_digest=digest(scope),
            repository_id=123, target='main', configuration_revision=b['configuration_revision'],
            deployment_digest=b['deployment_digest'], **owner, created=self.now - 5, execution_deadline=self.now + 600,
            pr=None, head=None, base=None, merge=None)
        self.registry.acquire_operation(b['branch_head'], b['configuration_revision'], op)
        self.session = ConfigurationSession(self.registry, '1' * 32, 1, owner, scope, lambda: self.now)
        self.auth = model_auth_store.AuthStore(self.host, 'owner/authority', 456, 'a' * 40, session=self.session)
        self.calls = []
        self.provider = self.issuer.provider
        def token(data):
            self.calls.append(copy.deepcopy(data))
            self.assertEqual(self.controller.journal.read()['value']['attempt']['phase'], 'exchange-started')
            challenge = base64.urlsafe_b64encode(hashlib.sha256(data['code_verifier'].encode()).digest()).rstrip(b'=').decode()
            self.assertEqual(challenge, self.authorized_challenge)
            if isinstance(self.response, Exception): raise self.response
            return copy.deepcopy(self.response)
        self.provider.token = token
        self.controller = self.controller_for()
        self.host.writes.clear()

    def controller_for(self, browser=None):
        return model_consent.Consent(self.auth, self.session, Path(self.temporary.name) / 'setup',
                                     provider=self.provider, browser=browser, clock=lambda: self.now)

    def begin(self, controller=None):
        controller = controller or self.controller
        url = controller._begin('http://127.0.0.1:1455/auth/callback')
        values = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
        self.authorized_challenge = values['code_challenge']
        self.response = dict(access_token='SYNTHETIC-ACCESS', refresh_token='SYNTHETIC-REFRESH', token_type='Bearer',
            expires_in=3600, scope='openid profile email offline_access resource.invoke chatgpt.tokens.use.direct',
            id_token=self.issuer.token(dict(self.issuer.claims, nonce=values['nonce'])))
        return values, dict(state=values['state'], code='SYNTHETIC-CODE', client_id='oaiapp_synthetic')

    def test_public_hold_precedes_private_storage_keys_browser_and_provider(self):
        browser = unittest.mock.Mock()
        controller = self.controller_for(browser)
        with self.assertRaises(authority_release.Held): controller.run()
        self.assertFalse((Path(self.temporary.name) / 'setup').exists())
        browser.assert_not_called()
        self.assertEqual(self.calls, [])
        self.assertEqual(self.host.writes, [])

    def test_expired_or_invalid_consent_clock_refuses_before_private_state(self):
        for now in (True, self.now + 601, self.now + 3601):
            controller = self.controller_for()
            controller.clock = lambda now=now: now
            with self.subTest(now=now), self.assertRaises(Refusal):
                controller._begin('http://127.0.0.1:1455/auth/callback')
        self.assertFalse((Path(self.temporary.name) / 'setup').exists())
        self.assertEqual(self.calls, [])

    def test_persisted_host_and_pkce_before_url_and_verified_vault_before_profile(self):
        values, callback = self.begin()
        before = self.controller.journal.read()['value']
        self.assertEqual(values['ext_agent_host_id'], before['host_id'])
        self.assertEqual(values['client_id'], 'dynamic_agent_client')
        self.assertEqual(values['agent_name_hint'], 'AGENTIC')
        self.assertEqual(values['code_challenge_method'], 'S256')
        result = self.controller._exchange(callback)
        state = self.auth.read()['state']
        keys = before['keys']
        expected = {k: state['vault'][k] for k in model_vault.BINDING_FIELDS}
        record = model_vault.open_record(state['vault'], keys['vault'], expected)
        self.assertEqual(record['authorization']['nonce'], values['nonce'])
        self.assertEqual(result['resources']['model_account'], digest(record['identity']))
        self.assertEqual(self.calls[0]['client_id'], 'oaiapp_synthetic')
        self.assertEqual(self.calls[0]['redirect_uri'], values['redirect_uri'])
        self.assertFalse(result['enforcement_active'])
        self.assertFalse(result['model_execution_qualified'])
        self.assertNotIn('SYNTHETIC-CODE', json.dumps(self.controller.journal.read()))
        self.assertNotIn('SYNTHETIC-ACCESS', json.dumps(result))
        with self.assertRaises(Refusal): self.controller._exchange(callback)
        self.assertEqual(len(self.calls), 1)

    def test_state_denial_callback_scope_and_client_substitution_never_authorize(self):
        values, callback = self.begin()
        with self.assertRaises(Refusal): self.controller._exchange(dict(callback, state='wrong-state'))
        self.assertEqual(self.calls, [])
        self.response['scope'] = 'openid profile email offline_access resource.invoke'
        with self.assertRaises(Refusal): self.controller._exchange(dict(callback, scope='chatgpt.tokens.use.direct'))
        self.assertIsNone(self.auth.read()['state'])
        self.assertEqual(len(self.calls), 1)

    def test_denial_precedes_code_and_negative_control_detects_ignored_denial(self):
        def contract(exchange):
            values, callback = self.begin()
            with self.assertRaises(Refusal): exchange(dict(callback, error='access_denied'))
            self.assertEqual(self.calls, [])
            self.assertIsNone(self.auth.read()['state'])
        original = self.controller._exchange
        contract(original)
        # Same contract must fail if the error branch is deliberately bypassed.
        with self.assertRaises(AssertionError):
            contract(lambda query: original({key: value for key, value in query.items() if key != 'error'}))

    def test_unknown_exchange_restarts_with_fresh_attempt_and_unverified_client_hint(self):
        values, callback = self.begin()
        self.response = Refusal('synthetic unknown exchange completion')
        with self.assertRaises(Refusal): self.controller._exchange(callback)
        old = self.controller.journal.read()['value']
        self.assertEqual(old['attempt']['phase'], 'exchange-started')
        self.assertIsNone(self.auth.read()['state'])
        replacement = self.controller_for()
        fresh, new_callback = self.begin(replacement)
        self.assertEqual(fresh['ext_agent_host_id'], values['ext_agent_host_id'])
        self.assertEqual(fresh['client_id'], 'oaiapp_synthetic')
        self.assertNotIn('agent_name_hint', fresh)
        self.assertNotEqual(fresh['state'], values['state'])
        self.assertNotEqual(fresh['nonce'], values['nonce'])
        with self.assertRaises(Refusal): replacement._exchange(callback)
        with self.assertRaises(Refusal): replacement._exchange(dict(new_callback, client_id='foreign-client'))
        self.assertEqual(len(self.calls), 1)

    def test_uncertain_intent_persistence_never_reaches_token_endpoint(self):
        values, callback = self.begin()
        real = private_setup.replace
        def uncertain(*args):
            real(*args)
            raise OSError('synthetic persistence completion unknown')
        with patch.object(private_setup, 'replace', side_effect=uncertain), self.assertRaises(Refusal):
            self.controller._exchange(callback)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.controller.journal.read()['value']['attempt']['phase'], 'exchange-started')

    def test_sealed_envelope_recovers_storage_without_exchange_or_resealing(self):
        values, callback = self.begin()
        real = self.auth.initialize
        def lost(vault):
            real(vault)
            raise Refusal('synthetic lost completion after initialized storage')
        with patch.object(self.auth, 'initialize', side_effect=lost), self.assertRaises(Refusal):
            self.controller._exchange(callback)
        sealed = self.controller.journal.read()['value']['sealed_vault']
        replacement = self.controller_for(unittest.mock.Mock(side_effect=AssertionError('browser must not reopen')))
        result = replacement._run(seconds=1)
        self.assertEqual(self.auth.read()['state']['vault'], sealed)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(result['auth_generation'], 1)

    def test_actual_loopback_callback_stray_state_then_valid_code_exchanges_once(self):
        responses, children = [], []
        def browser(uri):
            values = {k: v[0] for k, v in parse_qs(urlsplit(uri).query).items()}
            self.authorized_challenge = values['code_challenge']
            self.response = dict(access_token='SYNTHETIC-ACCESS', refresh_token='SYNTHETIC-REFRESH', token_type='Bearer',
                expires_in=3600, scope='offline_access resource.invoke chatgpt.tokens.use.direct',
                id_token=self.issuer.token(dict(self.issuer.claims, nonce=values['nonce'])))
            target = urlsplit(values['redirect_uri'])
            def callback():
                for state in ('stray-state', values['state']):
                    client = http.client.HTTPConnection('127.0.0.1', target.port, timeout=3)
                    client.request('GET', target.path + '?' + urlencode(dict(state=state, code='SYNTHETIC-CODE', client_id='oaiapp_synthetic')))
                    response = client.getresponse()
                    responses.append((response.status, response.read()))
                    client.close()
            child = threading.Thread(target=callback)
            children.append(child)
            child.start()
            return True
        self.controller = self.controller_for(browser)
        result = self.controller._run(seconds=5)
        for child in children: child.join(timeout=3)
        self.assertTrue(all(not child.is_alive() for child in children))
        self.assertEqual([status for status, body in responses], [400, 200])
        self.assertNotIn(b'SYNTHETIC', b''.join(body for status, body in responses))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.auth.read()['state']['vault']['session_id'], result['resources']['model_session'])


if __name__ == '__main__': unittest.main()
