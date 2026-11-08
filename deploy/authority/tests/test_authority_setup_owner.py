"""Native setup actor admission over API/Git fixtures, not context attestation."""
import backend_test_support
import copy
import unittest
from unittest.mock import patch

from test_authority_registry import RegistryHost, coordinates, intent
from test_authority_fence import pending
from test_authority_app_proofs import identities, AppAPI
from trusted_ci_policy import Refusal, digest
import configuration
import operation_fence
import registry
import repository


class Operator:
    def __init__(self):
        self.user = dict(id=71, type='User')
        self.repositories = {'owner/project': dict(id=123, permissions={'admin': True}, owner={'id': 7}),
            'owner/authority': dict(id=456, private=True, permissions={'admin': True}, owner={'id': 7})}
    def get(self, path):
        if path == '/user': return copy.deepcopy(self.user)
        return copy.deepcopy(self.repositories[path.removeprefix('/repos/')])


def fixture(software=False, credential_names=(), host_type=RegistryHost, embedded_identities=False, cloud_setup=None, dispatch_lock=None):
    host = host_type()
    store = registry.Registry(host, coordinates())
    d = intent()
    d['state'] = 'setup'
    d['policy']['merge_actors'] = [19]
    records = identities(d)
    d['resources']['identity_digest'] = digest(records)
    if embedded_identities:
        import json
        d['resources']['identity_record'] = json.dumps(records, sort_keys=True, separators=(',', ':'))
    if cloud_setup is not None:
        d.update(adapter=cloud_setup[0]['adapter'], account=cloud_setup[0]['account'])
    store.write(None, d)
    before = store.binding()
    scope = {'credentials': ['owner/authority:model-vault'], 'registry': ['owner/authority:agentic-registry'],
             'software': ['owner/authority:main']}
    scope['credentials'].extend('owner/authority:secret:' + name for name in credential_names)
    if cloud_setup is not None: scope['cloud-apply'] = [digest(cloud_setup[0])]
    if dispatch_lock is not None: scope['rules'] = ['owner/authority:dispatch-lock']
    preview = dict(schema_version=1, kind='adopter-setup-preview', operator_id=71,
        repository='owner/project', repository_id=123, target='main', authority_repository='owner/authority',
        authority_repository_id=456, adapter=d['adapter'], account=d['account'],
        configuration_revision=before['configuration_revision'], deployment_digest=before['deployment_digest'],
        workflow_sha=d['policy']['workflow_sha'], effects=scope,
        changes=dict(software={'inventory_digest': 'a' * 64}, cloud=None,
                     protections={'plan_digest': 'b' * 64}, credentials=['model-vault', *credential_names]))
    if cloud_setup is not None: preview['changes']['cloud'] = copy.deepcopy(cloud_setup[1])
    if dispatch_lock is not None: preview['changes']['protections']['authority_dispatch'] = copy.deepcopy(dispatch_lock)
    files = {'.ai/scripts/tool.py': b'approved independent software fixture'}
    if software:
        preview['changes']['software'] = repository.Repository(host, 'owner/authority', 456, 'main').preview(files)
    op = pending(before, 'configuration')
    op.update(run_id=None, attempt=None, scope_digest=digest(scope),
              setup=dict(operator_id=71, installation_id=records['apps']['admin']['installation_id'], approval_digest=digest(preview)))
    acquired = store.acquire_operation(before['branch_head'], before['configuration_revision'], op)
    known = {k: acquired[k] for k in ('configuration_revision', 'deployment_digest', 'branch_head')}
    operator, app = Operator(), AppAPI(d, records, 'admin')
    clock = [1001]
    def session(approved=None, known_progress=None, progress=None, writer=None):
        kwargs = {}
        if progress is not None: kwargs['software_progress'] = progress
        if writer is not None: kwargs['persist_software_progress'] = writer
        return configuration.SetupConfigurationSession(store, op['operation_id'], 1, operator, app, records,
            preview if approved is None else approved, scope, known if known_progress is None else known_progress, lambda: clock[0], **kwargs)
    session.files = files
    host.writes.clear()
    return host, store, session, operator, app, preview, known, clock


