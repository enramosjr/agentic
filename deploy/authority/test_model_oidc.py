"""Real JWT signatures against generated issuer fixtures; no OpenAI requests."""
import copy
from pathlib import Path
import sys
import time
import unittest

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

sys.path[:0] = [str(Path(__file__).resolve().parents[2] / '.ai/scripts'),
               str(Path(__file__).resolve().parents[2] / '.ai/scripts/tests')]
from trusted_ci_policy import Refusal
from test_model_vault import fixture as vault_fixture
import model_oidc


class ModelOIDCContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.first = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.second = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self):
        self.now = int(time.time())
        self.nonce = 'SYNTHETIC-VERIFIED-NONCE-0123456789'
        self.claims = dict(iss='https://auth.openai.com', sub='synthetic-subject', aud='oaiapp_synthetic',
            iat=self.now - 1, exp=self.now + 600, nonce=self.nonce, auth_time=self.now - 60)
        first = jwt.algorithms.RSAAlgorithm.to_jwk(self.first.public_key(), as_dict=True)
        second = jwt.algorithms.RSAAlgorithm.to_jwk(self.second.public_key(), as_dict=True)
        first.update(kid='first', use='sig', alg='RS256')
        second.update(kid='second', use='sig', alg='RS256')
        class Provider:
            def __init__(self): self.keys, self.fetches = [first], 0
            def discovery(self):
                return dict(issuer='https://auth.openai.com', jwks_uri='https://auth.openai.com/.well-known/jwks.json',
                            id_token_signing_alg_values_supported=['RS256'])
            def jwks(self, uri):
                self.fetches += 1
                return {'keys': copy.deepcopy(self.keys)}
        self.provider, self.second_jwk = Provider(), second
        self.verifier = model_oidc.Verifier(self.provider)

    def token(self, claims=None, key=None, kid='first'):
        return jwt.encode(claims or self.claims, key or self.first, algorithm='RS256', headers={'kid': kid})

    def test_malformed_discovery_key_uri_is_a_controlled_refusal(self):
        for uri in ('https://auth.openai.com:bad/keys', 'https://auth.openai.com:99999/keys',
                    'https://[auth.openai.com/keys'):
            self.provider.discovery = lambda uri=uri: dict(issuer='https://auth.openai.com', jwks_uri=uri,
                                                           id_token_signing_alg_values_supported=['RS256'])
            verifier = model_oidc.Verifier(self.provider)
            with self.subTest(uri=uri), self.assertRaises(Refusal):
                verifier.initial(self.token(), 'oaiapp_synthetic', self.nonce, self.now)
        self.assertEqual(self.provider.fetches, 0)

    def record(self):
        verified = self.verifier.initial(self.token(), 'oaiapp_synthetic', self.nonce, self.now)
        value, _, _ = vault_fixture()
        value.update(identity=verified['identity'], authorization=verified['authorization'])
        value['credentials'].update(issued=self.now - 1, access_expires=self.now + 3600, id_token=self.token())
        return value

    def test_initial_signature_client_issuer_and_nonce_produce_verified_private_context(self):
        result = self.verifier.initial(self.token(), 'oaiapp_synthetic', self.nonce, self.now)
        self.assertEqual(result['identity']['subject'], 'synthetic-subject')
        self.assertEqual(result['authorization']['nonce'], self.nonce)
        self.assertEqual(result['authorization']['auth_time'], self.now - 60)
        self.assertEqual(self.provider.fetches, 1)

    def test_invalid_signature_nonce_issuer_audience_and_temporal_types_refuse(self):
        for field, bad in [('nonce', 'different-synthetic-nonce'), ('iss', 'https://attacker.invalid'),
            ('aud', 'foreign-client'), ('aud', ['oaiapp_synthetic', 'foreign-client']),
            ('iat', True), ('iat', str(self.now)), ('exp', str(self.now + 600)), ('exp', self.now - 1),
            ('auth_time', str(self.now - 60))]:
            claims = dict(self.claims, **{field: bad})
            with self.subTest(field=field, bad=bad), self.assertRaises(Refusal):
                self.verifier.initial(self.token(claims), 'oaiapp_synthetic', self.nonce, self.now)
        with self.assertRaises(Refusal):
            self.verifier.initial(self.token(key=self.second), 'oaiapp_synthetic', self.nonce, self.now)
        claims = dict(self.claims)
        claims.pop('nonce')
        with self.assertRaises(Refusal): self.verifier.initial(self.token(claims), 'oaiapp_synthetic', self.nonce, self.now)

    def test_unapproved_algorithm_and_critical_headers_never_select_token_directed_keys(self):
        encoded = jwt.encode(self.claims, 'SYNTHETIC-HMAC-SECRET-NEVER-TRUST' * 2, algorithm='HS256', headers={'kid': 'first'})
        with self.assertRaises(Refusal): self.verifier.initial(encoded, 'oaiapp_synthetic', self.nonce, self.now)
        encoded = jwt.encode(self.claims, self.first, algorithm='RS256', headers={'kid': 'first', 'crit': ['unknown']})
        with self.assertRaises(Refusal): self.verifier.initial(encoded, 'oaiapp_synthetic', self.nonce, self.now)
        self.assertEqual(self.provider.fetches, 0)

    def test_refresh_missing_nonce_preserves_original_authentication_time(self):
        record = self.record()
        claims = dict(self.claims, iat=self.now, exp=self.now + 900)
        claims.pop('nonce')
        result = self.verifier.refresh(self.token(claims), record, self.now, requested_at=self.now)
        self.assertEqual(result['identity'], record['identity'])
        self.assertEqual(result['authorization'], record['authorization'])

    def test_refresh_cannot_switch_subject_nonce_authentication_time_or_audience(self):
        record = self.record()
        for field, bad in [('sub', 'different-subject'), ('nonce', 'different-synthetic-nonce'),
            ('auth_time', self.now - 30), ('aud', 'foreign-client'), ('azp', 'oaiapp_synthetic')]:
            claims = dict(self.claims, iat=self.now, **{field: bad})
            with self.subTest(field=field), self.assertRaises(Refusal):
                self.verifier.refresh(self.token(claims), record, self.now, requested_at=self.now)

    def test_signed_authentication_time_can_fill_an_absent_original_baseline(self):
        claims = dict(self.claims)
        claims.pop('auth_time')
        verified = self.verifier.initial(self.token(claims), 'oaiapp_synthetic', self.nonce, self.now)
        record = self.record()
        record['authorization'] = verified['authorization']
        refreshed = dict(self.claims, iat=self.now)
        refreshed.pop('nonce')
        result = self.verifier.refresh(self.token(refreshed), record, self.now, requested_at=self.now)
        self.assertEqual(result['authorization']['auth_time'], self.now - 60)
        refreshed['auth_time'] = self.now
        with self.assertRaises(Refusal): self.verifier.refresh(self.token(refreshed), record, self.now, requested_at=self.now)

    def test_unknown_kid_refreshes_only_published_issuer_keys_once(self):
        record = self.record()
        self.provider.keys = [self.second_jwk]
        claims = dict(self.claims, iat=self.now)
        claims.pop('nonce')
        result = self.verifier.refresh(self.token(claims, self.second, 'second'), record, self.now, requested_at=self.now)
        self.assertEqual(result['identity'], record['identity'])
        self.assertEqual(self.provider.fetches, 2)

    def test_foreign_key_origin_or_missing_key_fails_closed(self):
        self.provider.discovery = lambda: dict(issuer='https://auth.openai.com', jwks_uri='https://attacker.invalid/keys',
                                             id_token_signing_alg_values_supported=['RS256'])
        with self.assertRaises(Refusal): self.verifier.initial(self.token(), 'oaiapp_synthetic', self.nonce, self.now)
        self.assertEqual(self.provider.fetches, 0)
        self.provider.discovery = lambda: dict(issuer='https://auth.openai.com',
            jwks_uri='https://auth.openai.com/.well-known/jwks.json', id_token_signing_alg_values_supported=['RS256'])
        self.provider.keys = []
        with self.assertRaises(Refusal): self.verifier.initial(self.token(), 'oaiapp_synthetic', self.nonce, self.now)


if __name__ == '__main__':
    unittest.main()
