"""Positive service boundary components; native prerequisites are modeled here.

Strict16 separately authenticates native history/grants. These tests keep the
actual service ordering, protected Store, App proof/mint and token POST paths.
"""
import backend_test_support
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from contextlib import ExitStack

from authority_private import Store
from trusted_ci_policy import Refusal,digest
import service
import trial_broker_positive as positive
import test_authority_private_setup as private_fixture
from test_authority_producer_composition import Composition


class ServiceMintBoundaries(unittest.TestCase):
    def test_positive_service_passes_guard_before_real_authority_mint(self):
        from contextlib import contextmanager
        f=Composition(); p=f.binding['deployment']['policy']
        env=f.job('finalize','finalize',700)
        pin={k:p[k] for k in ('authority_repository','authority_repository_id','workflow','workflow_sha')}
        env.update(GITHUB_REPOSITORY=p['authority_repository'],GITHUB_TOKEN='component-actions',
            AGENTIC_TRIAL_CASE_ORIGIN_TOKEN='component-case-read',AGENTIC_ADMIN_PRIVATE_KEY='component-admin',
            AGENTIC_RECOVERY_PIN=json.dumps(pin))
        hint=dict(origin=f.registry.coordinates,revision='e'*40)
        def guard(): raise Refusal('positive effect guard rejected changed authority')
        def admission(*args):
            return SimpleNamespace(candidate=dict(name='positive'),guard=guard,bind_source=lambda source:None)
        @contextmanager
        def source(*args,**kwargs): yield f.source
        admin=service._admin_authority
        def missing_guard(*args,**kwargs):
            kwargs.pop('before_effect',None)
            return admin(*args,**kwargs)
        def attempt():
            return service._case_producer(env,hint,'component-node','finalize',clock=lambda:f.clock[0],
                api_factory=lambda token:f.api,app_factory=lambda *args:f.roots['admin'],
                token_factory=f.token_api,uploader_factory=lambda *args:f.upload)
        with patch.object(service,'context',return_value=(f.api,f.registry,f.binding,f.identities)),\
             patch.object(__import__('trial_case'),'read',return_value=(dict(launch=None,execution=True),{})),\
             patch.object(__import__('trial_case'),'Hosted',side_effect=admission),\
             patch.object(positive,'begin',return_value=None),patch.object(service,'_source_token',source):
            with self.assertRaisesRegex(Refusal,'positive effect guard'): attempt()
            self.assertEqual(f.roots['admin'].visible,{})
            with patch.object(service,'_admin_authority',missing_guard),self.assertRaisesRegex(Refusal,'positive effect guard'):
                attempt()
            self.assertEqual(len(f.roots['admin'].visible),1,'missing positive before_effect did not expose the authority mint')
            self.assertEqual(len(f.roots['admin'].revoked),1)

    def test_actual_first_app_post_is_after_consumed_role_and_unknown_ack_never_remints(self):
        for role in ('broker','finalize'):
            with self.subTest(role=role),private_fixture.PrivateSetupContracts().temporary() as folder,ExitStack() as patches:
                f=Composition(); b=f.binding; p=b['deployment']['policy']
                b['deployment'].update(state='qualification',qualification=None)
                b['deployment_digest']=digest(b['deployment'])
                b['fence']['pending']['deployment_digest']=b['deployment_digest']
                pin={k:p[k] for k in ('authority_repository','authority_repository_id','workflow','workflow_sha')}
                job_name='broker ('+str(f.snapshot['pr'])+')' if role=='broker' else 'finalize'
                env=f.job(job_name,role,700)
                env.update(GITHUB_REPOSITORY=p['authority_repository'],GITHUB_TOKEN='component-actions',RUNNER_TEMP=folder,
                    AGENTIC_TRIAL_CASE_ORIGIN_TOKEN='component-case-read')
                for purpose in (('merge','reader') if role=='broker' else ('admin',)):
                    env['AGENTIC_'+purpose.upper()+'_PRIVATE_KEY']='component-'+purpose
                if role=='finalize': env['AGENTIC_RECOVERY_PIN']=json.dumps(pin)
                link=dict(kind=positive.GRANT,revision='a'*40)
                grant=dict(preview=dict(expires=1400,pin=pin,roles=dict(broker='broker ('+str(f.snapshot['pr'])+')',finalize='finalize')))
                job=dict(run_id=99,attempt=1,job_id=700,workflow_sha=p['workflow_sha'])
                root=Path(folder)/('agentic-positive-'+digest(dict(grant=link,role=role,operation=f.request['operation_id'])))
                store=Store(root); reserved=store.write(None,dict(phase='reserved',nonce='original-component-reservation'))
                bound=dict(job=job,scratch=str(Path(folder).resolve()),reserved=reserved)
                case=dict(request=f.request)
                record=dict(task_id='d'*32)
                hint=dict(origin=f.registry.coordinates,revision='e'*40)
                admissions=[]; posts=[]; factories=[]; enforce_boundary=[True]
                def admitted(*args):
                    a=SimpleNamespace(candidate=dict(name='positive'),worker=None,record=record,request=f.request,binding=b,
                        clock=lambda:f.clock[0],guard=lambda:None,_state=lambda:dict(),_positive=None,
                        bind_source=lambda source:self.fail('unknown first mint reached source binding'))
                    admissions.append(a); return a
                def app_factory(identity,pem):
                    factories.append(identity)
                    return next(root for root in f.roots.values() if root.record['id']==identity)
                selected=f.roots['reader' if role=='broker' else 'admin']; post=selected.post
                def lost(path,body):
                    if enforce_boundary[0]:
                        self.assertEqual(store.read()['value']['phase'],'marker-bound')
                        self.assertTrue(any(a['name'].startswith(positive.ROLES[role]) for a in f.api.artifacts))
                    result=post(path,body)  # Real AppAPI commits an actual scoped fixture token.
                    posts.append((path,copy.deepcopy(body),result['token']))
                    raise OSError('actual first App token POST acknowledgement lost')
                patches.enter_context(patch.object(selected,'post',lost))
                patches.enter_context(patch.object(service,'context',return_value=(f.api,f.registry,b,f.identities)))
                patches.enter_context(patch.object(__import__('trial_case'),'read',return_value=(dict(launch=None,execution=True),record)))
                patches.enter_context(patch.object(__import__('trial_case'),'Hosted',side_effect=admitted))
                for name,value in (('original',None),('_case',case),('grant_link',link),('authenticate_grant',grant),
                                   ('job_link',dict(kind=positive.JOB,revision='f'*40)),('authenticate_job',bound)):
                    patches.enter_context(patch.object(positive,name,return_value=value))
                patches.enter_context(patch.object(positive,'guard',return_value=None))
                def attempt(environment=env):
                    return service._case_producer(environment,hint,'component-node',role,clock=lambda:f.clock[0],
                        api_factory=lambda token:f.api,app_factory=app_factory,token_factory=f.token_api,
                        uploader_factory=lambda *args:f.upload)
                with self.assertRaisesRegex(OSError,'actual first App token'): attempt()
                self.assertEqual(len(posts),1)
                self.assertIn(posts[0][2],selected.visible)
                f.api.artifacts[:]=[a for a in f.api.artifacts if not a['name'].startswith(positive.ROLES[role])]
                for replacement in ('restart','numeric-job','scratch'):
                    changed=dict(env)
                    next(j for j in f.api.jobs if j['name']==job_name)['id']=700
                    if replacement=='numeric-job':
                        next(j for j in f.api.jobs if j['name']==job_name)['id']=701
                    if replacement=='scratch': changed['RUNNER_TEMP']=str(Path(folder)/'different-scratch')
                    message={'restart':'missing or consumed','numeric-job':'numeric job was replaced','scratch':'RUNNER_TEMP changed'}[replacement]
                    with self.assertRaisesRegex(Refusal,message): attempt(changed)
                self.assertEqual(len(posts),1)
                self.assertEqual(len(factories),1,'restart or substituted job reached an App root')
                self.assertEqual(len(admissions),4,'each attempted job must reconstruct a fresh admission')
                # Deliberately omit only the one-shot service boundary. A second
                # real token POST is now observable without restoring any Store.
                enforce_boundary[0]=False
                next(j for j in f.api.jobs if j['name']==job_name)['id']=700
                with patch.object(positive,'begin',return_value=None),self.assertRaises(OSError): attempt()
                self.assertEqual(len(posts),2,'broken-boundary control did not expose the duplicate mint')


