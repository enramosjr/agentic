"""Native broker context handover, never a live qualification or merge."""
import backend_test_support
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from trusted_ci_policy import Refusal, digest


class ContextContracts(unittest.TestCase):
    def test_original_fifteenth_reservation_follows_exact_fourteen_predecessors(self):
        import trial_controller
        self.assertEqual(len(trial_controller.CASE_CHAIN), 16)
        self.assertEqual(trial_controller.CASE_CHAIN[13:], ('revoked-qualification', 'context-transition', 'positive'))
        self.assertEqual(trial_controller.predecessor('context-transition'), 'revoked-qualification')

    def test_transition_receipt_is_evidence_only_and_requires_actual_context(self):
        import trial_broker_context as context
        from test_authority_fence import FenceContracts, pending
        _, registry, before = FenceContracts().prepared()
        op = pending(before)
        old = registry.acquire_operation(before['branch_head'], before['configuration_revision'], op)
        prepared = dict(binding=old, job_id=17)
        a = SimpleNamespace(candidate=dict(name='context-transition'), request=dict(operation_id=op['operation_id'], sequence=1),
                            binding=old, clock=lambda:1001)
        current = copy.deepcopy(old)
        with self.assertRaises(Refusal): context.changed(old, current)
        current['fence']['sequence'] += 1
        with self.assertRaises(Refusal): context.changed(old, current)
        current['configuration_revision'] = 'a'*40
        current['deployment']['generation'] += 1
        current['deployment']['policy'].update(epoch='new', check_name='AGENTIC new')
        self.assertTrue(context.changed(old, current))

    def test_release_hold_precedes_native_context_reads(self):
        from trial_controller import Native
        with self.assertRaisesRegex(Refusal, 'qualify-live blocked'):
            Native(None).transition_context('prompt', 'context-transition', None, None, None)

    def test_native_and_hosted_share_original_case_delegation_deadline(self):
        import trial_broker_context as context
        from pathlib import Path
        publication=dict(value=dict(phase='bound',execution=dict(credential=dict(expires=150))))
        a=SimpleNamespace(record=dict(expires=500,origin=dict(binding=dict(fence=dict(pending=dict(execution_deadline=600))))),
            value=dict(certificate=dict(expires=400)),binding=dict(deployment=dict(expires=450),fence=dict(pending=dict(execution_deadline=350))),
            candidate=dict(name='context-transition'),native=SimpleNamespace(provision=SimpleNamespace(root=Path('/native'),
                store=lambda path:SimpleNamespace(read=lambda:publication))))
        self.assertEqual(context.deadline(a),150)
        a.case=dict(execution=dict(credential=dict(expires=150)))
        self.assertEqual(context.deadline(a),150)

    def test_administrative_readback_cannot_cross_config_deadline_or_source_change(self):
        import trial_broker_context as context
        from trial_configuration import _Boundary
        for fault in ('deadline','source'):
            with self.subTest(fault=fault):
                clock=[100]; snapshot=dict(pr=7,run_id=99,run_attempt=1)
                current=dict(deployment={})
                a=SimpleNamespace(binding=current,request=dict(snapshot=snapshot),clock=lambda:clock[0],local_guard=lambda:None,
                    registry=SimpleNamespace(api=None,binding=lambda:current,unchanged=lambda b:None))
                value=dict(current=current,preview={},operation=dict(setup={},execution_deadline=300),claim=dict(job_id=17),intent=None)
                document={}; journal=SimpleNamespace(read=lambda:document); writes=[]; moved=[]
                def identity(*args):
                    if fault=='deadline': clock[0]=301
                    else: moved.append(True)
                    return {}
                def source(admission):
                    if moved: raise Refusal('source moved during admin readback')
                api=SimpleNamespace(post=lambda *args:writes.append(args))
                with patch.object(context,'guard',return_value=current),patch.object(context,'deadline',return_value=500),\
                     patch.object(context,'fresh_source',side_effect=source),\
                     patch.object(__import__('trial_broker_case'),'_revocation_identity',side_effect=identity),\
                     patch.object(__import__('provenance'),'execution_job',return_value=dict(id=17,status='in_progress',conclusion=None)):
                    boundary=_Boundary(api,lambda:context.native_guard(a,journal,document,value,None,None))
                    with self.assertRaises(Refusal): boundary.post('/rulesets',{})
                    self.assertEqual(writes,[])
                    # The fault is observable: removing the boundary guard lets
                    # the same transport execute after the deliberately bad read.
                    _Boundary(api,lambda:None).post('/rulesets',{})
                    self.assertEqual(len(writes),1)

    def test_unknown_host_response_never_becomes_acknowledged_inventory(self):
        from trial_configuration import _Boundary
        events=[]
        def lost(*args):
            events.append('effect'); raise OSError('unknown create acknowledgement')
        boundary=_Boundary(SimpleNamespace(post=lost),lambda:None,
                           after_response=lambda *args:events.append('acknowledged'))
        with self.assertRaises(OSError): boundary.post('/rulesets',{})
        self.assertEqual(events,['effect'])

    def test_retained_receipts_cannot_create_ordinary_authorization(self):
        from merge_receipts import ActionsReceipts
        store=ActionsReceipts.__new__(ActionsReceipts)
        store.recovery=False; store.uploader=lambda *args:self.fail('retained context uploaded ordinary authorization')
        store._context_evidence=True
        for kind in ('gate','dispatch','outcome','control-ready','not-submitted','host-denied','trial-preloaded'):
            with self.subTest(kind=kind),self.assertRaises(Refusal): store.append(kind,{})

    def test_unknown_issuance_ack_or_mint_never_reissues_even_after_marker_removal(self):
        import json
        import trial_broker_context as context
        from test_authority_private_setup import PrivateSetupContracts
        for fault in ('upload-ack','mint-ack'):
            with self.subTest(fault=fault),PrivateSetupContracts().temporary() as folder:
                recovery=dict(run_id=99,attempt=1,job_id=23,workflow_sha='a'*40)
                pin=dict(authority_repository='owner/authority',authority_repository_id=456,
                         workflow='.github/workflows/authority-v2.yml',workflow_sha='a'*40)
                grant=dict(run_id=99,attempt=1,job='finalize',nonce='1'*32,pin=pin)
                held=dict(deployment=dict(policy=dict(authority_repository='owner/authority',authority_repository_id=456)))
                transition=dict(links={},intent=dict(preview=dict(recovery=grant),case_digest='b'*64,
                    operation=dict(execution_deadline=400)),result=dict(after=held))
                artifacts=[]; claims=[]; mints=[]
                api=SimpleNamespace(pages=lambda *args:artifacts)
                a=SimpleNamespace(candidate=dict(name='context-transition'),worker=None,_context_recovery=True,_context_issuance=None,
                    request=dict(operation_id='2'*32,sequence=1,snapshot=dict(run_id=99,run_attempt=1)),
                    registry=SimpleNamespace(api=api),record=dict(task_id='3'*32),binding=held,clock=lambda:100,
                    _state=lambda:dict())
                environment=dict(AGENTIC_RECOVERY_PIN=json.dumps(pin),RUNNER_TEMP=folder)
                def upload(name,raw):
                    claims.append(json.loads(raw)); artifacts.append(dict(name=name,id=7))
                    if fault=='upload-ack': raise OSError('unknown upload acknowledgement')
                    return 7
                def attempt():
                    context.begin_recovery(a,api,environment,upload)
                    mints.append(True); raise OSError('unknown mint acknowledgement')
                with patch.object(__import__('broker_finalize').Finalizer,'_admit',return_value=recovery),\
                     patch.object(__import__('service'),'_case_broker_job',return_value=17),\
                     patch.object(context,'publications',return_value=transition),\
                     patch.object(context,'closed_history_store',return_value=None),\
                     patch.object(context,'guard',return_value=held),patch.object(context,'deadline',return_value=500),\
                     patch.object(__import__('provenance'),'live_context_recovery',side_effect=lambda *args:dict(document=claims[-1])):
                    with self.assertRaises(OSError): attempt()
                    artifacts.clear()
                    # Emulate process restart: discard the in-memory object while
                    # preserving the same protected original-job storage.
                    a._context_issuance=None
                    with self.assertRaisesRegex(Refusal,'already attempted'): attempt()
                    self.assertEqual(len(claims),1)
                    self.assertEqual(len(mints),int(fault=='mint-ack'))


