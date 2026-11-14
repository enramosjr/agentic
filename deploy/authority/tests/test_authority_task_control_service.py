"""Separate admin producer over local GitHub/control fixtures, never live setup."""
import backend_test_support
import copy
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch

from test_authority_task_controls import prepared
from test_authority_app_proofs import identities, AppAPI
from test_authority_closed_artifacts import HistoricalAPI
from trusted_ci_policy import digest, Refusal
import authority_release
import service
import task_controls


class TaskControlServiceContracts(unittest.TestCase):
    def test_admin_observation_follows_live_readiness_and_revokes_before_upload(self):
        for mode in ('normal','forged-ready','mixed-credentials','upload-failure','omitted-bypass'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                admin,b,request = prepared(folder)
                d = b['deployment']
                records = identities(d)
                d['resources']['identity_digest'] = digest(records)
                b['deployment_digest'] = digest(d)
                request['deployment_digest'] = digest(d)
                readiness = task_controls.ready(request,b,77,'c'*64,'d'*32,1000)
                class API(HistoricalAPI):
                    def get(self,path):
                        if path.endswith('/actions/runs/99'): return self.run
                        if path == '/repos/owner/authority': return dict(id=456,private=True,owner={'id':7})
                        return super().get(path)
                    def pages(self,path,collection):
                        if collection == 'jobs': return [self.job,admin_job]
                        return super().pages(path,collection)
                api = API('task-ready',request['task']['task_id'])
                api.job.update(status='in_progress',conclusion=None)
                api.document = readiness
                api.raw = api.archive(api.member)
                api.artifact.update(created_at='1970-01-01T00:16:40Z',
                    digest='sha256:' + hashlib.sha256(api.raw).hexdigest())
                if mode == 'forged-ready': api.artifact['digest'] = 'sha256:'+'0'*64
                admin_job = dict(api.job,id=88,name='task controls ('+request['task']['task_id']+')')
                root = AppAPI(d,records,'admin')
                token_api = root.token_api
                def token_factory(token):
                    base = token_api(token)
                    class Scoped:
                        def get(self,path):
                            if path == '/users/agentic-admin%5Bbot%5D': return base.get(path)
                            return admin.get(path)
                        def pages(self,path,collection=None):
                            if path == '/installation/repositories': return base.pages(path,collection)
                            return admin.pages(path)
                        def fetch(self,*args,**kwargs): return base.fetch(*args,**kwargs)
                    return Scoped()
                class Registry:
                    def binding(self): return copy.deepcopy(b)
                loaded,uploads = [],[]
                def app_factory(identity,pem):
                    self.assertEqual((identity,pem),(d['apps']['admin'],'SYNTHETIC-ADMIN-ROOT'))
                    loaded.append(identity)
                    return root
                def upload(name,raw):
                    self.assertEqual(set(root.revoked),set(root.visible))
                    self.assertNotIn(b'SYNTHETIC-',raw)
                    uploads.append(json.loads(raw))
                    if mode == 'upload-failure': raise OSError('synthetic unknown acknowledgement')
                    return 556
                env = dict(GITHUB_REPOSITORY_ID='456',GITHUB_SHA=d['policy']['workflow_sha'],GITHUB_RUN_ID='99',
                    GITHUB_RUN_ATTEMPT='1',GITHUB_JOB='task_controls',AGENTIC_ADMIN_PRIVATE_KEY='SYNTHETIC-ADMIN-ROOT')
                if mode == 'mixed-credentials': env['AGENTIC_CODING_PRIVATE_KEY'] = 'FORBIDDEN'
                if mode == 'omitted-bypass':
                    original = admin.pages
                    def pages(path):
                        values = original(path)
                        if '/rulesets?' in path:
                            values = copy.deepcopy(values)
                            for value in values: value.pop('bypass_actors',None)
                        return values
                    admin.pages = pages
                with self.assertRaises(authority_release.Held): service.task_controls(env,request,'fixture-node')
                with patch.object(service,'context',return_value=(api,Registry(),copy.deepcopy(b),records)):
                    args = dict(clock=lambda:1009,app_factory=app_factory,token_factory=token_factory,
                                uploader_factory=lambda *args:upload)
                    if mode == 'normal':
                        result = service._task_controls(env,request,'fixture-node',**args)
                        self.assertEqual(result,dict(run_id=99,attempt=1,job_id=88,artifact_id=556))
                        self.assertEqual(len(uploads),1)
                        self.assertEqual(uploads[0]['ready_location']['artifact_id'],555)
                    else:
                        with self.assertRaises((Refusal,OSError,KeyError)):
                            service._task_controls(env,request,'fixture-node',**args)
                    if mode in ('forged-ready','mixed-credentials'): self.assertEqual(loaded,[])
                    self.assertEqual(set(root.revoked),set(root.visible))
                    self.assertEqual(admin.writes,[])


if __name__ == '__main__': unittest.main()
