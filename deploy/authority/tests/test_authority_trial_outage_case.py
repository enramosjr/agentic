"""Fifth native reservation traverses the real warm broker graph."""
import backend_test_support
import copy
import unittest
from unittest.mock import patch

import broker_session
import merge_transport
from trusted_ci_github import HostRefusal
from trusted_ci_policy import Refusal
import test_authority_trial_broker_case as broker_fixture


class Outage(broker_fixture.Expired):
    def through_fourth(self):
        self.fourth(); self.run('broker')
        # Real waiting producers observe CLOSED refusal, then terminate without
        # producing fabricated controls/final proofs for the fourth case.
        import service
        from test_authority_broker_evidence import stamp
        for job in self.remote.jobs:
            if job['name'].startswith(('controls (','final proof (')):
                with self.owner.assertRaises(Refusal):
                    service._wait_broker_ready(self.api,self.registry,self.fresh[-1].binding,
                        lambda:self.clock[0],self.fresh[-1].guard,self.sleeper,self.fresh[-1])
                job.update(status='completed',conclusion='failure',completed_at=stamp(self.clock[0]))
        self.finalize(); self.observe()
        self.original=copy.deepcopy(self.admission.record)
        self.production=self.origin.binding()
        self.prior={run:copy.deepcopy(remote.raw) for run,remote in self.runs.items()}

    def fifth(self):
        self.through_fourth()
        self.second('authority-outage',109,'fresh-fifth-case')
        with self.owner.assertRaisesRegex(Refusal,'pending'): self.coordinate()
        self.owner.assertEqual(self.close_handoff()['host_case'],'none')
        self.published()
        self.armed=False; self.failed=[]; self.fault_status=503
        pages=self.api.pages; source_pages=self.source.pages
        def reviewed(path,collection=None):
            value=source_pages(path,collection)
            if self.armed and path.endswith('/reviews'): self.reviewed=True
            return value
        def outage(path,collection=None):
            if self.fault_status is not None and self.armed and getattr(self,'reviewed',False) and path.endswith('/runs/109/artifacts'):
                self.armed=False; self.failed.append(path)
                raise HostRefusal(self.fault_status)
            return pages(path,collection)
        self.api.pages=outage; self.source.pages=reviewed

    def upload(self,name,raw):
        identity=super().upload(name,raw)
        if self.admission.candidate['name']=='authority-outage' and name.endswith('-control-ready'):
            self.clock[0]+=1
            self.run('controls')
            for purpose in broker_session.PURPOSES: self.run('final-proof',purpose)
            if getattr(self,'after_final',None): self.after_final()
            self.armed=True; self.reviewed=False
        return identity


