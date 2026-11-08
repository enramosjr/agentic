"""Real encrypted delivery and source token wiring; parent execution is substituted.

Not an E2E, OCI qualification, or live provider/model/GitHub operation.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parent / 'tests'),
               str(Path(__file__).resolve().parents[2] / '.ai/scripts')]
from test_model_auth import fixture
from test_authority_app_proofs import identities, AppAPI
from test_authority_closed_artifacts import HistoricalAPI
from trusted_ci_policy import digest, Refusal
import registry as registry_backend
import authority_release
import service


class TaskServiceContracts(unittest.TestCase):
    def test_authenticated_access_only_delivery_precedes_source_key_loading_and_parent(self):
        for mode in ('normal','forged','stale-intent'):
            forged = mode == 'forged'
            with self.subTest(mode=mode):
                controller, host, _, _, keys, b, task, _, _ = fixture(False)
                d = copy.deepcopy(b['deployment'])
                d['policy']['merge_actors'] = [19]
                records = identities(d)
                d['resources'].update(identity_digest=digest(records),
                    identity_record=json.dumps(records,sort_keys=True,separators=(',',':')))
                registry = registry_backend.Registry(host,dict(schema_version=2,repository='owner/authority',
                    repository_id=456,registry_branch='agentic-registry'))
                registry.write(None,d)
                controller.registry = registry
                delivery = []
                locator = controller._produce(task,lambda name,raw:(delivery.append(json.loads(raw)),555)[1])
                historical = HistoricalAPI('model-lease',task['task_id'])
                historical.job.update(id=800,started_at='1970-01-01T00:24:59Z',completed_at='1970-01-01T00:25:02Z')
                historical.artifact['created_at'] = '1970-01-01T00:25:01Z'
                for row in (historical.run,historical.job,historical.artifact['workflow_run']): row['head_sha'] = 'a' * 40
                historical.document = delivery[0]
                historical.raw = historical.archive(historical.member)
                historical.artifact['digest'] = 'sha256:' + hashlib.sha256(historical.raw).hexdigest()
                if forged: historical.job['name'] = 'untrusted producer'
                task_job = dict(id=801,run_id=99,head_sha='a' * 40,name='task ('+task['task_id']+')',
                    status='in_progress',conclusion=None)
                class API:
                    def get(self,route):
                        if route.endswith('/actions/runs/99'): return historical.run
                        if '/actions/' in route: return historical.get(route)
                        value = host.get(route)
                        if route == '/repos/owner/authority': value = dict(value,owner={'id':7})
                        return value
                    def pages(self,route,collection):
                        if collection == 'jobs': return [historical.job,task_job]
                        if '/actions/' in route: return historical.pages(route,collection)
                        return host.pages(route,collection)
                    def fetch(self,route,**kwargs): return historical.fetch(route,**kwargs)
                root = AppAPI(d,records,'coding')
                loaded, parents, uploaded = [], [], []
                def app_factory(identity,pem):
                    self.assertEqual((identity,pem),(d['apps']['coding'],'SYNTHETIC-CODING-ROOT'))
                    loaded.append(identity)
                    return root
                outer = self
                class Parent:
                    def __init__(self,reg,authority,source,environment,observed,clock):
                        outer.assertEqual(observed,records)
                        outer.assertEqual(set(environment),{'GITHUB_REPOSITORY_ID','GITHUB_SHA','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','GITHUB_JOB'})
                        outer.assertEqual(source.pages('/installation/repositories','repositories'),[{'id':123}])
                    def _run(self,request,lease,uploader):
                        outer.assertEqual(set(request),{'schema_version','task','source_base','prompt','configuration_revision','deployment_digest'})
                        outer.assertEqual(lease['access_token'],'SYNTHETIC-ACCESS-ONLY')
                        outer.assertNotIn('refresh_token',lease)
                        parents.append(request)
                        return {'fixture':'parent execution tested separately'}
                env = dict(controller.environment,GITHUB_REPOSITORY='owner/authority',GITHUB_TOKEN='SYNTHETIC-READ',
                    GITHUB_JOB='task',AGENTIC_MODEL_DELIVERY_KEY=keys['delivery'],AGENTIC_CODING_PRIVATE_KEY='SYNTHETIC-CODING-ROOT')
                request = dict(schema_version=2,task=task,source_base='a'*40,prompt='Reviewed task',
                    configuration_revision=registry.binding()['configuration_revision'],deployment_digest=digest(d))
                if mode == 'stale-intent': request['deployment_digest'] = 'f'*64
                with self.assertRaises(authority_release.Held): service.task(env,request,'synthetic-node')
                if mode != 'normal':
                    with self.assertRaises(Refusal): service._task(env,request,'synthetic-node',clock=lambda:1503,
                        api_factory=lambda token:API(),app_factory=app_factory,token_factory=root.token_api,
                        uploader_factory=lambda node,environment:None,parent_factory=Parent)
                    self.assertEqual(loaded,[])
                    self.assertEqual(parents,[])
                else:
                    result = service._task(env,request,'synthetic-node',clock=lambda:1503,
                        api_factory=lambda token:API(),app_factory=app_factory,token_factory=root.token_api,
                        uploader_factory=lambda node,environment:None,parent_factory=Parent)
                    self.assertEqual(result,{'fixture':'parent execution tested separately'})
                    self.assertEqual(len(parents),1)
                    self.assertEqual(len(loaded),1)
                    self.assertEqual(set(root.revoked),set(root.visible))

    def test_stale_intent_negative_control_detects_removed_pre_key_guard(self):
        original = service.require
        def broken(condition,message):
            if message != 'prepared task service configuration changed': original(condition,message)
        case = TaskServiceContracts('test_authenticated_access_only_delivery_precedes_source_key_loading_and_parent')
        result = unittest.TestResult()
        with patch.object(service,'require',side_effect=broken): case.run(result)
        self.assertFalse(result.wasSuccessful(), 'stale intent regression failed to detect a removed pre-key guard')


if __name__ == '__main__': unittest.main()
