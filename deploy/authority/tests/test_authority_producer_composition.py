"""Execute held service roles against local API/OCI boundaries, never hosted proof."""
import backend_test_support
import copy
import io
import json
import tarfile
import unittest
from unittest.mock import patch

import service
from trusted_ci_policy import Refusal
from test_authority_app_proofs import AppAPI
from test_authority_broker_evidence import fixture, stamp


class Composition:
    def __init__(self):
        self.registry,self.source,self.api,self.binding,self.identities,self.snapshot,self.locators,self.clock = fixture()
        self.clock[0] = 1080
        read = self.registry.binding
        self.registry.binding = lambda **kwargs:read()
        self.binding['branch_head'] = 'c'*40
        self.registry.coordinates = dict(schema_version=2,repository='owner/authority',repository_id=456,registry_branch='agentic-registry')
        self.request = dict(schema_version=2,configuration_revision=self.binding['configuration_revision'],
            deployment_digest=self.binding['deployment_digest'],operation_id=self.binding['fence']['pending']['operation_id'],
            sequence=self.binding['fence']['sequence'],snapshot=self.snapshot,
            task=self.locators['task'],qualification=self.locators['qualification'])
        self.roots = {p:AppAPI(self.binding['deployment'],self.identities,p) for p in self.identities['apps']}
        self.tokens, self.events = {}, []
        for purpose,root in self.roots.items():
            original = root.post
            def post(path,body,root=root,purpose=purpose,original=original):
                result = original(path,body)
                old = result['token']
                result['token'] = purpose + ':' + old
                root.visible[result['token']] = root.visible.pop(old)
                self.tokens[result['token']] = root
                return result
            root.post = post
        # Archive is the fixture boundary; no OCI engine/privileged disk is run.
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream,mode='w') as archive:
            member = tarfile.TarInfo('candidate/file.txt')
            member.size = 5
            archive.addfile(member,io.BytesIO(b'hello'))
        self.tar = stream.getvalue()
        self.source.fetch = lambda path,**kw:self.tar
        original_post = self.source.post
        def post(path,body):
            if path.endswith('/check-runs'):
                self.events.append('published')
                value = dict(body,id=300,app={'id':self.binding['deployment']['apps']['issuer']})
                self.source.checks = [value]
                return value
            return original_post(path,body)
        self.source.post = post
        self.facts = dict(schema_version=2,deployment_digest=self.binding['deployment_digest'],
            generation=self.binding['deployment']['generation'],base=self.snapshot['base'],controls_digest='b'*64,
            owners_digest='b'*64,access_digest='c'*64,automation_digest='d'*64,coding_bot_id=18,
            isolation_established=False,enforcement_active=False,
            required_checks=[dict(context=self.binding['deployment']['policy']['check_name'],integration_id=42)])

    def token_api(self,token):
        root = self.tokens[token]
        probe = root.token_api(token)
        source, api, parent = self.source, self.api, self
        class Scoped:
            def __init__(self): self.token = token
            def get(self,path):
                if path.startswith('/users/'): return probe.get(path)
                return source.get(path)
            def pages(self,path,collection=None):
                if path == '/installation/repositories': return probe.pages(path,collection)
                return source.pages(path,collection)
            def fetch(self,path,**kwargs):
                if path == '/installation/token': return probe.fetch(path,**kwargs)
                return source.fetch(path,**kwargs)
            def post(self,path,body): return source.post(path,body)
        return Scoped()

    def job(self,name,key,identity):
        self.api.jobs = [j for j in self.api.jobs if j['name'] != name]
        self.api.jobs.append(dict(id=identity,run_id=99,head_sha=self.binding['deployment']['policy']['workflow_sha'],
            name=name,status='in_progress',conclusion=None,started_at=stamp(self.clock[0]),completed_at=None))
        return dict(GITHUB_REPOSITORY_ID='456',GITHUB_SHA=self.binding['deployment']['policy']['workflow_sha'],
            GITHUB_RUN_ID='99',GITHUB_RUN_ATTEMPT='1',GITHUB_JOB=key)

    def upload(self,name,raw):
        from artifact_uploader import document_member
        if any(a['name'] == name for a in self.api.artifacts): raise Refusal('fixture artifact conflict')
        identity = max([2000,*self.api.raw])+1
        self.api.artifacts.append(dict(id=identity,name=name,expired=False,created_at=stamp(self.clock[0]),
            workflow_run=dict(id=99,repository_id=456,head_repository_id=456,head_sha=self.binding['deployment']['policy']['workflow_sha'])))
        self.api.replace(identity,json.loads(raw),document_member(name))
        self.events.append('upload:'+name)
        return identity

    def run(self,role,purpose=None,verifier=None):
        name = ('publication controls' if role == 'publication-controls' else 'final proof' if role == 'final-proof' else role)
        key = (purpose+'_'+role.replace('-','_') if purpose else role.replace('-','_'))
        name += ' ('+(purpose or str(self.snapshot['pr']))+')'
        identity = 500+len(self.events)
        env = self.job(name,key,identity)
        purposes = ([purpose] if purpose else ['merge','reader'] if role == 'broker' else
            ['admin'] if role in ('publication-controls','controls') else ['issuer'] if role == 'publish' else ['reader'])
        env.update({'AGENTIC_'+p.upper()+'_PRIVATE_KEY':'SYNTHETIC-'+p for p in purposes})
        # Delete earlier fixture versions: this run must produce its own reports.
        prefix = ('evidence' if role == 'verify' else role)+'-'+(purpose or str(self.snapshot['pr']))+'-1'
        self.api.artifacts[:] = [a for a in self.api.artifacts if a['name'] != prefix]
        with patch.object(service,'context',return_value=(self.api,self.registry,copy.deepcopy(self.binding),self.identities)):
            result = service._producer(env,self.request,'synthetic-node',role,clock=lambda:self.clock[0],
                app_factory=lambda app,pem:next(r for r in self.roots.values() if r.record['id'] == app),
                token_factory=self.token_api,uploader_factory=lambda *args:self.upload,verifier=verifier,
                sleeper=lambda seconds:self.clock.__setitem__(0,self.clock[0]+int(seconds)))
        job = next(j for j in self.api.jobs if j['id'] == identity)
        job.update(status='completed',conclusion='success',completed_at=stamp(self.clock[0]))
        return result

    def verify(self,source,d,s,job_id,guard,clock,cleanup_failure=False):
        events = self.events
        class Disk:
            name = 'agentic-fixture'
            def __init__(self,*args,**kwargs): pass
            def __enter__(self): events.append('disk-open'); return self
            def __exit__(self,*args):
                events.append('disk-clean')
                if cleanup_failure: raise Refusal('fixture disk cleanup failed')
        class Box:
            def __init__(self,*args,**kwargs): pass
            def __enter__(self): events.append('box-open'); return self
            def __exit__(self,*args): events.append('box-clean')
        def controller(box,p,snapshot,**kwargs):
            events.append('fixture-obligations')
            return dict(outcomes=[dict(id=name,status='success') for name in p['checks']])
        return service._verify_actions(source,d,s,job_id,guard,clock,disk_factory=Disk,box_factory=Box,
            controller=controller,image_loader=lambda d,guard:events.append('fixture-image'))


