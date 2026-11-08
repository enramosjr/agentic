"""Fixed OAuth transport contracts with synthetic tokens; no provider calls."""
import backend_test_support
import io
import json
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs

from trusted_ci_policy import Refusal
import oauth_transport


def request():
    return dict(schema_version=1, purpose='token', data=dict(grant_type='refresh_token', client_id='oaiapp_synthetic',
        refresh_token='SYNTHETIC-REFRESH-SECRET', resource='https://api.openai.com/v1'))


class OAuthTransportContracts(unittest.TestCase):
    def test_malformed_code_callback_is_refused_before_http(self):
        for uri in ('http://127.0.0.1:bad/auth/callback', 'http://127.0.0.1:99999/auth/callback',
                    'http://[127.0.0.1/auth/callback'):
            value = request()
            value['data'] = dict(grant_type='authorization_code', client_id='oaiapp_synthetic',
                resource=oauth_transport.RESOURCE, code='SYNTHETIC-CODE', code_verifier='a' * 43, redirect_uri=uri)
            with self.subTest(uri=uri), patch.object(oauth_transport, 'build_opener') as network:
                with self.assertRaises(Refusal): oauth_transport.request_once(value)
                network.assert_not_called()

    def test_refresh_uses_one_fixed_https_form_post_without_scope_or_redirect(self):
        calls = []
        class Response(io.BytesIO):
            status = 200
        class Opener:
            def open(self, req, timeout):
                calls.append((req, timeout))
                return Response(b'{"access_token":"SYNTHETIC-NEW-ACCESS"}')
        result = oauth_transport.request_once(request(), Opener())
        self.assertTrue(result['ok'])
        self.assertEqual(result['value']['access_token'], 'SYNTHETIC-NEW-ACCESS')
        self.assertEqual(len(calls), 1)
        req, timeout = calls[0]
        self.assertEqual(req.full_url, 'https://auth.openai.com/api/accounts/oauth/token')
        self.assertEqual(req.method, 'POST')
        self.assertEqual(timeout, 30)
        self.assertEqual(parse_qs(req.data.decode())['refresh_token'], ['SYNTHETIC-REFRESH-SECRET'])
        self.assertNotIn('scope', parse_qs(req.data.decode()))
        self.assertIsNone(oauth_transport.NoRedirect().redirect_request(req, None, 307, '', {}, 'https://attacker.invalid'))

    def test_unknown_route_scope_or_foreign_jwks_uri_fails_before_http(self):
        for value in (dict(request(), purpose='arbitrary'),
                      dict(request(), data=dict(request()['data'], scope='expanded')),
                      dict(schema_version=1, purpose='jwks', uri='https://attacker.invalid/keys')):
            with self.subTest(value=value), patch.object(oauth_transport, 'build_opener') as network:
                with self.assertRaises(Refusal): oauth_transport.request_once(value)
                network.assert_not_called()

    def test_provider_error_body_is_not_echoed_or_used_as_success(self):
        class Opener:
            def open(self, req, timeout):
                raise HTTPError(req.full_url, 400, 'refused', {}, io.BytesIO(
                    b'{"error":"invalid_grant","error_description":"SYNTHETIC-REFRESH-SECRET"}'))
        result = oauth_transport.request_once(request(), Opener())
        self.assertEqual(result, {'ok': False, 'status': 400, 'error': 'invalid_grant'})
        self.assertNotIn('SYNTHETIC', json.dumps(result))

    def test_total_deadline_kills_and_reaps_stalled_child_without_env_or_argv_secret(self):
        children = []
        real = subprocess.Popen
        def stalled(argv, **kwargs):
            self.assertNotIn('SYNTHETIC-REFRESH-SECRET', ' '.join(argv))
            self.assertNotIn('GITHUB_TOKEN', kwargs['env'])
            self.assertNotIn('HOME', kwargs['env'])
            self.assertNotIn('HTTPS_PROXY', kwargs['env'])
            child = real([sys.executable, '-I', '-c', 'import time; time.sleep(10)'], **kwargs)
            children.append(child)
            return child
        started = time.monotonic()
        with patch.object(oauth_transport.subprocess, 'Popen', side_effect=stalled), self.assertRaises(Refusal):
            oauth_transport.isolated(request(), .15)
        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].poll())

    def test_private_response_protocol_cannot_promote_unknown_or_malformed_results(self):
        for response in ({'ok': False, 'status': None, 'error': 'completion_unknown'},
                         {'ok': True, 'status': 200, 'value': []}):
            with self.subTest(response=response), patch.object(oauth_transport, 'isolated', return_value=response):
                with self.assertRaises(Refusal): oauth_transport.OpenAI().token(request()['data'])


if __name__ == '__main__':
    unittest.main()
