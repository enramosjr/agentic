"""Native operator composition over existing setup and registration Git fixtures."""
import backend_test_support
import copy
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

import authority_release
import operator_setup
from test_authority_initial_setup import Host
from test_authority_registration import Gh as RegistrationGh
from test_authority_runtime_pins import Journal
from trusted_ci_policy import Refusal, digest
import dispatch_controls


class OperatorCompositionContracts(unittest.TestCase):
    def test_configuration_fence_controls_and_lost_registry_ack_recover_exact_progress(self):
        import registry as registry_module
        from test_authority_registry import RegistryHost, coordinates
        from test_authority_setup_owner import fixture as admitted_fixture
        from test_authority_reconcile import Host as SourceControls
        for mode in ('normal', 'configuration-ack', 'acquisition-ack'):
            lost = mode == 'configuration-ack'
            _, _, make, native, admin, preview, _, clock = admitted_fixture()
            d = copy.deepcopy(make().registry.read())
            d['resources']['bundle_sha'] = 'e' * 64
            records = make().identities
            host, source = RegistryHost(), SourceControls()
            host.lose_ack = mode == 'acquisition-ack'
            registry = registry_module.Registry(host, coordinates())
            journals = {}
            def store(path):
                key = str(path)
                if key not in journals:
                    journals[key] = Journal()
                    journals[key].root = Path(path)
                return journals[key]
            class API:
                def get(self, route):
                    if route == '/user': return dict(id=71, type='User')
                    if route == '/repos/owner/authority':
                        return dict(id=456, full_name='owner/authority', private=True, default_branch='main',
                                    owner=dict(id=7), permissions=dict(admin=True))
                    if route == '/repos/owner/project':
                        return dict(source.get(route), full_name='owner/project', owner=dict(id=7), permissions=dict(admin=True))
                    if '/git/' in route: return host.get(route)
                    return source.get(route)
                def pages(self, route, collection=None):
                    if route == '/repos/owner/authority/rulesets': return []
                    return source.pages(route, collection)
                def post(self, route, body): return source.post(route, body)
            api = API()
            controller = operator_setup.Operator(api, None, Path('/synthetic-native-config'), {}, lambda: clock[0], store_factory=store)
            controller.document = store(controller.root).write(None, dict(source='owner/project', authority='owner/authority'))
            store(controller.root / 'registration').write(None, dict(apps={p: dict(registration=dict(id=v['id'], pem='synthetic'))
                                                                          for p, v in records['apps'].items()}))
            connected = dict(repository='owner/project', authority_repository='owner/authority', authority_repository_id=456,
                software_revision='a' * 40, identities=records)
            def consumers(*args, **kwargs):
                if lost: host.lose_ack = True
                return dict(state='setup', credentials_verified=list(setup.CREDENTIAL_NAMES), enforcement_active=False,
                    hosted_qualified=False, model_resources=dict(model_auth='chatgpt-plan', model_host_id='fixture-host',
                    model_session='fixture-session', model_account='f' * 64, model_client='fixture-client'))
            import setup
            with self.subTest(mode=mode), patch.object(authority_release, 'authorize'), \
                 patch.object(controller, 'connect', return_value=connected), \
                 patch.object(operator_setup.bootstrap, 'app_api', return_value=admin), \
                 patch.object(operator_setup.bootstrap, 'installation_token', return_value='synthetic'), \
                 patch.object(operator_setup.bootstrap, 'revoke_token'), \
                 patch.object(operator_setup, 'GitHub', return_value=host), \
                 patch.object(operator_setup.Configuration, 'run', side_effect=consumers) as consumed, \
                 patch.object(dispatch_controls, 'preview', return_value={'kind': 'synthetic-dispatch-preview'}):
                interrupted = mode != 'normal'
                if interrupted:
                    with self.assertRaises(OSError): operator_setup.configure_operator(controller, 'e' * 64, digest, select=lambda *args: d)
                result = operator_setup.configure_operator(controller, 'e' * 64, digest, select=lambda *args: self.fail('selection replayed')) if interrupted else \
                         operator_setup.configure_operator(controller, 'e' * 64, digest, select=lambda *args: d)
                self.assertEqual(result['state'], 'qualification')
                self.assertFalse(result['enforcement_active'])
                self.assertEqual(registry.read()['state'], 'qualification')
                self.assertEqual(registry.read()['resources']['model_session'], 'fixture-session')
                self.assertIsNone(registry.binding()['fence']['pending'])
                self.assertEqual(consumed.call_count, 1)
                self.assertEqual(operator_setup.configure_operator(controller, 'e' * 64, digest), result)
                self.assertEqual(len(source.writes), 2)
                self.assertEqual(source.rules[0]['name'], 'Existing stronger control')
                current = registry.binding()
                registry._replace(current, {registry_module.OPERATION: current['fence']})
                with self.assertRaises(Refusal): operator_setup.configure_operator(controller, 'e' * 64, digest)
                self.assertEqual(len(source.writes), 2)

    def test_guided_policy_and_provider_selection_use_existing_validators(self):
        from types import SimpleNamespace
        from trusted_ci_policy import CHECKS, loads
        from test_authority_setup_owner import fixture
        _, _, make, _, _, _, _, _ = fixture()
        records = make().identities
        class API:
            def get(self, route):
                if route == '/users/reviewer': return dict(id=17, type='User')
                return dict(id=123, default_branch='main', permissions=dict(admin=True))
        operator = SimpleNamespace(api=API(), document=dict(value=dict(source_id=123)), clock=lambda: 1000)
        connected = dict(repository='owner/project', authority_repository='owner/authority', authority_repository_id=456,
                         software_revision='a' * 40, identities=records)
        for adapter, account in (('github-actions', 'owner'), ('aws', '123456789012'),
                                 ('azure', '12345678-1234-1234-1234-123456789012')):
            answers = iter(['reviewer', CHECKS[0], 'registry/verifier@sha256:' + '1' * 64,
                '60', '512', '64', '128', '3600', 'registry/coding@sha256:' + '2' * 64,
                '3' * 64, '1.2.3', 'selected-model', 'chatgpt-plan', adapter] +
                ([account, 'us-east-1' if adapter == 'aws' else 'eastus'] if adapter != 'github-actions' else []))
            with self.subTest(adapter=adapter):
                d = operator_setup.select_deployment(operator, connected, 'e' * 64, ask=lambda _: next(answers))
                self.assertEqual(d['adapter'], adapter)
                self.assertEqual(d['account'], account)
                self.assertEqual(d['state'], 'setup')
                self.assertIsNone(d['qualification'])
                if adapter != 'github-actions':
                    config = loads(d['resources']['cloud_configuration'])
                    self.assertEqual(config['account'], account)
                    self.assertEqual(config['authority'], 'owner/authority')

    def test_setup_progress_recovers_only_the_exact_conditional_registry_commit(self):
        from test_authority_setup_owner import fixture
        import registry as registry_module
        host, registry, make, operator, admin, preview, known, clock = fixture()
        before = registry.binding()
        updated = copy.deepcopy(before['deployment'])
        updated['generation'] += 1
        updated['resources']['acceptance_rule'] = '81'
        make().write_configuration(digest(before['deployment']), updated)
        self.assertEqual(registry.authenticate_setup_progress(before, {registry_module.DOCUMENT: updated}), registry.binding())
        commit = host.commits[registry.binding()['branch_head']]
        commit['message'] = 'foreign registry commit'
        with self.assertRaises(Refusal): registry.authenticate_setup_progress(before, {registry_module.DOCUMENT: updated})

    def test_native_dispatch_transport_accepts_empty_success_without_retry(self):
        from trusted_ci_github import GitHub
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b''
        response.__enter__.return_value.status = 204
        opener = MagicMock()
        opener.open.return_value = response
        self.assertIsNone(GitHub('synthetic', opener).post('/repos/owner/authority/actions/workflows/authority-v2.yml/dispatches',
                                                       dict(ref='main')))
        self.assertEqual(opener.open.call_count, 1)

    def fixture(self):
        host, registration = Host(), RegistrationGh()
        class Gh:
            def api(self, route, method='GET', body=None):
                if route == '/repos/owner/project': return registration.api(route)
                return host.get(route)
            def exchange(self, code): return registration.exchange(code)
        journals = {}
        def store(path):
            name = str(path)
            if name not in journals:
                journals[name] = Journal()
                journals[name].root = Path(path)
            return journals[name]
        def registrar(purpose, capture, organization): return capture.exchange(purpose)
        def installer(app, owner, repositories):
            self.assertEqual(repositories, [123, 456] if app['slug'].endswith(('admin', 'reader')) else [123])
            return dict(id=app['id'], slug=app['slug'], installation_id=app['id'] + 100, actor_id=app['id'] + 1000)
        gh = Gh()
        controller = operator_setup.Operator(host, gh, Path('/synthetic-owned-operator'),
            {'.ai/scripts/authority_release.py': b'SYNTHETIC FIXED RELEASE'}, lambda: 1000,
            store_factory=store, registrar=registrar, installer=installer)
        return controller, host, registration, journals

    def test_connect_installs_then_registers_and_returns_no_private_roots(self):
        controller, host, registration, journals = self.fixture()
        approvals = []
        def approve(preview):
            approvals.append(copy.deepcopy(preview))
            if preview['kind'] == 'registration-setup-preview':
                self.assertEqual(host.creations, 1)
                self.assertEqual(preview['software_revision'], host.ref)
            return digest(preview)
        with patch.object(authority_release, 'authorize'):
            result = controller.connect('owner/project', 'owner/authority', approve)
            self.assertEqual(result['state'], 'setup')
            self.assertFalse(result['enforcement_active'])
            self.assertEqual(len(result['identities']['apps']), 5)
            self.assertEqual(controller.connect('owner/project', 'owner/authority', approve), result)
        self.assertEqual(len(approvals), 2)
        self.assertEqual(host.creations, 1)
        self.assertEqual(len(registration.exchanges), 5)
        import json
        self.assertNotIn('SYNTHETIC-PRIVATE', json.dumps(result))

    def test_missing_consent_and_changed_selection_cannot_create_or_adopt(self):
        controller, host, registration, journals = self.fixture()
        with patch.object(authority_release, 'authorize'):
            with self.assertRaises(Refusal): controller.connect('owner/project', 'owner/authority', lambda _: '0' * 64)
            self.assertEqual(host.creations, 0)
            controller.connect('owner/project', 'owner/authority', digest)
            with self.assertRaises(Refusal): controller.connect('owner/other', 'owner/authority', digest)
        self.assertEqual(host.creations, 1)

    def test_unknown_creation_resumes_without_second_post(self):
        controller, host, registration, journals = self.fixture()
        host.unknown_create = True
        with patch.object(authority_release, 'authorize'):
            with self.assertRaises(OSError): controller.connect('owner/project', 'owner/authority', digest)
            with self.assertRaises(Refusal): controller.connect('owner/project', 'owner/authority', digest)
        self.assertEqual(host.creations, 1)
        self.assertEqual(registration.exchanges, [])

    def test_public_hold_precedes_storage_or_authentication(self):
        class NoIO:
            def __getattr__(self, name): raise AssertionError(name)
        controller = operator_setup.Operator(NoIO(), NoIO(), Path('/unused'), {}, lambda: 1000,
            store_factory=lambda _: self.fail('storage opened while held'))
        with self.assertRaises(authority_release.Held): controller.connect('source', 'authority', digest)


if __name__ == '__main__': unittest.main()
