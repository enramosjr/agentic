"""Warm broker/admin ordering; local fixtures cannot qualify hosted latency."""
import backend_test_support
import copy
import io
import hashlib
import json
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from test_authority_merge_window import binding
from test_authority_merge_receipts import ReceiptAPI
from trusted_ci_policy import Refusal
from trusted_ci_policy import digest
import test_authority_controls as control_fixtures
from test_authority_github import Host as SnapshotHost
import control_rendezvous
import merge_receipts


class RendezvousContracts(unittest.TestCase):
    def test_ready_non_object_is_refused_after_archive_authentication(self):
        b, api = binding(), ReceiptAPI()
        store = merge_receipts.ActionsReceipts(api, lambda: b, 77, lambda: 1002, uploader=api.upload)
        request = control_rendezvous.ready(b, 77, 'c' * 32, 1002)
        loc = store.append('control-ready', request)
        for document in ([], dict(request, issued='bad'), dict(request, issued=1003)):
            raw = io.BytesIO()
            with zipfile.ZipFile(raw, 'w') as archive:
                archive.writestr('receipt.json', json.dumps(document))
            api.archives[loc['artifact_id']] = raw.getvalue()
            checksum = 'sha256:' + hashlib.sha256(raw.getvalue()).hexdigest()
            api.artifacts[0]['digest'] = loc['archive_digest'] = checksum
            with self.subTest(document=document), self.assertRaises(Refusal):
                store.authenticate(loc)

    def test_admin_collects_real_control_facts_only_after_authenticating_warm_broker(self):
        with tempfile.TemporaryDirectory() as folder:
            admin, journal = control_fixtures.ControlContracts().prepared(folder)
            d = journal.read()
            d.update(state='active', qualification='f' * 64)
            d['policy']['merge_actors'] = [19]
            b = binding()
            b.update(deployment=d, deployment_digest=digest(d))
            b['fence']['pending'].update(deployment_digest=digest(d), workflow_sha=d['policy']['workflow_sha'],
                head='4' * 40, merge='6' * 40)
            api = ReceiptAPI()
            api.run['head_sha'] = api.job['head_sha'] = d['policy']['workflow_sha']
            def upload(name, raw):
                identity = api.upload(name, raw)
                api.artifacts[-1]['workflow_run']['head_sha'] = d['policy']['workflow_sha']
                return identity
            store = merge_receipts.ActionsReceipts(api, lambda: b, 77, lambda: 1002, uploader=upload)
            request = control_rendezvous.ready(b, 77, 'c' * 32, 1002)
            loc = store.append('control-ready', request)
            events = []
            original_fetch = api.fetch
            def fetch(path, **kwargs):
                events.append('ready-archive')
                return original_fetch(path, **kwargs)
            api.fetch = fetch
            original_get, source = admin.get, SnapshotHost()
            def get(path):
                events.append('admin-read')
                if '/pulls/' in path or '/git/ref/pull/' in path or path.endswith('/git/commits/' + '6' * 40):
                    return source.get(path)
                return original_get(path)
            admin.get = get
            result = control_rendezvous.collect(admin, api, lambda: b, 77, loc, lambda: 1002)
            self.assertEqual(result['result']['base'], '5' * 40)
            self.assertEqual(result['result']['coding_bot_id'], 18)
            self.assertIn('ready-archive', events)
            self.assertIn('admin-read', events)
            self.assertLess(events.index('ready-archive'), events.index('admin-read'))
            self.assertEqual(admin.writes, [])
            bad = dict(loc, artifact_id=999)
            events.clear()
            with self.assertRaises(Refusal):
                control_rendezvous.collect(admin, api, lambda: b, 77, bad, lambda: 1002)
            self.assertNotIn('admin-read', events)

    def test_after_implementation_producer_test_detects_a_deliberately_broken_variant(self):
        method = 'test_admin_collects_real_control_facts_only_after_authenticating_warm_broker'
        suite = unittest.TestSuite([RendezvousContracts(method)])
        with patch.object(control_rendezvous, 'collect', return_value={'result': {'base': '5' * 40, 'coding_bot_id': 18}}):
            result = unittest.TextTestRunner(stream=io.StringIO()).run(suite)
        self.assertGreater(len(result.failures), 0)
        self.assertEqual(len(result.errors), 0)

    def test_ready_is_not_authorization_and_queue_delay_precedes_readback(self):
        b = binding()
        clock = [1002]
        api = ReceiptAPI()
        store = merge_receipts.ActionsReceipts(api, lambda: b, 77, lambda: clock[0], uploader=api.upload)
        ready = control_rendezvous.ready(b, 77, 'c' * 32, 1002)
        locator = store.append('control-ready', ready)
        self.assertEqual(store.authenticate(locator), ready)
        self.assertNotIn('check_id', ready)
        self.assertNotIn('readback_started', ready)
        self.assertEqual(ready['expires'], 1122)
        # Arbitrary cold-start delay occurred before readiness was requested.
        late = control_rendezvous.ready(b, 77, 'd' * 32, 1200)
        self.assertEqual(late['issued'], 1200)
        self.assertEqual(late['expires'], b['fence']['pending']['execution_deadline'])
        self.assertEqual(control_rendezvous.validate_ready(late, b, 77, 1200), late)

    def test_ready_is_single_use_and_cannot_restart_after_dispatch_intent(self):
        b, api = binding(), ReceiptAPI()
        store = merge_receipts.ActionsReceipts(api, lambda: b, 77, lambda: 1002, uploader=api.upload)
        ready = control_rendezvous.ready(b, 77, 'c' * 32, 1002)
        store.append('control-ready', ready)
        with self.assertRaises(Refusal):
            store.append('control-ready', ready)
        api = ReceiptAPI()
        api.artifacts.append({'id': 999, 'name': 'agentic-merge-' + '1' * 32 + '-s1-a1-dispatch'})
        store = merge_receipts.ActionsReceipts(api, lambda: b, 77, lambda: 1002, uploader=api.upload)
        with self.assertRaises(Refusal):
            store.append('control-ready', ready)
        self.assertEqual(len(api.artifacts), 1)

    def test_wrong_current_operation_identity_or_short_window_refuses_ready(self):
        b = binding()
        value = control_rendezvous.ready(b, 77, 'c' * 32, 1002)
        for field, bad in [('operation_id', 'd' * 32), ('sequence', 2), ('broker_job_id', 78),
            ('configuration_revision', 'c' * 40), ('head', '0' * 40), ('attempt', 2),
            ('expires', 1061), ('nonce', 'invalid')]:
            changed = dict(value, **{field: bad})
            with self.subTest(field=field), self.assertRaises(Refusal):
                control_rendezvous.validate_ready(changed, b, 77, 1002)

    def test_response_binds_ready_and_actual_readback_clock(self):
        b = binding()
        request = control_rendezvous.ready(b, 77, 'c' * 32, 1002)
        facts = dict(schema_version=2, deployment_digest=b['deployment_digest'], generation=b['deployment']['generation'],
            base='5' * 40, controls_digest='a' * 64, owners_digest='b' * 64, access_digest='c' * 64,
            automation_digest='d' * 64, coding_bot_id=18,
            required_checks=[{'context': b['deployment']['policy']['check_name'], 'integration_id': 42}],
            isolation_established=False, enforcement_active=False)
        response = control_rendezvous.response(request, b, 77, 1003, 1004, facts)
        proof = dict(role='controls', key=7, run_id=99, attempt=1, job_id=88,
            job_started=1000, job_completed=1006, artifact_created=1005)
        self.assertEqual(control_rendezvous.validate_response(response, request, b, proof, 1007), response)
        for defect in ('nonce', 'digest', 'age', 'future', 'facts', 'attempt'):
            changed, changed_proof, now = copy.deepcopy(response), copy.deepcopy(proof), 1007
            if defect == 'nonce': changed['nonce'] = 'd' * 32
            if defect == 'digest': changed['ready_digest'] = '0' * 64
            if defect == 'age': now = 1034
            if defect == 'future': changed['readback_completed'] = 1008
            if defect == 'facts': changed['result']['base'] = '0' * 40
            if defect == 'attempt': changed_proof['attempt'] = 2
            with self.subTest(defect=defect), self.assertRaises(Refusal):
                control_rendezvous.validate_response(changed, request, b, changed_proof, now)


if __name__ == '__main__':
    unittest.main()
