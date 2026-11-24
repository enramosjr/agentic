"""Encrypted opaque-state CAS only; real cryptography is tested separately."""
import backend_test_support
import copy
import unittest

from test_authority_registry import RegistryHost
from trusted_ci_policy import Refusal
import model_auth_store


class AuthHost(RegistryHost):
    def __init__(self):
        super().__init__()
        self.visible = [456]
    def pages(self, path, collection):
        if path == '/installation/repositories': return [{'id': v} for v in self.visible]
        raise AssertionError(path)


class InitialSession:
    def __init__(self): self.calls = []
    def require_effect(self, action, target):
        if (action, target) != ('credentials', 'owner/authority:model-vault'):
            raise Refusal('unexpected credential scope')
        self.calls.append((action, target))


def sealed(generation=1):
    return dict(schema_version=1, kind='encrypted-model-vault', authority_repository_id=456,
        session_id='a' * 32, generation=generation, identity_digest='b' * 64,
        ciphertext='SYNTHETIC-OPAQUE-CIPHERTEXT-GENERATION-' + str(generation))


def store(api, session=None, owner=True):
    return model_auth_store.AuthStore(api, 'owner/authority', 456, 'a' * 40, session=session,
        admitted_owner=dict(workflow_sha='a' * 40, run_id=99, attempt=1) if owner else None)


class AuthStoreContracts(unittest.TestCase):
    def prepared(self):
        api, session = AuthHost(), InitialSession()
        value = store(api, session)
        value.initialize(sealed())
        api.writes.clear()
        return api, value, session

    def test_initialization_needs_configuration_scope_and_preserves_default_software(self):
        api = AuthHost()
        with self.assertRaises(Refusal): store(api).initialize(sealed())
        self.assertEqual(api.writes, [])
        api, value, session = self.prepared()
        result = value.read()
        self.assertEqual(result['state']['vault'], sealed())
        self.assertIsNone(result['state']['pending'])
        self.assertEqual(api.refs['main'], 'a' * 40)
        self.assertTrue(session.calls)

    def test_claim_then_complete_rotates_once_with_owned_pending_intent(self):
        api, value, _ = self.prepared()
        before = value.read()
        claimed = value.claim(before, 'c' * 32, 1000)
        self.assertEqual(claimed['state']['vault'], sealed())
        self.assertEqual(claimed['state']['pending']['expected_generation'], 1)
        completed = value.complete(claimed, claimed['state']['pending'], sealed(2))
        self.assertEqual(completed['state']['vault'], sealed(2))
        self.assertIsNone(completed['state']['pending'])
        self.assertEqual(api.refs['main'], 'a' * 40)

    def test_concurrent_claim_owner_and_software_drift_refuse_before_pointer_update(self):
        for defect in ('stale', 'owner', 'scope', 'software'):
            api, value, _ = self.prepared()
            before = value.read()
            if defect == 'stale': value.claim(before, 'd' * 32, 1000)
            if defect == 'owner': value = store(api, owner=False)
            if defect == 'scope': api.visible = [456, 123]
            if defect == 'software': api.refs['main'] = 'b' * 40
            writes = len(api.writes)
            with self.subTest(defect=defect), self.assertRaises(Refusal): value.claim(before, 'c' * 32, 1000)
            self.assertEqual(len(api.writes), writes)

    def test_pending_intent_never_expires_or_allows_a_second_refresh(self):
        api, value, _ = self.prepared()
        claimed = value.claim(value.read(), 'c' * 32, 1000)
        before = len(api.writes)
        with self.assertRaises(Refusal): value.claim(claimed, 'd' * 32, 1000000000)
        with self.assertRaises(Refusal): value.complete(claimed, dict(claimed['state']['pending'], attempt=2), sealed(2))
        self.assertEqual(len(api.writes), before)
        self.assertIsNotNone(value.read()['state']['pending'])

    def test_lost_pointer_ack_is_recovered_only_by_exact_written_commit(self):
        api, value, _ = self.prepared()
        api.lose_ack = True
        claimed = value.claim(value.read(), 'c' * 32, 1000)
        self.assertEqual(claimed['state']['pending']['operation_id'], 'c' * 32)
        api.lose_ack = True
        completed = value.complete(claimed, claimed['state']['pending'], sealed(2))
        self.assertEqual(completed['state']['vault']['generation'], 2)
        self.assertIsNone(completed['state']['pending'])

    def test_rotation_cannot_switch_identity_session_or_skip_generations(self):
        for field, bad in [('session_id', 'b' * 32), ('identity_digest', 'c' * 64), ('generation', 3)]:
            api, value, _ = self.prepared()
            claimed = value.claim(value.read(), 'c' * 32, 1000)
            replacement = dict(sealed(2), **{field: bad})
            writes = len(api.writes)
            with self.subTest(field=field), self.assertRaises(Refusal):
                value.complete(claimed, claimed['state']['pending'], replacement)
            self.assertEqual(len(api.writes), writes)


if __name__ == '__main__':
    unittest.main()
