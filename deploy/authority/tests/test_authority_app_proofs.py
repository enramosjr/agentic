"""Each purpose proves only its own App capability in a candidate-free context."""
import backend_test_support
import copy
import json
import unittest

from test_authority_protocol import deployment
from trusted_ci_policy import Refusal, digest
from trusted_ci_github import HostRefusal
from bootstrap import PERMISSIONS
import app_proofs


def identities(d):
    return {'schema_version': 2, 'owner_id': 7, 'apps': {purpose: {
        'id': identity, 'slug': 'agentic-' + purpose, 'installation_id': identity + 100,
        'actor_id': 18 if purpose == 'coding' else 19 if purpose == 'merge' else identity + 1000}
        for purpose, identity in d['apps'].items()}}


class AppAPI:
    def __init__(self, d, records, purpose):
        self.d, self.records, self.purpose = d, records, purpose
        self.record = records['apps'][purpose]
        self.permissions = dict(PERMISSIONS[purpose], metadata='read')
        self.visible = {}
        self.revoked = []
        self.authority_installed = False
        self.unexpected_mint = False
        self.generic_denial = False
    def get(self, path):
        if path == '/app':
            return dict(id=self.record['id'], slug=self.record['slug'], owner={'id': 7}, permissions=self.permissions)
        if path == '/repos/owner/authority/installation' and self.purpose in ('coding', 'issuer', 'merge') and not self.authority_installed:
            raise HostRefusal(404)
        return dict(id=self.record['installation_id'], app_id=self.record['id'], account={'id': 7},
                    permissions=self.permissions, suspended_at=None, repository_selection='selected')
    def post(self, path, body):
        forbidden_repo = body['repository_ids'] == [456] and self.purpose in ('coding', 'merge')
        forbidden_permission = any(self.permissions.get(k) != 'write' and v == 'write' for k, v in body['permissions'].items())
        if (forbidden_repo or forbidden_permission) and not self.unexpected_mint:
            raise HostRefusal(422, 'unknown' if self.generic_denial else 'repository_scope' if forbidden_repo else 'permission_scope')
        token = 'SYNTHETIC-TOKEN-' + str(len(self.visible))
        self.visible[token] = body['repository_ids']
        return {'token': token, 'permissions': dict(body['permissions'], metadata='read'),
                'repositories': [{'id': r} for r in body['repository_ids']]}
    def token_api(self, token):
        parent = self
        class Scoped:
            def pages(self, path, collection):
                return [{'id': r} for r in parent.visible[token]]
            def get(self, path):
                return {'id': parent.record['actor_id'], 'type': 'Bot'}
            def fetch(self, path, method='GET', **kwargs):
                if path == '/installation/token' and method == 'DELETE':
                    parent.revoked.append(token)
                    return b''
                raise AssertionError(path)
        return Scoped()


class AuthorityReader:
    def get(self, path):
        return {'id': 456, 'private': True, 'owner': {'id': 7}}


class AppProofContracts(unittest.TestCase):
    def test_public_identities_are_loaded_only_from_pinned_deployment(self):
        for adapter, account in [('github-actions', 'owner'), ('aws', '123456789012'),
                                 ('azure', '12345678-1234-1234-1234-123456789abc')]:
            d, records, _ = self.prepared('reader')
            d.update(adapter=adapter, account=account)
            d['resources']['identity_record'] = json.dumps(records, sort_keys=True, separators=(',', ':'))
            with self.subTest(adapter=adapter):
                self.assertEqual(app_proofs.load_identities(d), records)
                for key, value in [('identity_digest', 'f' * 64), ('identity_record', '{}'),
                                   ('identity_record', d['resources']['identity_record'][:-1] + ',"apps":{}}')]:
                    bad = copy.deepcopy(d)
                    bad['resources'][key] = value
                    with self.assertRaises(Refusal): app_proofs.load_identities(bad)
                del d['resources']['identity_record']
                with self.assertRaises(Refusal): app_proofs.load_identities(d)

    def prepared(self, purpose):
        d = deployment()
        d['policy']['merge_actors'] = [19]
        records = identities(d)
        d['resources']['identity_digest'] = digest(records)
        return d, records, AppAPI(d, records, purpose)

    def test_merge_is_source_only_and_cannot_reuse_an_independent_human(self):
        d, records, api = self.prepared('merge')
        self.assertEqual(PERMISSIONS['merge'], {'contents': 'write', 'pull_requests': 'read'})
        proof = app_proofs.prove(api, AuthorityReader(), d, records, 'merge',
                                'b' * 40, 1000, token_factory=api.token_api)
        self.assertEqual(proof['repository_ids'], [123])
        self.assertIn('repository:authority', proof['denials'])
        d['policy']['merge_actors'] = d['policy']['reviewers']
        with self.assertRaises(Refusal):
            app_proofs.identity_record(d, records)

    def test_each_domain_has_exact_scope_no_secret_and_revokes_probe_tokens(self):
        for purpose in PERMISSIONS:
            with self.subTest(purpose=purpose):
                d, records, api = self.prepared(purpose)
                proof = app_proofs.prove(api, AuthorityReader(), d, records, purpose,
                                        'b' * 40, 1000, token_factory=api.token_api)
                self.assertEqual(proof['purpose'], purpose)
                self.assertEqual(len(api.visible), len(api.revoked))
                self.assertNotIn('SYNTHETIC-TOKEN', json.dumps(proof))
                self.assertFalse(proof['isolation_established'])
                app_proofs.validate(proof, d, records, purpose, 'b' * 40, 1001)

    def test_broad_registration_generic_denial_and_authority_access_fail(self):
        for defect in ('registration', 'generic_denial', 'authority_installed'):
            d, records, api = self.prepared('coding')
            if defect == 'registration':
                api.permissions['administration'] = 'write'
            else:
                setattr(api, defect, True)
            with self.subTest(defect=defect), self.assertRaises(Refusal):
                app_proofs.prove(api, AuthorityReader(), d, records, 'coding', 'b' * 40, 1000,
                                 token_factory=api.token_api)

    def test_unexpected_escalation_token_is_revoked_before_refusal(self):
        d, records, api = self.prepared('coding')
        api.unexpected_mint = True
        with self.assertRaises(Refusal):
            app_proofs.prove(api, AuthorityReader(), d, records, 'coding', 'b' * 40, 1000,
                             token_factory=api.token_api)
        self.assertEqual(len(api.visible), len(api.revoked))

    def test_stale_or_substituted_identity_and_local_separation_claim_are_rejected(self):
        d, records, api = self.prepared('coding')
        proof = app_proofs.prove(api, AuthorityReader(), d, records, 'coding', 'b' * 40, 1000,
                                 token_factory=api.token_api)
        for field, value in [('app_id', 18), ('installation_id', d['apps']['coding']),
                             ('registry_revision', 'c' * 40), ('isolation_established', True), ('expires', 1000)]:
            forged = copy.deepcopy(proof)
            forged[field] = value
            with self.subTest(field=field), self.assertRaises(Refusal):
                app_proofs.validate(forged, d, records, 'coding', 'b' * 40, 1001)


if __name__ == '__main__':
    unittest.main()