class SetupOwnerContracts(unittest.TestCase):
    def test_retained_progress_authenticates_parent_inventory_and_unrelated_files(self):
        for defect in ('parent', 'message', 'unrelated', 'owned-mode'):
            host, store, make, operator, app, preview, known, clock = fixture(software=True)
            retained = []
            session = make(writer=lambda value: (retained.append(copy.deepcopy(value)), digest(value))[1])
            result = repository.Repository(host, 'owner/authority', 456, 'main', session=session).apply(
                make.files, digest(preview['changes']['software']))
            commit = host.commits[result['revision']]
            tree = host.trees[commit['tree']['sha']]
            if defect == 'parent': commit['parents'] = [{'sha': 'e' * 40}]
            elif defect == 'message': commit['message'] = 'not the approved transition'
            elif defect == 'unrelated': tree['README.md'] = ('100644', host.blob(b'changed unrelated adopter data'))
            else:
                name = next(iter(make.files))
                tree[name] = ('100755', tree[name][1])
            def contract():
                with self.assertRaises(Refusal): make(progress=retained[0])
            with self.subTest(defect=defect): contract()
            if defect == 'parent':
                with patch.object(repository.Repository, 'authenticate_transition', return_value=None), self.assertRaises(AssertionError):
                    contract()  # Detect deliberately bypassed transition proof.

    def test_registry_repin_cannot_accept_a_software_rollback_to_old_approved_base(self):
        host, store, make, operator, app, preview, known, clock = fixture(software=True)
        retained = []
        session = make(writer=lambda value: (retained.append(copy.deepcopy(value)), digest(value))[1])
        result = repository.Repository(host, 'owner/authority', 456, 'main', session=session).apply(
            make.files, digest(preview['changes']['software']))
        before = store.binding(check_software=False)['deployment']
        changed = copy.deepcopy(before)
        changed['generation'] += 1
        changed['policy']['workflow_sha'] = result['revision']
        session.write_configuration(digest(before), changed)
        host.refs['main'] = 'a' * 40
        def contract():
            with self.assertRaises(Refusal): session.require_effect('credentials', 'owner/authority:model-vault')
        contract()
        with patch.object(configuration.SetupConfigurationSession, '_owned', configuration.ConfigurationSession._owned), \
             self.assertRaises(AssertionError): contract()

    def test_exact_prepared_software_recovers_interruption_before_registry_repin(self):
        host, store, make, operator, app, preview, known, clock = fixture(software=True)
        retained = []
        def persist(value):
            retained.append(copy.deepcopy(value))
            return digest(value)
        session = make(writer=persist)
        installer = repository.Repository(host, 'owner/authority', 456, 'main', session=session)
        host.lose_ack = True
        with self.assertRaises(OSError): installer.apply(make.files, digest(preview['changes']['software']))
        self.assertEqual(len(retained), 1)
        self.assertEqual(host.refs['main'], retained[0]['revision'])
        self.assertEqual(store.binding(check_software=False)['deployment']['policy']['workflow_sha'], 'a' * 40)
        with self.assertRaises(Refusal): make()
        restored = make(progress=retained[0], writer=persist)
        restored.require_effect('credentials', 'owner/authority:model-vault')
        host.writes.clear()
        result = repository.Repository(host, 'owner/authority', 456, 'main', session=restored).resume_transition(
            preview['changes']['software'], retained[0]['revision'])
        self.assertEqual(result['revision'], retained[0]['revision'])
        self.assertEqual(host.writes, [])
        for field, bad in [('revision', 'e' * 40), ('plan_digest', '0' * 64), ('operation_id', '2' * 32), ('sequence', 2)]:
            with self.subTest(field=field), self.assertRaises(Refusal): make(progress=dict(retained[0], **{field: bad}))

    def test_wire_variant_is_configuration_only_and_runtime_coordinates_stay_strict(self):
        host = RegistryHost()
        store = registry.Registry(host, coordinates())
        store.write(None, intent())
        value = pending(store.binding(), 'configuration')
        value.update(run_id=None, attempt=None, setup=dict(operator_id=71, installation_id=141, approval_digest='a' * 64))
        self.assertIs(operation_fence.operation(value), value)
        for defect in ('merge', 'run', 'attempt', 'missing-setup', 'operator', 'installation', 'approval', 'extra'):
            changed = copy.deepcopy(value)
            if defect == 'merge': changed['kind'] = 'merge'
            elif defect == 'run': changed['run_id'] = 99
            elif defect == 'attempt': changed['attempt'] = 1
            elif defect == 'missing-setup': changed.pop('setup')
            elif defect == 'operator': changed['setup']['operator_id'] = True
            elif defect == 'installation': changed['setup']['installation_id'] = 0
            elif defect == 'approval': changed['setup']['approval_digest'] = 'invalid'
            else: changed['setup']['unknown'] = True
            with self.subTest(defect=defect), self.assertRaises(Refusal): operation_fence.operation(changed)
        self.assertIsNotNone(operation_fence.operation(pending(store.binding())))

    def test_actual_api_identity_scope_and_owned_writes_preserve_pending_fence(self):
        host, store, make, operator, app, preview, known, clock = fixture()
        session = make()
        session.require_effect('credentials', 'owner/authority:model-vault')
        with self.assertRaises(Refusal): session.require_effect('credentials', 'other/authority:model-vault')
        before = store.read()
        changed = copy.deepcopy(before)
        changed.update(generation=2, expires=2100)
        session.write_configuration(digest(before), changed)
        self.assertEqual(store.read(), changed)
        self.assertIsNotNone(store.binding()['fence']['pending'])
        with self.assertRaises(Refusal): make()  # Old known progress cannot accept a new branch head.

    def test_revoked_native_identity_registration_or_installation_blocks_next_effect(self):
        for defect in ('operator', 'bot', 'source-admin', 'authority-admin', 'authority-private', 'app', 'permissions', 'installation'):
            host, store, make, operator, app, preview, known, clock = fixture()
            session = make()
            if defect == 'operator': operator.user['id'] = 72
            elif defect == 'bot': operator.user['type'] = 'Bot'
            elif defect == 'source-admin': operator.repositories['owner/project']['permissions']['admin'] = False
            elif defect == 'authority-admin': operator.repositories['owner/authority']['permissions']['admin'] = False
            elif defect == 'authority-private': operator.repositories['owner/authority']['private'] = False
            elif defect == 'app': app.record = dict(app.record, id=99)
            elif defect == 'permissions': app.permissions['checks'] = 'write'
            else: app.record = dict(app.record, installation_id=999)
            with self.subTest(defect=defect), self.assertRaises(Refusal):
                session.require_effect('credentials', 'owner/authority:model-vault')
            self.assertEqual(host.writes, [])

    def test_changed_approval_or_known_progress_cannot_create_a_session(self):
        host, store, make, operator, app, preview, known, clock = fixture()
        changed = copy.deepcopy(preview)
        changed['changes']['protections']['plan_digest'] = 'c' * 64
        with self.assertRaises(Refusal): make(approved=changed)
        with self.assertRaises(Refusal): make(known_progress=dict(known, branch_head='e' * 40))
        self.assertEqual(host.writes, [])

    def test_workflow_owner_cannot_borrow_setup_fence_and_expiry_cannot_unlock(self):
        host, store, make, operator, app, preview, known, clock = fixture()
        session = make()
        with self.assertRaises(Refusal):
            configuration.ConfigurationSession(store, '1' * 32, 1,
                dict(workflow_sha='a' * 40, run_id=99, attempt=1), preview['effects'], lambda: clock[0])
        clock[0] = 1300
        with self.assertRaises(Refusal): session.require_effect('credentials', 'owner/authority:model-vault')
        self.assertIsNotNone(store.binding()['fence']['pending'])
        self.assertEqual(host.writes, [])

    def test_caller_mutation_does_not_replace_admitted_approval(self):
        host, store, make, operator, app, preview, known, clock = fixture()
        session = make()
        preview['effects']['credentials'].append('other/authority:model-vault')
        preview['changes']['protections']['plan_digest'] = 'c' * 64
        with self.assertRaises(Refusal): session.require_effect('credentials', 'other/authority:model-vault')
        session.require_effect('credentials', 'owner/authority:model-vault')


if __name__ == '__main__': unittest.main()
