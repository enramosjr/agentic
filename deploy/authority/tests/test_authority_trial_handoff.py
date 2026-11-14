"""Native publication uses real provisioning, configuration and conditional Git."""
import backend_test_support
import copy
from contextlib import ExitStack
import unittest
from unittest.mock import patch

import authority_release
import trial_configuration
import trial_handoff
from trusted_ci_policy import Refusal, digest
import test_authority_trial_configuration as preparation


@unittest.skipIf(preparation.jwt is None, 'optional model-auth cryptography environment required')
class Publication(unittest.TestCase):
    def fixture(self):
        if hasattr(self, 'stack'): self.stack.close()
        c, api, reg, production, clock, patches = preparation.NativePreparation().fixture(native_window=True)
        stack = ExitStack()
        self.stack = stack
        self.addCleanup(stack.close)
        for p in patches: stack.enter_context(p)
        trial_configuration.Prepare(c).run(digest)
        return c, api, reg, production, clock

    def test_publish_authenticated_exact_record_without_origin_or_configuration_change(self):
        c, api, reg, production, clock = self.fixture()
        original, before = production.binding(), reg.binding()
        controller = trial_handoff.Native(c, reg)
        result = controller.publish('approved fixture prompt', digest)
        record, binding = trial_handoff.read(production, result['revision'], clock[0])
        self.assertEqual(record['prompt_digest'], digest('approved fixture prompt'))
        self.assertEqual(record['origin']['binding'], original)
        self.assertEqual(record['trial'], before)
        self.assertEqual(production.binding(), original)
        self.assertEqual(binding, original)
        self.assertEqual(reg.binding(), before)
        writes = copy.deepcopy(api.secrets)
        self.assertEqual(controller.publish('approved fixture prompt', digest), result)
        self.assertEqual(api.secrets, writes)
        self.assertNotIn('approved fixture prompt', str(record))
        for value in api.secrets.values(): self.assertNotIn(value, str(record))

    def test_lost_publication_ack_recovers_exact_commit_without_republishing(self):
        c, api, reg, production, clock = self.fixture()
        post = production.api.post
        count = [0]
        def lost(route, body):
            result = post(route, body)
            if route.endswith('/git/refs'):
                count[0] += 1
                if count[0] == 1: raise OSError('lost publication acknowledgement')
            return result
        production.api.post = lost
        controller = trial_handoff.Native(c, reg)
        with self.assertRaises(OSError): controller.publish('prompt', digest)
        result = controller.publish('prompt', digest)
        self.assertEqual(count[0], 1)
        self.assertEqual(trial_handoff.read(production, result['revision'], clock[0])[0]['prompt_digest'], digest('prompt'))

    def test_decline_expiry_and_late_origin_movement_prevent_publication(self):
        for fault in ('decline', 'expiry', 'scope', 'late-origin'):
            c, api, reg, production, clock = self.fixture()
            before = reg.binding()
            def approve(value):
                if fault == 'expiry': clock[0] = value['expires']
                if fault == 'scope': c.session.scope = {'qualification-fixture': ['other/repo']}
                if fault == 'late-origin': production.api.refs['main'] = '9' * 40
                return None if fault == 'decline' else digest(value)
            with self.subTest(fault=fault), self.assertRaises(Refusal):
                trial_handoff.Native(c, reg).publish('prompt', approve)
            self.assertEqual(reg.binding(), before)

    def test_foreign_commit_with_same_record_is_not_recovery(self):
        c, api, reg, production, clock = self.fixture()
        controller = trial_handoff.Native(c, reg)
        result = controller.publish('prompt', digest)
        api = production.api
        metadata = api.get(production.root + '/git/commits/' + result['revision'])
        foreign = api.post(production.root + '/git/commits', dict(message='foreign', tree=metadata['tree']['sha'], parents=[result['revision']]))['sha']
        task_id = result['task_id']
        api.fetch(production.root + '/git/refs/heads/agentic-trial-' + task_id, method='PATCH', data=dict(sha=foreign, force=False))
        with self.assertRaises(Refusal): controller.publish('prompt', digest)
        with self.assertRaises(Refusal): trial_handoff.read(production, foreign, clock[0])

    def test_task_ref_moving_during_immutable_authentication_is_refused(self):
        c, api, reg, production, clock = self.fixture()
        result = trial_handoff.Native(c, reg).publish('prompt', digest)
        get, checked = production.api.get, [False]
        parent = production.binding()['branch_head']
        branch = 'agentic-trial-' + result['task_id']
        def race(route):
            value = get(route)
            if route.endswith('/git/ref/heads/' + branch): checked[0] = True
            if checked[0] and '/git/commits/' in route:
                production.api.refs[branch] = parent
            return value
        production.api.get = race
        with self.assertRaises(Refusal): trial_handoff.read(production, result['revision'], clock[0])

    def test_origin_moving_during_last_trial_observation_prevents_ref_creation(self):
        c, api, reg, production, clock = self.fixture()
        post, get, prepared, publications = production.api.post, api.get, [False], []
        def retain(route, body):
            value = post(route, body)
            if route.endswith('/git/commits'): prepared[0] = True
            if route.endswith('/git/refs'): publications.append(body)
            return value
        def race(route):
            value = get(route)
            if prepared[0] and route == '/repos/owner/trial-authority':
                production.api.refs['main'] = '9' * 40
            return value
        production.api.post, api.get = retain, race
        with self.assertRaises(Refusal): trial_handoff.Native(c, reg).publish('prompt', digest)
        self.assertEqual(publications, [])


class Holds(unittest.TestCase):
    def test_publication_hold_precedes_native_or_registry_access(self):
        with self.assertRaises(authority_release.Held):
            trial_handoff.Native(None, None).publish('prompt', digest)
