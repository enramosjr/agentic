"""Warm task/admin rendezvous semantics; no hosted latency qualification."""
import backend_test_support
import copy
import hashlib
import tempfile
import unittest
from unittest.mock import patch

import test_authority_controls as fixtures
from test_authority_closed_artifacts import HistoricalAPI
from trusted_ci_policy import digest, Refusal
import controls


def prepared(folder):
    admin,journal = fixtures.ControlContracts().prepared(folder)
    d = journal.read()
    d.update(state='active',qualification='f'*64)
    d['policy']['merge_actors'] = [19]
    b = dict(deployment=d,configuration_revision='b'*40,deployment_digest=digest(d),
             branch_head='c'*40,fence={'pending':None})
    request = dict(schema_version=2,configuration_revision=b['configuration_revision'],deployment_digest=digest(d),
        source_base='5'*40,prompt='Reviewed task',task=dict(task_id='a'*32,run_id=99,attempt=1,deadline=1800,purpose='task'))
    return admin,b,request


class TaskControlContracts(unittest.TestCase):
    def test_elapsed_admin_observation_and_ready_upload_cannot_be_renewed_by_wall_rollback(self):
        import task_controls
        with tempfile.TemporaryDirectory() as folder:
            admin,b,request = prepared(folder)
            readiness = task_controls.ready(request,b,77,'c'*64,'d'*32,1000)
            location = dict(run_id=99,attempt=1,job_id=77,artifact_id=554)
            # The same wall interval cannot conceal a thirty-one-second observation.
            with patch.object(task_controls,'read_ready',return_value=readiness), \
                 patch.object(task_controls.time,'monotonic',side_effect=[10,41]):
                with self.assertRaisesRegex(Refusal,'original budget'):
                    task_controls.collect(admin,None,lambda:copy.deepcopy(b),request,location,88,lambda:1005)
            def upload(name,raw): return 554
            with patch.object(task_controls,'read_ready',return_value=readiness), \
                 patch.object(task_controls.secrets,'token_hex',return_value='d'*32), \
                 patch.object(task_controls.time,'monotonic',side_effect=[10,131]):
                with self.assertRaisesRegex(Refusal,'rendezvous expired'):
                    task_controls.acquire(None,lambda:copy.deepcopy(b),request,77,'c'*64,upload,lambda:1000,lambda:None)

    def test_ready_is_not_admission_and_closed_readback_is_bound_and_ages_out(self):
        import task_controls
        with tempfile.TemporaryDirectory() as folder:
            admin,b,request = prepared(folder)
            ready = task_controls.ready(request,b,77,'c'*64,'d'*32,1000)
            ready_location = dict(run_id=99,attempt=1,job_id=77,artifact_id=554)
            facts = controls.observe(admin,b['deployment'])
            response = task_controls.response(request,ready,ready_location,b,88,facts,1005,1006)
            api = HistoricalAPI('task-controls',request['task']['task_id'])
            api.job.update(id=88,started_at='1970-01-01T00:16:41Z',completed_at='1970-01-01T00:16:48Z')
            api.artifact.update(created_at='1970-01-01T00:16:47Z')
            location = dict(run_id=99,attempt=1,job_id=88,artifact_id=555)
            def install(value):
                api.document = value
                api.raw = api.archive(api.member)
                api.artifact['digest'] = 'sha256:' + hashlib.sha256(api.raw).hexdigest()
            install(response)
            observed = task_controls.read_response(api,b,request,ready,ready_location,location,1009)
            self.assertEqual(observed['result'],facts)
            with self.assertRaises(Refusal): task_controls.validate_response(observed,request,ready,ready_location,b,1036)
            for field,value in [('nonce','e'*32),('request_digest','f'*64),('export_digest','0'*64)]:
                bad = dict(response,**{field:value})
                install(bad)
                with self.subTest(field=field),self.assertRaises(Refusal):
                    task_controls.read_response(api,b,request,ready,ready_location,location,1009)
            self.assertNotIn('isolation_established',ready)
            self.assertEqual(admin.writes,[])

    def test_only_exact_live_task_readiness_is_accepted_and_it_is_never_closed_evidence(self):
        import task_controls
        import provenance
        with tempfile.TemporaryDirectory() as folder:
            _,b,request = prepared(folder)
            value = task_controls.ready(request,b,77,'c'*64,'d'*32,1000)
            api = HistoricalAPI('task-ready',request['task']['task_id'])
            api.job.update(status='in_progress',conclusion=None)
            api.artifact['created_at'] = '1970-01-01T00:16:40Z'
            api.document = value
            api.raw = api.archive(api.member)
            api.artifact['digest'] = 'sha256:' + hashlib.sha256(api.raw).hexdigest()
            location = dict(run_id=99,attempt=1,job_id=77,artifact_id=555)
            self.assertEqual(task_controls.read_ready(api,b,request,location,1001),value)
            with self.assertRaises(Refusal):
                provenance.authenticated_document(api,b['deployment'],location,'task-ready',request['task']['task_id'],1001)
            for record,field,bad in [('job','status','completed'),('job','id',78),
                ('artifact','created_at','1970-01-01T00:16:39Z'),('artifact','expired',True),
                ('run','head_sha','f'*40)]:
                target = getattr(api,record)
                original = target[field]
                target[field] = bad
                with self.subTest(field=field),self.assertRaises(Refusal):
                    task_controls.read_ready(api,b,request,location,1001)
                target[field] = original

    def test_response_cannot_change_the_retained_ready_artifact_or_observation_time(self):
        import task_controls
        with tempfile.TemporaryDirectory() as folder:
            admin,b,request = prepared(folder)
            ready = task_controls.ready(request,b,77,'c'*64,'d'*32,1000)
            location = dict(run_id=99,attempt=1,job_id=77,artifact_id=554)
            response = task_controls.response(request,ready,location,b,88,controls.observe(admin,b['deployment']),1005,1006)
            for changed in (dict(location,artifact_id=555),dict(location,job_id=78),dict(location,attempt=2)):
                with self.assertRaises(Refusal): task_controls.validate_response(response,request,ready,changed,b,1009)
            for field,bad in [('readback_started',999),('readback_completed',1004),('source_base','6'*40),
                              ('admin_job_id',77),('request_digest','f'*64)]:
                with self.subTest(field=field),self.assertRaises(Refusal):
                    task_controls.validate_response(dict(response,**{field:bad}),request,ready,location,b,1009)
            task_controls.validate_response(response,request,ready,location,b,1035)
            with self.assertRaises(Refusal): task_controls.validate_response(response,request,ready,location,b,1036)


if __name__ == '__main__': unittest.main()