@unittest.skipIf(getattr(broker_fixture.NativeBroker,'__unittest_skip__',False),'optional cryptography required')
class NativeOutage(unittest.TestCase):
    fixture=broker_fixture.NativeBroker.fixture
    prepared=broker_fixture.NativeBroker.prepared
    connected=broker_fixture.NativeBroker.connected
    configured=broker_fixture.NativeBroker.configured
    exercise=broker_fixture.NativeBroker.exercise
    prepare=broker_fixture.NativeBroker.prepare

    def test_delayed_receipt_handling_keeps_actual_failure_timestamp(self):
        def check(*args):
            from broker_refusal import BrokerRefusal
            f=Outage(self,args); f.fifth()
            run=broker_session.Session._run; upload=f.upload; delayed=[]
            def uploading(name,raw):
                if name.endswith('-not-submitted'):
                    delayed.append(f.clock[0]); f.clock[0]+=2
                return upload(name,raw)
            def collect(session,*args,**kwargs):
                try: return run(session,*args,**kwargs)
                except BrokerRefusal:
                    f.clock[0]+=1; raise
            f.upload=uploading
            with patch.object(broker_session.Session,'_run',collect):
                self.assertEqual(f.run('broker')['refusal'],'readback_unavailable')
            self.assertEqual(len(delayed),1)
            terminal=f.finalize(); self.assertEqual(f.observe()['binding'],terminal)
        self.exercise(continuation=check)

    def test_fifth_selection_reauthenticates_each_owned_native_completion(self):
        for name in ('direct-push','coding-update','missing-approval','expired-proof'):
            def check(*args):
                import trial_controller
                f=Outage(self,args); f.through_fourth()
                store=f.native.provision.store(f.native.provision.root/trial_controller.case_journal('trial-controller',dict(name=name)))
                saved=store.read(); value=copy.deepcopy(saved['value'])
                value['terminal']['binding']['fence']['completed'][-1]['receipt_digest']='0'*64
                store.write(saved,value)
                with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open('prompt','authority-outage',f.source)
                self.assertIsNone(f.native.provision.store(f.native.provision.root/'trial-controller-authority-outage').read())
            with self.subTest(name=name): self.exercise(continuation=check)

    def test_unknown_fifth_intent_or_outcome_never_replays_or_closes(self):
        for prefix in ('trial-broker-intent-','trial-broker-denial-'):
            def check(*args):
                f=Outage(self,args); f.fifth(); upload=f.upload; effects=[]
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
            with self.subTest(prefix=prefix): self.exercise(continuation=check)

    def test_fifth_target_move_during_terminal_admission_blocks_writes(self):
        def check(*args):
            from registry import Registry
            f=Outage(self,args); f.fifth(); f.run('broker')
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
                armed.append(True); return finalize(registry,*args,**kwargs)
            f.tokens=scoped; f.api.post=write
            with patch.object(Registry,'finalize_operation',close),self.assertRaises(Refusal): f.finalize()
            self.assertTrue(armed); self.assertEqual(writes,[])
            self.assertIsNotNone(f.registry.binding()['fence']['pending'])
            self.assertFalse(any(a['name'].startswith('trial-case-terminal-') for a in f.remote.artifacts))
            return f.source.refs['main']
        self.exercise(continuation=check)

    def test_wrong_failure_or_success_never_counts_as_outage_or_dispatches(self):
        for defect in ('status','no-outage','missing-approval','stale-final','foreign-final'):
            def check(*args):
                f=Outage(self,args); f.fifth()
                if defect=='status': f.fault_status=403
                elif defect=='no-outage': f.fault_status=None
                elif defect=='missing-approval': f.reviews=[]
                elif defect=='stale-final': f.after_final=lambda:f.clock.__setitem__(0,f.clock[0]+31)
                else:
                    def foreign():
                        import io,json,zipfile
                        a=next(a for a in f.remote.artifacts if a['name'].startswith('final-proof-reader-'))
                        with zipfile.ZipFile(io.BytesIO(f.remote.raw[a['id']])) as z:
                            member=z.namelist()[0]; value=json.loads(z.read(member))
                        value['ready_nonce']='0'*32; f.remote.replace(a['id'],value,member)
                    f.after_final=foreign
                with patch.object(merge_transport,'isolated',side_effect=AssertionError('negative dispatched')):
                    with self.assertRaises(Refusal): f.run('broker')
                    with self.assertRaises(Refusal): f.finalize()
                self.assertFalse(any(a['name'].startswith('trial-broker-denial-') for a in f.remote.artifacts))
                self.assertFalse(any(a['name'].endswith(('-dispatch','-host-denied','-gate')) for a in f.remote.artifacts))
                self.assertIsNotNone(f.registry.binding()['fence']['pending'])
            with self.subTest(defect=defect): self.exercise(continuation=check)

    def test_retained_outage_substitutions_and_missing_evidence_keep_fence(self):
        def check(*args):
            import io,json,zipfile
            f=Outage(self,args); f.fifth(); f.run('broker')
            artifact=next(a for a in f.remote.artifacts if a['name'].startswith('trial-broker-denial-'))
            with zipfile.ZipFile(io.BytesIO(f.remote.raw[artifact['id']])) as z:
                member=z.namelist()[0]; saved=json.loads(z.read(member))
            for change in (lambda v:v['refusal'].update(code='proof_expired'),
                           lambda v:v['refusal']['observation'].update(status=True),
                           lambda v:v['refusal']['observation'].update(path='/repos/foreign/actions/runs/109/artifacts'),
                           lambda v:v.update(observed=float(v['observed'])),
                           lambda v:v.update(receipt_digest='0'*64),
                           lambda v:v['collection']['request'].update(nonce='0'*32),
                           lambda v:v['collection']['proofs']['reader'].update(artifact_id=1),
                           lambda v:v['before'].update(head='0'*40)):
                value=copy.deepcopy(saved); change(value); f.remote.replace(artifact['id'],value,member)
                with self.assertRaises(Refusal): f.finalize()
                self.assertIsNotNone(f.registry.binding()['fence']['pending'])
            f.remote.replace(artifact['id'],saved,member)
            f.remote.artifacts.remove(artifact)
            with self.assertRaises(Refusal): f.finalize()
            with self.assertRaises(Refusal): f.run('broker')
            self.assertIsNotNone(f.registry.binding()['fence']['pending'])
        self.exercise(continuation=check)

    def test_all_prior_tokens_and_late_history_refs_fail_closed(self):
        def check(*args):
            import trial_controller,trial_case,trial_launch
            from registry import Registry,trial_reference
            f=Outage(self,args); f.fifth()
            for name in trial_controller.CASE_CHAIN[:4]:
                token=f.native.provision.store(f.native.provision.root/trial_controller.case_journal('trial-case-read-staging',dict(name=name))).read()['value']['credential']['token']
                self.assertIn(token,f.revoked); f.revoked.discard(token)
                with self.assertRaises(Refusal): f.run('broker',change=lambda env:env.update(**{trial_case.CaseReadStaging.NAME:token}))
                env=f.job('trial case ready','trial_case_ready'); env[trial_case.CaseReadStaging.NAME]=token
                with self.assertRaises(Refusal): trial_launch.consume(f.registry,Registry(f.origin_factory(token),f.origin.coordinates),env,f.ready_hint,lambda:f.clock[0])
                env=f.job('trial case handoff','trial_case_handoff')
                env.update(GITHUB_REPOSITORY=f.p['authority_repository'],GITHUB_TOKEN='case-actions-read',**{trial_case.CaseReadStaging.NAME:token})
                import service
                with self.assertRaises(Refusal): service._case_producer(env,f.hint,'fixture-node','handoff',clock=lambda:f.clock[0],
                    api_factory=lambda token:f.api if token=='case-actions-read' else f.origin_factory(token),uploader_factory=lambda *a:f.upload)
                f.revoked.add(token)
            broker=next(j for j in f.remote.jobs if j['name'].startswith('broker ('))
            broker.update(status='in_progress',conclusion=None,completed_at=None)
            f.run('broker')
            for entry in f.admission.value['history']:
                prior,_=trial_case.read(f.origin,entry['revision'],lambda:f.clock[0])
                for value in (prior,dict(prior,execution=None),dict(prior,kind='trial-case-ready',execution=None)):
                    ref=trial_reference(value); revision=f.origin.api.refs[ref]
                    pages=f.api.pages; armed=[]
                    def move(path,collection=None):
                        result=pages(path,collection)
                        if path.endswith('/runs/109/artifacts') and not armed:
                            armed.append(True); f.origin.api.refs[ref]='0'*40
                        return result
                    f.api.pages=move
                    with self.assertRaises(Refusal): f.finalize()
                    f.api.pages=pages; f.origin.api.refs[ref]=revision
                    self.assertTrue(armed); self.assertIsNotNone(f.registry.binding()['fence']['pending'])
            self.assertFalse(any(a['name'].startswith('trial-case-terminal-') for a in f.remote.artifacts))
        self.exercise(continuation=check)

    def test_history_move_during_session_exception_and_receipt_inventory_stops_upload(self):
        for boundary in ('exception','receipt'):
            def check(*args):
                import trial_case
                from broker_refusal import BrokerRefusal
                from merge_receipts import ActionsReceipts
                from registry import trial_reference
                f=Outage(self,args); f.fifth()
                prior,_=trial_case.read(f.origin,f.admission.value['history'][3]['revision'],lambda:f.clock[0])
                reference=trial_reference(dict(prior,kind='trial-case-ready',execution=None))
                collect=broker_session.Session._collect; matches=ActionsReceipts._matches
                def collecting(session,op):
                    try: return collect(session,op)
                    except BrokerRefusal:
                        f.origin.api.refs[reference]='0'*40; raise
                def inventory(store,kind):
                    result=matches(store,kind)
                    if kind=='not-submitted' and f.failed: f.origin.api.refs[reference]='0'*40
                    return result
                target,attribute,replacement=(broker_session.Session,'_collect',collecting) if boundary=='exception' else (ActionsReceipts,'_matches',inventory)
                with patch.object(target,attribute,replacement),self.assertRaises(Refusal): f.run('broker')
                self.assertTrue(f.failed)
                self.assertFalse(any(a['name'].endswith('-not-submitted') for a in f.remote.artifacts))
                self.assertIsNotNone(f.registry.binding()['fence']['pending'])
            with self.subTest(boundary=boundary): self.exercise(continuation=check)

    def test_fifth_real_outage_closes_same_original_trial_without_dispatch(self):
        def check(*args):
            import trial_controller,trial_launch
            f=Outage(self,args)
            with patch.object(merge_transport,'isolated',side_effect=AssertionError('negative dispatched')):
                f.fifth()
                journals={name:f.native.provision.store(f.native.provision.root/trial_controller.case_journal('trial-controller',dict(name=name))).read()
                          for name in trial_controller.CASE_CHAIN[:4]}
                result=f.run('broker')
                self.assertEqual(result['refusal'],'readback_unavailable')
                self.assertEqual(len(f.failed),1)
                self.assertEqual(len(f.admission.value['history']),4)
                self.assertEqual(len(f.admission.value['candidates']['value']['candidates']),16)
                self.assertEqual(f.admission.record,f.original); self.assertEqual(f.origin.binding(),f.production)
                self.assertTrue(all(j['status']=='completed' and j['conclusion']=='success' for j in f.remote.jobs
                                    if j['name'].startswith(('controls (','final proof ('))))
                for prefix in ('controls-','final-proof-admin-','final-proof-reader-','final-proof-issuer-','final-proof-coding-','final-proof-merge-'):
                    self.assertTrue(any(a['name'].startswith(prefix) for a in f.remote.artifacts))
                self.assertFalse(any(a['name'].endswith(('-dispatch','-host-denied','-gate')) for a in f.remote.artifacts))
                terminal=f.finalize(); self.assertEqual(f.observe()['binding'],terminal)
                self.assertEqual([v['kind'] for v in terminal['fence']['completed'][-5:]],['not-submitted']*5)
                self.assertEqual(len(f.attempts),3); self.assertEqual(f.merges,[])
                self.assertEqual(terminal['deployment']['state'],'qualification'); self.assertIsNone(terminal['deployment']['qualification'])
                for run,raw in f.prior.items(): self.assertEqual(f.runs[run].raw,raw)
                for name,journal in journals.items():
                    self.assertEqual(f.native.provision.store(f.native.provision.root/trial_controller.case_journal('trial-controller',dict(name=name))).read(),journal)
                self.assertIn('fresh-fourth-case',f.revoked)
                f.clock[0]+=1000
                trial_launch.revoke(f.native.provision,f.origin_factory,name='authority-outage')
                self.assertIn(f.case_token,f.revoked)
        self.exercise(continuation=check)
