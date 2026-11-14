"""Fresh configuration-session ownership before every external side effect."""
import backend_test_support
import copy
import unittest

from test_authority_fence import pending
from test_authority_registry import RegistryHost, coordinates, intent
from trusted_ci_policy import Refusal, digest
import registry
from configuration import ConfigurationSession
import cloud
import reconcile
import repository
from backend_test_support import config
from test_authority_reconcile import Host
from test_authority_repository import GitHost
from authority_protocol import Journal
from pathlib import Path
import tempfile


class ConfigurationContracts(unittest.TestCase):
    def test_native_administrator_identity_rejects_numeric_aliases(self):
        from configuration import SetupConfigurationSession
        from test_authority_app_proofs import AppProofContracts
        for fault in (None,'repository','repository-owner','app','app-owner','installation','installation-app','installation-owner'):
            with self.subTest(fault=fault):
                d,records,admin=AppProofContracts().prepared('admin')
                p=d['policy']; get=admin.get
                def app_read(path):
                    value=copy.deepcopy(get(path))
                    if path=='/app':
                        if fault=='app': value['id']=float(value['id'])
                        if fault=='app-owner': value['owner']['id']=float(value['owner']['id'])
                    else:
                        if fault=='installation': value['id']=float(value['id'])
                        if fault=='installation-app': value['app_id']=float(value['app_id'])
                        if fault=='installation-owner': value['account']['id']=float(value['account']['id'])
                    return value
                admin.get=app_read
                class Operator:
                    def get(self,path):
                        if path=='/user': return dict(id=17,type='User')
                        repository_id=p['authority_repository_id'] if path=='/repos/'+p['authority_repository'] else p['repository_id']
                        return dict(id=float(repository_id) if fault=='repository' else repository_id,
                            owner=dict(id=7.0 if fault=='repository-owner' else 7),private=True,permissions=dict(admin=True))
                session=SetupConfigurationSession.__new__(SetupConfigurationSession)
                session.operator_api,session.admin_api,session.identities=Operator(),admin,records
                session.preview=dict(operator_id=17,adapter=d['adapter'],account=d['account'],
                    **{k:p[k] for k in ('repository','repository_id','target','authority_repository','authority_repository_id')})
                if fault is None:
                    self.assertEqual(session._native_identity(d)['operator_id'],17)
                else:
                    with self.assertRaises(Refusal): session._native_identity(d)

    def test_established_mutators_without_session_make_no_external_calls(self):
        for adapter in (cloud.Aws, cloud.Azure):
            calls = []
            api = adapter(config('aws' if adapter is cloud.Aws else 'azure'),
                          runner=lambda *args, **kwargs: calls.append(args))
            for operation in (lambda: api.apply('a' * 64), lambda: api.destroy(['owned'], 'a' * 64)):
                with self.assertRaises(Refusal):
                    operation()
                self.assertEqual(calls, [])
        host = GitHost()
        installer = repository.Repository(host, 'owner/authority', 456, 'main')
        files = {'.ai/scripts/tool.py': b'approved source'}
        with self.assertRaises(Refusal):
            installer.apply(files, digest(installer.preview(files)))
        self.assertEqual(host.writes, [])
        with tempfile.TemporaryDirectory() as folder:
            journal = Journal(Path(folder) / 'd.json')
            journal.write(None, intent())
            host = Host()
            reconciler = reconcile.Reconciler(host, journal, lambda: 1000)
            with self.assertRaises(Refusal):
                reconciler.apply(digest(reconciler.preview()))
            self.assertEqual(host.writes, [])

    def test_preview_does_not_manufacture_an_ownership_nonce(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = Journal(Path(folder) / 'd.json')
            value = intent()
            value['resources'].pop('operation_id')
            journal.write(None, value)
            host = Host()
            with self.assertRaises(Refusal):
                reconcile.Reconciler(host, journal, lambda: 1000).preview()
            self.assertEqual(journal.read(), value)
            self.assertEqual(host.writes, [])

    def prepared(self):
        host = RegistryHost()
        store = registry.Registry(host, coordinates())
        store.write(None, intent())
        before = store.binding()
        scope = {'rules': ['owner/project'], 'registry': ['owner/authority:agentic-registry'],
                 'software': ['owner/authority:main']}
        operation = pending(before, 'configuration')
        operation['scope_digest'] = digest(scope)
        store.acquire_operation(before['branch_head'], before['configuration_revision'], operation)
        clock = [1001]
        owner = {'workflow_sha': 'a' * 40, 'run_id': 99, 'attempt': 1}
        session = ConfigurationSession(store, operation['operation_id'], 1, owner, scope, lambda: clock[0])
        return host, store, session, clock

    def test_exact_scope_and_owner_are_mandatory(self):
        host, store, session, clock = self.prepared()
        session.require_effect('rules', 'owner/project')
        for action, scope in [('rules', 'other/project'), ('cloud-apply', 'any'), ('registry', 'owner/project')]:
            with self.subTest(action=action, scope=scope), self.assertRaises(Refusal):
                session.require_effect(action, scope)
        before = store.binding()
        op = before['fence']['pending']
        with self.assertRaises(Refusal):
            ConfigurationSession(store, op['operation_id'], 1,
                {'workflow_sha': 'a' * 40, 'run_id': 100, 'attempt': 1}, session.scope, lambda: clock[0])

    def test_deadline_and_changed_fence_block_the_next_effect(self):
        host, store, session, clock = self.prepared()
        session.require_effect('rules', 'owner/project')
        clock[0] = 1300
        with self.assertRaises(Refusal):
            session.require_effect('rules', 'owner/project')
        self.assertIsNotNone(store.binding()['fence']['pending'])
        clock[0] = 1002
        current = store.binding()
        store.finalize_operation(current['branch_head'], {'operation_id': '1' * 32, 'sequence': 1,
            'kind': 'configuration-complete', 'receipt_digest': 'a' * 64})
        with self.assertRaises(Refusal):
            session.require_effect('rules', 'owner/project')

    def test_successive_owned_writes_advance_session_without_unlocking(self):
        host, store, session, clock = self.prepared()
        for generation in (2, 3):
            before = store.read()
            new = copy.deepcopy(before)
            new.update(generation=generation, state='blocked')
            new['resources']['acceptance_rule'] = str(generation)
            session.write_configuration(digest(before), new)
            session.require_effect('rules', 'owner/project')
        self.assertEqual(store.read()['generation'], 3)
        self.assertIsNotNone(store.binding()['fence']['pending'])

    def test_deadline_expiry_during_object_upload_prevents_registry_ref_write(self):
        host, store, session, clock = self.prepared()
        before = store.binding()
        changed = copy.deepcopy(before['deployment'])
        changed.update(generation=2, state='blocked')
        original_post = host.post
        def slow_upload(path, data):
            result = original_post(path, data)
            if path.endswith('/git/blobs'):
                clock[0] = 1300
            return result
        host.post = slow_upload
        with self.assertRaises(Refusal):
            session.write_configuration(digest(before['deployment']), changed)
        self.assertEqual(store.binding()['branch_head'], before['branch_head'])

    def test_unexpected_configuration_or_software_progress_is_rejected(self):
        host, store, session, clock = self.prepared()
        changed = copy.deepcopy(store.read())
        changed.update(generation=2, state='blocked')
        store.write(digest(store.read()), changed, operation_id='1' * 32, before_effect=lambda: None)
        with self.assertRaises(Refusal):
            session.require_effect('rules', 'owner/project')
        host, store, session, clock = self.prepared()
        host.refs['main'] = 'f' * 40
        with self.assertRaises(Refusal):
            session.require_effect('rules', 'owner/project')


if __name__ == '__main__':
    unittest.main()
