"""Read-only broker collection to one fixture merge; never hosted acceptance."""
import backend_test_support
import copy
from datetime import datetime, timezone
import hashlib
import io
import json
import unittest
import zipfile

import test_authority_task_admission as task_fixtures
import test_authority_submission as submission_fixtures
import test_authority_broker_proofs as proof_fixtures
from trusted_ci_policy import Refusal, digest
from trusted_ci_fixtures import snapshot
import broker_evidence
import broker_proofs
import checks
import control_rendezvous
import merge_receipts
import merge_window
import qualification_record
import submission


def stamp(value):
    return datetime.fromtimestamp(value, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class AuthorityAPI:
    def __init__(self, d, clock):
        self.d, self.clock = d, clock
        self.jobs, self.artifacts, self.raw, self.documents = [], [], {}, {}
        self.revoked_purposes = set()
        self.run = dict(id=99, path=d['policy']['workflow'], workflow_id=33,
            repository={'id': 456}, head_sha=d['policy']['workflow_sha'], run_attempt=1,
            event='schedule', head_branch='main')

    def add(self, role, key, document, job_id, started=960, completed=1020, created=1003):
        names = {'evidence': ('verify (' + str(key) + ')', 'evidence-' + str(key)),
            'proof': ('proof (' + str(key) + ')', 'proof-' + str(key)),
            'final-proof': ('final proof (' + str(key) + ')', 'final-proof-' + str(key)),
            'task': ('task (' + str(key) + ')', 'task-' + str(key)),
            'qualification': ('hosted qualification', 'qualification'),
            'controls': ('controls (' + str(key) + ')', 'controls-' + str(key))}
        job_name, name = names[role]
        job = dict(id=job_id, run_id=99, head_sha=self.d['policy']['workflow_sha'],
            name=job_name, status='completed', conclusion='success', started_at=stamp(started), completed_at=stamp(completed))
        existing = next((j for j in self.jobs if j['id'] == job_id), None)
        if existing is not None: existing.update(job)
        else: self.jobs.append(job)
        artifact_id = 1000 + len(self.artifacts)
        artifact = dict(id=artifact_id, name=name + '-1', expired=False, created_at=stamp(created),
            workflow_run=dict(id=99, repository_id=456, head_repository_id=456, head_sha=self.d['policy']['workflow_sha']))
        self.artifacts.append(artifact)
        self.documents[artifact_id] = document
        self.replace(artifact_id, document, role + '.json')
        return dict(run_id=99, attempt=1, job_id=job_id, artifact_id=artifact_id)

    def replace(self, identity, value, member):
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as archive:
            archive.writestr(member, json.dumps(value))
        self.raw[identity] = output.getvalue()
        next(a for a in self.artifacts if a['id'] == identity)['digest'] = 'sha256:' + hashlib.sha256(output.getvalue()).hexdigest()

    def get(self, path):
        if path == '/repos/owner/authority': return dict(id=456, private=True, owner={'id': 7})
        if path.endswith('/actions/runs/99/attempts/1') or path.endswith('/actions/runs/99'): return self.run
        if path.endswith('/actions/workflows/33'): return dict(id=33, path=self.d['policy']['workflow'])
        raise AssertionError(path)

    def pages(self, path, collection):
        if path.endswith('/runs/99/attempts/1/jobs'): return self.jobs
        if path.endswith('/runs/99/artifacts'): return self.artifacts
        raise AssertionError(path)

    def fetch(self, path, **kwargs):
        return self.raw[int(path.split('/')[-2])]

    def upload(self, name, raw):
        if any(a['name'] == name for a in self.artifacts): raise Refusal('fixture provider conflict')
        identity = 2000 + len(self.artifacts)
        self.artifacts.append(dict(id=identity, name=name, expired=False, created_at=stamp(self.clock[0]),
            workflow_run=dict(id=99, repository_id=456, head_repository_id=456, head_sha=self.d['policy']['workflow_sha'])))
        self.replace(identity, json.loads(raw), 'receipt.json')
        return identity


class SourceAPI(submission_fixtures.SubmissionHost):
    def __init__(self):
        super().__init__()
        self.checks, self.reviews, self.merges = [], [], []
        self.current_base = '5' * 40
        self.merge_head, self.merge_tree = None, '9' * 40

    def get(self, path):
        if '/branches/main' in path: return {'commit': {'sha': self.current_base}}
        if '/git/ref/pull/' in path: return {'object': {'sha': '6' * 40}}
        if path.endswith('/git/commits/' + '6' * 40):
            return dict(sha='6' * 40, tree={'sha': self.merge_tree},
                        parents=[{'sha': self.current_base}, {'sha': self.merge_head}])
        return super().get(path)

    def pages(self, path, collection=None):
        if '/check-runs' in path: return self.checks
        if path.endswith('/reviews'): return self.reviews
        return super().pages(path, collection)

    def merge(self, repository, pr, head, timeout):
        self.merges.append((repository, pr, head, timeout))
        return {'merged': True, 'sha': '8' * 40}


def fixture():
    _, proof_apis, b, identities, _, _ = proof_fixtures.fixture()
    d = b['deployment']
    clock, source = [1090], SourceAPI()
    _, request, files = submission_fixtures.fixture()
    request['deployment_digest'] = digest(d)
    submitted = submission.submit(source, d, request, files, 1001)
    source.merge_head = submitted['head']
    source.prs[0]['base']['sha'] = source.current_base
    s = snapshot(d['policy'])
    s.update(pr=submitted['pr'], head=submitted['head'])
    b['fence']['pending'].update(pr=s['pr'], head=s['head'], execution_deadline=1400)
    api = AuthorityAPI(d, clock)
    locators = dict(proofs={})
    for index, purpose in enumerate(('admin', 'reader', 'issuer', 'coding', 'merge')):
        value = copy.deepcopy(proof_apis[purpose].document)
        value['snapshot'] = s
        locators['proofs'][purpose] = api.add('proof', purpose, value, 100 + index)
    result = dict(schema_version=2, deployment_digest=digest(d), generation=d['generation'], snapshot=s,
        adapter=d['adapter'], execution=dict(run_id=99, attempt=1, job_id=200, account=d['account'],
        resource=d['resources']['actions_resource']), outcomes=[{'id': c, 'status': 'success'} for c in d['policy']['checks']])
    evidence = dict(schema_version=2, kind='actions', registry_revision=b['configuration_revision'],
        result=dict(schema_version=2, report=result, cleanup_complete=True, enforcement_active=False))
    locators['evidence'] = api.add('evidence', s['pr'], evidence, 200, started=1010, completed=1080, created=1070)
    _, _, _, _, _, task = task_fixtures.fixture()
    task.update(submitted=submitted, deployment_digest=digest(d))
    task['execution']['job_id'] = 201
    locators['task'] = dict(task_id=task['task_id'], locator=api.add('task', task['task_id'], task, 201))
    _, _, _, qualification = proof_fixtures.qualified_fixture()
    locators['qualification'] = api.add('qualification', None, qualification, 77)
    coordinates = dict(configuration_revision=b['configuration_revision'], operation=b['fence']['pending'], sequence=1,
        issuer_installation_id=identities['apps']['issuer']['installation_id'], evidence_job_id=200,
        evidence_digest=digest(evidence), task_digest=digest(task))
    check = checks.publication_body(d, s, evidence, coordinates, 1090)
    source.checks = [dict(check, id=300, app={'id': d['apps']['issuer']})]
    source.reviews = [dict(id=400, state='APPROVED', commit_id=s['head'], user={'id': 17, 'type': 'User'})]
    api.jobs.append(dict(id=900, run_id=99, head_sha=d['policy']['workflow_sha'], name='broker (' + str(s['pr']) + ')',
        status='in_progress', conclusion=None, started_at=stamp(1085), completed_at=None))
    class Registry:
        def binding(self): return copy.deepcopy(b)
    return Registry(), source, api, b, identities, s, locators, clock


def execute(f, defect=None, final_defect=None):
    registry, source, api, b, identities, s, locators, clock = f
    prepared = broker_evidence.preload(registry, source, api, identities, 900, locators, lambda: clock[0])
    clock[0] = 1099
    ready = control_rendezvous.ready(b, 900, 'c' * 32, clock[0])
    store = merge_receipts.ActionsReceipts(api, registry.binding, 900, lambda: clock[0], uploader=api.upload)
    store.append('control-ready', ready)
    facts = dict(schema_version=2, deployment_digest=b['deployment_digest'], generation=b['deployment']['generation'],
        base=s['base'], controls_digest='b' * 64, owners_digest='b' * 64, access_digest='c' * 64,
        automation_digest='d' * 64, coding_bot_id=18, isolation_established=False, enforcement_active=False,
        required_checks=[{'context': b['deployment']['policy']['check_name'], 'integration_id': 42}])
    response = control_rendezvous.response(ready, b, 900, 1100, 1101, facts)
    control_locator = api.add('controls', s['pr'], response, 202, started=1085, completed=1103, created=1102)
    clock[0] = 1104
    if defect: defect(f, control_locator)
    final_locators = {}
    for index, purpose in enumerate(('admin', 'reader', 'issuer', 'coding', 'merge')):
        job_id = 301 + index
        api.jobs.append(dict(id=job_id, run_id=99, head_sha=b['deployment']['policy']['workflow_sha'],
            name='final proof (' + purpose + ')', status='in_progress', conclusion=None,
            started_at=stamp(1090), completed_at=None))
        class OwnAPI(proof_fixtures.AppAPI):
            def get(self, path):
                result = super().get(path)
                if self.purpose in api.revoked_purposes and ('/installations/' in path or path.endswith('/installation')):
                    result['suspended_at'] = stamp(1099)
                return result
        own = OwnAPI(b['deployment'], identities, purpose)
        env = dict(GITHUB_REPOSITORY_ID='456', GITHUB_SHA=b['deployment']['policy']['workflow_sha'],
            GITHUB_RUN_ID='99', GITHUB_RUN_ATTEMPT='1', GITHUB_JOB=purpose + '_final_proof')
        ready_artifact = next(a for a in api.artifacts if a['name'].endswith('-control-ready'))
        ready_locator = dict(kind='control-ready', name=ready_artifact['name'], artifact_id=ready_artifact['id'],
                             archive_digest=ready_artifact['digest'])
        value = broker_proofs.refresh(own, api, registry, identities, purpose, env, 900, ready_locator,
                                       lambda: 1100, own.token_api)
        final_locators[purpose] = api.add('final-proof', purpose, value, job_id, started=1090, completed=1103, created=1102)
    if final_defect: final_defect(f, final_locators)
    gate = broker_evidence.finish(registry, source, api, identities, prepared, ready, control_locator,
                                  final_locators, lambda: clock[0])
    return merge_window.dispatch(gate, registry.binding, store, source, lambda: clock[0])


class BrokerCollectionContracts(unittest.TestCase):
    def test_missing_replayed_or_old_final_capabilities_cannot_fall_back_to_preload(self):
        for defect in ('missing', 'nonce', 'stale', 'producer', 'artifact'):
            f = fixture()
            def mutate(values, final_locators):
                api = values[2]
                if defect == 'missing':
                    final_locators.pop('issuer')
                    return
                loc = final_locators['issuer']
                if defect == 'artifact':
                    next(a for a in api.artifacts if a['id'] == loc['artifact_id'])['expired'] = True
                    return
                if defect == 'producer':
                    next(j for j in api.jobs if j['id'] == loc['job_id'])['conclusion'] = 'failure'
                    return
                value = api.documents[loc['artifact_id']]
                if defect == 'nonce': value['ready_nonce'] = '0' * 32
                if defect == 'stale': value['issued'] = 1000
                api.replace(loc['artifact_id'], value, 'final-proof.json')
            with self.subTest(defect=defect), self.assertRaises(Refusal):
                execute(f, final_defect=mutate)
            self.assertEqual(f[1].merges, [])

    def test_revocation_after_preload_retains_old_artifacts_but_blocks_dispatch(self):
        for purpose in ('admin', 'reader', 'issuer', 'coding', 'merge'):
            f = fixture()
            original = copy.deepcopy(f[2].artifacts[:5])
            def revoke(values, locator):
                values[2].revoked_purposes.add(purpose)
            with self.subTest(purpose=purpose), self.assertRaises(Refusal):
                execute(f, revoke)
            self.assertEqual(f[2].artifacts[:5], original)
            self.assertEqual(f[1].merges, [])

    def test_real_validators_and_artifact_store_reach_one_expected_head_fixture_merge(self):
        f = fixture()
        result = execute(f)
        self.assertEqual(result['state'], 'submitted')
        self.assertEqual(f[1].merges, [('owner/project', 1, f[5]['head'], 30)])
        names = [a['name'] for a in f[2].artifacts]
        self.assertEqual(sum(n.endswith('-dispatch') for n in names), 1)

    def test_missing_or_invalid_static_evidence_blocks_without_merge(self):
        for defect in ('missing-proof', 'failed-producer', 'qualification', 'cleanup', 'task'):
            f = fixture()
            _, source, api, _, _, _, locators, _ = f
            if defect == 'missing-proof': locators['proofs'].pop('merge')
            if defect == 'failed-producer': api.jobs[0]['conclusion'] = 'failure'
            if defect in ('qualification', 'cleanup', 'task'):
                loc = locators['task']['locator'] if defect == 'task' else locators[('evidence' if defect == 'cleanup' else defect)]
                value = api.documents[loc['artifact_id']]
                if defect == 'qualification': value['qualified_generation'] += 1
                if defect == 'cleanup': value['result']['cleanup_complete'] = False
                if defect == 'task': value['cleanup_complete'] = False
                api.replace(loc['artifact_id'], value, ('evidence' if defect == 'cleanup' else defect) + '.json')
            with self.subTest(defect=defect), self.assertRaises(Refusal): execute(f)
            self.assertEqual(source.merges, [])

    def test_changed_refs_review_check_fence_and_stale_controls_block(self):
        for defect in ('base', 'review', 'issuer', 'fence', 'age', 'artifact', 'unsupported-check'):
            f = fixture()
            def mutate(values, locator):
                _, source, api, b, _, _, _, clock = values
                if defect == 'base': source.current_base = '0' * 40
                if defect == 'review': source.reviews = []
                if defect == 'issuer': source.checks[0]['app']['id'] = 999
                if defect == 'fence': b['fence']['pending']['operation_id'] = 'd' * 32
                if defect == 'age': clock[0] = 1131
                if defect == 'artifact': api.artifacts[0]['expired'] = True
                if defect == 'unsupported-check':
                    value = api.documents[locator['artifact_id']]
                    value['result']['required_checks'].append(dict(context='Any source', integration_id=None))
                    api.replace(locator['artifact_id'], value, 'controls.json')
            with self.subTest(defect=defect), self.assertRaises(Refusal): execute(f, mutate)
            self.assertEqual(f[1].merges, [])


if __name__ == '__main__':
    unittest.main()