class CurrentAuthorizationBoundaries(unittest.TestCase):
    def test_positive_guard_resamples_deadline_after_blocking_issuance_read(self):
        # Native publication/history inputs are modeled; the guarded Store read
        # and positive.guard's final deadline calculation/sample are real.
        for delayed in (False,True):
            with self.subTest(delayed=delayed),private_fixture.PrivateSetupContracts().temporary() as folder,ExitStack() as patches:
                clock=[100]; job=dict(run_id=99,attempt=1,job_id=700,workflow_sha='b'*40)
                binding=dict(deployment=dict(expires=500),fence=dict(pending=dict(execution_deadline=500)))
                record=dict(expires=500,origin=dict(binding=dict(fence=dict(pending=dict(execution_deadline=500)))))
                case=dict(history=[],request=dict(snapshot=dict(pr=7)),execution=dict(publication_revision='c'*40,credential=dict(expires=500)))
                store=Store(Path(folder)/'original-role'); document=store.write(None,dict(phase='marker-bound'))
                state=dict(after=None,claim=dict(preview=dict(expires=500)),grant={},role='broker',job=job,
                    root=str(store.root),marker={},issuance=dict(kind='original-issuance'))
                original=SimpleNamespace(unchanged=lambda binding:None,ref=lambda name:'d'*40 if name=='bound' else 'c'*40)
                a=SimpleNamespace(local_guard=lambda binding=None:None,_positive_store=store,_positive_document=document,
                    _positive=state,binding=binding,record=record,case=case,value=dict(certificate=dict(expires=500)),
                    registry=SimpleNamespace(api=None,binding=lambda:binding),clock=lambda:clock[0],revision='d'*40,source=None)
                def issuance(*args):
                    if delayed: clock[0]=500
                    return dict(document=state['issuance'])
                for name,value in (('original',original),('_case',case),('authenticate_grant',{}),
                                   ('authenticate_job',dict(job=job,scratch=folder))):
                    patches.enter_context(patch.object(positive,name,return_value=value))
                patches.enter_context(patch.object(__import__('registry'),'trial_reference',side_effect=lambda case:'bound' if case['execution'] else 'unbound'))
                patches.enter_context(patch.object(__import__('trial_case'),'history_guard',return_value=None))
                patches.enter_context(patch.object(__import__('provenance'),'live_positive_issuance',side_effect=issuance))
                if delayed:
                    with self.assertRaisesRegex(Refusal,'deadline consumed by blocking reads'): positive.guard(a)
                    # A deliberately stale sample makes the unchanged guard pass.
                    with patch.object(a,'clock',return_value=100): positive.guard(a)
                else: positive.guard(a)

    def test_real_review_check_evidence_and_source_validators_reject_withdrawal(self):
        from test_authority_broker_evidence import fixture
        import task_admission
        for fault in ('review','check','expiry','base'):
            with self.subTest(fault=fault):
                registry,source,api,b,identities,s,locators,clock=fixture()
                a=SimpleNamespace(binding=b,request=dict(snapshot=s,task=locators['task']),
                    record=dict(pair=dict(identities=identities)),registry=SimpleNamespace(api=api),source=source,clock=lambda:clock[0])
                a.task=lambda binding,snapshot,locator,task_id:task_admission.read(source,api,binding,identities,snapshot,locator,task_id,clock[0])
                positive.authorization(a)
                if fault=='review': source.reviews=[]
                if fault=='check': source.checks[0]['conclusion']='failure'
                if fault=='expiry': clock[0]=2001
                if fault=='base': source.current_base='f'*40
                with self.assertRaises(Refusal): positive.authorization(a)
                self.assertEqual(source.merges,[])

    def test_changed_effective_protections_block_actual_authority_token_post(self):
        import tempfile
        import controls
        from test_authority_controls import ControlContracts
        from test_authority_app_proofs import identities,AppAPI
        for fault in ('actions_enabled','hook_active','coding_admin'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as folder:
                host,journal=ControlContracts().prepared(folder)
                d=journal.read(); expected=controls.observe(host,d); binding=dict(deployment=d)
                records=identities(d); root=AppAPI(d,records,'admin')
                registry=SimpleNamespace(coordinates=dict(schema_version=2,repository=d['policy']['authority_repository'],
                    repository_id=d['policy']['authority_repository_id'],registry_branch='agentic-registry'))
                def guard(): return positive.protections(host,host,binding,expected,expected['base'])
                guard(); setattr(host,fault,True)
                with self.assertRaisesRegex(Refusal,'indirect credential path|coding|admin'):
                    with service._admin_authority(root,host,registry,binding,records,root.token_api,before_effect=guard):
                        self.fail('changed protection borrowed registry write authority')
                self.assertEqual(root.visible,{})
                self.assertEqual(host.writes,[])
                # A broken missing guard exposes the actual privileged POST.
                with service._admin_authority(root,host,registry,binding,records,root.token_api): pass
                self.assertEqual(len(root.visible),1)
                self.assertEqual(len(root.revoked),1)
