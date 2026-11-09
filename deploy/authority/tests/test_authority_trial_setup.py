"""Disposable trial provisioning through real setup/registration over fake APIs."""
import backend_test_support
import copy
from pathlib import Path
import unittest
from unittest.mock import patch

import authority_release
import bootstrap
import configuration
import registration
import registry
import trial_setup
from test_authority_fence import pending
from test_authority_initial_setup import Host
from test_authority_registry import RegistryHost, coordinates, intent
from test_authority_registration import Gh as AppGh
from test_authority_runtime_pins import Journal
from trusted_ci_policy import Refusal, digest
from contextlib import ExitStack


class PairHost:
    def __init__(self):
        self.hosts = {name: Host() for name in ('owner/trial', 'owner/trial-authority')}
        self.ids = {'owner/trial': 701, 'owner/trial-authority': 702}
        self.creation_names = []

    def get(self, route):
        if route == '/user': return dict(id=7, type='User', login='owner')
        for name, host in self.hosts.items():
            if route == '/repos/' + name or route.startswith('/repos/' + name + '/'):
                value = host.get(route.replace('/repos/' + name, '/repos/owner/authority', 1))
                if route == '/repos/' + name:
                    value.update(id=self.ids[name], full_name=name)
                return value
        raise AssertionError(route)

    def post(self, route, body):
        if route == '/user/repos':
            name = 'owner/' + body['name']
            self.creation_names.append(name)
            host = self.hosts[name]
            host.creations += 1
            host.exists = True
            if host.unknown_create: raise OSError('synthetic lost creation acknowledgement')
            return self.get('/repos/' + name)
        return self._git('post', route, body)

    def _git(self, operation, route, *args, **kwargs):
        for name, host in self.hosts.items():
            if route.startswith('/repos/' + name + '/'):
                return getattr(host, operation)(route.replace('/repos/' + name, '/repos/owner/authority', 1), *args, **kwargs)
        raise AssertionError(route)

    def fetch(self, route, **kwargs): return self._git('fetch', route, **kwargs)


