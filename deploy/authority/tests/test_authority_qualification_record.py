"""Strict v2 qualification receipt semantics; fixtures are never hosted evidence."""
import backend_test_support
import copy
import hashlib
import unittest

from test_authority_task_admission import fixture as task_fixture
from test_authority_closed_artifacts import HistoricalAPI, locator
from trusted_ci_policy import Refusal, digest
from authority_protocol import configuration_digest
import qualification_record


def fixture():
    _, _, binding, identities, _, task = task_fixture()
    d = binding['deployment']
    d['resources'].update(bundle_sha='e' * 64,
        actions_resource='github-actions:owner/authority:.github/workflows/authority.yml')
    cases = []
    for index, name in enumerate(qualification_record.CASES):
        case = dict(name=name, pr=index + 1, head=hex(index + 1)[2:].zfill(40),
            base='5' * 40, merge='6' * 40, tree='7' * 40, before='5' * 40, after='5' * 40,
            actor_id=19, request_sent=True, http_status=405, denial_category='required_check',
            denied_obligation=d['policy']['check_name'], broker_refusal=None,
            merge_commit=None, merge_parents=[], merge_tree=None, evidence_digest='a' * 64)
        if name == 'positive':
            case.update(after='8' * 40, http_status=200, denial_category=None, denied_obligation=None,
                merge_commit='8' * 40, merge_parents=[case['base'], case['head']], merge_tree=case['tree'])
        elif name == 'missing-approval':
            case.update(denial_category='required_review', denied_obligation=None)
        elif name in ('direct-push', 'coding-update', 'human-update'):
            case.update(denial_category='protected_update', denied_obligation=None,
                        actor_id=17 if name == 'human-update' else 18)
        elif name in qualification_record.BROKER_DENIALS:
            case.update(request_sent=False, http_status=None, denial_category=None,
                denied_obligation=None, broker_refusal=qualification_record.BROKER_DENIALS[name])
        cases.append(case)
    value = dict(schema_version=2, kind='hosted-qualification', configuration_digest=configuration_digest(d),
        qualified_generation=1, adapter=d['adapter'], account=d['account'], fixture_repository_id=789,
        controls_digest='b' * 64, execution=dict(run_id=99, attempt=1, job_id=77,
            resource=d['resources']['actions_resource'], runtime_digest=d['resources']['bundle_sha']),
        model_probe=dict(profile='chatgpt-plan', model_id=d['resources']['model_id'],
            codex_sha=d['resources']['codex_sha'], coding_image=d['resources']['coding_image'],
            thread_id=task['protocol']['thread_id'], turn_id=task['protocol']['turn_id'],
            response_digest='c' * 64), cases=cases, issued=970, completed=1002, expires=1500)
    d.update(generation=2, qualification=digest(value))
    binding['deployment_digest'] = digest(d)
    api = HistoricalAPI('qualification', None)
    api.document = value
    api.raw = api.archive('qualification.json')
    api.artifact.update(created_at='1970-01-01T00:16:43Z', digest='sha256:' + hashlib.sha256(api.raw).hexdigest())
    return api, binding, identities, value


def replace(api, binding, value):
    api.document = value
    api.raw = api.archive('qualification.json')
    api.artifact['digest'] = 'sha256:' + hashlib.sha256(api.raw).hexdigest()
    binding['deployment']['qualification'] = digest(value)
    binding['deployment_digest'] = digest(binding['deployment'])


class QualificationRecordContracts(unittest.TestCase):
    def test_positive_merge_runs_after_every_denial_probe(self):
        self.assertEqual(qualification_record.CASES[-1], 'positive')

    def test_exact_qualified_configuration_advances_once_to_active(self):
        api, b, identities, value = fixture()
        result = qualification_record.read(api, b, identities, locator(), 'b' * 64, 1100)
        self.assertEqual(result['qualification_digest'], b['deployment']['qualification'])
        self.assertEqual(result['expires'], 1500)
        self.assertEqual(result['document'], value)

    def test_digest_configuration_generation_and_producer_substitution_refuse(self):
        for defect in ('digest', 'configuration', 'generation', 'job', 'controls', 'expired', 'model'):
            api, b, identities, value = fixture()
            if defect == 'digest':
                b['deployment']['qualification'] = '0' * 64
            elif defect == 'configuration':
                b['deployment']['resources']['coding_image'] = 'coding@sha256:' + '0' * 64
            elif defect == 'generation':
                b['deployment']['generation'] += 1
            elif defect == 'job':
                api.job['conclusion'] = 'failure'
            else:
                if defect == 'controls': value['controls_digest'] = '0' * 64
                if defect == 'expired': value['expires'] = 1099
                if defect == 'model': value['model_probe']['model_id'] = 'foreign'
                replace(api, b, value)
            with self.subTest(defect=defect), self.assertRaises(Refusal):
                qualification_record.read(api, b, identities, locator(), 'b' * 64, 1100)

    def test_skipped_generic_denials_missing_cases_and_false_positive_merges_refuse(self):
        for defect in ('missing', 'duplicate', 'generic', 'obligation', 'ref-moved', 'parents', 'tree', 'outage-dispatched'):
            api, b, identities, value = fixture()
            if defect == 'missing': value['cases'].pop(0)
            if defect == 'duplicate': value['cases'][1] = copy.deepcopy(value['cases'][0])
            if defect == 'generic': value['cases'][0]['denial_category'] = 'unknown'
            if defect == 'obligation': value['cases'][0]['denied_obligation'] = 'foreign check'
            if defect == 'ref-moved': value['cases'][0]['after'] = '9' * 40
            positive = next(c for c in value['cases'] if c['name'] == 'positive')
            if defect == 'parents': positive['merge_parents'].reverse()
            if defect == 'tree': positive['merge_tree'] = '0' * 40
            if defect == 'outage-dispatched':
                next(c for c in value['cases'] if c['name'] == 'authority-outage')['request_sent'] = True
            replace(api, b, value)
            with self.subTest(defect=defect), self.assertRaises(Refusal):
                qualification_record.read(api, b, identities, locator(), 'b' * 64, 1100)


if __name__ == '__main__':
    unittest.main()