import test_authority_trial_revocation_case as revocation_fixture


class Context(revocation_fixture.Revocation):
    TRANSITION_CASES = (*revocation_fixture.Revocation.TRANSITION_CASES,'context-transition')

    def job(self,name,key):
        environment=super().job(name,key)
        if name=='finalize':
            if not hasattr(self,'recovery_temporary'):
                from test_authority_private_setup import PrivateSetupContracts
                self.recovery_temporary=PrivateSetupContracts().temporary()
                self.owner.addCleanup(self.recovery_temporary.cleanup)
            environment['RUNNER_TEMP']=self.recovery_temporary.name
        return environment

    def fifteenth(self):
        self.fourteenth(); self.deletion_transport()
        self.sleeper=lambda seconds:self.delete()
        self.run('broker'); self.finalize(); self.observe()
        # Provider IDs are permanent. The older single-transition fixture used
        # list length, which aliases a surviving ID after old controls retire.
        target=self.target
        target.next_identity=max(r['id'] for r in target.rules)+1
        def create(path,body):
            result=dict(copy.deepcopy(body),id=target.next_identity); target.next_identity+=1
            target.writes.append((path,copy.deepcopy(body))); target.rules.append(result)
            target.events.append(('create',result['id']))
            return copy.deepcopy(result)
        target.post=create
        self.second('context-transition',135,'fresh-fifteenth-case')
        with self.owner.assertRaisesRegex(Refusal,'pending'): self.coordinate()
        self.owner.assertEqual(self.close_handoff()['host_case'],'none')
        self.published()

    def transition(self):
        import trial_controller
        return trial_controller.Native(self.preparer).transition_context('prompt','context-transition',
            self.operator,self.admin,digest,self.tokens)


