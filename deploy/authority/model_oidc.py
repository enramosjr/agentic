"""Signature-verified initial and refresh ID-token context for public SIWC.

ID identity alone grants no model usage. Token response scopes, durable rotation,
current task binding and completed inference are separately required.
"""
import copy
import hmac
import time

from model_vault import validate_record
from oauth_transport import ISSUER, OpenAI, validate_jwks_uri
from trusted_ci_policy import Refusal, positive, require


def _text(value, limit=512):
    return isinstance(value, str) and 0 < len(value) <= limit and all(32 < ord(c) < 127 for c in value)


class Verifier:
    def __init__(self, provider=None):
        self.provider = provider or OpenAI()
        self.uri, self.keys = None, None

    def _load(self):
        import jwt
        if self.uri is None:
            metadata = self.provider.discovery()
            require(isinstance(metadata, dict) and metadata.get('issuer') == ISSUER and
                    isinstance(metadata.get('id_token_signing_alg_values_supported'), list) and
                    'RS256' in metadata['id_token_signing_alg_values_supported'], 'approved issuer metadata unavailable')
            uri = validate_jwks_uri(metadata.get('jwks_uri'))
            self.uri = uri
        value = self.provider.jwks(self.uri)
        require(isinstance(value, dict) and isinstance(value.get('keys'), list) and 0 < len(value['keys']) <= 100,
                'bounded issuer public keys required')
        keys = {}
        seen = set()
        for item in value['keys']:
            require(isinstance(item, dict) and _text(item.get('kid'), 200) and item['kid'] not in seen,
                    'unique issuer public key identifiers required')
            seen.add(item['kid'])
            if item.get('kty') != 'RSA' or item.get('alg') not in (None, 'RS256') or item.get('use') not in (None, 'sig'):
                continue
            require(not any(k in item for k in ('d', 'p', 'q', 'dp', 'dq', 'qi')) and
                    (item.get('key_ops') is None or isinstance(item['key_ops'], list) and 'verify' in item['key_ops']) and
                    _text(item.get('n'), 2048) and _text(item.get('e'), 16), 'issuer signature key is not public or bounded')
            try:
                key = jwt.PyJWK.from_dict(item, algorithm='RS256')
                require(2048 <= key.key.key_size <= 8192, 'unsupported issuer RSA key size')
            except (jwt.PyJWTError, ValueError, TypeError, KeyError, AttributeError):
                raise Refusal('invalid issuer signature key') from None
            keys[item['kid']] = key
        require(keys, 'supported issuer signature keys unavailable')
        self.keys = keys

    def _decode(self, encoded, client_id, now):
        import jwt
        require(_text(encoded, 16 * 1024) and _text(client_id) and client_id != 'dynamic_agent_client' and
                type(now) is int and now > 0, 'bounded issued-client ID token required')
        try:
            header = jwt.get_unverified_header(encoded)  # Routing/rejection only, never identity.
        except (jwt.PyJWTError, ValueError, TypeError):
            raise Refusal('invalid ID-token header') from None
        require(header.get('alg') == 'RS256' and _text(header.get('kid'), 200) and
                header.get('typ') in (None, 'JWT') and 'crit' not in header,
                'unsupported ID-token algorithm or critical header')
        if self.keys is None:
            self._load()
        elif header['kid'] not in self.keys:
            self._load()  # One published-key refresh, never a grant retry.
        require(header['kid'] in self.keys, 'ID-token issuer key unavailable')
        try:
            claims = jwt.decode(encoded, key=self.keys[header['kid']].key, algorithms=['RS256'],
                issuer=ISSUER, audience=client_id, options={'require': ['iss', 'sub', 'aud', 'exp', 'iat']}, leeway=30)
        except (jwt.PyJWTError, ValueError, TypeError):
            raise Refusal('ID-token signature or registered claims invalid') from None
        audiences = [claims['aud']] if isinstance(claims['aud'], str) else claims['aud']
        require(audiences == [client_id] and claims.get('azp') in (None, client_id) and _text(claims['sub']) and
                positive(claims['iat']) and positive(claims['exp']) and claims['iat'] <= now + 30 and now < claims['exp'],
                'ID-token identity, audience or time differs')
        auth_time = claims.get('auth_time')
        require(auth_time is None or positive(auth_time) and auth_time <= claims['iat'], 'invalid original authentication time')
        return claims, audiences

    def initial(self, encoded, client_id, nonce, now=None):
        now = int(time.time()) if now is None else now
        require(_text(nonce, 200) and len(nonce) >= 16, 'saved initial authorization nonce required')
        claims, audiences = self._decode(encoded, client_id, now)
        require(_text(claims.get('nonce'), 200) and hmac.compare_digest(claims['nonce'], nonce),
                'initial ID-token nonce differs')
        return dict(identity=dict(issuer=ISSUER, subject=claims['sub'], client_id=client_id),
            authorization=dict(nonce=nonce, initial_id_issued=claims['iat'], audiences=audiences,
                               auth_time=claims.get('auth_time'), authorized_party=claims.get('azp')))

    def refresh(self, encoded, record, now=None, requested_at=None):
        validate_record(record)
        now = int(time.time()) if now is None else now
        requested_at = now if requested_at is None else requested_at
        require(positive(requested_at) and requested_at <= now, 'refresh request start time required')
        claims, audiences = self._decode(encoded, record['identity']['client_id'], now)
        original = record['authorization']
        require(claims['sub'] == record['identity']['subject'] and audiences == original['audiences'] and
                claims.get('azp') == original['authorized_party'] and claims['iat'] >= requested_at - 30,
                'refresh changed identity, audience, authorized party or issuance context')
        if 'nonce' in claims:
            require(_text(claims['nonce'], 200) and hmac.compare_digest(claims['nonce'], original['nonce']),
                    'refresh ID-token nonce differs')
        authorization = copy.deepcopy(original)
        if 'auth_time' in claims:
            auth_time = claims['auth_time']
            require(auth_time is not None and (auth_time == original['auth_time'] if original['auth_time'] is not None else
                    auth_time <= original['initial_id_issued']), 'refresh changed the original authentication time')
            authorization['auth_time'] = auth_time
        return dict(identity=copy.deepcopy(record['identity']), authorization=authorization)
