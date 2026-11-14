"""Held initial public-client consent with durable, private setup recovery.

No native login cache, client secret or API billing fallback. The host identity
is installation metadata, not account identity or evidence of model entitlement.
Secret wiring and the final deployment transition belong to the setup workflow.
"""
import base64
import copy
import hashlib
import hmac
import re
import secrets
import socket
import time
from urllib.parse import parse_qs, urlencode, urlsplit
import uuid
import webbrowser

import authority_release
from configuration import require_session
from model_oidc import Verifier
import model_vault
from oauth_transport import ISSUER, RESOURCE, OpenAI
import private_setup
from trusted_ci_policy import Refusal, digest, object_fields, positive, require

SCOPES = ('openid', 'profile', 'email', 'offline_access', 'resource.invoke', 'chatgpt.tokens.use.direct')
BODY_FIELDS = ('schema_version kind configuration host_id session_id keys attempt sealed_vault').split()
ATTEMPT_FIELDS = ('attempt_id phase redirect_uri state nonce verifier requested_client_id received_issued_client_id exchange_started').split()


def callback_uri(value):
    require(isinstance(value, str) and len(value) <= 200, 'exact model loopback callback required')
    try:
        uri = urlsplit(value)
        port = uri.port
    except ValueError:
        raise Refusal('invalid model callback URI') from None
    require(uri.scheme == 'http' and port is not None and 1024 <= port <= 65535 and
            uri.netloc == '127.0.0.1:' + str(port) and uri.path == '/auth/callback' and
            not uri.query and not uri.fragment, 'exact model loopback callback required')
    return value


