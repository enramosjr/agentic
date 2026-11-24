"""Native scoped authority-reference setup, without changing GitHub controls."""
import backend_test_support
import copy
import os
from pathlib import Path
import tempfile
import unittest

import authority_release
import private_setup
from test_authority_setup_owner import fixture
from trusted_ci_policy import Refusal


class DispatchControlContracts(unittest.TestCase):
    def test_native_approved_lock_is_created_once_and_unknown_creation_is_not_adopted(self):
        import dispatch_controls
        outer = self
        class API:
            rules = None
            posts = 0
            lose_ack = False
            expire = None
            def get(self, route):
                if route == '/user':
                    if self.expire is not None: self.expire()
                    return dict(id=71, type='User')
                if route == '/repos/owner/authority':
                    return dict(id=456, private=True, default_branch='main')
                if route.endswith('/git/ref/heads/main'): return dict(object=dict(sha='a' * 40))
                if route.endswith('/rulesets/81'): return dict(self.rules, id=81, source='owner/authority', source_type='Repository')
                if route.endswith('/rules/branches/main'):
                    return [dict(type=t, ruleset_id=81, ruleset_source_type='Repository',
                        ruleset_source='owner/authority') for t in ('update', 'deletion')] if self.rules else []
                raise AssertionError(route)
            def pages(self, route):
                outer.assertEqual(route, '/repos/owner/authority/rulesets')
                return [] if self.rules is None else [dict(id=81, name=self.rules['name'])]
            def post(self, route, body):
                outer.assertEqual(route, '/repos/owner/authority/rulesets')
                self.posts += 1
                self.rules = copy.deepcopy(body)
                if self.lose_ack: raise OSError('synthetic lost creation acknowledgement')
                return self.get(route + '/81')
        for mode in ('normal', 'lost', 'expired'):
            with self.subTest(mode=mode):
                api = API()
                plan = dispatch_controls.preview(api, 'owner/authority', 456, 'a' * 40)
                host, registry, make, operator, admin, approved, known, clock = fixture(dispatch_lock=plan)
                parent = str(Path.home()) if os.name == 'nt' else '/tmp'
                with tempfile.TemporaryDirectory(prefix='agentic-dispatch-fixture-', dir=parent) as temporary:
                    controller = dispatch_controls.DispatchLock(make(), api, private_setup.Store(Path(temporary) / 'lock'))
                    with self.assertRaises(authority_release.Held): controller.run()
                    self.assertEqual(api.posts, 0)
                    api.lose_ack = mode == 'lost'
                    if mode == 'expired':
                        def expire():
                            document = controller.journal.read()
                            if document is not None and document['value']['phase'] == 'create-started':
                                clock[0] = registry.binding()['fence']['pending']['execution_deadline']
                        api.expire = expire
                        with self.assertRaises(Refusal): controller._apply()
                        self.assertEqual(api.posts, 0)
                        continue
                    if mode == 'lost':
                        with self.assertRaises(OSError): controller._apply()
                        with self.assertRaisesRegex(Refusal, 'unknown'): controller._apply()
                    else:
                        result = controller._apply()
                        self.assertEqual(result['ruleset_id'], 81)
                        self.assertFalse(result['enforcement_active'])
                        self.assertEqual(controller._apply(), result)
                        api.rules['bypass_actors'] = [dict(actor_id=5, actor_type='RepositoryRole', bypass_mode='always')]
                        with self.assertRaises(Refusal): controller._apply()
                    self.assertEqual(api.posts, 1)


if __name__ == '__main__': unittest.main()
