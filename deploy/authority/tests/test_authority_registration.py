"""Protected registration persistence with synthetic browser/GitHub responses."""
import backend_test_support
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bootstrap import PERMISSIONS
from trusted_ci_policy import Refusal, digest
import authority_release
import private_setup
import registration


class Gh:
    def __init__(self): self.identity, self.exchanges = 7, []
    def api(self, route):
        if route == '/user': return dict(id=self.identity, type='User', login='owner')
        if route.startswith('/user/memberships/orgs/'): return dict(state='active', role='member')
        if route.startswith('/orgs/'): return dict(id=7)
        if route.endswith('/git/ref/heads/main'): return dict(object=dict(sha='a' * 40))
        name = route.removeprefix('/repos/')
        if name in ('owner/project', 'owner/authority'):
            return dict(id=123 if name.endswith('project') else 456, full_name=name, private=True,
                owner=dict(id=7), permissions=dict(admin=True), default_branch='main')
        raise AssertionError(route)
    def exchange(self, purpose):
        self.exchanges.append(purpose)
        number = list(PERMISSIONS).index(purpose) + 10
        return dict(id=number, slug='agentic-' + purpose, pem='SYNTHETIC-PRIVATE-' + purpose,
                    permissions=PERMISSIONS[purpose], owner=dict(id=7))


class RegistrationContracts(unittest.TestCase):
    def test_install_uses_minimal_valid_permission_and_enumerates_entire_installation(self):
        app = dict(id=10, slug='agentic-admin', pem='synthetic', permissions=PERMISSIONS['admin'])
        class API:
            def get(self, route):
                if route == '/app': return dict(id=10, slug=app['slug'], owner=dict(id=7), permissions=PERMISSIONS['admin'])
                return dict(app_id=10, account=dict(id=7), repository_selection='selected', suspended_at=None,
                            permissions=PERMISSIONS['admin'])
            def post(inner, route, body):
                self.assertEqual(body, dict(permissions=dict(contents='read')))
                return dict(token='synthetic', permissions=dict(contents='read'), repositories=[dict(id=123), dict(id=456)])
        class Scoped:
            ids = [123, 456]
            def pages(self, route, collection): return [dict(id=n) for n in self.ids]
            def get(self, route): return dict(id=1010, type='Bot')
        scoped = Scoped()
        with patch.object(registration.bootstrap, 'await_installation', return_value=110), \
             patch.object(registration.bootstrap, 'app_api', return_value=API()), \
             patch.object(registration.bootstrap, 'revoke_token') as revoke, \
             patch.object(registration, 'GitHub', return_value=scoped):
            self.assertEqual(registration.install(app, 7, [123, 456], 30)['actor_id'], 1010)
            scoped.ids.append(999)
            with self.assertRaises(Refusal): registration.install(app, 7, [123, 456], 30)
            self.assertEqual(revoke.call_count, 2)

    def fixture(self):
        temporary = tempfile.TemporaryDirectory(prefix='agentic-registration-fixture-',
            dir=str(Path.home()) if os.name == 'nt' else '/tmp')
        self.addCleanup(temporary.cleanup)
        store = private_setup.Store(Path(temporary.name) / 'registration')
        gh, calls = Gh(), []
        def registrar(purpose, capture, organization):
            self.assertIsNone(organization)
            result = capture.exchange(purpose)
            # Durable before a response is returned to the browser flow.
            self.assertEqual(store.read()['value']['apps'][purpose]['registration']['pem'], result['pem'])
            return result
        def installer(app, owner, repositories):
            purpose = app['slug'].removeprefix('agentic-')
            self.assertIn(store.read()['value']['apps'][purpose]['phase'], ('captured', 'installed'))
            self.assertEqual(owner, 7)
            self.assertEqual(repositories, [123, 456] if purpose in ('admin', 'reader') else [123])
            return dict(id=app['id'], slug=app['slug'], installation_id=app['id'] + 100, actor_id=app['id'] + 1000)
        def register(purpose, capture, organization):
            calls.append(purpose)
            return registrar(purpose, capture, organization)
        controller = registration.Registration(gh, store, clock=lambda: 1000, registrar=register, installer=installer)
        return gh, store, calls, controller

    def test_public_hold_before_journal_or_browser(self):
        _, store, calls, controller = self.fixture()
        with self.assertRaises(authority_release.Held): controller.run({}, '')
        self.assertIsNone(store.read())
        self.assertEqual(calls, [])

    def test_five_resumable_captures_precede_installation_and_public_result_has_no_keys(self):
        gh, store, calls, controller = self.fixture()
        preview = controller.preview('owner/project', 'owner/authority', 'a' * 40)
        result = controller._run(preview, digest(preview))
        self.assertEqual(len(calls), 5)
        self.assertEqual(set(result['identities']['apps']), set(PERMISSIONS))
        self.assertNotIn('SYNTHETIC-PRIVATE', str(result))
        self.assertFalse(result['enforcement_active'])
        before = store.read()
        self.assertEqual(controller._run(preview, digest(preview)), result)
        self.assertEqual(store.read(), before)
        self.assertEqual(len(gh.exchanges), 5)

    def test_lost_browser_return_recovers_captured_key_without_registering_again(self):
        gh, store, calls, controller = self.fixture()
        normal = controller.registrar
        def lost(*args):
            normal(*args)
            raise OSError('synthetic lost browser return')
        controller.registrar = lost
        preview = controller.preview('owner/project', 'owner/authority', 'a' * 40)
        with self.assertRaises(OSError): controller._run(preview, digest(preview))
        self.assertEqual(store.read()['value']['apps']['admin']['phase'], 'captured')
        controller.registrar = normal
        result = controller._run(preview, digest(preview))
        self.assertEqual(len(gh.exchanges), 5)
        self.assertEqual(len(result['identities']['apps']), 5)

    def test_unknown_exchange_cannot_be_retried_or_adopted_and_actor_change_stops(self):
        gh, store, calls, controller = self.fixture()
        preview = controller.preview('owner/project', 'owner/authority', 'a' * 40)
        def unknown(*args): raise OSError('synthetic unknown browser outcome')
        controller.registrar = unknown
        with self.assertRaises(OSError): controller._run(preview, digest(preview))
        with self.assertRaises(Refusal): controller._run(preview, digest(preview))
        self.assertEqual(store.read()['value']['apps']['admin']['phase'], 'registration-started')
        gh.identity = 8
        with self.assertRaises(Refusal): controller._run(preview, digest(preview))


if __name__ == '__main__': unittest.main()
