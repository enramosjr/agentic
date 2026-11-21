"""Read-only effective controls and conservative indirect-credential blockers."""
import backend_test_support
import base64
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

from test_authority_protocol import deployment
from test_authority_reconcile import Host
from authority_protocol import Journal
from trusted_ci_policy import Refusal, digest
import reconcile
import controls
from app_proofs import TOKEN_PERMISSIONS
from trusted_ci_github import HostRefusal


class ControlHost(Host):
    def __init__(self):
        super().__init__()
        self.actions_enabled, self.hook_active = False, False
        self.owner_mode = '100644'
        self.coding_admin = False
        self.token_permissions = dict(TOKEN_PERMISSIONS['admin'])
        self.owners = b'* @maintainer\n'
        self.owner_sha = hashlib.sha1(b'blob ' + str(len(self.owners)).encode() + b'\0' + self.owners).hexdigest()
    def get(self, path):
        if path.endswith('/actions/permissions'):
            return {'enabled': self.actions_enabled}
        if path.endswith('/users/agentic-coding%5Bbot%5D'):
            return {'id': 18, 'type': 'Bot'}
        if '/git/commits/' in path:
            return {'tree': {'sha': 'a' * 40}}
        if path.endswith('/git/trees/' + 'a' * 40):
            return {'truncated': False, 'tree': [{'path': '.github', 'mode': '040000', 'type': 'tree', 'sha': 'b' * 40}]}
        if path.endswith('/git/trees/' + 'b' * 40):
            return {'truncated': False, 'tree': [{'path': 'CODEOWNERS', 'mode': self.owner_mode, 'type': 'blob', 'sha': self.owner_sha}]}
        if '/git/blobs/' in path:
            return {'sha': self.owner_sha, 'encoding': 'base64', 'content': base64.b64encode(self.owners).decode()}
        return super().get(path)
    def pages(self, path, collection=None):
        if path.endswith('/hooks'):
            if self.token_permissions.get('repository_hooks') != 'read':
                raise HostRefusal(403, 'permission_scope')
            return [{'id': 1, 'active': True}] if self.hook_active else []
        if '/collaborators?' in path:
            people = [{'id': 17, 'type': 'User', 'permissions': {'admin': True, 'push': True}, 'role_name': 'admin'}]
            if self.coding_admin:
                people.append({'id': 18, 'type': 'Bot', 'permissions': {'admin': True, 'push': True}, 'role_name': 'admin'})
            return people
        return super().pages(path, collection)


class ControlContracts(unittest.TestCase):
    def prepared(self, folder):
        journal = Journal(Path(folder) / 'deployment.json')
        value = deployment()
        value['resources'].update(coding_bot_id='18', coding_slug='agentic-coding')
        journal.write(None, value)
        host = ControlHost()
        setup = reconcile.Reconciler(host, journal, now=lambda: 1000, session=backend_test_support.LocalSession(journal))
        setup.apply(digest(setup.preview()))
        host.writes.clear()
        return host, journal

    def test_readback_never_mutates_and_bot_is_not_required_as_human_collaborator(self):
        with tempfile.TemporaryDirectory() as folder:
            host, journal = self.prepared(folder)
            before = copy.deepcopy(journal.read())
            result = controls.observe(host, before)
            self.assertEqual(result['base'], '5' * 40)
            self.assertFalse(result['isolation_established'])
            self.assertFalse(result['enforcement_active'])
            self.assertEqual(journal.read(), before)
            self.assertEqual(host.writes, [])

    def test_readback_retains_all_required_check_sources_including_unsupported_ones(self):
        with tempfile.TemporaryDirectory() as folder:
            host, journal = self.prepared(folder)
            host.rules.append(dict(id=777, name='Additional checks', enforcement='active', bypass_actors=[],
                rules=[dict(type='required_status_checks', parameters=dict(
                    required_status_checks=[dict(context='External integration', integration_id=99),
                                            dict(context='Any-source legacy status', integration_id=None)]))]))
            result = controls.observe(host, journal.read())
            checks = result['required_checks']
            self.assertIn(dict(context='External integration', integration_id=99), checks)
            self.assertIn(dict(context='Any-source legacy status', integration_id=None), checks)
            self.assertIn(dict(context=journal.read()['policy']['check_name'], integration_id=42), checks)
            self.assertEqual(len(checks), 3)
            self.assertEqual(host.writes, [])

    def test_unqualified_indirect_automation_blocks_without_disabling_anything(self):
        for field in ('actions_enabled', 'hook_active'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                host, journal = self.prepared(folder)
                setattr(host, field, True)
                with self.assertRaisesRegex(Refusal, 'indirect credential path'):
                    controls.observe(host, journal.read())
                self.assertEqual(host.writes, [])

    def test_bypass_coding_admin_and_symlink_owners_are_rejected(self):
        for defect in ('bypass', 'coding_admin', 'symlink'):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as folder:
                host, journal = self.prepared(folder)
                if defect == 'bypass':
                    host.rules[1]['bypass_actors'] = [{'actor_type': 'Integration', 'actor_id': 43, 'bypass_mode': 'always'}]
                elif defect == 'coding_admin':
                    host.coding_admin = True
                else:
                    host.owner_mode = '120000'
                with self.assertRaises(Refusal):
                    controls.observe(host, journal.read())

    def test_omitted_bypass_visibility_is_not_an_empty_bypass_list(self):
        with tempfile.TemporaryDirectory() as folder:
            host,journal = self.prepared(folder)
            acceptance = next(rule for rule in host.rules if any(r['type'] == 'required_status_checks' for r in rule['rules']))
            identity = acceptance['id']
            acceptance.pop('bypass_actors')
            acceptance['_links'] = {'self':{'href':'https://api.github.com/repos/owner/repo/rulesets/'+str(identity)}}
            original = host.get
            def get(path):
                if path.endswith('/rulesets/'+str(identity)): return copy.deepcopy(acceptance)
                return original(path)
            host.get = get
            with self.assertRaises(Refusal): controls.observe(host,journal.read())
            self.assertEqual(host.writes,[])


if __name__ == '__main__':
    unittest.main()