@unittest.skipIf(getattr(revocation_fixture.NativeRevocation,'__unittest_skip__',False),'optional cryptography required')
class NativeBrokerContext(unittest.TestCase):
    fixture=revocation_fixture.NativeRevocation.fixture
    prepared=revocation_fixture.NativeRevocation.prepared
    connected=revocation_fixture.NativeRevocation.connected
    configured=revocation_fixture.NativeRevocation.configured
    exercise=revocation_fixture.NativeRevocation.exercise
    prepare=revocation_fixture.NativeRevocation.prepare

    def test_actual_native_and_hosted_share_bound_expiry(self):
        def check(*args):
            import trial_broker_context as context
            from test_authority_trial_case import Fresh
            from trial_broker_case import _case_value
            f=Fresh(self,args); f.prepare(name='direct-push'); f.handoff(lifetime=151)
            _,case=_case_value(f.admission)
            expiry=case['execution']['credential']['expires']
            self.assertLess(expiry,f.admission.value['certificate']['expires'])
            self.assertEqual(context.deadline(f.admission),expiry)
            f.run('verify')
            hosted=f.fresh[-1]
            self.assertEqual(hosted.case,case)
            self.assertEqual(context.deadline(hosted),expiry)
            self.assertEqual(context.deadline(f.admission),context.deadline(hosted))
        self.exercise(continuation=check)

    def test_real_fifteen_case_context_handover_closed_pair_and_fresh_history(self):
        def check(*args):
            import trial_controller,trial_case,trial_broker_context
            f=Context(self,args); f.fifteenth()
            self.assertEqual(len(f.admission.value['history']),14)
            before=f.registry.binding(); source=copy.deepcopy(f.admission.request['snapshot'])
            original=f.origin.binding(); reservations=f.admission.value['candidates']
            with self.assertRaises(Refusal): f.transition()
            self.assertIsNone(f.native.provision.store(f.native.provision.root/trial_broker_context.JOURNAL).read())
            transitions=[]
            def advance(seconds):
                self.assertFalse(transitions)
                transitions.append(f.transition())
            f.sleeper=advance
            self.assertEqual(f.run('broker')['refusal'],'configuration_changed')
            held=f.registry.binding()
            self.assertEqual(held['fence']['schema_version'],3)
            self.assertEqual(held['fence']['retained']['binding'],before)
            self.assertEqual(held['fence']['completed'],before['fence']['completed'])
            self.assertEqual(f.origin.binding(),original)
            self.assertEqual(f.admission.request['snapshot'],source)
            self.assertEqual(f.source.refs['main'],source['base'])
            self.assertEqual(f.merges,[])
            self.assertFalse(any(a['name'].endswith('-gate') or a['name'].endswith('-dispatch') for a in f.remote.artifacts))
            broker=next(j for j in f.remote.jobs if j['name'].startswith('broker ('))
            completed=copy.deepcopy(broker); broker.update(status='in_progress',conclusion=None,completed_at=None)
            with self.assertRaises(Refusal): f.finalize()
            self.assertEqual(f.registry.binding(),held); broker.update(completed)
            for suffix in ('-trial-preloaded','-trial-context-refusal'):
                artifact=next(a for a in f.remote.artifacts if a['name'].endswith(suffix))
                f.remote.artifacts.remove(artifact)
                with self.assertRaises(Refusal): f.finalize()
                self.assertEqual(f.registry.binding(),held); f.remote.artifacts.append(artifact)
            from registry import trial_reference
            from trial_broker_case import _case_value
            case_ref=trial_reference(_case_value(f.admission)[1]); saved=f.origin.api.refs[case_ref]
            constructor=trial_case.Hosted.__init__; moved=[]
            def moving_after_admission(admitted,*args,**kwargs):
                constructor(admitted,*args,**kwargs)
                if not moved:
                    f.origin.api.refs[case_ref]=f.admission.value['history'][-1]['revision']; moved.append(True)
            try:
                with patch.object(trial_case.Hosted,'__init__',moving_after_admission),self.assertRaises(Refusal): f.finalize()
                self.assertEqual(f.registry.binding(),held)
            finally:
                f.origin.api.refs[case_ref]=saved
            after=f.finalize()
            self.assertEqual(after['fence']['schema_version'],2)
            self.assertIsNone(after['fence']['pending'])
            self.assertEqual([v['kind'] for v in after['fence']['completed'][-2:]],['not-submitted','configuration-complete'])
            observed=f.observe()
            self.assertEqual(observed['binding'],after)
            self.assertEqual(f.admission.value['candidates'],reservations)
            publication=f.native.provision.store(f.native.provision.root/'trial-case-publication-context-transition').read()
            history=f.admission.value['history']+[dict(revision=publication['value']['revision_bound'],terminal=observed['locator'])]
            self.assertEqual(trial_case.baseline(f.origin,f.registry,f.admission.record,history,lambda:f.clock[0]),after)
            self.assertEqual(trial_controller.Native(f.preparer).recover_terminal('prompt','context-transition')['binding'],after)
            self.assertEqual(f.merges,[])
            return source['base']
        from test_authority_trial_storage import bounded_native_writes
        with bounded_native_writes(self) as sizes:
            self.exercise(continuation=check,export_files=revocation_fixture.context_fixture.previous.spoof_fixture.forged_fixture.EXPORT)
        self.assertTrue(any(name.endswith('trial-broker-context') for name in sizes))


if __name__ == '__main__':
    unittest.main()
