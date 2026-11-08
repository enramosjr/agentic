"""Fresh-resource installation through real private storage and a Git API fixture."""
import backend_test_support
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from trusted_ci_github import HostRefusal
from trusted_ci_policy import Refusal, digest
import authority_release
import private_setup
import repository
import setup
import test_authority_repository as git_fixture


class Host(git_fixture.GitHost):
    def __init__(self):
        super().__init__()
        self.exists, self.creations, self.unknown_create = False, 0, False
        self.owner, self.registry_exists = 7, False
        self.commits[self.ref]['sha'] = self.ref

    def get(self, path):
        if path == '/user': return dict(id=7, login='owner', type='User')
        if path == '/repos/owner/authority':
            if not self.exists: raise HostRefusal(404, 'not_found', 'synthetic missing')
            return dict(id=456, full_name='owner/authority', private=True, default_branch='main',
                        owner=dict(id=self.owner), permissions=dict(admin=True))
        if path == '/repos/owner/authority/git/ref/heads/agentic-registry':
            if self.registry_exists: return {'object': {'sha': 'e' * 40}}
            raise HostRefusal(404, 'not_found', 'synthetic missing')
        return super().get(path)

    def post(self, path, body):
        if path == '/user/repos':
            self.creations += 1
            self.exists = True
            if self.unknown_create: raise OSError('synthetic lost creation response')
            return self.get('/repos/owner/authority')
        return super().post(path, body)


class InitialSetupContracts(unittest.TestCase):
    def fixture(self):
        parent = str(Path.home()) if os.name == 'nt' else '/tmp'
        temporary = tempfile.TemporaryDirectory(prefix='agentic-initial-fixture-', dir=parent)
        self.addCleanup(temporary.cleanup)
        host = Host()
        store = private_setup.Store(Path(temporary.name) / 'authority')
        files = {'.ai/scripts/authority_release.py': b'SYNTHETIC FIXED RELEASE'}
        controller = setup.InitialAuthority(host, store, files, clock=lambda: 1000)
        return host, store, files, controller

    def test_public_entry_is_held_before_any_io(self):
        class NoIO:
            def __getattr__(self, name): raise AssertionError(name)
        with self.assertRaises(authority_release.Held):
            setup.InitialAuthority(NoIO(), NoIO(), {}, clock=lambda: 1000).run('owner/authority', '0' * 64)

    def test_creates_and_installs_exact_release_with_no_configuration_bypass(self):
        host, store, files, controller = self.fixture()
        preview = controller.preview('owner/authority')
        result = controller._run(preview, digest(preview))
        self.assertEqual(host.creations, 1)
        self.assertFalse(result['enforcement_active'])
        self.assertEqual(result['revision'], host.ref)
        self.assertEqual(store.read()['value']['phase'], 'installed')
        observed = repository.Repository(host, 'owner/authority', 456, 'main').inspect()
        self.assertEqual(observed[3]['files'], preview['release']['files'])
        self.assertIn('README.md', observed[2])
        self.assertTrue(all(not value.get('force', False) for _, value in host.writes))
        before = copy.deepcopy(host.writes)
        self.assertEqual(controller._run(preview, digest(preview)), result)
        self.assertEqual(host.writes, before)

    def test_unknown_creation_is_never_retried_or_adopted_by_name(self):
        host, store, files, controller = self.fixture()
        preview = controller.preview('owner/authority')
        host.unknown_create = True
        with self.assertRaises(OSError): controller._run(preview, digest(preview))
        self.assertEqual(store.read()['value']['phase'], 'create-started')
        with self.assertRaises(Refusal): controller._run(preview, digest(preview))
        self.assertEqual(host.creations, 1)
        self.assertFalse(host.writes)

    def test_lost_software_ack_recovers_exact_prepared_commit_without_second_write(self):
        host, store, files, controller = self.fixture()
        preview = controller.preview('owner/authority')
        host.lose_ack = True
        with self.assertRaises(OSError): controller._run(preview, digest(preview))
        self.assertEqual(store.read()['value']['phase'], 'prepared')
        prepared = host.ref
        before = copy.deepcopy(host.writes)
        restored = setup.InitialAuthority(host, store, files, clock=lambda: 1001)
        result = restored._run(preview, digest(preview))
        self.assertEqual(result['revision'], prepared)
        self.assertEqual(host.writes, before)
        self.assertEqual(host.creations, 1)

    def test_existing_resource_wrong_approval_and_expired_preview_have_no_effects(self):
        for fault in ('existing', 'approval', 'expired', 'release'):
            with self.subTest(fault=fault):
                host, store, files, controller = self.fixture()
                preview = controller.preview('owner/authority')
                if fault == 'existing': host.exists = True
                if fault == 'expired': controller.clock = lambda: preview['expires']
                if fault == 'release': controller.files['.ai/scripts/authority_release.py'] = b'changed'
                approval = '0' * 64 if fault == 'approval' else digest(preview)
                with self.assertRaises(Refusal): controller._run(preview, approval)
                self.assertEqual(host.creations, 0)
                self.assertFalse(host.writes)

    def test_recovery_refuses_changed_owner_registry_or_unapproved_commit(self):
        for fault in ('owner', 'registry', 'commit'):
            with self.subTest(fault=fault):
                host, store, files, controller = self.fixture()
                preview = controller.preview('owner/authority')
                host.lose_ack = True
                with self.assertRaises(OSError): controller._run(preview, digest(preview))
                if fault == 'owner': host.owner = 99
                if fault == 'registry': host.registry_exists = True
                if fault == 'commit': host.commits[host.ref]['message'] = 'unapproved'
                before = copy.deepcopy(host.writes)
                with self.assertRaises(Refusal): controller._run(preview, digest(preview))
                self.assertEqual(host.writes, before)

    def test_prepared_recovery_rebinds_inventory_to_original_release_approval(self):
        host, store, files, controller = self.fixture()
        preview = controller.preview('owner/authority')
        host.lose_ack = True
        with self.assertRaises(OSError): controller._run(preview, digest(preview))
        state = copy.deepcopy(store.read()['value'])
        host.ref = state['plan']['base']
        other = repository.Repository(host, 'owner/authority', 456, 'main', backend_test_support.LocalSession())
        substituted = {'.ai/scripts/authority_release.py': b'UNAPPROVED DIFFERENT RELEASE'}
        other_plan = other.preview(substituted)
        other_result = other.apply(substituted, digest(other_plan))
        state.update(plan=other_plan, revision=other_result['revision'])
        store.write(store.read(), state)
        before = copy.deepcopy(host.writes)
        with self.assertRaises(Refusal): controller._run(preview, digest(preview))
        self.assertEqual(host.writes, before)

    def test_approval_expiring_during_intent_persistence_prevents_creation(self):
        host, store, files, controller = self.fixture()
        preview = controller.preview('owner/authority')
        write = store.write
        def persist(expected, value):
            result = write(expected, value)
            if value['phase'] == 'create-started': controller.clock = lambda: preview['expires']
            return result
        with patch.object(store, 'write', side_effect=persist), self.assertRaises(Refusal):
            controller._run(preview, digest(preview))
        self.assertEqual(host.creations, 0)
        self.assertFalse(host.writes)
        self.assertEqual(store.read()['value']['phase'], 'create-started')


if __name__ == '__main__': unittest.main()
