"""Origin access delegates one contents-read capability, never an App root."""
import backend_test_support
import json
import unittest
from unittest.mock import patch

import app_proofs
import setup
import trial_handoff
import test_authority_trial_handoff as handoff
from test_authority_app_proofs import AppAPI, identities
from trusted_ci_policy import Refusal, digest
from trusted_ci_github import HostRefusal


@unittest.skipIf(handoff.preparation.jwt is None, 'optional model-auth cryptography environment required')
class Delegation(unittest.TestCase):
    fixture = handoff.Publication.fixture

    def prepared(self):
        origin = handoff.preparation.provisioning.intent()
        records = identities(origin)
        origin['policy']['coding_actors'] = [records['apps']['coding']['actor_id']]
        origin['policy']['merge_actors'] = [records['apps']['merge']['actor_id']]
        origin['resources'].update(identity_record=json.dumps(records), identity_digest=digest(records))
        with patch.object(handoff.preparation.provisioning, 'intent', return_value=origin):
            c, api, reg, production, clock = self.fixture()
        get = production.api.get
        production.api.get = lambda route: dict(get(route), owner={'id': 7}) if route == production.root else get(route)
        result = trial_handoff.Native(c, reg).publish('prompt', digest)
        reader = AppAPI(origin, records, 'reader')
        mint = reader.post
        def post(*args): return dict(mint(*args), expires_at='1970-01-01T00:33:20Z')
        reader.post = post
        return c, api, reg, production, clock, result, reader

    def test_only_original_authority_contents_read_is_minted_and_staged_once(self):
        c, api, reg, production, clock, result, reader = self.prepared()
        controller = setup.TrialReadStaging(c, reg, result['revision'], reader, reader.token_api)
        value = controller.run()
        self.assertEqual(list(reader.visible.values()), [[456]])
        self.assertEqual(value['repository_id'], 456)
        self.assertEqual(value['expires'], 2000)
        self.assertEqual(value['token_digest'], digest(api.secrets['AGENTIC_TRIAL_ORIGIN_TOKEN']))
        self.assertEqual(api.secret_writes.count('AGENTIC_TRIAL_ORIGIN_TOKEN'), 1)
        self.assertEqual(controller.run(), value)
        self.assertNotIn(api.secrets['AGENTIC_TRIAL_ORIGIN_TOKEN'], str(value))

    def test_lost_secret_ack_is_not_repeated_and_token_remains_exact(self):
        c, api, reg, production, clock, result, reader = self.prepared()
        api.lost_secret = True
        controller = setup.TrialReadStaging(c, reg, result['revision'], reader, reader.token_api)
        with self.assertRaises(OSError): controller.run()
        value = controller.run()
        self.assertEqual(value['token_digest'], digest(api.secrets['AGENTIC_TRIAL_ORIGIN_TOKEN']))
        self.assertEqual(api.secret_writes.count('AGENTIC_TRIAL_ORIGIN_TOKEN'), 1)
        self.assertEqual(len(reader.visible), 1)

    def test_expired_or_expanded_token_is_revoked_before_secret_write(self):
        for fault in ('scope', 'expiry', 'postguard'):
            c, api, reg, production, clock, result, reader = self.prepared()
            post = reader.post
            def bad(*args):
                token = post(*args)
                if fault == 'scope': token['permissions']['contents'] = 'write'
                if fault == 'expiry': token['expires_at'] = '1970-01-01T00:16:00Z'
                if fault == 'postguard': clock[0] = 2000
                return token
            reader.post = bad
            with self.subTest(fault=fault), self.assertRaises(Refusal):
                setup.TrialReadStaging(c, reg, result['revision'], reader, reader.token_api).run()
            self.assertEqual(len(reader.visible), 1)
            self.assertEqual(len(reader.revoked), 1)
            self.assertNotIn('AGENTIC_TRIAL_ORIGIN_TOKEN', api.secret_writes)

    def test_origin_movement_during_final_trial_read_prevents_secret_write(self):
        c, api, reg, production, clock, result, reader = self.prepared()
        origin_get, trial_get, checked = production.api.get, api.get, [False]
        def origin(route):
            value = origin_get(route)
            if route == production.root: checked[0] = False
            if '/git/ref/heads/agentic-trial-' in route: checked[0] = True
            return value
        def trial(route):
            value = trial_get(route)
            document = c.store(c.root / 'trial-read-staging').read()
            if route == reg.root and document and document['value']['phase'] == 'secret-started':
                production.api.refs['main'] = '9' * 40
            return value
        production.api.get, api.get = origin, trial
        with self.assertRaises(Refusal): setup.TrialReadStaging(c, reg, result['revision'], reader, reader.token_api).run()
        self.assertNotIn('AGENTIC_TRIAL_ORIGIN_TOKEN', api.secret_writes)
        self.assertEqual(len(reader.revoked), 1)

    def test_cleanup_recovers_lost_delete_ack_and_expired_exact_token(self):
        c, api, reg, production, clock, result, reader = self.prepared()
        controller = setup.TrialReadStaging(c,reg,result['revision'],reader,reader.token_api)
        controller.run()
        calls = []
        class Invalidated:
            def fetch(self,path,**kwargs):
                calls.append((path,kwargs.get('method')))
                if len(calls) == 1: raise OSError('DELETE succeeded but acknowledgement was lost')
                raise HostRefusal(401)
        controller.token_factory = lambda token:Invalidated()
        clock[0] = 2001
        with self.assertRaises(OSError): controller.revoke()
        controller.revoke()
        controller.revoke()
        self.assertEqual(calls,[('/installation/token','DELETE')]*2)
        self.assertEqual(c.store(c.root / 'trial-read-staging').read()['value']['phase'],'revoked')
