"""Local setup contracts. These tests do not claim hosted enforcement qualification."""
import backend_test_support  # Establish the explicit source-only test paths.
import json
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import trusted_ci_fixtures
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'deploy' / 'authority'))
import bootstrap_stage as setup
from trusted_ci_policy import Refusal, digest


class BootstrapStageContracts(unittest.TestCase):
    def test_probe_tokens_are_revoked_after_success_failure_and_unexpected_admin_mint(self):
        from trusted_ci_github import HostRefusal
        for mode in ('success', 'read_failure', 'forbidden_admin'):
            case = self
            revoked = []
            app = {'id': 42, 'pem': 'PRIVATE', 'permissions': setup.PERMISSIONS['issuer']}
            class Api:
                def get(self, path):
                    return {'id': 42, 'permissions': app['permissions']}
                def post(self, path, body):
                    if mode == 'forbidden_admin':
                        return {'token': 'unexpected-admin'}
                    raise HostRefusal(422, 'permission_scope')
            class Scoped:
                def __init__(self, token):
                    self.token = token
                def pages(self, path, collection):
                    if mode == 'read_failure':
                        raise OSError('synthetic read failure')
                    return [{'id': 123}]
                def fetch(self, path, **kwargs):
                    case.assertEqual(path, '/installation/token')
                    case.assertEqual(kwargs, {'method': 'DELETE', 'binary': True})
                    revoked.append(self.token)
                    return b''
            with patch.object(setup, 'await_installation', return_value=17), \
                 patch.object(setup, 'app_api', return_value=Api()), \
                 patch.object(setup, 'installation_token', return_value='scoped'), \
                 patch('trusted_ci_github.GitHub', side_effect=Scoped), self.subTest(mode=mode):
                if mode == 'success':
                    self.assertEqual(setup.install_and_verify(app, 7, 123), 17)
                else:
                    with self.assertRaises(OSError if mode == 'read_failure' else Refusal):
                        setup.install_and_verify(app, 7, 123)
            self.assertEqual(sorted(revoked), sorted(['scoped', 'unexpected-admin'] if mode == 'forbidden_admin' else ['scoped']))

    def test_coding_authority_grant_is_rejected_and_unexpected_token_revoked(self):
        from trusted_ci_github import HostRefusal
        app = {'id': 44, 'pem': 'PRIVATE', 'permissions': setup.PERMISSIONS['coding']}
        revoked = []
        class Api:
            def get(self, path):
                return {'id': 44, 'permissions': app['permissions']}
            def post(self, path, body):
                if 'administration' in body['permissions']:
                    raise HostRefusal(422, 'permission_scope')
                return {'token': 'unexpected-authority-write'}
        class Reader:
            def pages(self, path, collection):
                return [{'id': 789}]
            def fetch(self, path, **kwargs):
                revoked.append((path, kwargs))
                return b''
        with patch.object(setup, 'await_installation', return_value=17), \
             patch.object(setup, 'app_api', return_value=Api()), \
             patch.object(setup, 'installation_token', return_value='fixture-scoped'), \
             patch('trusted_ci_github.GitHub', return_value=Reader()):
            with self.assertRaisesRegex(Refusal, 'grants authority write'):
                setup.install_and_verify(app, 7, 789, 456)
        self.assertEqual(revoked, [('/installation/token', {'method': 'DELETE', 'binary': True})] * 2)

    def test_authority_access_negative_control_detects_a_disabled_probe(self):
        original = setup.install_and_verify
        def broken(app, account, repository, forbidden=None):
            return original(app, account, repository)
        suite = unittest.TestSuite([BootstrapStageContracts(
            'test_coding_authority_grant_is_rejected_and_unexpected_token_revoked')])
        with patch.object(setup, 'install_and_verify', side_effect=broken):
            result = unittest.TextTestRunner(stream=io.StringIO()).run(suite)
        self.assertEqual(len(result.failures), 1)
        self.assertEqual(len(result.errors), 0)
        self.assertIn('Refusal not raised', result.failures[0][1])

    def test_generic_422_cannot_establish_permission_denial(self):
        from trusted_ci_github import HostRefusal
        app = {'id': 42, 'pem': 'PRIVATE', 'permissions': setup.PERMISSIONS['issuer']}
        class Api:
            def get(self, path):
                return {'id': 42, 'permissions': app['permissions']}
            def post(self, path, body):
                raise HostRefusal(422)
        class Reader:
            def pages(self, path, collection):
                return [{'id': 456}]
            def fetch(self, path, **kwargs):
                return b''
        with patch.object(setup, 'await_installation', return_value=17), \
             patch.object(setup, 'app_api', return_value=Api()), \
             patch.object(setup, 'installation_token', return_value='scoped'), \
             patch('trusted_ci_github.GitHub', return_value=Reader()), self.assertRaises(Refusal):
            setup.install_and_verify(app, 7, 456)

    def test_specific_scope_denials_are_not_generic_validation(self):
        from trusted_ci_github import denial_category
        for message, expected in [
            ('The permissions requested are not granted to this installation.', 'permission_scope'),
            ('There is at least one repository that does not exist or is not accessible to the parent installation.', 'repository_scope'),
            ('Validation Failed', 'unknown'), ('spam detected', 'unknown')]:
            self.assertEqual(denial_category(422, json.dumps({'message': message})), expected)

    def test_installation_accepts_only_implicit_metadata_read(self):
        from trusted_ci_github import HostRefusal
        permissions = dict(setup.PERMISSIONS['issuer'], metadata='read')
        app = {'id': 42, 'pem': 'PRIVATE', 'permissions': permissions}
        class Api:
            def get(self, path):
                return {'id': 42, 'permissions': permissions}
            def post(self, path, body):
                raise HostRefusal(422, 'permission_scope')
        class Reader:
            def pages(self, path, collection):
                return [{'id': 456}]
            def fetch(self, path, **kwargs):
                return b''
        with patch.object(setup, 'await_installation', return_value=17), \
             patch.object(setup, 'app_api', return_value=Api()), \
             patch.object(setup, 'installation_token', return_value='scoped'), \
             patch('trusted_ci_github.GitHub', return_value=Reader()):
            self.assertEqual(setup.install_and_verify(app, 7, 456), 17)

    def test_preview_has_no_secret_and_no_cloud_dependency(self):
        class Gh:
            def api(self, path, method='GET', body=None):
                self.last = (path, method, body)
                return {'id': 7, 'login': 'owner'}
        gh = Gh()
        p = setup.preview(gh, 'owner/authority')
        self.assertEqual(p['repository'], 'owner/authority')
        self.assertEqual(p['account_id'], 7)
        self.assertEqual(set(p['apps']), {'admin', 'issuer', 'coding', 'reader', 'merge'})
        self.assertNotIn('pem', json.dumps(p))
        self.assertEqual(gh.last[1], 'GET')

    def test_no_resource_mutation_without_exact_preview_approval(self):
        class Gh:
            def api(self, path, method='GET', body=None):
                if method != 'GET':
                    raise AssertionError('unapproved mutation')
                return {'id': 7, 'login': 'owner'}
        with self.assertRaises(Refusal):
            setup.apply(Gh(), 'owner/authority', 'wrong', lambda *args: {})

    def test_setup_records_registration_without_claiming_enforcement(self):
        calls, keys = [], []
        class Gh:
            def api(self, path, method='GET', body=None):
                calls.append((path, method, body))
                if method == 'GET':
                    return {'id': 7, 'login': 'owner'}
                if path == '/user/repos':
                    return {'id': (456 if body['name'] == 'authority' else 789),
                            'full_name': 'owner/' + body['name'], 'private': True,
                            'owner': {'id': 7}}
                return {'content': {'sha': 'a' * 40}}

            def secret(self, repository, name, value):
                keys.append((repository, name, value))

        gh = Gh()
        counter = iter(range(41, 46))
        def register(purpose, gh, organization):
            return {'id': next(counter), 'pem': purpose + '-PRIVATE',
                    'slug': 'agentic-' + purpose, 'owner': {'id': 7}}
        p = setup.preview(gh, 'owner/authority')
        installed = []
        def installer(app, account, repository_id, forbidden_repository=None):
            installed.append((app['slug'], account, repository_id, forbidden_repository))
            return app['id'] + 100
        result = setup.apply(gh, 'owner/authority', digest(p), register, installer)
        self.assertEqual(result['state'], 'setup')
        self.assertFalse(result['enforcement_qualified'])
        self.assertEqual(len(keys), 5)
        self.assertEqual(len(installed), 5)
        self.assertIn(('agentic-merge', 7, 789, 456), installed)
        self.assertIn(('agentic-coding', 7, 789, 456), installed)
        self.assertIn(('agentic-issuer', 7, 789, None), installed)
        self.assertFalse(any(purpose == 'agentic-coding' and repo == 456
                             for purpose, account, repo, forbidden in installed))
        self.assertTrue(all(v['installation_id'] > 0 for v in result['apps'].values()))
        self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertTrue(any(method == 'PUT' and path.endswith('/contents/bootstrap.json')
                            for path, method, body in calls))


if __name__ == '__main__':
    unittest.main()