class ProducerCompositionContracts(unittest.TestCase):
    def test_denied_attempt_records_positive_no_dispatch_and_terminal_admin_can_finalize(self):
        import merge_receipts
        for defect in ('failed-publication','missing-evidence'):
            f = Composition()
            if defect == 'missing-evidence':
                f.api.artifacts[:] = [a for a in f.api.artifacts if not a['name'].startswith('evidence-')]
                f.job('controls ('+str(f.snapshot['pr'])+')','controls',800)
                for i,p in enumerate(('admin','reader','issuer','coding','merge')): f.job('final proof ('+p+')',p+'_final_proof',801+i)
            with self.subTest(defect=defect),self.assertRaises(Refusal): f.run('broker')
            self.assertEqual(f.source.merges,[])
            broker = next(j for j in f.api.jobs if j['name'].startswith('broker ('))
            broker.update(status='completed',conclusion='failure',completed_at=stamp(f.clock[0]))
            terminal = merge_receipts.ActionsReceipts(f.api,f.registry.binding,broker['id'],lambda:f.clock[0],recovery=True)
            self.assertIsNotNone(terminal.find_for_recovery('not-submitted'))
            self.assertIsNone(terminal.find_for_recovery('dispatch'))
            def finalize(head,value):
                self.assertEqual(value['kind'],'not-submitted')
                self.assertEqual(value['operation_id'],f.request['operation_id'])
                f.binding['fence']['pending'] = None
                return copy.deepcopy(f.binding)
            f.registry.finalize_operation = finalize
            env = f.job('finalize','finalize',950)
            env.update(AGENTIC_ADMIN_PRIVATE_KEY='SYNTHETIC-admin',AGENTIC_RECOVERY_PIN=json.dumps(dict(
                authority_repository='owner/authority',authority_repository_id=456,
                workflow=f.binding['deployment']['policy']['workflow'],workflow_sha=f.binding['deployment']['policy']['workflow_sha'])))
            with patch.object(service,'Registry',return_value=f.registry), \
                 patch.object(service.app_proofs,'load_identities',return_value=f.identities):
                after = service._finalize(env,{},clock=lambda:f.clock[0],api_factory=lambda token:f.api,
                    app_factory=lambda *args:f.roots['admin'],token_factory=f.token_api)
            self.assertIsNone(after['fence']['pending'])

    def test_discovery_and_admin_preparation_reuse_retained_producers_before_one_fence(self):
        f = Composition()
        f.clock[0] = 1090
        f.binding['fence']['pending'] = None
        f.binding['fence']['sequence'] = 0
        f.binding['branch_head'] = 'c'*40
        f.registry.coordinates = dict(schema_version=2,repository='owner/authority',repository_id=456,registry_branch='agentic-registry')
        def acquire(head,configuration,op):
            self.assertEqual(head,f.binding['branch_head'])
            self.assertEqual(configuration,f.binding['configuration_revision'])
            f.binding['fence']['pending'] = op
            f.binding['fence']['sequence'] += 1
            return copy.deepcopy(f.binding)
        f.registry.acquire_operation = acquire
        source_pages,api_pages = f.source.pages,f.api.pages
        f.source.pages = lambda path,collection=None: f.source.prs if '/pulls?' in path else source_pages(path,collection)
        f.api.pages = lambda path,collection=None: (f.api.artifacts if path.endswith('/actions/artifacts') else
            [a for a in f.api.artifacts if a['workflow_run']['id'] == 99] if path.endswith('/runs/99/artifacts') else api_pages(path,collection))
        f.api.artifacts.insert(0,dict(id=1,name='qualification-1',expired=False,
            workflow_run=dict(id=98,head_sha='0'*40,repository_id=456,head_repository_id=456)))
        kwargs = dict(clock=lambda:f.clock[0],app_factory=lambda app,pem:next(r for r in f.roots.values() if r.record['id'] == app),token_factory=f.token_api)
        env = f.job('discover','discover',850)
        env['AGENTIC_READER_PRIVATE_KEY'] = 'SYNTHETIC-reader'
        with patch.object(service,'context',side_effect=lambda *a:(f.api,f.registry,copy.deepcopy(f.binding),f.identities)):
            selected = service._discover(env,{},**kwargs)
            self.assertEqual(selected,dict(pr=f.snapshot['pr']))
            env = f.job('prepare','prepare',851)
            env['AGENTIC_ADMIN_PRIVATE_KEY'] = 'SYNTHETIC-admin'
            with patch.object(service,'Registry',return_value=f.registry): prepared = service._prepare(env,selected,**kwargs)
        self.assertEqual(prepared['task'],f.locators['task'])
        self.assertEqual(prepared['qualification'],f.locators['qualification'])
        self.assertEqual(prepared['snapshot'],f.snapshot)
        self.assertEqual(f.binding['fence']['sequence'],1)
        self.assertEqual(f.binding['fence']['pending']['operation_id'],prepared['operation_id'])
        for root in f.roots.values(): self.assertEqual(set(root.visible),set(root.revoked))

    def test_service_recovery_keeps_independent_pin_and_reconciles_after_software_drift_and_expiry(self):
        import test_authority_broker_finalize as recovery
        from test_authority_app_proofs import identities as records
        import app_proofs
        from trusted_ci_policy import digest
        original = recovery.intent
        def configured():
            d = original()
            d['policy']['merge_actors'] = [19]
            identities = records(d)
            d['resources'].update(identity_digest=digest(identities),identity_record=json.dumps(identities,separators=(',',':')))
            return d
        with patch.object(recovery,'intent',side_effect=configured): controller,host,api,source,store = recovery.fixture('dispatch')
        host.refs['main'] = 'e'*40
        host.commits['e'*40] = copy.deepcopy(host.commits['a'*40])
        d = store.binding(check_software=False)['deployment']
        root = AppAPI(d,app_proofs.load_identities(d),'admin')
        original_get = api.get
        api.get = lambda path: dict(id=456,private=True,owner={'id':7}) if path == '/repos/owner/authority' else original_get(path)
        def token_factory(token):
            probe = root.token_api(token)
            class Scoped:
                def get(self,path): return source.get(path)
                def pages(self,path,collection): return probe.pages(path,collection)
                def fetch(self,path,**kwargs): return probe.fetch(path,**kwargs)
            return Scoped()
        env = dict(controller.environment,AGENTIC_RECOVERY_PIN=json.dumps(controller.pin),AGENTIC_ADMIN_PRIVATE_KEY='SYNTHETIC-admin')
        with patch.object(service,'Registry',return_value=store),patch.object(service,'context',side_effect=AssertionError('normal context defeats recovery')):
            result = service._finalize(env,{},clock=lambda:3000,api_factory=lambda token:api,
                app_factory=lambda *args:root,token_factory=token_factory)
        self.assertIsNone(result['fence']['pending'])
        self.assertEqual(result['fence']['completed'][-1]['kind'],'merged')
        self.assertEqual(set(root.visible),set(root.revoked))

    def test_execution_cleanup_closed_publication_and_fresh_producers_dispatch_once(self):
        import controls
        import broker_session
        import merge_window
        f = Composition()
        f.run('verify',verifier=f.verify)
        self.assertLess(f.events.index('box-clean'),f.events.index('disk-clean'))
        self.assertLess(f.events.index('disk-clean'),next(i for i,v in enumerate(f.events) if v.startswith('upload:evidence')))
        f.clock[0] = 1090
        for purpose in ('admin','reader','issuer','coding','merge'): f.run('proof',purpose)
        with patch.object(controls,'observe',return_value=f.facts): f.run('publication-controls')
        f.source.checks.clear()
        f.run('publish')
        self.assertEqual(len(f.source.checks),1)
        # Producers are warm before broker readiness. The local scheduler invokes
        # them only when the broker creates the authenticated immutable request.
        f.clock[0] = 1095
        f.job('controls ('+str(f.snapshot['pr'])+')','controls',800)
        for i,purpose in enumerate(('admin','reader','issuer','coding','merge')):
            f.job('final proof ('+purpose+')',purpose+'_final_proof',801+i)
        original = f.upload
        def upload(name,raw):
            identity = original(name,raw)
            if name.endswith('-control-ready'):
                f.clock[0] = 1096
                with patch.object(controls,'observe',return_value=f.facts): f.run('controls')
                for purpose in ('admin','reader','issuer','coding','merge'): f.run('final-proof',purpose)
            return identity
        f.upload = upload
        with patch.object(merge_window.MergeSource,'merge',side_effect=f.source.merge): result = f.run('broker')
        self.assertEqual(result['state'],'submitted')
        self.assertEqual(len(f.source.merges),1)
        self.assertEqual(f.source.merges[0],('owner/project',f.snapshot['pr'],f.snapshot['head'],30))
        self.assertIsNotNone(f.binding['fence']['pending'])
        for root in f.roots.values(): self.assertEqual(set(root.visible),set(root.revoked))

    def test_failed_cleanup_cannot_upload_evidence_or_publish(self):
        f = Composition()
        with self.assertRaisesRegex(Refusal,'cleanup failed'):
            f.run('verify',verifier=lambda *args:f.verify(*args,cleanup_failure=True))
        self.assertFalse(any(v.startswith('upload:evidence') for v in f.events))
        self.assertNotIn('published',f.events)

    def test_publication_cannot_use_final_controls_or_unclosed_admin_observation(self):
        import controls
        for defect in ('missing','live','stale'):
            f = Composition()
            f.clock[0] = 1090
            with patch.object(controls,'observe',return_value=f.facts): f.run('publication-controls')
            job = next(j for j in f.api.jobs if j['name'].startswith('publication controls'))
            if defect == 'missing': f.api.artifacts[:] = [a for a in f.api.artifacts if not a['name'].startswith('publication-controls-')]
            if defect == 'live': job.update(status='in_progress',conclusion=None)
            if defect == 'stale': f.clock[0] = 1391
            f.source.checks.clear()
            with self.subTest(defect=defect),self.assertRaises(Refusal): f.run('publish')
            self.assertEqual(f.source.checks,[])


if __name__ == '__main__': unittest.main()
