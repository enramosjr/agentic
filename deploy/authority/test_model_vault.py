"""Real encryption with synthetic credentials; no OAuth/model/network calls."""
import copy
import json
from pathlib import Path
import sys
import unittest

from cryptography.fernet import Fernet

sys.path[:0] = [str(Path(__file__).resolve().parents[2] / '.ai/scripts'),
               str(Path(__file__).resolve().parents[2] / '.ai/scripts/tests')]
from test_authority_protocol import deployment
from trusted_ci_policy import Refusal, digest
import model_vault


def fixture():
    record = dict(schema_version=1, kind='model-refresh-vault', authority_repository_id=456,
        session_id='a' * 32, generation=1,
        identity=dict(issuer='https://auth.openai.com', subject='synthetic-verified-subject', client_id='oaiapp_synthetic'),
        authorization=dict(nonce='SYNTHETIC-VERIFIED-NONCE-0123456789', initial_id_issued=1000,
            audiences=['oaiapp_synthetic'], auth_time=900, authorized_party=None),
        credentials=dict(access_token='SYNTHETIC-ACCESS-ONLY', refresh_token='SYNTHETIC-REFRESH-ROOT',
            id_token='SYNTHETIC-ID-TOKEN', token_type='Bearer', issued=1000, access_expires=2000,
            scopes=['chatgpt.tokens.use.direct', 'offline_access', 'resource.invoke']))
    d = deployment()
    d.update(state='active', qualification='f' * 64)
    d['resources'].update(model_auth='chatgpt-plan', model_id='approved-fixture-model',
        codex_sha='c' * 64, codex_version='0.1.0', coding_image='coding@sha256:' + 'd' * 64,
        model_session=record['session_id'], model_account=digest(record['identity']),
        model_client=record['identity']['client_id'])
    binding = dict(deployment=d, deployment_digest=digest(d), configuration_revision='b' * 40)
    task = dict(task_id='c' * 32, run_id=99, attempt=1, deadline=1800, purpose='task')
    return record, binding, task


