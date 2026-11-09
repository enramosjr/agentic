"""One native dispatch, exact closed token consumer, original signed run binding."""
import backend_test_support
import copy
import hashlib
import unittest

import credential_workflow
import setup
import trial_handoff
import test_authority_trial_read_staging as staging
from test_authority_closed_artifacts import HistoricalAPI
from trusted_ci_policy import Refusal


@unittest.skipIf(staging.handoff.preparation.jwt is None, 'optional model-auth cryptography environment required')
class Dispatch(unittest.TestCase):
    fixture = staging.handoff.Publication.fixture
    prepared = staging.Delegation.prepared

    def connected(self, lost=False, absent=False):
        c, api, reg, production, clock, published, reader = self.prepared()
        delegate = setup.TrialReadStaging(c, reg, published['revision'], reader, reader.token_api)
        record, _ = trial_handoff.read(production, published['revision'], clock[0])
        proof = HistoricalAPI()
        proof.member = 'trial-handoff.json'
        proof.run.update(id=100, run_attempt=1, event='workflow_dispatch', head_sha=record['pair']['software_revision'],
                         path=record['trial']['deployment']['policy']['workflow'], repository={'id': 702})
        proof.job.update(id=800, run_id=100, name='trial handoff', head_sha=proof.run['head_sha'],
                         started_at='1970-01-01T00:16:41Z', completed_at='1970-01-01T00:16:42Z')
        proof.artifact.update(id=900, name='trial-handoff-' + record['task_id'] + '-1', created_at='1970-01-01T00:16:42Z')
        proof.artifact['workflow_run'].update(id=100, repository_id=702, head_repository_id=702, head_sha=proof.run['head_sha'])
        get, pages, fetch, post = api.get, api.pages, api.fetch, api.post
        dispatched = []
        def send(route, body):
            if not route.endswith('/dispatches'): return post(route, body)
            dispatched.append(copy.deepcopy(body))
            token = api.secrets[setup.TrialReadStaging.NAME]
            scoped = reader.token_api(token)
            class Origin:
                def __init__(self): self.token = token
                def get(self, path): return production.api.get(path)
                def pages(self, *args): return scoped.pages(*args)
            live = copy.deepcopy(proof.job)
            live.update(status='in_progress', conclusion=None)
            env = dict(GITHUB_REPOSITORY_ID='702', GITHUB_SHA=proof.run['head_sha'], GITHUB_JOB='trial_handoff',
                       GITHUB_RUN_ID='100', GITHUB_RUN_ATTEMPT='1', AGENTIC_TRIAL_ORIGIN_TOKEN=token)
            proof.job, closed = live, proof.job
            proof.document = trial_handoff.consume(reg, api, env, body['inputs']['handoff'], Origin(), c.clock)
            proof.job = closed
            proof.raw = proof.archive(proof.member)
            proof.artifact['digest'] = 'sha256:' + hashlib.sha256(proof.raw).hexdigest()
            clock[0] = 1003
            if lost: raise OSError('lost trial dispatch acknowledgement')
        def runs(route, collection=None):
            if collection == 'workflow_runs': return pages(route, collection) + ([proof.run] if dispatched else [])
            if '/runs/100/' in route:
                return [proof.job] if collection == 'jobs' else ([] if absent else [proof.artifact])
            return pages(route, collection)
        api.post, api.pages = send, runs
        api.get = lambda route: copy.deepcopy(proof.run) if '/actions/runs/100' in route else get(route)
        api.fetch = lambda route, **kwargs: proof.raw if '/actions/artifacts/900/zip' in route else fetch(route, **kwargs)
        controller = credential_workflow.TrialWorkflow(delegate, api, c.store(c.root / 'trial-workflow'))
        return controller, c, reg, production, clock, proof, dispatched, published

    def test_one_dispatch_authenticated_consumption_and_bound_execution(self):
        controller, c, reg, production, clock, proof, dispatched, published = self.connected()
        result = controller.run('prompt')
        record, _ = trial_handoff.read(production, result['revision'], clock[0])
        self.assertEqual(record['execution']['handshake'], dict(run_id=100, attempt=1, job_id=800, artifact_id=900))
        self.assertEqual(record['execution']['publication_revision'], published['revision'])
        self.assertEqual(len(dispatched), 1)
        self.assertEqual(dispatched[0]['ref'], 'main')
        self.assertEqual(dispatched[0]['inputs']['mode'], 'qualification')
        self.assertEqual(controller.run('prompt'), result)
        self.assertEqual(len(dispatched), 1)

    def test_unknown_dispatch_ack_observes_exact_handshake_without_another_post(self):
        controller, *rest = self.connected(lost=True)
        with self.assertRaises(OSError): controller.run('prompt')
        result = controller.run('prompt')
        self.assertEqual(result['run_id'], 100)
        self.assertEqual(len(rest[5]), 1)

    def test_missing_closed_consumer_stays_pending_without_redispatch(self):
        controller, *rest = self.connected(absent=True)
        for _ in range(2):
            with self.assertRaisesRegex(Refusal, 'pending'): controller.run('prompt')
        self.assertEqual(len(rest[5]), 1)

    def test_bound_execution_ref_moving_during_recursive_authentication_is_refused(self):
        controller, c, reg, production, clock, proof, dispatched, published = self.connected()
        result = controller.run('prompt')
        get = production.api.get
        def race(route):
            value = get(route)
            if route.endswith('/git/ref/heads/agentic-trial-' + result['task_id']):
                production.api.refs['agentic-trial-' + result['task_id'] + '-execution'] = published['revision']
            return value
        production.api.get = race
        with self.assertRaises(Refusal): trial_handoff.read(production, result['revision'], clock[0])
