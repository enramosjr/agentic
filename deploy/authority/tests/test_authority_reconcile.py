"""Reconciliation against a local API fixture, not live GitHub enforcement."""
import backend_test_support  # Establish the explicit source-only test paths.
import base64
import copy
from pathlib import Path
import sys
import tempfile
import unittest

from test_authority_protocol import deployment
from trusted_ci_policy import Refusal, digest
from authority_protocol import Journal
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'deploy/authority'))
import reconcile


class Host:
    def __init__(self):
        self.rules = [{'id': 88, 'name': 'Existing stronger control', 'enforcement': 'active',
                       'rules': [{'type': 'required_signatures'}], 'bypass_actors': []}]
        self.writes = []
        self.lose_ack = False

    def get(self, path):
        if path == '/repos/owner/project':
            return {'id': 123, 'default_branch': 'main', 'allow_merge_commit': True}
        if path == '/repos/owner/authority':
            return {'id': 456, 'private': True}
        if '/branches/' in path:
            return {'commit': {'sha': '5' * 40}}
        if '/contents/' in path:
            return {'encoding': 'base64', 'content': base64.b64encode(b'* @maintainer\n').decode()}
        if path == '/users/maintainer':
            return {'id': 17, 'login': 'maintainer'}
        raise AssertionError(path)

    def pages(self, path, collection=None):
        if '/rules/branches/' in path:
            return [{'ruleset_id': r['id'], **rule} for r in self.rules for rule in r['rules']]
        if '/rulesets' in path:
            return copy.deepcopy(self.rules)
        raise AssertionError(path)

    def post(self, path, data):
        self.writes.append((path, copy.deepcopy(data)))
        result = dict(copy.deepcopy(data), id=100 + len(self.rules))
        self.rules.append(result)
        if self.lose_ack:
            self.lose_ack = False
            raise OSError('interrupted after provider committed')
        return result


class ReconcileContracts(unittest.TestCase):
    def test_interruption_recovers_without_duplicate_rules_or_weakening_foreign_controls(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = Journal(Path(folder) / 'operation.json')
            journal.write(None, deployment())
            host = Host()
            before = copy.deepcopy(host.rules[0])
            engine = reconcile.Reconciler(host, journal, now=lambda: 1000, session=backend_test_support.LocalSession(journal))
            plan = engine.preview()
            host.lose_ack = True
            with self.assertRaises(OSError):
                engine.apply(digest(plan))
            resumed = reconcile.Reconciler(host, journal, now=lambda: 1000, session=backend_test_support.LocalSession(journal))
            result = resumed.apply(digest(resumed.preview()))
            self.assertEqual(len(host.writes), 2)
            self.assertEqual(host.rules[0], before)
            self.assertEqual(result['state'], 'qualification')
            self.assertFalse(result['enforcement_active'])
            unchanged = resumed.preview()
            resumed.apply(digest(unchanged))
            self.assertEqual(len(host.writes), 2)

    def test_stale_or_missing_consent_never_mutates_host(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = Journal(Path(folder) / 'operation.json')
            journal.write(None, deployment())
            host = Host()
            engine = reconcile.Reconciler(host, journal, now=lambda: 1000, session=backend_test_support.LocalSession(journal))
            plan = engine.preview()
            host.rules[0]['rules'].append({'type': 'deletion'})
            with self.assertRaises(Refusal):
                engine.apply(digest(plan))
            self.assertFalse(host.writes)


if __name__ == '__main__':
    unittest.main()