class ModelVaultContracts(unittest.TestCase):
    def test_verified_authorization_context_stays_in_vault_not_access_delivery(self):
        record, b, task = fixture()
        vault_key, delivery_key = Fernet.generate_key(), Fernet.generate_key()
        sealed = model_vault.seal_record(record, vault_key)
        expected = {k: sealed[k] for k in model_vault.BINDING_FIELDS}
        self.assertEqual(model_vault.open_record(sealed, vault_key, expected)['authorization'], record['authorization'])
        lease = model_vault.issue_lease(record, delivery_key, b, task, 1100)
        value = model_vault.open_lease(lease, delivery_key, b, task, 1101)
        self.assertNotIn('authorization', value)
        self.assertNotIn('nonce', value)

    def test_boolean_generation_alias_is_not_an_authenticated_integer_binding(self):
        record, b, task = fixture()
        key = Fernet.generate_key()
        sealed = model_vault.seal_record(record, key)
        expected = {k: sealed[k] for k in model_vault.BINDING_FIELDS}
        with self.assertRaises(Refusal):
            model_vault.open_record(dict(sealed, generation=True), key, expected)
        with self.assertRaises(Refusal):
            model_vault.open_record(sealed, key, dict(expected, generation=True))

    def test_generated_keys_are_distinct_and_shared_keys_are_refused(self):
        keys = model_vault.generate_keys()
        self.assertNotEqual(keys['vault'], keys['delivery'])
        model_vault.validate_keys(keys['vault'], keys['delivery'])
        with self.assertRaises(Refusal): model_vault.validate_keys(keys['vault'], keys['vault'])
        with self.assertRaises(Refusal): model_vault.validate_keys(keys['vault'].encode(), keys['vault'])

    def test_vault_round_trip_uses_authenticated_encryption_and_distinct_delivery_key(self):
        record, b, task = fixture()
        vault_key, delivery_key = Fernet.generate_key(), Fernet.generate_key()
        sealed = model_vault.seal_record(record, vault_key)
        expected = {k: sealed[k] for k in model_vault.BINDING_FIELDS}
        self.assertEqual(model_vault.open_record(sealed, vault_key, expected), record)
        text = json.dumps(sealed)
        for value in record['credentials'].values():
            if isinstance(value, str): self.assertNotIn(value, text)
        with self.assertRaises(Refusal): model_vault.open_record(sealed, delivery_key, expected)

    def test_vault_metadata_ciphertext_and_expected_generation_cannot_be_substituted(self):
        record, b, task = fixture()
        key = Fernet.generate_key()
        sealed = model_vault.seal_record(record, key)
        expected = {k: sealed[k] for k in model_vault.BINDING_FIELDS}
        for field, bad in [('session_id', 'b' * 32), ('generation', 2), ('identity_digest', '0' * 64),
                           ('ciphertext', sealed['ciphertext'][:-2] + 'AA')]:
            with self.subTest(field=field), self.assertRaises(Refusal):
                model_vault.open_record(dict(sealed, **{field: bad}), key, expected)
        with self.assertRaises(Refusal):
            model_vault.open_record(sealed, key, dict(expected, generation=2))

    def test_task_delivery_contains_only_access_credentials_and_exact_binding(self):
        record, b, task = fixture()
        delivery_key = Fernet.generate_key()
        sealed = model_vault.issue_lease(record, delivery_key, b, task, 1100)
        value = model_vault.open_lease(sealed, delivery_key, b, task, 1101)
        self.assertEqual(value['access_token'], record['credentials']['access_token'])
        self.assertEqual(value['expires'], task['deadline'])
        self.assertEqual(value['model_id'], b['deployment']['resources']['model_id'])
        self.assertNotIn('refresh_token', value)
        self.assertNotIn('id_token', value)
        self.assertNotIn(record['credentials']['access_token'], sealed)

    def test_task_model_identity_revision_attempt_and_expiry_substitution_refuse(self):
        record, b, task = fixture()
        key = Fernet.generate_key()
        sealed = model_vault.issue_lease(record, key, b, task, 1100)
        for field, bad in [('task_id', 'd' * 32), ('run_id', 100), ('attempt', 2)]:
            with self.subTest(field=field), self.assertRaises(Refusal):
                model_vault.open_lease(sealed, key, b, dict(task, **{field: bad}), 1101)
        for field, bad in [('configuration_revision', 'd' * 40), ('deployment_digest', '0' * 64)]:
            with self.subTest(field=field), self.assertRaises(Refusal):
                model_vault.open_lease(sealed, key, dict(b, **{field: bad}), task, 1101)
        for clock in (1099, 1800, 5000):
            with self.subTest(clock=clock), self.assertRaises(Refusal):
                model_vault.open_lease(sealed, key, b, task, clock)

    def test_insufficient_access_lifetime_or_missing_plan_scope_has_no_billing_fallback(self):
        record, b, task = fixture()
        key = Fernet.generate_key()
        record['credentials']['access_expires'] = 1200
        with self.assertRaises(Refusal): model_vault.issue_lease(record, key, b, task, 1100)
        record['credentials']['access_expires'] = 2000
        record['credentials']['scopes'].remove('chatgpt.tokens.use.direct')
        with self.assertRaises(Refusal): model_vault.issue_lease(record, key, b, task, 1100)

    def test_even_authenticated_delivery_rejects_root_fields(self):
        record, b, task = fixture()
        key = Fernet.generate_key()
        sealed = model_vault.issue_lease(record, key, b, task, 1100)
        value = model_vault.open_lease(sealed, key, b, task, 1101)
        value['refresh_token'] = 'SYNTHETIC-ROOT-MUST-NOT-ENTER-TASK'
        forged = Fernet(key).encrypt_at_time(json.dumps(value).encode(), 1100).decode()
        with self.assertRaises(Refusal): model_vault.open_lease(forged, key, b, task, 1101)


if __name__ == '__main__':
    unittest.main()
