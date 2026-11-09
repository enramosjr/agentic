"""Fourth native reservation reaches the real broker expiry boundary."""
import backend_test_support
import copy
import unittest
from unittest.mock import patch

import merge_transport
from trusted_ci_policy import Refusal
import test_authority_trial_host_case as host_fixture


class Expired(host_fixture.Sequential):
    def fourth(self):
        self.third()
        self.reviews=[]
        self.host(); self.run('broker'); self.finalize(); self.observe()
        self.second('expired-proof',107,'fresh-fourth-case')
        with self.owner.assertRaisesRegex(Refusal,'pending'): self.coordinate()
        self.owner.assertEqual(self.close_handoff()['host_case'],'none')
        self.published()
        self.sleeper=lambda seconds:self.clock.__setitem__(0,self.clock[0]+seconds)


@unittest.skipIf(getattr(host_fixture.NativeHost,'__unittest_skip__',False),'optional cryptography required')
class NativeBroker(unittest.TestCase):
    fixture=host_fixture.NativeHost.fixture
    prepared=host_fixture.NativeHost.prepared
    connected=host_fixture.NativeHost.connected
    configured=host_fixture.NativeHost.configured
    exercise=host_fixture.NativeHost.exercise
    prepare=host_fixture.NativeHost.prepare

    def test_actual_pre_readiness_wait_survives_proof_aging_then_observes_closed_broker(self):
        def check(*args):
            import service
            f=Expired(self,args); f.fourth(); admission=f.fresh[-1]
            f.job('broker ('+str(f.admission.candidate['submitted']['pr'])+')','broker')
            started=f.clock[0]
            class StillWaiting(Exception): pass
            def tick(seconds):
                f.clock[0]+=seconds
                if f.clock[0]-started>120: raise StillWaiting()
            with self.assertRaises(StillWaiting):
                service._wait_broker_ready(f.api,f.registry,admission.binding,lambda:f.clock[0],admission.guard,tick,admission)
            self.assertEqual(f.clock[0]-started,121)
            self.assertEqual(f.run('broker')['refusal'],'proof_expired')
            for job in f.remote.jobs:
                if job['name'].startswith(('controls (','final proof (')):
                    with self.assertRaisesRegex(Refusal,'producer is not admissible'):
                        service._wait_broker_ready(f.api,f.registry,admission.binding,lambda:f.clock[0],admission.guard,f.sleeper,admission)
                    job.update(status='completed',conclusion='failure',completed_at=__import__('test_authority_broker_evidence').stamp(f.clock[0]))
            self.assertEqual(f.finalize()['fence']['completed'][-1]['kind'],'not-submitted')
        self.exercise(continuation=check)

    def test_predecessor_move_during_real_session_refusal_blocks_receipt(self):
        def check(*args):
            import broker_session
            from registry import trial_reference
            import trial_case
            from broker_refusal import BrokerRefusal
            f=Expired(self,args); f.fourth()
            prior,_=trial_case.read(f.origin,f.admission.value['history'][2]['revision'],lambda:f.clock[0])
            reference=trial_reference(dict(prior,execution=None))
            collect=broker_session.Session._collect
            def move(session,op):
                try: return collect(session,op)
                except BrokerRefusal:
                    f.origin.api.refs[reference]='0'*40
                    raise
            with patch.object(broker_session.Session,'_collect',move),self.assertRaises(Refusal): f.run('broker')
            self.assertFalse(any(a['name'].endswith('-not-submitted') for a in f.remote.artifacts))
            self.assertIsNotNone(f.registry.binding()['fence']['pending'])
        self.exercise(continuation=check)

    def test_predecessor_move_during_receipt_inventory_blocks_upload(self):
        def check(*args):
            from merge_receipts import ActionsReceipts
            from registry import trial_reference
            import trial_case
            f=Expired(self,args); f.fourth()
            prior,_=trial_case.read(f.origin,f.admission.value['history'][0]['revision'],lambda:f.clock[0])
            reference=trial_reference(dict(prior,kind='trial-case-ready',execution=None))
            matches=ActionsReceipts._matches; moved=[]
            def inventory(store,kind):
                result=matches(store,kind)
                if kind=='not-submitted' and not moved:
                    moved.append(True); f.origin.api.refs[reference]='0'*40
                return result
            with patch.object(ActionsReceipts,'_matches',inventory),self.assertRaises(Refusal): f.run('broker')
            self.assertTrue(moved)
            self.assertFalse(any(a['name'].endswith('-not-submitted') for a in f.remote.artifacts))
            self.assertIsNotNone(f.registry.binding()['fence']['pending'])
        self.exercise(continuation=check)

    def test_target_move_during_terminal_admission_blocks_all_registry_writes(self):
        def check(*args):
            from registry import Registry
            f=Expired(self,args); f.fourth(); f.run('broker')
            finalize=Registry.finalize_operation; tokens=f.tokens; post=f.api.post
            armed=[]; writes=[]
            def scoped(token):
                result=tokens(token); get=result.get
                def read(path):
                    value=get(path)
                    if armed and path=='/repos/'+f.p['repository']: f.source.refs['main']='0'*40
                    return value
                result.get=read
                return result
            def write(path,body):
                if armed and '/git/' in path: writes.append(path)
                return post(path,body)
            def close(registry,*args,**kwargs):
                armed.append(True)
                return finalize(registry,*args,**kwargs)
            f.tokens=scoped; f.api.post=write
            with patch.object(Registry,'finalize_operation',close),self.assertRaises(Refusal): f.finalize()
            self.assertTrue(armed); self.assertEqual(writes,[])
            self.assertIsNotNone(f.registry.binding()['fence']['pending'])
            self.assertFalse(any(a['name'].startswith('trial-case-terminal-') for a in f.remote.artifacts))
            return f.source.refs['main']
        # Show this assertion detects the deliberately broken late-snapshot guard.
        import trial_broker_case
        with patch.object(trial_broker_case,'guard',lambda a:a.guard()),self.assertRaises(AssertionError):
            self.exercise(continuation=check)
        self.exercise(continuation=check)

    def test_fourth_selection_authenticates_all_owned_predecessors(self):
        for name in ('direct-push','coding-update','missing-approval'):
            def check(*args):
                import trial_controller
                f=Expired(self,args); f.third(); f.reviews=[]
                f.host(); f.run('broker'); f.finalize(); f.observe()
                store=f.native.provision.store(f.native.provision.root/trial_controller.case_journal('trial-controller',dict(name=name)))
                saved=store.read(); value=copy.deepcopy(saved['value']); value['terminal']['binding']['fence']['completed'][-1]['receipt_digest']='0'*64
                store.write(saved,value)
                with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open('prompt','expired-proof',f.source)
                self.assertIsNone(f.native.provision.store(f.native.provision.root/'trial-controller-expired-proof').read())
            with self.subTest(name=name): self.exercise(continuation=check)

    def test_fourth_credentials_refuse_all_old_tokens_and_host_producer(self):
        def check(*args):
            import trial_controller,trial_case,trial_launch
            f=Expired(self,args); f.fourth()
            for name in ('direct-push','coding-update','missing-approval'):
                token=f.native.provision.store(f.native.provision.root/trial_controller.case_journal('trial-case-read-staging',dict(name=name))).read()['value']['credential']['token']
                self.assertIn(token,f.revoked); f.revoked.discard(token)
                with self.assertRaises(Refusal): f.run('broker',change=lambda env:env.update(**{trial_case.CaseReadStaging.NAME:token}))
                env=f.job('trial case ready','trial_case_ready'); env[trial_case.CaseReadStaging.NAME]=token
                from registry import Registry
                with self.assertRaises(Refusal): trial_launch.consume(f.registry,Registry(f.origin_factory(token),f.origin.coordinates),env,f.ready_hint,lambda:f.clock[0])
                env=f.job('trial case handoff','trial_case_handoff')
                env.update(GITHUB_REPOSITORY=f.p['authority_repository'],GITHUB_TOKEN='case-actions-read',**{trial_case.CaseReadStaging.NAME:token})
                import service
                with self.assertRaises(Refusal): service._case_producer(env,f.hint,'fixture-node','handoff',clock=lambda:f.clock[0],
                    api_factory=lambda token:f.api if token=='case-actions-read' else f.origin_factory(token),uploader_factory=lambda *a:f.upload)
            with self.assertRaises(Refusal): f.host(selected='missing-approval')
            self.assertFalse(any(a['name'].startswith('trial-broker-intent-') for a in f.remote.artifacts))
            self.assertEqual(len(f.attempts),3)
        self.exercise(continuation=check)

    def test_late_predecessor_ready_pending_and_execution_moves_stop_broker(self):
        for index in range(3):
            for kind in ('ready','pending','execution'):
                def check(*args):
                    from registry import trial_reference
                    import trial_case
                    f=Expired(self,args); f.fourth()
                    prior,_=trial_case.read(f.origin,f.admission.value['history'][index]['revision'],lambda:f.clock[0])
                    value=dict(prior,kind='trial-case-ready',execution=None) if kind=='ready' else dict(prior,execution=None) if kind=='pending' else prior
                    reference=trial_reference(value); upload=f.upload
                    def move(name,raw):
                        result=upload(name,raw)
                        if name.startswith('trial-broker-intent-'): f.origin.api.refs[reference]='0'*40
                        return result
                    f.upload=move
                    with patch.object(merge_transport,'isolated',side_effect=AssertionError('negative dispatched')),self.assertRaises(Refusal): f.run('broker')
                    self.assertFalse(any(a['name'].endswith('-not-submitted') for a in f.remote.artifacts))
                    self.assertIsNotNone(f.registry.binding()['fence']['pending'])
                with self.subTest(index=index,kind=kind): self.exercise(continuation=check)

    def test_unknown_intent_or_outcome_never_replays_or_finalizes(self):
        for prefix in ('trial-broker-intent-','trial-broker-denial-'):
            def check(*args):
                f=Expired(self,args); f.fourth(); upload=f.upload; effects=[]
                def lose(name,raw):
                    result=upload(name,raw)
                    if name.startswith(prefix):
                        effects.append(name)
                        if prefix=='trial-broker-denial-':
                            artifact=next(a for a in f.remote.artifacts if a['id']==result)
                            f.remote.artifacts.remove(artifact); f.remote.raw.pop(result)
                        raise OSError('fixture unknown acknowledgement')
                    return result
                f.upload=lose
                with self.assertRaises(OSError): f.run('broker')
                broker=next(j for j in f.remote.jobs if j['name'].startswith('broker ('))
                broker.update(status='in_progress',conclusion=None,completed_at=None)
                with self.assertRaisesRegex(Refusal,'never replay'): f.run('broker')
                with self.assertRaises(Refusal): f.finalize()
                self.assertEqual(len(effects),1); self.assertIsNotNone(f.registry.binding()['fence']['pending'])
                self.assertEqual(f.merges,[])
            with self.subTest(prefix=prefix): self.exercise(continuation=check)

    def test_wrong_prerequisites_and_incomplete_outcome_preserve_pending(self):
        def check(*args):
            import io,json,zipfile
            f=Expired(self,args); f.fourth()
            def document(artifact):
                with zipfile.ZipFile(io.BytesIO(f.remote.raw[artifact['id']])) as archive:
                    member=archive.namelist()[0]; return member,json.loads(archive.read(member))
            proof=next(a for a in f.remote.artifacts if a['name']=='proof-admin-1')
            member,saved=document(proof)
            def live():
                f.job('broker ('+str(f.admission.candidate['submitted']['pr'])+')','broker')
                next(j for j in f.remote.jobs if j['name'].startswith('broker (')).update(status='in_progress',conclusion=None,completed_at=None)
            for field,value in (('operation_id','0'*32),('expires',1),('snapshot',dict(saved['snapshot'],head='0'*40))):
                changed=copy.deepcopy(saved); changed[field]=value; f.remote.replace(proof['id'],changed,member)
                live()
                with self.assertRaises(Refusal): f.run('broker')
                f.remote.replace(proof['id'],saved,member)
            reviews=f.reviews; f.reviews=[]
            live()
            with self.assertRaises(Refusal): f.run('broker')
            f.reviews=reviews
            self.assertFalse(any(a['name'].startswith('trial-broker-intent-') for a in f.remote.artifacts))
            # Failed fixture invocations don't manufacture a live broker job.
            broker=next(j for j in f.remote.jobs if j['name'].startswith('broker ('))
            broker.update(status='in_progress',conclusion=None,completed_at=None)
            with patch.object(merge_transport,'isolated',side_effect=AssertionError('negative dispatched')):
                self.assertEqual(f.run('broker')['refusal'],'proof_expired')
                denial=next(a for a in f.remote.artifacts if a['name'].startswith('trial-broker-denial-'))
                member,saved=document(denial)
                for change in (lambda v:v['refusal'].update(code='readback_unavailable'),
                               lambda v:v['refusal']['observation'].update(proof_digest='0'*64),
                               lambda v:v.update(receipt_digest='0'*64),
                               lambda v:v['intent'].update(proofs_digest='0'*64),
                               lambda v:v.update(schema_version=True),
                               lambda v:v.update(job_id=float(v['job_id']))):
                    value=copy.deepcopy(saved); change(value); f.remote.replace(denial['id'],value,member)
                    with self.assertRaises(Refusal): f.finalize()
                    self.assertIsNotNone(f.registry.binding()['fence']['pending'])
                    f.remote.replace(denial['id'],saved,member)
                intent=next(a for a in f.remote.artifacts if a['name'].startswith('trial-broker-intent-'))
                intent_member,intent_saved=document(intent)
                f.remote.replace(intent['id'],dict(intent_saved,schema_version=True),intent_member)
                with self.assertRaises(Refusal): f.finalize()
                value=copy.deepcopy(saved); value['intent']['schema_version']=True
                f.remote.replace(denial['id'],value,member)
                with self.assertRaises(Refusal): f.finalize()
                f.remote.replace(intent['id'],intent_saved,intent_member)
                f.remote.replace(denial['id'],saved,member)
                raw=f.remote.raw.pop(denial['id']); f.remote.artifacts.remove(denial)
                with self.assertRaises(Refusal): f.finalize()
                with self.assertRaises(Refusal): f.run('broker')
                f.remote.artifacts.append(denial); f.remote.raw[denial['id']]=raw
            self.assertIsNotNone(f.registry.binding()['fence']['pending']); self.assertEqual(f.merges,[])
        self.exercise(continuation=check)

    def test_fourth_expiry_uses_session_receipt_and_native_terminal(self):
        def check(*args):
            import trial_controller,trial_launch
            f=Expired(self,args)
            with patch.object(merge_transport,'isolated',side_effect=AssertionError('negative dispatched')):
                f.fourth()
                origin=f.origin.binding(); original=copy.deepcopy(f.admission.record)
                prior={run:copy.deepcopy(f.runs[run].raw) for run in (101,103,105)}
                retained_proofs=copy.deepcopy(f.remote.raw)
                journals={name:f.native.provision.store(f.native.provision.root/trial_controller.case_journal('trial-controller',dict(name=name))).read()
                          for name in ('direct-push','coding-update','missing-approval')}
                result=f.run('broker')
                self.assertEqual(result['state'],'broker-denied')
                self.assertEqual(result['refusal'],'proof_expired')
                self.assertTrue(any(a['name'].endswith('-not-submitted') for a in f.remote.artifacts))
                self.assertFalse(any(a['name'].endswith(('-dispatch','-host-denied')) for a in f.remote.artifacts))
                self.assertTrue(all(f.remote.raw[key]==raw for key,raw in retained_proofs.items()))
                terminal=f.finalize(); self.assertEqual(f.observe()['binding'],terminal)
                self.assertEqual([v['kind'] for v in terminal['fence']['completed'][-4:]],['not-submitted']*4)
                self.assertEqual(len(f.admission.value['history']),3)
                self.assertEqual(len(f.admission.value['candidates']['value']['candidates']),16)
                self.assertEqual(f.admission.record,original); self.assertEqual(f.origin.binding(),origin)
                self.assertEqual(len(f.attempts),3); self.assertEqual(f.merges,[])
                self.assertEqual(terminal['deployment']['state'],'qualification'); self.assertIsNone(terminal['deployment']['qualification'])
                for run,raw in prior.items(): self.assertEqual(f.runs[run].raw,raw)
                for name,journal in journals.items():
                    self.assertEqual(f.native.provision.store(f.native.provision.root/trial_controller.case_journal('trial-controller',dict(name=name))).read(),journal)
                f.clock[0]+=1000
                trial_launch.revoke(f.native.provision,f.origin_factory,name='expired-proof')
                self.assertIn(f.case_token,f.revoked)
        self.exercise(continuation=check)
