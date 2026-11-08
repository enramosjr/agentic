"""Five authenticated purpose-job proofs bound to one pending broker attempt."""
import backend_test_support
import copy
import hashlib
import unittest

from test_authority_qualification_record import fixture as qualified_fixture
from test_authority_app_proofs import AppAPI, AuthorityReader
from test_authority_closed_artifacts import HistoricalAPI
from trusted_ci_fixtures import snapshot
from trusted_ci_policy import Refusal
import app_proofs
import broker_proofs
import operation_fence


def fixture():
    _, binding, identities, _ = qualified_fixture()
    d = binding['deployment']
    s = snapshot(d['policy'])
    op = dict(kind='merge', operation_id='a' * 32, scope_digest=None, repository_id=123, target='main',
        configuration_revision=binding['configuration_revision'], deployment_digest=binding['deployment_digest'],
        workflow_sha=d['policy']['workflow_sha'], run_id=99, attempt=1, created=1000, execution_deadline=1400,
        pr=s['pr'], head=s['head'], base=s['base'], merge=s['merge'])
    fence = operation_fence.empty(d)
    fence.update(sequence=1, pending=op)
    binding['fence'] = fence
    apis, locators = {}, {}
    for index, purpose in enumerate(d['apps']):
        own = AppAPI(d, identities, purpose)
        result = app_proofs.prove(own, AuthorityReader(), d, identities, purpose,
                                 binding['configuration_revision'], 1000, own.token_api)
        api = HistoricalAPI('proof', purpose)
        api.job['id'], api.artifact['id'] = 77 + index, 555 + index
        api.document = dict(schema_version=2, kind='broker-purpose-proof', operation_id=op['operation_id'], sequence=1,
            configuration_revision=binding['configuration_revision'], deployment_digest=binding['deployment_digest'],
            snapshot=s, issued=1000, completed=1001, expires=1300, result=result)
        api.raw = api.archive('proof.json')
        api.artifact.update(created_at='1970-01-01T00:16:43Z',
                            digest='sha256:' + hashlib.sha256(api.raw).hexdigest())
        apis[purpose] = api
        locators[purpose] = dict(run_id=99, attempt=1, job_id=api.job['id'], artifact_id=api.artifact['id'])
    class MultiAPI:
        def get(self, path):
            return apis['admin'].get(path)
        def pages(self, path, collection):
            if path.endswith('/attempts/1/jobs'): return [api.job for api in apis.values()]
            if path.endswith('/runs/99/artifacts'): return [api.artifact for api in apis.values()]
            raise AssertionError(path)
        def fetch(self, path, **kwargs):
            return next(api.raw for api in apis.values() if path.endswith('/artifacts/' + str(api.artifact['id']) + '/zip'))
    return MultiAPI(), apis, binding, identities, s, locators


class BrokerProofContracts(unittest.TestCase):
    def test_all_five_domains_are_authenticated_for_the_current_operation(self):
        api, apis, b, identities, s, locators = fixture()
        result = broker_proofs.read(api, b, identities, s, locators, 1100)
        self.assertEqual(set(result['documents']), set(b['deployment']['apps']))
        self.assertEqual(result['valid_until'], {p: 1300 for p in b['deployment']['apps']})
        self.assertEqual(result['documents']['merge']['result']['app_id'], 45)
        self.assertEqual(len(result['provenance']), 5)

    def test_missing_wrong_purpose_or_other_attempt_cannot_be_substituted(self):
        for defect in ('missing', 'purpose', 'attempt', 'producer'):
            api, apis, b, identities, s, locators = fixture()
            if defect == 'missing': locators.pop('merge')
            if defect == 'attempt': locators['merge']['attempt'] = 2
            if defect == 'producer': apis['merge'].job['conclusion'] = 'failure'
            if defect == 'purpose':
                apis['merge'].document['result'] = copy.deepcopy(apis['coding'].document['result'])
                apis['merge'].raw = apis['merge'].archive('proof.json')
                apis['merge'].artifact['digest'] = 'sha256:' + hashlib.sha256(apis['merge'].raw).hexdigest()
            with self.subTest(defect=defect), self.assertRaises(Refusal):
                broker_proofs.read(api, b, identities, s, locators, 1100)

    def test_current_configuration_operation_and_expiry_are_required(self):
        for key, bad in [('operation_id', 'b' * 32), ('sequence', 2),
            ('configuration_revision', 'c' * 40), ('deployment_digest', '0' * 64),
            ('expires', 1099), ('completed', 999)]:
            api, apis, b, identities, s, locators = fixture()
            apis['reader'].document[key] = bad
            apis['reader'].raw = apis['reader'].archive('proof.json')
            apis['reader'].artifact['digest'] = 'sha256:' + hashlib.sha256(apis['reader'].raw).hexdigest()
            with self.subTest(key=key), self.assertRaises(Refusal):
                broker_proofs.read(api, b, identities, s, locators, 1100)


if __name__ == '__main__':
    unittest.main()
