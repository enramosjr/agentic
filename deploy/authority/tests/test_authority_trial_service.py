"""Native configuration -> once dispatch -> real protected Worker and separate Controls.

Only GitHub/OAuth/OCI/kernel/model transports are fixtures. Crypto, source objects,
model authorization, App proofs, worker subprocess protocol, relay, cleanup,
readiness authentication, administrative observation and PR submission are real.
"""
import backend_test_support
import base64
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import coding_transport
import model_relay
import service
import submission
import test_authority_trial_hosted as hosted
from artifact_uploader import document_member
from test_authority_app_proofs import AppAPI
from test_authority_closed_artifacts import HistoricalAPI
from test_authority_coding_transport import WORKER
from test_authority_controls import ControlHost
from test_authority_model_relay import Transport
from test_authority_submission import SubmissionHost
from test_authority_task_admission import fixture as task_fixture
from trusted_ci_github import HostRefusal
from trusted_ci_policy import Refusal


def iso(value): return datetime.fromtimestamp(value, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


@unittest.skipIf(hosted.workflow.staging.handoff.preparation.jwt is None, 'optional cryptography required')
class TrialService(unittest.TestCase):
    fixture = hosted.Hosted.fixture
    prepared = hosted.Hosted.prepared
    connected = hosted.Hosted.connected
    configured = hosted.Hosted.configured

    def test_native_to_worker_independent_controls_and_exact_fixture_pr(self):
        self.exercise()

    def test_complete_service_path_fits_unchanged_windows_at_100ms_per_request(self):
        self.exercise(latency=True)

    def test_cleanup_nonce_and_unknown_submission_fail_closed(self):
        for fault in ('cleanup', 'nonce', 'lost-pr'):
            with self.subTest(fault=fault): self.exercise(fault)

    def exercise(self, fault=None, latency=False, continuation=None):
        continuation_base = None
        f = self.configured()
        native, registry, origin, clock, env, hint, model, proofs, delivery, jobs, artifacts = f
        api, d, events, receipts = registry.api, registry.read(), [], []
        elapsed, depth = [clock[0] * 10], [0]
        def delay(transport, methods):
            if not latency: return
            for method in methods:
                original = getattr(transport,method)
                def invoke(*args,_original=original,**kwargs):
                    if depth[0]: return _original(*args,**kwargs)
                    depth[0] += 1
                    elapsed[0] += 1
                    clock[0] = elapsed[0] // 10
                    try: return _original(*args,**kwargs)
                    finally: depth[0] -= 1
                setattr(transport,method,invoke)
        delay(api,('get','pages','fetch','post'))
        delay(origin.api,('get','post','fetch'))
        delay(origin.reader,('pages',))
        ids = __import__('app_proofs').load_identities(d)
        env = dict(env, AGENTIC_TRIAL_ORIGIN_TOKEN=api.secrets['AGENTIC_TRIAL_ORIGIN_TOKEN'])
        prepare_job = dict(id=819, run_id=100, head_sha=d['policy']['workflow_sha'], name='trial preparation',
                           status='in_progress', conclusion=None, started_at=iso(clock[0]))
        jobs.append(prepare_job)
        factory = lambda token: api if token == env['GITHUB_TOKEN'] else origin.reader
        request = service._trial(dict(env, GITHUB_JOB='trial_prepare'), dict(handoff=json.loads(hint), prompt='prompt'),
                                 'fixture-node', 'trial-prepare', clock=native.clock, api_factory=factory)
        self.assertEqual(request['task']['run_id'],100)
        parent = next(j for j in jobs if j['name'] == 'hosted qualification')
        admin_job = dict(id=821, run_id=100, head_sha=d['policy']['workflow_sha'],
            name='trial task controls (' + request['task']['task_id'] + ')', status='in_progress', conclusion=None,
            started_at=iso(clock[0]))
        jobs.append(admin_job)
        base = request['source_base']
        commit = api.get('/repos/owner/trial/git/commits/' + base)
        tree = api.get('/repos/owner/trial/git/trees/' + commit['tree']['sha'] + '?recursive=1')['tree']
        outer, bot = self, ids['apps']['coding']['actor_id']
        class Coding(SubmissionHost):
            def get(self, route):
                if route == '/repos/owner/trial':
                    return dict(id=701, private=True, owner={'id':7}, default_branch='main', allow_merge_commit=True)
                if route.startswith('/users/'): return dict(id=bot, type='Bot')
                return super().get(route)
            def pages(self, route, collection=None):
                if '/rulesets?' in route or '/rules/branches/' in route: return api.pages(route, collection)
                if '/pulls?' in route:
                    from urllib.parse import parse_qs, urlsplit
                    branch = parse_qs(urlsplit(route).query)['head'][0].split(':',1)[1]
                    return copy.deepcopy([pr for pr in self.prs if pr['head']['ref'] == branch])
                return super().pages(route, collection)
            def fetch(self, route, method='GET', **kwargs):
                if method == 'GET' and '/git/blobs/' in route: return self.get(route)
                return super().fetch(route, method=method, **kwargs)
            def post(self, route, body):
                outer.assertTrue({'disk-cleaned','box-cleaned','relay-revoked'} <= set(events))
                try:
                    value = super().post(route, body)
                finally:
                    if route.endswith('/pulls') and self.prs:
                        self.prs[-1]['user']['id'] = bot
                        for side in ('head','base'): self.prs[-1][side]['repo']['id'] = 701
                if route.endswith('/pulls'):
                    value = copy.deepcopy(self.prs[-1])
                    if fault == 'lost-pr': raise OSError('lost exact PR acknowledgement')
                return value
        coding = Coding()
        coding.commits[base] = commit
        coding.trees[commit['tree']['sha']] = {e['path']:(e['mode'],e['sha']) for e in tree if e['type'] == 'blob'}
        for e in tree:
            if e['type'] == 'blob': coding.blobs[e['sha']] = base64.b64decode(api.get('/repos/owner/trial/git/blobs/' + e['sha'])['content'])
        coding.refs = {'main':base}
        class Admin(ControlHost):
            def get(self, route):
                if route == '/repos/owner/trial': return dict(id=701, default_branch='main', allow_merge_commit=True)
                if '/branches/' in route: return dict(commit=dict(sha=base))
                if route.startswith('/users/') and 'bot' in route: return dict(id=bot, type='Bot')
                return super().get(route)
        admin = Admin()
        admin.rules = api.pages('/repos/owner/trial/rulesets?includes_parents=true')
        delay(coding,('get','pages','post','fetch'))
        delay(admin,('get','pages'))
        roots, minted, revoked = {}, {}, []
        class Root(AppAPI):
            def get(self, route):
                if route == '/repos/owner/trial-authority/installation' and self.purpose in ('coding','issuer','merge'):
                    raise HostRefusal(404)
                return super().get(route)
            def post(self, route, body):
                if body['repository_ids'] == [702] and self.purpose in ('coding','merge'): raise HostRefusal(422,'repository_scope')
                value = super().post(route, body)
                value['token'] = self.purpose + '-' + value['token']
                minted[value['token']] = (self.purpose, body['repository_ids'])
                return value
        def app_factory(identity, key):
            purpose = next(p for p, record in ids['apps'].items() if record['id'] == identity)
            self.assertEqual(key, api.secrets['AGENTIC_' + purpose.upper() + '_PRIVATE_KEY'])
            roots[purpose] = Root(d, ids, purpose)
            delay(roots[purpose],('get','post'))
            return roots[purpose]
        def token_factory(token):
            purpose, repos = minted[token]
            transport = coding if purpose == 'coding' else admin
            class Scoped:
                def get(self, route):
                    if route.startswith('/users/') and 'bot' in route:
                        identity = next(v for v in ids['apps'].values() if v['slug'] in route)
                        return dict(id=identity['actor_id'], type='Bot')
                    return transport.get(route)
                def pages(self, route, collection=None):
                    if route == '/installation/repositories': return [{'id':v} for v in repos]
                    return transport.pages(route, collection)
                def post(self, *args): return transport.post(*args)
                def fetch(self, route, method='GET', **kwargs):
                    if route == '/installation/token' and method == 'DELETE': revoked.append(token); return b''
                    return transport.fetch(route, method=method, **kwargs)
            return Scoped()
        def artifact(role, raw, producer):
            self.assertEqual(document_member(role + '-' + request['task']['task_id'] + '-1'), role + '.json')
            value = json.loads(raw)
            if fault == 'nonce' and role == 'trial-task-controls': value['nonce'] = 'e' * 32
            a = HistoricalAPI()
            a.document = value
            a.raw = a.archive(role + '.json')
            a.artifact.update(id=1100 + len(artifacts), name=role + '-' + request['task']['task_id'] + '-1', created_at=iso(clock[0]))
            a.artifact['workflow_run'].update(id=100, repository_id=702, head_repository_id=702, head_sha=d['policy']['workflow_sha'])
            a.artifact['digest'] = 'sha256:' + hashlib.sha256(a.raw).hexdigest()
            artifacts.append((a.artifact, a.raw))
            return a.artifact['id']
        def admin_upload(name, raw):
            result = artifact('trial-task-controls', raw, admin_job)
            admin_job.update(status='completed', conclusion='success', completed_at=iso(clock[0]))
            return result
        def upload(name, raw):
            self.assertTrue({'disk-cleaned','box-cleaned','relay-revoked'} <= set(events))
            if name.startswith('trial-task-ready-'):
                result = artifact('trial-task-ready', raw, parent)
                service._trial(dict(env, GITHUB_JOB='trial_task_controls', AGENTIC_ADMIN_PRIVATE_KEY=api.secrets['AGENTIC_ADMIN_PRIVATE_KEY']),
                    request, 'fixture-node', 'trial-controls', clock=native.clock, api_factory=factory, app_factory=app_factory,
                    token_factory=token_factory, uploader_factory=lambda *args:admin_upload, root=Path('/fresh-actions-controls'), store_factory=native.store)
                return result
            receipts.append(json.loads(raw))
            return artifact('trial-task', raw, parent)
        relay_transport, relays = Transport(), []
        class Relay(model_relay.Relay):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, transport=relay_transport, **kwargs); relays.append(self)
            def _start(self, parent):
                self.directory = Path(parent) / 'relay'; self.directory.mkdir()
            def close(self): super().close(); events.append('relay-revoked')
        class Disk:
            def __init__(self, name, *args, **kwargs): self.name = name
            def __enter__(self): return self
            def __exit__(self, *args):
                events.append('disk-cleaned')
                if fault == 'cleanup': raise OSError('unconfirmed disk cleanup')
        sample = task_fixture()[-1]['isolation']
        class Box:
            process = None
            stopped = False
            def __init__(self, deployment, *args, **kwargs): self.deployment = deployment
            def _enter(self): pass
            def inspect(self):
                return dict(HostConfig=dict(Tmpfs={'/tmp':'rw','/home/agentic':'rw'}), Mounts=[
                    dict(Type='volume', Destination='/work', RW=True), dict(Type='bind', Destination='/run/agentic-model', RW=False)])
            def run(self, argv, cwd):
                return (0,'ext4') if argv[0] == 'stat' else (0,json.dumps({k:v for k,v in sample.items() if k not in ('work_filesystem','writable_mounts','host_mounts')}))
            def _attach(self):
                relay = relays[-1]
                relay.forward('Bearer ' + relay.capability, json.dumps(dict(model=d['resources']['model_id'],store=False,stream=True,
                    input=[dict(role='user',content='fixture')])).encode(), lambda raw:None)
                self.process = subprocess.Popen([sys.executable,'-I','-c',WORKER], stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
                return self.process
            def stop(self):
                if self.process and self.process.poll() is None: self.process.kill()
                self.stopped = True
            def _export(self, guard):
                outer.assertTrue(self.stopped and 'relay-revoked' in events)
                guard(force=True)
                return submission.pack_export({'result.bin':dict(content=b'\x00\xfftrial result',executable=True)})
            def close(self): events.append('box-cleaned')
        worker_environment = dict(env, AGENTIC_CODING_PRIVATE_KEY=api.secrets['AGENTIC_CODING_PRIVATE_KEY'], AGENTIC_MODEL_DELIVERY_KEY=delivery)
        kwargs = dict(clock=native.clock,api_factory=factory,app_factory=app_factory,token_factory=token_factory,
            uploader_factory=lambda *args:upload, root=Path('/fresh-actions-worker'),store_factory=native.store,
            image_loader=lambda d,guard:guard(),execution=dict(disk_factory=Disk,relay_factory=Relay,sandbox_factory=Box))
        run = lambda:service._trial(worker_environment,request,'fixture-node','trial-worker',**kwargs)
        with patch.object(coding_transport.time,'time',side_effect=native.clock):
            if fault:
                with self.assertRaises((Refusal,OSError)): run()
                self.assertEqual(receipts,[])
                self.assertEqual(len(coding.prs),1 if fault == 'lost-pr' else 0)
            else:
                result = run()
                self.assertFalse(result['hosted_qualified'])
                self.assertEqual(len(coding.prs),1)
                self.assertEqual(len(receipts),1)
                head = coding.commits[receipts[0]['submitted']['head']]
                self.assertEqual([p['sha'] for p in head['parents']],[base])
                exported = coding.trees[head['tree']['sha']]
                self.assertEqual(exported['result.bin'][0],'100755')
                self.assertEqual(coding.blobs[exported['result.bin'][1]],b'\x00\xfftrial result')
                if latency:
                    self.assertLess(clock[0],1303)  # Original App proof expiry; no window extension.
                else:
                    self.assertEqual(run(),result)
                    parent.update(status='completed',conclusion='success',completed_at=iso(clock[0]))
                    native_controller = __import__('trial_handoff').Native(native,registry)
                    recovered = native_controller.observe('prompt',coding,lambda token:origin.reader)
                    self.assertEqual(recovered['submitted']['head'],receipts[0]['submitted']['head'])
                    self.assertEqual(native_controller.observe('prompt',coding,lambda token:origin.reader),recovered)
                    if continuation is not None:
                        continuation_base = continuation(native_controller, coding, origin, app_factory, token_factory, admin, artifacts)
                    coding.prs[0]['head']['sha'] = '9' * 40
                    with self.assertRaises(Refusal): native_controller.observe('prompt',coding,lambda token:origin.reader)
        self.assertIsNone(native.store(Path('/fresh-actions-controls/worker')).read())
        self.assertEqual(coding.refs['main'],continuation_base or base)
        for token in minted: self.assertIn(token,revoked)
        text = json.dumps([native.store(Path('/fresh-actions-worker/worker')).read(),receipts])
        for key in api.secrets.values(): self.assertNotIn(key,text)
