"""Encrypted refresh storage and access-only delivery, with explicit callers.

Only the auth job may open refresh records. The task parent gets a separately
encrypted access lease; the coding worker gets neither key nor OAuth credential.
These functions do not validate an OAuth ID-token signature, authenticate a job,
read a native login cache, persist state, or qualify model access. Those steps must
precede/contain their use in the pinned trusted runtime.
"""
import base64
import json
import re

from authority_protocol import fingerprint, validate_deployment
from codex_harness import profile
from trusted_ci_policy import Refusal, digest, loads, object_fields, positive, require, sha

BINDING_FIELDS = ('authority_repository_id', 'session_id', 'generation', 'identity_digest')
RECORD_FIELDS = ('schema_version', 'kind', 'authority_repository_id', 'session_id', 'generation',
                 'identity', 'authorization', 'credentials')
TASK_FIELDS = ('task_id', 'run_id', 'attempt', 'deadline', 'purpose')
LEASE_FIELDS = ('schema_version kind authority_repository_id session_id identity_digest client_id auth_generation '
    'configuration_revision deployment_digest repository_id target task_id run_id attempt purpose model_id '
    'issued expires access_token scopes').split()
MAX_PLAIN, MAX_CIPHER = 32 * 1024, 64 * 1024
PLAN_SCOPES = ('chatgpt.tokens.use.direct', 'resource.invoke')


def _fernet(key):
    try:
        from cryptography.fernet import Fernet
        return Fernet(key)
    except ImportError:
        raise Refusal('optional model-auth cryptography dependency is unavailable') from None
    except (ValueError, TypeError):
        raise Refusal('invalid model-auth encryption key') from None


def validate_keys(vault_key, delivery_key):
    _fernet(vault_key)
    _fernet(delivery_key)
    require(base64.urlsafe_b64decode(vault_key) != base64.urlsafe_b64decode(delivery_key),
            'vault and delivery keys must be distinct')


def generate_keys():
    from cryptography.fernet import Fernet
    keys = dict(vault=Fernet.generate_key().decode('ascii'), delivery=Fernet.generate_key().decode('ascii'))
    validate_keys(keys['vault'], keys['delivery'])
    return keys


def _token(value):
    return isinstance(value, str) and 0 < len(value) <= 16 * 1024 and re.fullmatch(r'[A-Za-z0-9._~+/=-]+', value)


def _identifier(value):
    return isinstance(value, str) and 0 < len(value) <= 512 and all(32 < ord(c) < 127 for c in value)


def validate_record(value):
    object_fields(value, RECORD_FIELDS, 'model refresh record')
    require(type(value['schema_version']) is int and value['schema_version'] == 1 and
            value['kind'] == 'model-refresh-vault' and positive(value['authority_repository_id']) and
            isinstance(value['session_id'], str) and re.fullmatch('[0-9a-f]{32}', value['session_id']) and
            positive(value['generation']), 'model refresh identity differs')
    identity, credentials = value['identity'], value['credentials']
    object_fields(identity, ('issuer', 'subject', 'client_id'), 'verified model identity')
    require(identity['issuer'] == 'https://auth.openai.com' and _identifier(identity['subject']) and
            _identifier(identity['client_id']) and identity['client_id'] != 'dynamic_agent_client',
            'issued model client and verified identity required')
    authorization = value['authorization']
    object_fields(authorization, ('nonce', 'initial_id_issued', 'audiences', 'auth_time', 'authorized_party'),
                  'verified authorization context')
    require(_identifier(authorization['nonce']) and 16 <= len(authorization['nonce']) <= 200 and
            positive(authorization['initial_id_issued']) and authorization['audiences'] == [identity['client_id']] and
            (authorization['auth_time'] is None or positive(authorization['auth_time']) and
             authorization['auth_time'] <= authorization['initial_id_issued']) and
            authorization['authorized_party'] in (None, identity['client_id']), 'verified authorization context differs')
    object_fields(credentials, ('access_token', 'refresh_token', 'id_token', 'token_type', 'issued',
                                'access_expires', 'scopes'), 'model root credentials')
    require(all(_token(credentials[k]) for k in ('access_token', 'refresh_token', 'id_token')) and
            credentials['token_type'] == 'Bearer' and positive(credentials['issued']) and
            authorization['initial_id_issued'] <= credentials['issued'] + 30 and
            positive(credentials['access_expires']) and
            credentials['issued'] < credentials['access_expires'] <= credentials['issued'] + 86400,
            'bounded model credentials required')
    scopes = credentials['scopes']
    require(isinstance(scopes, list) and 0 < len(scopes) <= 32 and
            all(isinstance(v, str) and re.fullmatch('[a-zA-Z0-9._:-]{1,100}', v) for v in scopes) and
            len(set(scopes)) == len(scopes) and set((*PLAN_SCOPES, 'offline_access')) <= set(scopes),
            'ChatGPT plan and refresh permission required; no billing fallback')
    return value


