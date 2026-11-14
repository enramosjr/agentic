"""Dedicated auth-job rotation. A durable intent precedes exactly one grant.

Public execution remains release-held. Internal fixture entry points do not
qualify a deployment, launch a worker, or establish model entitlement.
"""
import copy
import json
import secrets
import time

import authority_release
import model_vault
from model_oidc import Verifier
from oauth_transport import OpenAI
from provenance import admit_job
from trusted_ci_policy import positive, require


class Controller:
    def __init__(self, registry, reader, store, environment, vault_key, delivery_key,
                 provider=None, clock=None):
        self.registry, self.reader, self.store = registry, reader, store
        self.environment = dict(environment)
        self._vault_key, self._delivery_key = vault_key, delivery_key
        self.provider = provider or OpenAI()
        self.clock = clock or (lambda: int(time.time()))

    def run(self, task):
        authority_release.authorize('protected-run')
        return self._lease(task)

    def produce(self, task, uploader):
        authority_release.authorize('protected-run')
        return self._produce(task, uploader)

    def _produce(self, task, uploader):
        before = self.registry.binding()
        document = self._lease(task)
        require(self.registry.binding() == before and callable(uploader), 'model delivery configuration changed')
        job = admit_job(self.reader, before['deployment'], self.environment, 'model authorization', self.clock())
        artifact = uploader('model-lease-' + task['task_id'] + '-' + str(task['attempt']),
                            json.dumps(document, sort_keys=True, allow_nan=False).encode())
        require(positive(artifact), 'encrypted model delivery upload acknowledgement unavailable')
        return dict(run_id=task['run_id'], attempt=task['attempt'], job_id=job['id'], artifact_id=artifact)

    def _refresh(self, record, response, started, now):
        require(isinstance(response, dict), 'bounded OAuth token response required')
        require(all(model_vault._token(response.get(k)) for k in ('access_token', 'refresh_token')) and
                isinstance(response.get('token_type'), str) and response['token_type'].lower() == 'bearer' and
                positive(response.get('expires_in')) and response['expires_in'] <= 86400,
                'complete rotated Bearer credentials required')
        updated = copy.deepcopy(record)
        credentials = updated['credentials']
        scopes = credentials['scopes']
        if 'scope' in response:
            raw = response['scope']
            require(isinstance(raw, str) and 0 < len(raw) <= 4096 and raw.isascii() and
                    all(32 <= ord(c) < 127 for c in raw), 'bounded OAuth scope response required')
            scopes = raw.split(' ')
            require(all(scopes) and len(scopes) == len(set(scopes)) and
                    set(scopes) <= set(credentials['scopes']) and
                    set((*model_vault.PLAN_SCOPES, 'offline_access')) <= set(scopes),
                    'refresh changed approved model permissions')
            scopes = sorted(scopes)
        if 'id_token' in response:
            verified = Verifier(self.provider).refresh(response['id_token'], record, now, started)
            updated.update(verified)
            credentials['id_token'] = response['id_token']
        credentials.update(access_token=response['access_token'], refresh_token=response['refresh_token'],
                           token_type='Bearer', issued=started, access_expires=started + response['expires_in'],
                           scopes=scopes)
        updated['generation'] += 1
        return model_vault.validate_record(updated)

    def _lease(self, task):
        binding = self.registry.binding()
        d, resources = model_vault._binding(binding, task)
        now = self.clock()
        require(positive(now) and min(task['deadline'], d['expires']) - now >= d['policy']['limits']['seconds'] + 60,
                'complete task window required before model authorization')
        admit_job(self.reader, d, self.environment, 'model authorization', now)
        owner = dict(workflow_sha=d['policy']['workflow_sha'], run_id=task['run_id'], attempt=task['attempt'])
        require(self.environment['GITHUB_RUN_ID'] == str(task['run_id']) and
                self.environment['GITHUB_RUN_ATTEMPT'] == str(task['attempt']) and self.store.owner == owner and
                self.store.identity == d['policy']['authority_repository_id'] and
                self.store.repository == d['policy']['authority_repository'], 'dedicated auth owner differs')
        model_vault.validate_keys(self._vault_key, self._delivery_key)
        current = self.store.read()
        state = current['state']
        require(state is not None and state['pending'] is None,
                'model authorization is missing or remains pending; do not repeat a grant')
        expected = dict(authority_repository_id=self.store.identity, session_id=resources['model_session'],
                        generation=state['vault']['generation'], identity_digest=resources['model_account'])
        record = model_vault.open_record(state['vault'], self._vault_key, expected)
        require(record['identity']['client_id'] == resources['model_client'] and record['credentials']['issued'] <= now,
                'configured issued model client differs')
        if record['credentials']['access_expires'] - now < d['policy']['limits']['seconds'] + 60:
            claimed = self.store.claim(current, secrets.token_hex(16), now)
            # Any unknown/invalid response deliberately leaves the durable intent.
            response = self.provider.refresh(record)
            record = self._refresh(record, response, now, self.clock())
            replacement = model_vault.seal_record(record, self._vault_key)
            self.store.complete(claimed, claimed['state']['pending'], replacement)
        require(self.registry.binding() == binding, 'deployment changed during model authorization')
        now = self.clock()
        ciphertext = model_vault.issue_lease(record, self._delivery_key, binding, task, now)
        return dict(ciphertext=ciphertext, model_execution_qualified=False)
