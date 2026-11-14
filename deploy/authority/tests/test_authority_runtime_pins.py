"""Exact native runtime-pin consent and recovery against a fake variable API."""
import backend_test_support
import copy
import unittest
from unittest.mock import patch

import authority_release
import setup
from test_authority_setup_owner import fixture
from trusted_ci_policy import Refusal, digest


class Journal:
    def __init__(self): self.document = None
    def read(self): return copy.deepcopy(self.document)
    def write(self, before, value):
        if before != self.document: raise Refusal('fixture CAS changed')
        self.document = dict(generation=1 if before is None else before['generation'] + 1,
                             value=copy.deepcopy(value))
        return self.read()


class RuntimePinContracts(unittest.TestCase):
    def fixture(self):
        host, registry, make, operator, admin, preview, known, clock = fixture()
        pins = {name: dict(authority_repository='owner/authority', authority_repository_id=456,
                workflow='.github/workflows/' + workflow, workflow_sha=revision * 40)
                for name, workflow, revision in (
                    ('AGENTIC_FINALIZE_PIN', 'authority-v2.yml', 'a'),
                    ('AGENTIC_RECOVERY_PIN', 'authority-v2-recovery.yml', 'b'))}
        # Change the fixture approval before admitting its session, preserving the
        # real fence digest and real SetupConfigurationSession authentication.
        preview['changes']['protections']['runtime_pins'] = pins
        preview['effects']['credentials'].extend('owner/authority:variable:' + n for n in pins)
        # The fixture helper exposes Git state, so replace its exact operation blob.
        import operation_fence
        import registry as registry_module
        before = registry.binding()
        updated = copy.deepcopy(before['fence'])
        updated['pending']['scope_digest'] = digest(preview['effects'])
        updated['pending']['setup']['approval_digest'] = digest(preview)
        operation_fence.validate(updated)
        after = registry._replace(before, {registry_module.OPERATION: updated})
        known.update({k: after[k] for k in known})
        session = make()
        outer = self
        class API:
            def __init__(self):
                self.values, self.writes = {}, []
                self.lose = self.drift = self.expire = False
            def api(self, route, method='GET', body=None):
                if route == '/user':
                    return dict(id=operator.user['id'], type=operator.user['type'])
                outer.assertEqual(route, '/repos/owner/authority/actions/variables')
                outer.assertEqual(method, 'POST')
                self.writes.append(copy.deepcopy(body))
                self.values[body['name']] = body['value']
                if self.expire: clock[0] = 1300
                if self.lose: raise OSError('synthetic lost acknowledgement')
            def pages(self, route, collection):
                outer.assertEqual(route, '/repos/owner/authority/actions/variables')
                outer.assertEqual(collection, 'variables')
                return [dict(name=n, value=v + ('drift' if self.drift else '')) for n, v in self.values.items()]
        api, journal = API(), Journal()
        operator.pages = api.pages
        return setup.RuntimePins(session, api, journal), api, journal, pins, operator, clock

    def test_release_hold_precedes_io(self):
        class NoIO:
            def __getattr__(self, name): raise AssertionError(name)
        with self.assertRaises(authority_release.Held):
            setup.RuntimePins(NoIO(), NoIO(), NoIO()).run()

    def test_exact_pins_read_back_and_resume_without_rewriting(self):
        controller, api, journal, pins, operator, clock = self.fixture()
        with patch.object(authority_release, 'authorize'):
            result = controller.run()
            self.assertEqual(result['state'], 'runtime-pins-configured')
            self.assertFalse(result['enforcement_active'])
            self.assertEqual(set(api.values), set(pins))
            self.assertEqual(controller.run(), result)
        self.assertEqual(len(api.writes), 2)
        import json
        self.assertEqual({n: json.loads(v) for n, v in api.values.items()}, pins)
        self.assertEqual(journal.read()['value']['phase'], 'verified')

    def test_unknown_write_is_observed_not_repeated_and_drift_blocks(self):
        controller, api, journal, pins, operator, clock = self.fixture()
        api.lose = True
        with patch.object(authority_release, 'authorize'):
            with self.assertRaises(OSError): controller.run()
            api.lose = False
            result = controller.run()
            self.assertEqual(result['state'], 'runtime-pins-configured')
            api.drift = True
            with self.assertRaises(Refusal): controller.run()
        self.assertEqual(len(api.writes), 2)

    def test_existing_unowned_value_or_changed_operator_cannot_write(self):
        for defect in ('existing', 'operator', 'expiry', 'missing-approval', 'wrong-pin'):
            controller, api, journal, pins, operator, clock = self.fixture()
            if defect == 'existing': api.values['AGENTIC_RECOVERY_PIN'] = 'unowned'
            elif defect == 'operator': operator.user['id'] = 999
            elif defect == 'expiry': clock[0] = 1300
            elif defect == 'missing-approval': controller.session.preview['changes']['protections'].pop('runtime_pins')
            else: controller.session.preview['changes']['protections']['runtime_pins']['AGENTIC_RECOVERY_PIN']['authority_repository_id'] = 999
            with self.subTest(defect=defect), patch.object(authority_release, 'authorize'):
                with self.assertRaises(Refusal): controller.run()
            self.assertEqual(api.writes, [])

    def test_expiry_during_write_does_not_acknowledge_or_write_next_pin(self):
        controller, api, journal, pins, operator, clock = self.fixture()
        api.expire = True
        with patch.object(authority_release, 'authorize'):
            with self.assertRaises(Refusal): controller.run()
        self.assertEqual(len(api.writes), 1)
        self.assertEqual(journal.read()['value']['phase'], 'writing')


if __name__ == '__main__': unittest.main()