def _pack(value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    require(0 < len(raw) <= MAX_PLAIN, 'model secret record exceeds limit')
    return raw


def _open(ciphertext, key, now=None):
    require(isinstance(ciphertext, str) and 0 < len(ciphertext) <= MAX_CIPHER and ciphertext.isascii(),
            'bounded encrypted model record required')
    fernet = _fernet(key)
    from cryptography.fernet import InvalidToken
    try:
        raw = (fernet.decrypt(ciphertext.encode('ascii')) if now is None else
               fernet.decrypt_at_time(ciphertext.encode('ascii'), ttl=3600, current_time=now))
        require(0 < len(raw) <= MAX_PLAIN, 'decrypted model record exceeds limit')
        return loads(raw)
    except (InvalidToken, UnicodeError, ValueError, TypeError):
        raise Refusal('model record authentication failed') from None


def seal_record(record, vault_key):
    validate_record(record)
    ciphertext = _fernet(vault_key).encrypt(_pack(record)).decode('ascii')
    return dict(schema_version=1, kind='encrypted-model-vault', authority_repository_id=record['authority_repository_id'],
        session_id=record['session_id'], generation=record['generation'], identity_digest=digest(record['identity']),
        ciphertext=ciphertext)


def validate_encrypted(value):
    """Opaque storage schema only; callers must open/authenticate before use."""
    object_fields(value, ('schema_version', 'kind', *BINDING_FIELDS, 'ciphertext'), 'encrypted model vault')
    require(type(value['schema_version']) is int and value['schema_version'] == 1 and
            value['kind'] == 'encrypted-model-vault' and positive(value['authority_repository_id']) and
            positive(value['generation']) and isinstance(value['session_id'], str) and
            re.fullmatch('[0-9a-f]{32}', value['session_id']) and fingerprint(value['identity_digest']) and
            isinstance(value['ciphertext'], str) and 0 < len(value['ciphertext']) <= MAX_CIPHER and
            value['ciphertext'].isascii() and not any(ord(c) < 32 for c in value['ciphertext']),
            'strict encrypted model vault required')
    return value


def open_record(value, vault_key, expected):
    validate_encrypted(value)
    object_fields(expected, BINDING_FIELDS, 'expected model vault binding')
    for item in (value, expected):
        require(positive(item['authority_repository_id']) and positive(item['generation']) and
                isinstance(item['session_id'], str) and re.fullmatch('[0-9a-f]{32}', item['session_id']) and
                fingerprint(item['identity_digest']), 'strict model vault binding required')
    require(type(value['schema_version']) is int and value['schema_version'] == 1 and
            value['kind'] == 'encrypted-model-vault' and all(value[k] == expected[k] for k in BINDING_FIELDS),
            'encrypted model vault binding differs')
    record = validate_record(_open(value['ciphertext'], vault_key))
    actual = {k: record[k] for k in ('authority_repository_id', 'session_id', 'generation')}
    actual['identity_digest'] = digest(record['identity'])
    require(actual == expected, 'decrypted model identity or generation differs')
    return record


def _binding(binding, task):
    d = validate_deployment(binding['deployment'])
    r = profile(d)
    object_fields(task, TASK_FIELDS, 'model task request')
    require(sha(binding['configuration_revision']) and binding['deployment_digest'] == digest(d) and
            isinstance(task['task_id'], str) and re.fullmatch('[0-9a-f]{32}', task['task_id']) and
            all(positive(task[k]) for k in ('run_id', 'attempt', 'deadline')) and
            ((d['state'] == 'active' and task['purpose'] == 'task') or
             (d['state'] == 'qualification' and task['purpose'] == 'qualification')),
            'current configured model task required')
    require(isinstance(r.get('model_session'), str) and re.fullmatch('[0-9a-f]{32}', r['model_session']) and
            fingerprint(r.get('model_account')) and _identifier(r.get('model_client')),
            'configured model identity required')
    return d, r


def issue_lease(record, delivery_key, binding, task, now):
    validate_record(record)
    d, r = _binding(binding, task)
    credentials = record['credentials']
    require(type(now) is int and credentials['issued'] <= now and
            record['authority_repository_id'] == d['policy']['authority_repository_id'] and
            record['session_id'] == r['model_session'] and digest(record['identity']) == r['model_account'] and
            record['identity']['client_id'] == r['model_client'], 'model account or client differs')
    expires = min(credentials['access_expires'], task['deadline'], d['expires'], now + 3600)
    require(expires - now >= d['policy']['limits']['seconds'] + 60,
            'model access needs refresh before the complete bounded task')
    value = dict(schema_version=1, kind='model-access-lease', authority_repository_id=record['authority_repository_id'],
        session_id=record['session_id'], identity_digest=digest(record['identity']), client_id=record['identity']['client_id'],
        auth_generation=record['generation'], configuration_revision=binding['configuration_revision'],
        deployment_digest=binding['deployment_digest'], repository_id=d['policy']['repository_id'], target=d['policy']['target'],
        task_id=task['task_id'], run_id=task['run_id'], attempt=task['attempt'], purpose=task['purpose'], model_id=r['model_id'],
        issued=now, expires=expires, access_token=credentials['access_token'], scopes=list(PLAN_SCOPES))
    return _fernet(delivery_key).encrypt_at_time(_pack(value), now).decode('ascii')


def open_lease(ciphertext, delivery_key, binding, task, now):
    require(type(now) is int and now > 0, 'current model lease clock required')
    value = _open(ciphertext, delivery_key, now)
    return validate_lease(value, binding, task, now)


def read_delivery(authority, binding, task, locator, delivery_key, now):
    """Authenticate the closed auth producer before opening an access-only lease."""
    from provenance import authenticated_document
    d, _ = _binding(binding, task)
    proof = authenticated_document(authority, d, locator, 'model-lease', task['task_id'], now)
    document = proof['document']
    object_fields(document, ('ciphertext', 'model_execution_qualified'), 'encrypted model delivery')
    require(document['model_execution_qualified'] is False and proof['run_id'] == task['run_id'] and
            proof['attempt'] == task['attempt'], 'model delivery execution differs')
    lease = open_lease(document['ciphertext'], delivery_key, binding, task, now)
    require(proof['job_started'] <= lease['issued'] <= proof['artifact_created'] <= proof['job_completed'] <= now,
            'model delivery was not issued during its authenticated job')
    return lease


def validate_lease(value, binding, task, now):
    """Validate already authenticated parent data; this is not decryption proof."""
    require(type(now) is int and now > 0, 'current model lease clock required')
    d, r = _binding(binding, task)
    object_fields(value, LEASE_FIELDS, 'access-only model lease')
    require(type(value['schema_version']) is int and value['schema_version'] == 1 and value['kind'] == 'model-access-lease' and
            all(positive(value[k]) for k in ('authority_repository_id', 'repository_id', 'auth_generation', 'run_id', 'attempt')) and
            value['authority_repository_id'] == d['policy']['authority_repository_id'] and value['session_id'] == r['model_session'] and
            value['identity_digest'] == r['model_account'] and value['client_id'] == r['model_client'] and positive(value['auth_generation']) and
            all(value[k] == binding[k] for k in ('configuration_revision', 'deployment_digest')) and
            value['repository_id'] == d['policy']['repository_id'] and value['target'] == d['policy']['target'] and
            all(value[k] == task[k] for k in ('task_id', 'run_id', 'attempt', 'purpose')) and
            value['model_id'] == r['model_id'] and value['scopes'] == list(PLAN_SCOPES) and _token(value['access_token']),
            'model access lease identity or task differs')
    require(positive(value['issued']) and positive(value['expires']) and value['issued'] <= now and
            value['expires'] <= min(value['issued'] + 3600, task['deadline'], d['expires']) and
            value['expires'] - now >= d['policy']['limits']['seconds'] + 60,
            'model access lease is stale or too short for admission')
    return value
