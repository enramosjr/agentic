"""Atomic repository installation against a local Git object API fixture."""
import backend_test_support  # Establish the explicit source-only test paths.
import base64
import copy
import hashlib
import json
import inspect
from pathlib import Path
import sys
import unittest

import trusted_ci_fixtures
from trusted_ci_github import GitHub
from trusted_ci_policy import Refusal, digest
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'deploy/authority'))
import repository


class GitHost:
    def __init__(self):
        self.blobs, self.trees, self.commits = {}, {}, {}
        self.ref, self.lose_ack = 'a' * 40, False
        self.trees['b' * 40] = {'README.md': ('100644', self.blob(b'adopter data'))}
        self.commits[self.ref] = {'tree': {'sha': 'b' * 40}, 'parents': []}
        self.writes = []

    def blob(self, raw):
        key = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        self.blobs[key] = raw
        return key

    def get(self, path):
        if path == '/repos/owner/authority':
            return {'id': 456, 'private': True, 'default_branch': 'main'}
        if '/git/ref/' in path:
            return {'object': {'sha': self.ref}}
        if '/git/commits/' in path:
            return self.commits[path.rsplit('/', 1)[1]]
        if '/git/trees/' in path:
            key = path.rsplit('/', 1)[1].split('?')[0]
            return {'truncated': False, 'tree': [dict(path=p, mode=m, type='blob', sha=s)
                    for p, (m, s) in self.trees[key].items()]}
        if '/git/blobs/' in path:
            key = path.rsplit('/', 1)[1]
            return {'sha': key, 'encoding': 'base64', 'content': base64.b64encode(self.blobs[key]).decode()}
        raise AssertionError(path)

    def post(self, path, body):
        self.writes.append((path, copy.deepcopy(body)))
        if path.endswith('/git/blobs'):
            return {'sha': self.blob(base64.b64decode(body['content']))}
        if path.endswith('/git/trees'):
            values = copy.deepcopy(self.trees[body['base_tree']])
            for item in body['tree']:
                if item['sha'] is None:
                    values.pop(item['path'])
                else:
                    values[item['path']] = (item['mode'], item['sha'])
            key = digest(values)[:40]
            self.trees[key] = values
            return {'sha': key}
        if path.endswith('/git/commits'):
            key = digest(body)[:40]
            self.commits[key] = {'sha': key, 'message': body['message'], 'tree': {'sha': body['tree']},
                                 'parents': [{'sha': p} for p in body['parents']]}
            return {'sha': key}
        raise AssertionError(path)

    def fetch(self, path, method='GET', **kwargs):
        # Keep the fixture bound to the actual transport, rather than allowing a
        # fake-only spelling to conceal a broken remote integration.
        inspect.signature(GitHub.fetch).bind(self, path, method=method, **kwargs)
        data = kwargs.get('data')
        self.writes.append((path, copy.deepcopy(data)))
        if method == 'PATCH' and '/git/refs/' in path:
            self.ref = data['sha']
            if self.lose_ack:
                self.lose_ack = False
                raise OSError('lost reference update acknowledgement')
            return {}
        raise AssertionError(path)


class RepositoryContracts(unittest.TestCase):
    def test_only_fixed_bootstrap_metadata_paths_can_be_installed(self):
        host = GitHost()
        installer = repository.Repository(host, 'owner/authority', 456, 'main', session=backend_test_support.LocalSession())
        files = {'.agentic-authority/bootstrap.json': b'{"registry_branch":"agentic-registry"}',
                 '.agentic-authority/identities.json': b'{"public_identifiers_only":true}'}
        installer.apply(files, digest(installer.preview(files)))
        with self.assertRaises(Refusal):
            installer.preview({'.agentic-authority/deployment.json': b'cannot embed self-referential policy'})

    def test_preview_refuses_ancestor_descendant_and_reserved_marker_collisions(self):
        for existing, desired in [('.ai/scripts/tool.py/keep.txt', '.ai/scripts/tool.py'),
                                   ('.ai/scripts', '.ai/scripts/tool.py'),
                                   (repository.MARKER + '/keep.txt', '.ai/scripts/tool.py'),
                                   ('.agentic-authority', '.ai/scripts/tool.py')]:
            host = GitHost()
            host.trees['b' * 40][existing] = ('100644', host.blob(b'adopter data'))
            installer = repository.Repository(host, 'owner/authority', 456, 'main', session=backend_test_support.LocalSession())
            with self.subTest(existing=existing), self.assertRaises(Refusal):
                installer.preview({desired: b'release'})
            self.assertFalse(host.writes)

    def test_installs_upgrades_and_removes_owned_files_preserving_adopter_data(self):
        host = GitHost()
        installer = repository.Repository(host, 'owner/authority', 456, 'main', session=backend_test_support.LocalSession())
        files = {'.ai/scripts/authority_release.py': b'held source'}
        installer.apply(files, digest(installer.preview(files)))
        first = host.ref
        self.assertFalse(installer.apply(files, digest(installer.preview(files)))['changed'])
        self.assertEqual(host.ref, first)
        files['.ai/scripts/authority_release.py'] = b'upgraded held source'
        installer.apply(files, digest(installer.preview(files)))
        self.assertNotEqual(host.ref, first)
        result = installer.apply({}, digest(installer.preview({})))
        self.assertFalse(result['enforcement_active'])
        current = host.trees[host.commits[host.ref]['tree']['sha']]
        self.assertEqual(set(current), {'README.md', repository.MARKER})
        self.assertEqual(host.blobs[current['README.md'][1]], b'adopter data')

    def test_lost_ack_is_resumable_and_drift_or_wrong_consent_refused(self):
        host = GitHost()
        installer = repository.Repository(host, 'owner/authority', 456, 'main', session=backend_test_support.LocalSession())
        files = {'.ai/scripts/authority_release.py': b'held source'}
        plan = installer.preview(files)
        with self.assertRaises(Refusal):
            installer.apply(files, '0' * 64)
        self.assertFalse(host.writes)
        host.lose_ack = True
        with self.assertRaises(OSError):
            installer.apply(files, digest(plan))
        self.assertFalse(installer.apply(files, digest(installer.preview(files)))['changed'])
        tree = host.trees[host.commits[host.ref]['tree']['sha']]
        tree['.ai/scripts/authority_release.py'] = ('100644', host.blob(b'foreign change'))
        with self.assertRaises(Refusal):
            installer.preview(files)


if __name__ == '__main__':
    unittest.main()
