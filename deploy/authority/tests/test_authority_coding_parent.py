"""Outer task composition with actual pipes/Git objects and fixture kernel facts.

This is deliberately not OCI, provider, model, or hosted-task qualification.
"""
import backend_test_support
import copy
import hashlib
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

from test_authority_coding_transport import WORKER
from test_authority_task_admission import fixture
from test_authority_closed_artifacts import HistoricalAPI
from trusted_ci_policy import digest, Refusal
from trusted_ci_fixtures import snapshot
import authority_release
import submission
import task_admission
import task_controls


class CodingParentContracts(unittest.TestCase):
    def test_control_expiry_cases_detect_a_removed_validation_guard(self):
        case = CodingParentContracts('test_actual_protocol_and_exact_submission_follow_all_worker_cleanup')
        result = unittest.TestResult()
        with patch.object(task_controls,'validate_response',side_effect=lambda value,*args:value):
            case.run(result)
        self.assertFalse(result.wasSuccessful(), 'expiry cases failed to detect removed controls validation')

    def test_actual_protocol_and_exact_submission_follow_all_worker_cleanup(self):
        import coding_parent
        for mode in ('normal', 'cleanup', 'expired-admission', 'expired-upload', 'pending-configuration',
                     'missing-controls', 'stale-controls', 'controls-expire-between-writes', 'monotonic-expiry'):
            cleanup_failure = mode == 'cleanup'
            with self.subTest(mode=mode):
                source, _, binding, identities, _, sample = fixture()
                source.refs = {'main':'a' * 40}
                source.prs.clear()
                source.writes.clear()
                now = int(time.time())
                clock = [now]
                monotonic_shift = [0]
                real_monotonic = time.monotonic
                d = binding['deployment']
                d['expires'] = now + 900
                d['resources'].update(model_session='a' * 32, model_account='b' * 64, model_client='oaiapp_synthetic')
                binding['deployment_digest'] = digest(d)
                binding['fence'] = {'pending': {'kind':'configuration'} if mode == 'pending-configuration' else None}
                task = dict(task_id='d' * 32, run_id=99, attempt=1, deadline=now + 600, purpose='task')
                lease = dict(schema_version=1, kind='model-access-lease', authority_repository_id=456,
                    session_id='a' * 32, identity_digest='b' * 64, client_id='oaiapp_synthetic', auth_generation=1,
                    configuration_revision=binding['configuration_revision'], deployment_digest=binding['deployment_digest'],
                    repository_id=123, target='main', model_id=d['resources']['model_id'], issued=now, expires=now + 600,
                    access_token='SYNTHETIC-UPSTREAM-ACCESS', scopes=['chatgpt.tokens.use.direct','resource.invoke'],
                    **{k:v for k,v in task.items() if k != 'deadline'})
                class Registry:
                    def binding(self): return copy.deepcopy(binding)
                class API(HistoricalAPI):
                    def __init__(self, *args):
                        super().__init__(*args)
                        self.ready_api = self.admin_api = None
                    def get(self, route):
                        if mode == 'expired-admission' and source.writes:
                            clock[0] = task['deadline']
                        if route.endswith('/actions/runs/99'): return self.run
                        return super().get(route)
                    def pages(self, route, collection):
                        if route.endswith('/attempts/1/jobs') and self.ready_api is not None:
                            return [self.job] + ([] if self.admin_api is None else [self.admin_api.job])
                        if route.endswith('/runs/99/artifacts') and self.ready_api is not None:
                            return [self.artifact,self.ready_api.artifact] + ([] if self.admin_api is None else [self.admin_api.artifact])
                        return super().pages(route,collection)
                    def fetch(self, route, **kwargs):
                        if route.endswith('/artifacts/554/zip'): return self.ready_api.raw
                        if route.endswith('/artifacts/556/zip'): return self.admin_api.raw
                        return super().fetch(route,**kwargs)
                api = API('task', task['task_id'])
                api.job.update(status='in_progress', conclusion=None,
                    started_at=datetime.fromtimestamp(now, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
                environment = dict(GITHUB_REPOSITORY_ID='456',GITHUB_SHA=d['policy']['workflow_sha'],
                    GITHUB_RUN_ID='99',GITHUB_RUN_ATTEMPT='1',GITHUB_JOB='task')
                events, uploaded = [], []
                class Disk:
                    def __init__(self, name, megabytes, **kwargs): self.name = name
                    def __enter__(self): events.append('disk-created'); return self
                    def __exit__(self, *args):
                        events.append('disk-cleaned')
                        if cleanup_failure: raise OSError('synthetic owned disk cleanup failure')
                class Relay:
                    failed = False
                    def __init__(self, *args, **kwargs): pass
                    def _start(self, parent):
                        self.directory = Path(parent) / 'relay-fixture'
                        self.directory.mkdir()
                    def close(self):
                        if 'relay-revoked' not in events: events.append('relay-revoked')
                    def result(self): return dict(completed_inference=True, requests=1, completed=1,
                        response_digests=['f' * 64], model_execution_qualified=False)
                class Box:
                    process = None
                    stopped = False
                    def __init__(self, deployment, *args, **kwargs): self.deployment = deployment
                    def _enter(self): events.append('box-created'); return self
                    def inspect(self): return dict(HostConfig=dict(Tmpfs={'/tmp':'rw','/home/agentic':'rw'}),
                        Mounts=[dict(Type='volume',Destination='/work',RW=True),
                                dict(Type='bind',Destination='/run/agentic-model',RW=False)])
                    def run(self, argv, cwd):
                        if argv[0] == 'stat': return 0, 'ext4'
                        return 0, json.dumps({k:v for k,v in sample['isolation'].items() if k not in
                            ('work_filesystem','writable_mounts','host_mounts')})
                    def _attach(self):
                        self.process = subprocess.Popen([sys.executable,'-I','-c',WORKER], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
                        return self.process
                    def stop(self):
                        if self.process is not None and self.process.poll() is None: self.process.kill()
                        self.stopped = True
                        events.append('box-stopped')
                    def _export(self, guard):
                        assert self.stopped and 'relay-revoked' in events
                        guard()
                        return submission.pack_export({'exact.bin':dict(content=b'\x00\xffedited result',executable=False)})
                    def close(self):
                        events.append('box-cleaned')
                original_fetch, original_post = source.fetch, source.post
                def fetch(route, **kwargs):
                    if '/git/blobs/' in route and kwargs.get('method','GET') == 'GET': return source.get(route)
                    return original_fetch(route, **kwargs)
                def post(route, body):
                    self.assertTrue({'disk-cleaned','box-cleaned','relay-revoked'} <= set(events))
                    result = original_post(route, body)
                    if mode == 'controls-expire-between-writes': clock[0] += 31
                    if mode == 'monotonic-expiry':
                        monotonic_shift[0] += 31
                        clock[0] -= 1
                    return result
                source.fetch, source.post = fetch, post
                def uploader(name, raw):
                    if name.startswith('task-ready-'):
                        self.assertTrue({'disk-cleaned','box-cleaned','relay-revoked'} <= set(events))
                        ready = json.loads(raw)
                        iso = lambda value: datetime.fromtimestamp(value,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                        api.ready_api = HistoricalAPI('task-ready',task['task_id'])
                        api.ready_api.document = ready
                        api.ready_api.raw = api.ready_api.archive('task-ready.json')
                        api.ready_api.artifact.update(id=554,created_at=iso(clock[0]),
                            digest='sha256:' + hashlib.sha256(api.ready_api.raw).hexdigest())
                        if mode != 'missing-controls':
                            api.admin_api = HistoricalAPI('task-controls',task['task_id'])
                            api.admin_api.job.update(id=88,started_at=iso(now),completed_at=iso(clock[0]))
                            facts = dict(schema_version=2,deployment_digest=digest(d),generation=d['generation'],base='a'*40,
                                controls_digest='1'*64,owners_digest='2'*64,access_digest='3'*64,automation_digest='4'*64,
                                coding_bot_id=d['policy']['coding_actors'][0],
                                required_checks=[dict(context=d['policy']['check_name'],integration_id=d['policy']['app_id'])],
                                isolation_established=False,enforcement_active=False)
                            api.admin_api.document = task_controls.response(request,ready,
                                dict(run_id=99,attempt=1,job_id=77,artifact_id=554),binding,88,facts,clock[0],clock[0])
                            api.admin_api.raw = api.admin_api.archive('task-controls.json')
                            api.admin_api.artifact.update(id=556,created_at=iso(clock[0]),
                                digest='sha256:' + hashlib.sha256(api.admin_api.raw).hexdigest())
                            if mode == 'stale-controls': clock[0] += 31
                            if mode == 'monotonic-expiry': clock[0] += 10
                        return 554
                    self.assertEqual(name, 'task-' + task['task_id'] + '-1')
                    self.assertNotIn(lease['access_token'].encode(),raw)
                    uploaded.append(json.loads(raw))
                    if mode == 'expired-upload': clock[0] = task['deadline']
                    return 555
                parent = coding_parent.Parent(Registry(), api, source, environment, identities, clock=lambda: clock[0])
                request = dict(schema_version=2, task=task, source_base='a' * 40, prompt='Approved local fixture',
                    configuration_revision=binding['configuration_revision'],deployment_digest=binding['deployment_digest'])
                with self.assertRaises(authority_release.Held): parent.run(request, lease, uploader)
                self.assertEqual(events, [])
                if mode == 'pending-configuration':
                    with self.assertRaises(Refusal): parent._run(request, lease, uploader,
                        disk_factory=Disk,relay_factory=Relay,sandbox_factory=Box)
                    self.assertEqual(events,[])
                    self.assertEqual(source.writes,[])
                    self.assertEqual(uploaded,[])
                elif cleanup_failure:
                    with self.assertRaises(OSError): parent._run(request, lease, uploader,
                        disk_factory=Disk, relay_factory=Relay, sandbox_factory=Box)
                    self.assertEqual(source.writes, [])
                    self.assertEqual(uploaded, [])
                elif mode.startswith('expired-'):
                    with self.assertRaises(Refusal): parent._run(request, lease, uploader,
                        disk_factory=Disk,relay_factory=Relay,sandbox_factory=Box)
                    self.assertTrue(source.writes)
                    self.assertEqual(len(uploaded), 1 if mode == 'expired-upload' else 0)
                elif mode in ('missing-controls','stale-controls','controls-expire-between-writes','monotonic-expiry'):
                    with patch.object(coding_parent.time,'monotonic',side_effect=lambda:real_monotonic()+monotonic_shift[0]):
                        with self.assertRaises(Refusal): parent._run(request,lease,uploader,
                            disk_factory=Disk,relay_factory=Relay,sandbox_factory=Box)
                    self.assertEqual(len(source.writes),1 if mode in ('controls-expire-between-writes','monotonic-expiry') else 0)
                    self.assertEqual(uploaded,[])
                else:
                    result = parent._run(request, lease, uploader, disk_factory=Disk,relay_factory=Relay,sandbox_factory=Box)
                    self.assertEqual(result['artifact_id'],555)
                    self.assertEqual(len(uploaded),1)
                    receipt = uploaded[0]
                    self.assertTrue(receipt['cleanup_complete'])
                    self.assertEqual(receipt['isolation'],sample['isolation'])
                    head = source.commits[receipt['submitted']['head']]
                    tree = source.trees[head['tree']['sha']]
                    self.assertEqual(set(tree),{'exact.bin'})
                    self.assertEqual(source.blobs[tree['exact.bin'][1]],b'\x00\xffedited result')
                    at = max(int(time.time()), receipt['completed'])
                    iso = lambda value: datetime.fromtimestamp(value,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                    api.document = receipt
                    api.raw = api.archive('task.json')
                    api.job.update(status='completed',conclusion='success',completed_at=iso(at + 2))
                    api.artifact.update(created_at=iso(at + 1),digest='sha256:' + hashlib.sha256(api.raw).hexdigest())
                    coordinates = dict(run_id=99,attempt=1,job_id=77,artifact_id=555)
                    candidate = snapshot(d['policy'])
                    candidate.update(pr=receipt['submitted']['pr'],head=receipt['submitted']['head'])
                    admitted = task_admission.read(source,api,binding,identities,candidate,coordinates,task['task_id'],at + 3)
                    self.assertTrue(admitted['admission_established'])
                    self.assertEqual(admitted['document'],receipt)


if __name__ == '__main__': unittest.main()