class Consent:
    def __init__(self, auth_store, session, journal_root, provider=None, browser=None, clock=None):
        self.auth_store, self.session, self.journal_root = auth_store, session, journal_root
        self.provider, self.browser = provider or OpenAI(), browser or webbrowser.open
        self.clock = clock or (lambda: int(time.time()))
        self.journal = self.document = self.pending = None
        self.consumed = False

    def run(self):
        authority_release.authorize('bootstrap')  # Before filesystem, keys, browser or network.
        return self._run()

    def _configuration(self):
        current = require_session(self.session, 'credentials', self.auth_store.repository + ':model-vault')
        require(isinstance(current, dict), 'authenticated setup configuration required')
        d, op = current['deployment'], current['fence']['pending']
        now = self.clock()
        require(positive(now) and now < d['expires'] and d['state'] == 'setup' and op is not None and op['kind'] == 'configuration' and
                op['created'] <= now < op['execution_deadline'] and
                d['policy']['authority_repository'] == self.auth_store.repository and
                d['policy']['authority_repository_id'] == self.auth_store.identity and
                d['policy']['workflow_sha'] == self.auth_store.workflow_sha,
                'initial consent requires the owned setup configuration')
        binding = dict(authority_repository=self.auth_store.repository, authority_repository_id=self.auth_store.identity,
            configuration_revision=current['configuration_revision'], deployment_digest=current['deployment_digest'],
            operation_id=op['operation_id'], sequence=current['fence']['sequence'])
        return current, binding

    def _load(self):
        current, binding = self._configuration()
        if self.journal is None: self.journal = private_setup.Store(self.journal_root)
        self.document = self.journal.read()
        if self.document is None:
            body = dict(schema_version=1, kind='model-setup', configuration=binding,
                host_id='urn:uuid:' + str(uuid.uuid4()), session_id=secrets.token_hex(16),
                keys=model_vault.generate_keys(), attempt=None, sealed_vault=None)
            self.document = self.journal.write(None, body)
        body = self.document['value']
        object_fields(body, BODY_FIELDS, 'private model setup')
        require(type(body['schema_version']) is int and body['schema_version'] == 1 and body['kind'] == 'model-setup' and
                body['configuration'] == binding and isinstance(body['host_id'], str) and
                re.fullmatch(r'urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}', body['host_id']) and
                isinstance(body['session_id'], str) and re.fullmatch('[0-9a-f]{32}', body['session_id']),
                'private model setup binding differs')
        object_fields(body['keys'], ('vault', 'delivery'), 'separate model setup keys')
        model_vault.validate_keys(body['keys']['vault'], body['keys']['delivery'])
        attempt = body['attempt']
        if attempt is not None:
            object_fields(attempt, ATTEMPT_FIELDS, 'private authorization attempt')
            require(attempt['phase'] in ('awaiting', 'exchange-started', 'sealed', 'installed', 'denied') and
                    isinstance(attempt['attempt_id'], str) and re.fullmatch('[0-9a-f]{32}', attempt['attempt_id']) and
                    all(isinstance(attempt[k], str) and re.fullmatch('[A-Za-z0-9_-]{43}', attempt[k])
                        for k in ('state', 'nonce', 'verifier')) and
                    model_vault._identifier(attempt['requested_client_id']) and
                    (attempt['received_issued_client_id'] is None or
                     model_vault._identifier(attempt['received_issued_client_id']) and
                     attempt['received_issued_client_id'] != 'dynamic_agent_client') and
                    (attempt['exchange_started'] is None or positive(attempt['exchange_started'])),
                    'private authorization attempt differs')
            callback_uri(attempt['redirect_uri'])
        require((body['sealed_vault'] is None) == (attempt is None or attempt['phase'] not in ('sealed', 'installed')),
                'sealed setup phase differs')
        if body['sealed_vault'] is not None: model_vault.validate_encrypted(body['sealed_vault'])
        return current, body

    def _save(self, body):
        self._configuration()
        self.document = self.journal.write(self.document, body)

    def _begin(self, redirect_uri):
        callback_uri(redirect_uri)
        current, body = self._load()
        require(body['sealed_vault'] is None, 'recover the verified envelope before another sign-in')
        old = body['attempt']
        client = 'dynamic_agent_client'
        if old is not None:
            client = old['received_issued_client_id'] or old['requested_client_id']
        # Never resume a code exchange after restart, even if old phase visibility
        # is uncertain. The retained client is only an unverified registration hint.
        body = copy.deepcopy(body)
        self.pending = dict(attempt_id=secrets.token_hex(16), phase='awaiting', redirect_uri=redirect_uri,
            state=secrets.token_urlsafe(32), nonce=secrets.token_urlsafe(32), verifier=secrets.token_urlsafe(32),
            requested_client_id=client, received_issued_client_id=None, exchange_started=None)
        body['attempt'] = self.pending
        self._save(body)  # Host, keys and new private attempt are durable before the URL.
        self.consumed = False
        challenge = base64.urlsafe_b64encode(hashlib.sha256(self.pending['verifier'].encode()).digest()).rstrip(b'=').decode()
        query = dict(client_id=client, ext_agent_host_id=body['host_id'], response_type='code', redirect_uri=redirect_uri,
                     scope=' '.join(SCOPES), resource=RESOURCE, state=self.pending['state'], nonce=self.pending['nonce'],
                     code_challenge_method='S256', code_challenge=challenge)
        if client == 'dynamic_agent_client': query['agent_name_hint'] = 'AGENTIC'
        return ISSUER + '/api/accounts/authorize?' + urlencode(query)

    def _exchange(self, query):
        require(self.pending is not None and not self.consumed and self.pending['phase'] == 'awaiting',
                'fresh unconsumed authorization attempt required')
        require(isinstance(query, dict) and set(query) <= {'state', 'code', 'client_id', 'scope', 'error', 'error_description'} and
                isinstance(query.get('state'), str) and query['state'].isascii() and
                hmac.compare_digest(query['state'], self.pending['state']), 'authorization callback state differs')
        self.consumed = True
        body = copy.deepcopy(self.document['value'])
        if 'error' in query:
            body['attempt']['phase'] = 'denied'
            self._save(body)
            raise Refusal('model authorization denied; credentials were not installed')
        client = query.get('client_id', self.pending['requested_client_id'])
        require(model_vault._identifier(client) and client != 'dynamic_agent_client' and
                (self.pending['requested_client_id'] == 'dynamic_agent_client' or client == self.pending['requested_client_id']),
                'issued model client differs or registration is incomplete')
        code = query.get('code')
        require(isinstance(code, str) and 0 < len(code) <= 4096 and all(32 < ord(c) < 127 for c in code),
                'bounded model authorization code required')
        started = self.clock()
        body['attempt'].update(phase='exchange-started', received_issued_client_id=client, exchange_started=started)
        self._save(body)  # The code itself is never persisted.
        self._configuration()
        response = self.provider.token(dict(grant_type='authorization_code', client_id=client, code=code,
            code_verifier=self.pending['verifier'], redirect_uri=self.pending['redirect_uri'], resource=RESOURCE))
        current, binding = self._configuration()
        now = self.clock()
        require(isinstance(response, dict) and all(model_vault._token(response.get(k)) for k in
                ('access_token', 'refresh_token', 'id_token')) and isinstance(response.get('token_type'), str) and
                response['token_type'].lower() == 'bearer' and positive(response.get('expires_in')) and
                response['expires_in'] <= 86400 and started + response['expires_in'] - now >=
                current['deployment']['policy']['limits']['seconds'] + 60, 'complete usable model credentials required')
        raw_scope = response.get('scope')
        require(isinstance(raw_scope, str) and 0 < len(raw_scope) <= 4096 and raw_scope.isascii(),
                'explicit granted model scopes required')
        scopes = raw_scope.split(' ')
        require(all(scopes) and len(scopes) == len(set(scopes)) and set(scopes) <= set(SCOPES) and
                set((*model_vault.PLAN_SCOPES, 'offline_access')) <= set(scopes), 'model plan permission was not granted')
        verified = Verifier(self.provider).initial(response['id_token'], client, self.pending['nonce'], now)
        record = dict(schema_version=1, kind='model-refresh-vault', authority_repository_id=self.auth_store.identity,
            session_id=body['session_id'], generation=1, **verified, credentials=dict(access_token=response['access_token'],
            refresh_token=response['refresh_token'], id_token=response['id_token'], token_type='Bearer', issued=started,
            access_expires=started + response['expires_in'], scopes=sorted(scopes)))
        body['sealed_vault'] = model_vault.seal_record(record, body['keys']['vault'])
        body['attempt']['phase'] = 'sealed'
        self._save(body)  # Preserve this exact ciphertext for uncertain Git initialization.
        return self._install(body)

    def _install(self, body):
        self._configuration()
        sealed = body['sealed_vault']
        expected = {k: sealed[k] for k in model_vault.BINDING_FIELDS}
        require(expected['authority_repository_id'] == self.auth_store.identity and
                expected['session_id'] == body['session_id'] and expected['generation'] == 1,
                'sealed initial model identity differs')
        record = model_vault.open_record(sealed, body['keys']['vault'], expected)
        require(record['identity']['client_id'] == body['attempt']['received_issued_client_id'], 'verified setup client differs')
        stored = self.auth_store.initialize(sealed)
        require(stored['state']['vault'] == sealed and stored['state']['pending'] is None, 'model installation readback differs')
        body = copy.deepcopy(body)
        body['attempt']['phase'] = 'installed'
        self._save(body)
        return dict(resources=dict(model_auth='chatgpt-plan', model_host_id=body['host_id'], model_session=body['session_id'],
            model_account=digest(record['identity']), model_client=record['identity']['client_id']), auth_generation=1,
            enforcement_active=False, model_execution_qualified=False)

    def _read_callback(self, connection, host, remaining):
        raw = bytearray()
        while b'\r\n\r\n' not in raw:
            connection.settimeout(min(2, remaining()))
            chunk = connection.recv(4096)
            require(chunk, 'incomplete consent callback')
            raw.extend(chunk)
            require(len(raw) <= 16384, 'consent callback exceeds bounds')
        head, body = bytes(raw).split(b'\r\n\r\n', 1)
        require(not body, 'callback body is not admitted')
        try: lines = head.decode('ascii').split('\r\n')
        except UnicodeError: raise Refusal('ASCII consent callback required') from None
        parts = lines.pop(0).split(' ')
        require(len(parts) == 3 and parts[0] == 'GET' and parts[2] == 'HTTP/1.1' and len(parts[1]) <= 4096,
                'bounded GET callback required')
        headers = {}
        for line in lines:
            key, separator, value = line.partition(':')
            require(separator and re.fullmatch('[A-Za-z0-9-]+', key) and key.lower() not in headers and
                    all(32 <= ord(c) < 127 for c in value), 'unambiguous callback headers required')
            headers[key.lower()] = value.strip()
        require(headers.get('host') == host and headers.get('origin') in (None, ISSUER) and
                not set(headers) & {'transfer-encoding', 'expect', 'upgrade'} and
                headers.get('content-length', '0') == '0', 'unexpected callback origin or framing')
        uri = urlsplit(parts[1])
        require(not uri.scheme and not uri.netloc and uri.path == '/auth/callback' and not uri.fragment,
                'unexpected consent callback route')
        try: query = parse_qs(uri.query, keep_blank_values=True, strict_parsing=True, max_num_fields=6)
        except ValueError: raise Refusal('invalid consent callback parameters') from None
        require(all(len(value) == 1 for value in query.values()), 'duplicate authorization callback parameter')
        return {key: value[0] for key, value in query.items()}

    def _run(self, seconds=300):
        require(type(seconds) is int and 0 < seconds <= 300, 'bounded browser consent interval required')
        current, body = self._load()
        if body['sealed_vault'] is not None: return self._install(body)
        deadline = time.monotonic() + seconds
        def remaining():
            value = deadline - time.monotonic()
            require(value > 0, 'model consent expired; start a fresh authorization')
            return value
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen(1)
            listener.settimeout(.2)
            host = '127.0.0.1:' + str(listener.getsockname()[1])
            url = self._begin('http://' + host + '/auth/callback')
            require(self.browser(url) is True, 'trusted browser could not start model consent')
            for _ in range(32):
                while True:
                    remaining()
                    try: connection, peer = listener.accept(); break
                    except socket.timeout: continue
                with connection:
                    result = None
                    try:
                        require(peer[0] == '127.0.0.1', 'loopback callback peer required')
                        query = self._read_callback(connection, host, remaining)
                        result = self._exchange(query)
                    except Exception:
                        payload, status = b'Authorization callback refused.', b'400 Bad Request'
                    else:
                        payload, status = b'Authorization received. Return to AGENTIC.', b'200 OK'
                    try:
                        connection.sendall(b'HTTP/1.1 ' + status + b'\r\nConnection: close\r\nCache-Control: no-store\r\n'
                            b'Referrer-Policy: no-referrer\r\nContent-Security-Policy: default-src \'none\'\r\n'
                            b'Content-Type: text/plain\r\nContent-Length: ' + str(len(payload)).encode() + b'\r\n\r\n' + payload)
                    except OSError: pass
                    if result is not None: return result
                    require(not self.consumed, 'model authorization incomplete; preserve setup state and start fresh')
            raise Refusal('too many invalid consent callbacks; start fresh')