class TrialProvisionContracts(unittest.TestCase):
    def fixture(self):
        rh = RegistryHost()
        reg = registry.Registry(rh, coordinates())
        d = intent()
        d['state'] = 'qualification'
        reg.write(None, d)
        before = reg.binding()
        scope = {'qualification-fixture': ['owner/trial', 'owner/trial-authority']}
        operation = pending(before, 'configuration')
        operation['scope_digest'] = digest(scope)
        reg.acquire_operation(before['branch_head'], before['configuration_revision'], operation)
        clock = [1001]
        session = configuration.ConfigurationSession(reg, operation['operation_id'], 1,
            dict(workflow_sha='a' * 40, run_id=99, attempt=1), scope, lambda: clock[0])
        api, apps, journals, installations, approvals = PairHost(), AppGh(), {}, [], []
        class Gh:
            def api(self, route): return api.get(route)
            def exchange(self, purpose): return apps.exchange(purpose)
        def store(path):
            return journals.setdefault(str(path), Journal())
        def installer(app, owner, repositories):
            installations.append((app['slug'], owner, list(repositories)))
            return dict(id=app['id'], slug=app['slug'], installation_id=app['id'] + 100, actor_id=app['id'] + 1000)
        def approve(value):
            approvals.append(copy.deepcopy(value))
            return digest(value)
        controller = trial_setup.Provision(session, api, Gh(), Path('/synthetic-trial-purpose'),
            {'.ai/scripts/qualification_fixture.py': b'approved fixture seed'},
            {'.ai/scripts/authority_release.py': b'approved fixed authority'},
            lambda: clock[0], store_factory=store,
            registrar=lambda purpose, capture, org: capture.exchange(purpose), installer=installer)
        return controller, api, apps, journals, installations, approvals, approve, reg, clock

    def run_local(self, controller, approve):
        # The only bypass is the public operational hold; all product validators run.
        with patch.object(authority_release, 'authorize'):
            return controller.run('owner/trial', 'owner/trial-authority', approve)

    def test_public_hold_precedes_storage_authentication_or_effects(self):
        c, api, apps, journals, *_ = self.fixture()
        with self.assertRaises(authority_release.Held): c.run('owner/trial', 'owner/trial-authority', digest)
        self.assertEqual(journals, {})
        self.assertEqual(api.creation_names, [])
        self.assertEqual(apps.exchanges, [])

    def test_provisions_exact_pair_and_five_own_scopes_without_production_mutation(self):
        c, api, apps, journals, installs, approvals, approve, reg, _ = self.fixture()
        before = reg.binding()
        result = self.run_local(c, approve)
        self.assertEqual(api.creation_names, ['owner/trial', 'owner/trial-authority'])
        self.assertEqual(len(apps.exchanges), 5)
        for slug, owner, repos in installs:
            self.assertEqual(owner, 7)
            self.assertEqual(repos, [701, 702] if slug.endswith(('admin', 'reader')) else [701])
            self.assertTrue(set(repos).isdisjoint({123, 456}))
        self.assertEqual(reg.binding(), before)
        self.assertEqual(result['fixture_repository_id'], 701)
        self.assertEqual(result['authority_repository_id'], 702)
        self.assertFalse(result['enforcement_active'])
        self.assertFalse(result['hosted_qualified'])
        self.assertFalse(result['execution_admitted'])
        self.assertNotIn('SYNTHETIC-PRIVATE', str(result))
        self.assertEqual(result['origin']['configuration_revision'], before['configuration_revision'])
        self.assertEqual(result['origin']['sequence'], before['fence']['sequence'])
        writes = [copy.deepcopy(h.writes) for h in api.hosts.values()]
        self.assertEqual(self.run_local(c, approve), result)
        self.assertEqual(len(apps.exchanges), 5)
        self.assertEqual(len(approvals), 2)
        self.assertEqual([h.writes for h in api.hosts.values()], writes)

    def test_creation_unknown_is_retained_and_never_repeated_or_adopted(self):
        c, api, apps, _, _, _, approve, *_ = self.fixture()
        api.hosts['owner/trial'].unknown_create = True
        with self.assertRaises(OSError): self.run_local(c, approve)
        with self.assertRaises(Refusal): self.run_local(c, approve)
        self.assertEqual(api.creation_names, ['owner/trial'])
        self.assertEqual(apps.exchanges, [])

    def test_lost_ref_ack_and_captured_callback_resume_without_duplicate_effects(self):
        for lost in ('ref', 'callback'):
            with self.subTest(lost=lost):
                c, api, apps, _, _, _, approve, *_ = self.fixture()
                if lost == 'ref': api.hosts['owner/trial'].lose_ack = True
                else:
                    normal = c.registrar
                    def registrar(*args):
                        normal(*args)
                        raise OSError('synthetic browser return lost')
                    c.registrar = registrar
                with self.assertRaises(OSError): self.run_local(c, approve)
                c.registrar = lambda purpose, capture, org: capture.exchange(purpose)
                result = self.run_local(c, approve)
                self.assertEqual(api.creation_names, ['owner/trial', 'owner/trial-authority'])
                self.assertEqual(len(apps.exchanges), 5)
                self.assertEqual(result['fixture_repository_id'], 701)

    def test_declined_or_substituted_consent_and_out_of_scope_target_have_no_effect(self):
        for fault in ('declined', 'substitute', 'production', 'same'):
            with self.subTest(fault=fault):
                c, api, apps, _, _, _, approve, *_ = self.fixture()
                def consent(value):
                    if fault == 'substitute': value['fixture']['repository'] = 'owner/other'
                    return '0' * 64 if fault == 'declined' else digest(value)
                source = 'owner/project' if fault == 'production' else 'owner/trial'
                authority = source if fault == 'same' else 'owner/trial-authority'
                with patch.object(authority_release, 'authorize'), self.assertRaises(Refusal):
                    c.run(source, authority, consent)
                self.assertEqual(api.creation_names, [])
                self.assertEqual(apps.exchanges, [])

    def test_expiry_or_fence_change_during_consent_blocks_creation(self):
        for fault in ('expiry', 'fence'):
            c, api, apps, _, _, _, approve, reg, clock = self.fixture()
            def consent(value):
                if fault == 'expiry': clock[0] = 1300
                else:
                    current = reg.binding()
                    reg.finalize_operation(current['branch_head'], dict(operation_id='1' * 32, sequence=1,
                        kind='configuration-complete', receipt_digest='a' * 64))
                return digest(value)
            with self.subTest(fault=fault), self.assertRaises(Refusal): self.run_local(c, consent)
            self.assertEqual(api.creation_names, [])
            self.assertEqual(apps.exchanges, [])

    def test_completed_pair_readback_rejects_identity_drift_and_changed_release(self):
        for fault in ('identity', 'release', 'origin'):
            c, api, apps, _, _, _, approve, reg, _ = self.fixture()
            self.run_local(c, approve)
            if fault == 'identity': api.ids['owner/trial'] = 999
            elif fault == 'release': c.fixture_files['.ai/scripts/qualification_fixture.py'] = b'substituted'
            else:
                current = reg.binding()
                reg.finalize_operation(current['branch_head'], dict(operation_id='1' * 32, sequence=1,
                    kind='configuration-complete', receipt_digest='a' * 64))
            writes = [copy.deepcopy(h.writes) for h in api.hosts.values()]
            with self.subTest(fault=fault), self.assertRaises(Refusal): self.run_local(c, approve)
            self.assertEqual([h.writes for h in api.hosts.values()], writes)
            self.assertEqual(len(apps.exchanges), 5)

    def test_production_app_substitution_is_rejected_before_installation(self):
        c, api, apps, journals, installs, _, approve, reg, _ = self.fixture()
        exchange = apps.exchange
        production_id = reg.read()['apps']['admin']
        def substitute(purpose):
            result = exchange(purpose)
            result['id'] = production_id
            return result
        apps.exchange = substitute
        with self.assertRaisesRegex(Refusal, 'production App'): self.run_local(c, approve)
        self.assertEqual(installs, [])
        self.assertEqual(len(apps.exchanges), 1)
        retained = journals[str(c.root / 'trial-operator' / 'registration')].read()
        self.assertEqual(retained['value']['apps']['admin']['phase'], 'captured')
        with self.assertRaises(Refusal): self.run_local(c, approve)
        self.assertEqual(len(apps.exchanges), 1)

    def test_repository_substitution_stops_before_software_writes(self):
        c, api, apps, _, installs, _, approve, *_ = self.fixture()
        api.ids['owner/trial'] = 123
        with self.assertRaisesRegex(Refusal, 'substituted'): self.run_local(c, approve)
        self.assertEqual(api.hosts['owner/trial'].writes, [])
        self.assertEqual(installs, [])
        with self.assertRaises(Refusal): self.run_local(c, approve)
        self.assertEqual(api.creation_names, ['owner/trial'])

    def test_configuration_fence_expiring_after_blob_stops_next_effect(self):
        c, api, apps, _, installs, _, approve, _, clock = self.fixture()
        normal = api.post
        def expire(route, body):
            result = normal(route, body)
            if route.endswith('/git/blobs'): clock[0] = 1300
            return result
        api.post = expire
        with self.assertRaises(Refusal): self.run_local(c, approve)
        self.assertEqual(api.creation_names, ['owner/trial'])
        self.assertEqual(len(api.hosts['owner/trial'].writes), 1)
        self.assertEqual(installs, [])

    def test_valid_metadata_permissions_preserve_the_two_repository_domains(self):
        c, _, apps, _, installs, _, approve, *_ = self.fixture()
        normal = apps.exchange
        def metadata(purpose):
            result = normal(purpose)
            result['permissions'] = dict(result['permissions'], metadata='read')
            return result
        apps.exchange = metadata
        self.run_local(c, approve)
        self.assertEqual(len(installs), 5)

    def test_native_installer_rechecks_wait_and_token_boundaries_and_resumes_exact_identity(self):
        for fault in ('none', 'wait', 'token'):
            with self.subTest(fault=fault):
                c, _, _, _, _, _, approve, _, clock = self.fixture()
                c.installer = None
                requests, waits, revoked = [], [], []
                class API:
                    def __init__(self, app_id, pem):
                        self.id = app_id
                        self.purpose = list(bootstrap.PERMISSIONS)[app_id - 10]
                        self.repos = [701, 702] if self.purpose in ('admin', 'reader') else [701]
                    def get(self, route):
                        requests.append((route, clock[0]))
                        if route == '/app':
                            return dict(id=self.id, slug='agentic-' + self.purpose, owner=dict(id=7),
                                        permissions=dict(bootstrap.PERMISSIONS[self.purpose], metadata='read'))
                        return dict(id=self.id + 100, app_id=self.id, account=dict(id=7),
                            repository_selection='selected', suspended_at=None, permissions=bootstrap.PERMISSIONS[self.purpose])
                    def pages(self, route):
                        waits.append(self.id)
                        if fault == 'wait': clock[0] = 1300
                        return [dict(id=self.id + 100, account=dict(id=7), suspended_at=None)]
                    def post(self, route, body):
                        requests.append((route, clock[0]))
                        if fault == 'token': clock[0] = 1300
                        return dict(token=self.purpose, permissions=dict(contents='read'),
                                    repositories=[dict(id=n) for n in self.repos])
                class Scoped:
                    def __init__(self, purpose): self.purpose = purpose
                    def pages(self, route, collection):
                        requests.append((route, clock[0]))
                        return [dict(id=n) for n in ([701, 702] if self.purpose in ('admin', 'reader') else [701])]
                    def get(self, route):
                        requests.append((route, clock[0]))
                        return dict(id=list(bootstrap.PERMISSIONS).index(self.purpose) + 1010, type='Bot')
                with ExitStack() as stack:
                    stack.enter_context(patch.object(bootstrap.webbrowser, 'open', return_value=True))
                    stack.enter_context(patch.object(bootstrap, 'app_api', side_effect=API))
                    stack.enter_context(patch.object(registration, 'GitHub', side_effect=Scoped))
                    stack.enter_context(patch.object(bootstrap, 'revoke_token', side_effect=lambda value: revoked.append(value)))
                    if fault == 'none':
                        result = self.run_local(c, approve)
                        self.assertEqual(self.run_local(c, approve), result)
                        self.assertEqual(len(waits), 5)  # Resume verifies the retained installation, without a new browser.
                        self.assertEqual(len(revoked), 10)
                    else:
                        with self.assertRaises(Refusal): self.run_local(c, approve)
                        self.assertTrue(all(at < 1300 for _, at in requests), requests)
                        self.assertEqual(len(revoked), 1 if fault == 'token' else 0)


if __name__ == '__main__': unittest.main()
