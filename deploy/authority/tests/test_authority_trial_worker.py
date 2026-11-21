"""Native trial worker/control composition with local transport boundaries."""
import backend_test_support
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import authority_release
import coding_transport
import model_relay
import provenance
import submission
import task_controls
from trial_controls import Controls
import trial_worker
import test_authority_trial_admission as admission_fixture
from test_authority_closed_artifacts import HistoricalAPI
from test_authority_submission import SubmissionHost
from test_authority_task_admission import fixture as task_fixture
from test_authority_controls import ControlHost
from test_authority_coding_transport import WORKER
from test_authority_model_relay import Transport
from trusted_ci_policy import Refusal, digest


def iso(now): return datetime.fromtimestamp(now, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class TrialWorkerContracts(unittest.TestCase):
    def test_public_entry_is_held_before_admission_or_execution(self):
        import authority_release
        with self.assertRaises(authority_release.Held):
            trial_worker.Worker(None).run('approved prompt', None, None)

    @unittest.skipIf(admission_fixture.Fernet is None, 'optional crypto required')
    def test_connected_worker_controls_and_exact_submission_with_fail_closed_boundaries(self):
        for fault in (None, 'cleanup', 'nonce', 'expired', 'fence', 'lost-ready', 'lost-pr', 'consent', 'model-key',
                      'late-journal', 'late-origin', 'late-trial', 'late-software', 'admin-consent', 'cancelled'):
            with self.subTest(fault=fault):
                self.connected(fault)

    @unittest.skipIf(admission_fixture.Fernet is None, 'optional crypto required')
    def test_connected_path_fits_original_windows_with_100ms_transport_latency(self):
        self.connected(None, latency=True)

    def connected(self, fault, latency=False):
        harness = admission_fixture.TrialAdmissionContracts()
        f = harness.fixture({'.github/CODEOWNERS': b'* @maintainer\n'})
        c, env, task, model, proofs, key, reader, host, provision, production, clock, journals = f
        elapsed, wrapped = [10050], set()
        def delay(api, methods):
            if not latency or id(api) in wrapped: return
            wrapped.add(id(api))
            for method in methods:
                original_call = getattr(api, method)
                def call(*args, _original=original_call, **kwargs):
                    elapsed[0] += 1
                    clock[0] = elapsed[0] // 10
                    return _original(*args, **kwargs)
                setattr(api, method, call)
        for api, methods in ((reader, ('get','pages','fetch')), (host, ('get','pages','fetch')),
                             (provision.api, ('get',)), (production.api, ('get',))): delay(api, methods)
        before = production.binding()
        harness.run_local(f)
        host.live['started_at'] = iso(clock[0])
        d, binding, events, receipts = c.binding['deployment'], c.binding, [], []
        self.assertEqual(d['policy']['reviewers'], [17])
        original = reader.pair.hosts['owner/trial']
        bot = d['policy']['coding_actors'][0]
        armed, cancelled = [False], [False]
        read_get = reader.get
        def get(path, *args):
            value = read_get(path, *args)
            if fault and fault.startswith('late-') and armed[0] and '/git/ref/heads/main' in path:
                armed[0] = False
                if fault == 'late-journal':
                    journal = c.store(c.root / 'worker')
                    old = journal.read()
                    journal.write(old, dict(old['value'], approval='changed'))
                elif fault == 'late-origin': production.api.refs['agentic-registry'] = '9' * 40
                elif fault == 'late-trial': host.git.refs['agentic-registry'] = '9' * 40
                elif fault == 'late-software': host.git.refs['main'] = '9' * 40
            return value
        reader.get = get
        class Coding(SubmissionHost):
            def get(self, path):
                if path == '/repos/owner/trial': return dict(id=701, default_branch='main')
                if path.startswith('/users/'):
                    armed[0] = True
                    return dict(id=bot, type='Bot')
                return super().get(path)
            def pages(self, path, collection=None):
                if path == '/installation/repositories': return [dict(id=701)]
                return super().pages(path, collection)
            def post(self, path, body):
                self_outer.assertTrue({'disk-cleaned', 'box-cleaned', 'relay-revoked'} <= set(events))
                value = super().post(path, body)
                if path.endswith('/pulls'):
                    self.prs[-1]['user']['id'] = bot
                    for side in ('base', 'head'): self.prs[-1][side]['repo']['id'] = 701
                    value = copy.deepcopy(self.prs[-1])
                    if fault == 'lost-pr': raise OSError('synthetic lost PR acknowledgement')
                return value
        self_outer = self
        coding = Coding()
        coding.blobs, coding.trees, coding.commits = copy.deepcopy(original.blobs), copy.deepcopy(original.trees), copy.deepcopy(original.commits)
        coding.refs = {'main': c.intent['source_base']}
        class Admin(ControlHost):
            def get(self, path):
                if path == '/repos/owner/trial': return dict(id=701, default_branch='main', allow_merge_commit=True)
                if path == '/repos/owner/trial-authority': return dict(id=702, private=True)
                if '/branches/' in path: return dict(commit=dict(sha=c.intent['source_base']))
                if path.startswith('/users/') and 'bot' in path: return dict(id=bot, type='Bot')
                return super().get(path)
            def pages(self, path, collection=None):
                result = super().pages(path, collection)
                if fault == 'admin-consent' and path.endswith('/hooks'):
                    journal = c.store(c.root / 'worker')
                    old = journal.read()
                    journal.write(old, dict(old['value'], approval='changed'))
                return result
        admin = Admin()
        delay(admin, ('get','pages'))
        delay(coding, ('get','pages','post'))
        admin.rules = reader.rules
        admin_request = dict(schema_version=2, task=task, prompt='Approved trial change',
            **{k:c.intent[k] for k in ('source_base', 'configuration_revision', 'deployment_digest')})
        controls = Controls(c, admin_request)
        admin_job = dict(id=901, run_id=99, head_sha=host.run['head_sha'], name=controls.admin_name(task['task_id']),
                         status='in_progress', conclusion=None, started_at=iso(clock[0]))
        host.jobs.append(admin_job)
        transport = Transport()
        relays = []
        class Relay(model_relay.Relay):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, transport=transport, **kwargs)
                relays.append(self)
            def _start(self, parent):
                self.directory = Path(parent) / 'relay'
                self.directory.mkdir()
            def close(self):
                super().close()
                events.append('relay-revoked')
        class Disk:
            def __init__(self, name, megabytes, **kwargs): self.name = name
            def __enter__(self): events.append('disk-created'); return self
            def __exit__(self, *args):
                events.append('disk-cleaned')
                if fault == 'cleanup': raise OSError('synthetic cleanup failure')
        sample = task_fixture()[-1]['isolation']
        class Box:
            process = None
            stopped = False
            def __init__(self, deployment, *args, **kwargs): self.deployment = deployment
            def _enter(self): events.append('box-created')
            def inspect(self):
                return dict(HostConfig=dict(Tmpfs={'/tmp':'rw', '/home/agentic':'rw'}),
                            Mounts=[dict(Type='volume', Destination='/work', RW=True),
                                    dict(Type='bind', Destination='/run/agentic-model', RW=False)])
            def run(self, argv, cwd):
                if argv[0] == 'stat': return 0, 'ext4'
                return 0, json.dumps({k:v for k,v in sample.items() if k not in ('work_filesystem','writable_mounts','host_mounts')})
            def _attach(self):
                relay = relays[-1]
                relay.forward('Bearer ' + relay.capability, json.dumps(dict(model=d['resources']['model_id'],
                    store=False, stream=True, input=[dict(role='user', content='local fixture')])).encode(), lambda raw:None)
                self.process = subprocess.Popen([sys.executable, '-I', '-c', WORKER], stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
                return self.process
            def stop(self):
                if self.process and self.process.poll() is None: self.process.kill()
                self.stopped = True
            def _export(self, guard):
                self_outer.assertTrue(self.stopped and 'relay-revoked' in events)
                guard(force=True)
                return submission.pack_export({'result.bin':dict(content=b'\x00\xfftrial result', executable=True)})
            def close(self): events.append('box-cleaned')

        def artifact(role, document, live=False):
            a = HistoricalAPI('task-ready' if live else 'task-controls', task['task_id'])
            a.run = copy.deepcopy(host.run)
            a.job = copy.deepcopy(host.live if live else admin_job)
            a.member = role + '.json'
            a.document = document
            a.raw = a.archive(a.member)
            a.artifact.update(id=800 + len(host.artifacts), name=role + '-' + task['task_id'] + '-1',
                created_at=iso(clock[0]), digest='sha256:' + hashlib.sha256(a.raw).hexdigest())
            a.artifact['workflow_run'].update(repository_id=702, head_repository_id=702, head_sha=host.run['head_sha'])
            host.artifacts.append(a)
            return a.artifact['id']
        def upload_admin(name, raw):
            value = json.loads(raw)
            if fault == 'nonce': value['nonce'] = 'e' * 32
            artifact_id = artifact('trial-task-controls', value)
            admin_job.update(status='completed', conclusion='success', completed_at=iso(clock[0]))
            if fault == 'expired': clock[0] += 31
            if fault == 'cancelled': cancelled[0] = True
            return artifact_id
        def upload(name, raw):
            self.assertTrue({'disk-cleaned', 'box-cleaned', 'relay-revoked'} <= set(events))
            if name.startswith('trial-task-ready-'):
                artifact_id = artifact('trial-task-ready', json.loads(raw), live=True)
                if fault == 'lost-ready': raise OSError('synthetic lost readiness acknowledgement')
                controls.collect(admin, dict(env, GITHUB_JOB='trial_task_controls'), upload_admin)
                if fault == 'fence': clock[0] = 1300
                return artifact_id
            receipts.append(json.loads(raw))
            return artifact('trial-task', receipts[-1])
        worker = trial_worker.Worker(c, coding)
        run = lambda: worker._run('Approved trial change', key if fault != 'model-key' else admission_fixture.Fernet.generate_key(),
            upload, digest if fault != 'consent' else lambda x:'bad',
            disk_factory=Disk, relay_factory=Relay, sandbox_factory=Box, cancelled=lambda:cancelled[0])
        with patch.object(authority_release, 'authorize'), patch.object(coding_transport.time, 'time', side_effect=lambda:clock[0]):
            if fault:
                with self.assertRaises((Refusal, OSError)): run()
                self.assertEqual(receipts, [])
                self.assertEqual(len(coding.prs), 1 if fault == 'lost-pr' else 0)
                if fault.startswith('late-'): self.assertEqual(coding.writes, [])
                if fault == 'late-origin': production.api.refs['agentic-registry'] = before['branch_head']
                if fault == 'late-trial': host.git.refs['agentic-registry'] = binding['branch_head']
                if fault == 'late-software': host.git.refs['main'] = binding['software_revision']
                if fault == 'admin-consent':
                    self.assertFalse(any(a.artifact['name'].startswith('trial-task-controls-') for a in host.artifacts))
                if events:
                    counts = (len(events), len(host.artifacts), len(coding.writes))
                    with self.assertRaises(Refusal): run()
                    self.assertEqual(counts, (len(events), len(host.artifacts), len(coding.writes)))
            else:
                result = run()
                counts = (len(events), len(host.artifacts), len(coding.writes))
                self.assertEqual(run(), result)
                self.assertEqual(counts, (len(events), len(host.artifacts), len(coding.writes)))
                self.assertEqual(len(receipts), 1)
                receipt = receipts[0]
                head = coding.commits[receipt['submitted']['head']]
                tree = coding.trees[head['tree']['sha']]
                self.assertEqual(tree['result.bin'][0], '100755')
                self.assertEqual(coding.blobs[tree['result.bin'][1]], b'\x00\xfftrial result')
                self.assertEqual([p['sha'] for p in head['parents']], [c.intent['source_base']])
                self.assertEqual(receipt['protocol']['turn_id'], 'turn-fixture')
                self.assertEqual(receipt['relay']['completed'], 1)
                self.assertFalse(result['hosted_qualified'])
                self.assertFalse(result['enforcement_active'])
                self.assertEqual(transport.calls[0][1], 'SYNTHETIC-ACCESS-ONLY')
                text = json.dumps([receipts, [j.read() for j in journals.values()]])
                for secret in ('SYNTHETIC-ACCESS-ONLY', key.decode()): self.assertNotIn(secret, text)
                with self.assertRaises(Refusal): task_controls.ready(admin_request,binding,900,'e'*64,'f'*32,clock[0])
                with self.assertRaises(Refusal): submission.submit(coding,d,dict(schema_version=2,task_id=task['task_id'],
                    configuration_revision=binding['configuration_revision'],deployment_digest=digest(d),base=c.intent['source_base'],
                    issued=clock[0],run_id=99,attempt=1),{},clock[0])
        self.assertEqual(production.binding(), before)
        self.assertEqual(coding.refs['main'], c.intent['source_base'])

    @unittest.skipIf(admission_fixture.Fernet is None, 'optional crypto required')
    def test_nonce_denial_detects_removed_response_validation(self):
        with patch.object(Controls, 'validate_response', side_effect=lambda value,*args:value):
            with self.assertRaises(AssertionError): self.connected('nonce')


if __name__ == '__main__': unittest.main()
