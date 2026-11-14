"""Native eligibility grants have only six exact historical tree-selection rights."""
import backend_test_support
import copy
import inspect
import unittest
from unittest.mock import patch

from trusted_ci_policy import CHECKS,Refusal,digest


class EligibilityContracts(unittest.TestCase):
    def test_public_eligibility_stays_release_held_before_access(self):
        import trial_eligibility
        with self.assertRaisesRegex(Refusal,'qualify-live blocked'):
            trial_eligibility.produce(None,None,None,None,None,None,None)

    def fixture(self):
        import trial_eligibility as eligibility
        files={'result.bin':dict(mode='100644',sha='a'*40,sha256='b'*64),
               '.ai/scripts/trusted_ci_controller.py':dict(mode='100644',sha='a'*40,sha256='4'*64),
               '.github/CODEOWNERS':dict(mode='100644',sha='6'*40,sha256='7'*64)}
        locator=dict(run_id=99,attempt=1,job_id=17,artifact_id=18)
        worker=dict(submitted=dict(tree='c'*40,export_digest=digest(files),head='5'*40,pr=7,run_id=99),locator=locator)
        from test_authority_protocol import deployment
        d=deployment(); d['policy']['checks']=list(CHECKS); d['expires']=500
        record=dict(task_id='f'*32,trial=dict(deployment=d),expires=400,pair=dict(fixture_revision='1'*40),
                    origin=dict(binding=dict(fence=dict(pending=dict(execution_deadline=300)))))
        p=d['policy']
        snapshot=dict(merge='3'*40,base='1'*40,head='5'*40,pr=7,run_id=99,run_attempt=1,
            **{k:p[k] for k in ('repository_id','epoch','verifier_sha','image','authority_repository_id','workflow_sha')},policy_digest=digest(p))
        proof=dict(locator,artifact_digest='sha256:'+'8'*64,role='trial-task',key=record['task_id'],job_started=90,artifact_created=97,job_completed=98)
        inputs=dict(record_digest=digest(record),worker=worker,worker_proof=proof,manifest=files,
            seed=dict(revision='1'*40,manifest={'.github/CODEOWNERS':files['.github/CODEOWNERS']}),source_pin='2'*40,snapshot=snapshot,
            binding=record['trial'],runtime='podman',image=d['policy']['image'],controller_sha256='4'*64,
            issued=100,expires=300)
        observed=dict(kind='native-local-critical-observation',snapshot=inputs['snapshot'],runtime='podman',image=inputs['image'],
            controller_sha256=inputs['controller_sha256'],started=101,completed=105,elapsed_ms=4000,
            outcomes=[dict(id=name,status='success') for name in CHECKS],cleanup_complete=True)
        preview=dict(kind='native-eligible-tree-preview',inputs=inputs,observation=observed,scope=eligibility.SCOPE)
        value=dict(schema_version=1,kind=eligibility.KIND,name='eligibility',task_id=record['task_id'],execution=None,
                   record_digest=digest(record),preview=preview,approval=digest(preview))
        return record,worker,value

    def test_grant_can_select_only_the_exact_worker_tree_in_six_phases(self):
        import trial_eligibility as eligibility
        record,worker,value=self.fixture()
        with patch.object(__import__('trial_transition'),'read_native',return_value=value):
            for case,phase in eligibility.SCOPE:
                self.assertEqual(eligibility.select(None,record,worker,{},case,phase,lambda:110),'c'*40)
            for case,phase in [('positive','fixture'),('new-head','current'),('bad-acceptance','fixture')]:
                with self.subTest(case=case),self.assertRaises(Refusal):
                    eligibility.select(None,record,worker,{},case,phase,lambda:110)

    def test_malformed_failed_or_extended_native_observation_never_selects_a_tree(self):
        import trial_eligibility as eligibility
        record,worker,value=self.fixture()
        for fault in ('failure','cleanup','expiry','worker','scope','interval','schema','controller'):
            changed=copy.deepcopy(value); p=changed['preview']
            if fault=='failure': p['observation']['outcomes'][0]['status']='failure'
            if fault=='cleanup': p['observation']['cleanup_complete']=False
            if fault=='expiry': p['inputs']['expires']=301
            if fault=='worker': p['inputs']['worker']['submitted']['tree']='9'*40
            if fault=='scope': p['scope'].append(['positive','fixture'])
            if fault=='interval': p['observation']['completed']=99
            if fault=='schema': changed['schema_version']=True
            if fault=='controller':
                p['inputs']['controller_sha256']='9'*64
                p['observation']['controller_sha256']='9'*64
            changed['approval']=digest(p)
            with self.subTest(fault=fault),patch.object(__import__('trial_transition'),'read_native',return_value=changed),self.assertRaises(Refusal):
                eligibility.select(None,record,worker,{},'new-head','prior',lambda:110)

    def test_fixed_producer_accepts_no_report_or_verifier_callback(self):
        import trial_eligibility as eligibility
        parameters=inspect.signature(eligibility.produce).parameters
        self.assertNotIn('report',parameters)
        self.assertNotIn('verifier',parameters)

    def test_static_manifest_syntax_reuse_never_reuses_grant_or_clock_authority(self):
        import submission
        import trial_eligibility as eligibility
        eligibility._file_syntax.cache_clear()
        self.addCleanup(eligibility._file_syntax.cache_clear)
        record,worker,value=self.fixture()
        inputs=value['preview']['inputs']
        name='syntax-reuse-contract.py'
        inputs['manifest'][name]=dict(mode='100644',sha='3'*40,sha256='9'*64)
        worker['submitted']['export_digest']=digest(inputs['manifest'])
        value['approval']=digest(value['preview'])
        with patch.object(__import__('trial_transition'),'read_native',return_value=value) as read,\
             patch.object(submission,'path_parts',wraps=submission.path_parts) as paths:
            for _ in range(2): eligibility.authenticate(None,record,worker,{},lambda:110)
            self.assertEqual(sum(call.args==(name,) for call in paths.call_args_list),1)
            self.assertEqual(read.call_count,2)
            with self.assertRaisesRegex(Refusal,'original interval'):
                eligibility.authenticate(None,record,worker,{},lambda:300)
            self.assertEqual(read.call_count,3)
            read.side_effect=Refusal('native grant reference moved')
            with self.assertRaisesRegex(Refusal,'reference moved'):
                eligibility.authenticate(None,record,worker,{},lambda:110)
            changed=copy.deepcopy(value); other=copy.deepcopy(worker)
            changed['preview']['inputs']['manifest'][name]['sha256']='8'*64
            other['submitted']['export_digest']=digest(changed['preview']['inputs']['manifest'])
            changed['preview']['inputs']['worker']=other
            changed['approval']=digest(changed['preview'])
            read.side_effect=None; read.return_value=changed
            eligibility.authenticate(None,record,other,{},lambda:110)
            self.assertEqual(sum(call.args==(name,) for call in paths.call_args_list),2)
        for fault in ('path','mode','sha','sha256','unhashable'):
            changed=copy.deepcopy(value); manifest=changed['preview']['inputs']['manifest']
            item=manifest.pop(name)
            if fault=='path': manifest['../'+name]=item
            else:
                item[('sha256' if fault=='unhashable' else fault)]=[] if fault=='unhashable' else 'invalid'
                manifest[name]=item
            changed['approval']=digest(changed['preview'])
            with self.subTest(fault=fault),patch.object(__import__('trial_transition'),'read_native',return_value=changed),self.assertRaises(Refusal):
                eligibility.authenticate(None,record,worker,{},lambda:110)

    def test_positive_grant_requires_authenticated_strict_original_lineage(self):
        import trial_broker_positive as positive
        import trial_eligibility as eligibility
        record,worker,value=self.fixture()
        link=dict(kind=eligibility.KIND,revision='a'*40)
        snapshot=value['preview']['inputs']['snapshot']
        case=dict(worker=worker,candidate=dict(name='positive',eligibility=link),history=[{} for _ in range(15)],
            request=dict(snapshot=snapshot),certificate=dict(expires=280),pending=dict(pending=dict(execution_deadline=260)),
            execution=dict(credential=dict(expires=250)))
        binding=dict(deployment=record['trial']['deployment'])
        p=binding['deployment']['policy']
        grant_link=dict(kind=positive.GRANT,revision='b'*40)
        def grant(case):
            preview=dict(kind='native-positive-preview',record_digest=digest(record),case_digest=digest(case),
                request_digest=digest(case['request']),worker=case['worker'],reservation=case['candidate'],history=case['history'],
                binding=binding,snapshot=snapshot,tree=worker['submitted']['tree'],controls={},
                pin={k:p[k] for k in ('authority_repository','authority_repository_id','workflow','workflow_sha')},
                run_id=99,attempt=1,roles=dict(broker='broker (7)',finalize='finalize'),issued=110,expires=250,nonce='c'*32)
            return dict(schema_version=1,kind=positive.GRANT,task_id=record['task_id'],execution=None,name='positive',
                record_digest=digest(record),case_digest=digest(case),request_digest=digest(case['request']),preview=preview,approval=digest(preview))
        for fault in ('valid','missing','worker','failed-eligibility'):
            changed=copy.deepcopy(case); evidence=copy.deepcopy(value)
            if fault=='missing': changed['candidate'].pop('eligibility')
            if fault=='worker': changed['worker']['submitted']['tree']='9'*40
            if fault=='failed-eligibility':
                evidence['preview']['observation']['outcomes'][0]['status']='failure'
                evidence['approval']=digest(evidence['preview'])
            claim=grant(changed)
            def native(registry,link,record): return claim if link['kind']==positive.GRANT else evidence
            with self.subTest(fault=fault),patch.object(__import__('trial_transition'),'read_native',side_effect=native):
                if fault=='valid': positive.authenticate_grant(None,record,changed,binding,grant_link,lambda:120)
                else:
                    with self.assertRaises(Refusal): positive.authenticate_grant(None,record,changed,binding,grant_link,lambda:120)

    def test_legacy_positive_approval_refuses_before_new_approval_effects(self):
        from unittest.mock import Mock
        from trial_controller import Admission
        import trial_broker_positive as positive
        record,worker,_=self.fixture()
        a=Admission.__new__(Admission)
        a.candidate=dict(name='positive'); a.value=dict(phase='bound',history=[{} for _ in range(15)])
        a.guard=Mock(); a.original=None; a.record=record; a.clock=lambda:120
        case=dict(candidate=a.candidate,worker=worker)
        with patch.object(__import__('trial_broker_case'),'_case_value',return_value=({},case)),\
             patch.object(__import__('trial_broker_case'),'_prerequisites') as prerequisites,\
             patch.object(__import__('trial_transition'),'_publish_native') as publish,\
             self.assertRaisesRegex(Refusal,'separate strict original eligibility'):
            positive.approve_native(a,{},digest)
        prerequisites.assert_not_called(); publish.assert_not_called()

    def test_strict_worker_cannot_reserve_candidates_without_completed_eligibility(self):
        from pathlib import Path
        from types import SimpleNamespace
        from trial_handoff import Native
        from trial_candidates import Prepare
        from trial_specimen import SPECIMEN
        record,worker,_=self.fixture()
        record['trial']['deployment'].update(adapter='github-actions',state='qualification',qualification=None)
        record['origin']['binding']={}
        native=Native.__new__(Native)
        native.observe=lambda *a:worker
        native._completion=lambda *a:dict(record=record,result=worker,proof={},files={'result.bin':dict(content=SPECIMEN,executable=False)})
        for value in (None,dict(value=dict(phase='execution-started'))):
            native.provision=SimpleNamespace(api=None,root=Path('/native'),store=lambda path:SimpleNamespace(read=lambda:value))
            with self.subTest(value=value),patch.object(__import__('trial_candidates'),'_source_token') as mint,\
                 self.assertRaisesRegex(Refusal,'strict worker eligibility required'):
                Prepare(native,None)._run('prompt')
            mint.assert_not_called()


if __name__=='__main__': unittest.main()
