"""Seventh original reservation uses hostile bytes from the initial worker export."""
import backend_test_support
import copy
import unittest
from unittest.mock import patch

import merge_transport
import service
from trusted_ci_policy import Refusal
import test_authority_trial_negative_case as negative_fixture


PERMISSIVE = b'import sys\nsys.exit(0)\n'
REPLACEMENT = '.ai/scripts/tests/test_replaced.py'
EXPORT = {'.ai/scripts/lifecycle.py':dict(content=PERMISSIVE,executable=False),
          REPLACEMENT:dict(content=b'def test_acceptance():\n    assert True\n',executable=False)}


class Replaced(negative_fixture.Negative):
    def through_sixth(self):
        import trial_controller
        self.sixth(); self.rejected(); self.host(); self.run('broker'); self.finalize(); self.observe()
        self.original=copy.deepcopy(self.admission.record)
        self.production=self.origin.binding()
        self.prior={run:copy.deepcopy(remote.raw) for run,remote in self.runs.items()}
        self.prior_terminal=self.registry.binding()
        self.prior_refs=copy.deepcopy(self.origin.api.refs)
        self.prior_journals={trial_controller.case_journal(base,dict(name=name)):
            self.native.provision.store(self.native.provision.root/trial_controller.case_journal(base,dict(name=name))).read()
            for name in trial_controller.CASE_CHAIN[:6] for base in ('trial-controller','trial-case-publication')}

    def seventh(self):
        self.through_sixth()
        self.second('replaced-checks',113,'fresh-seventh-case')
        with self.owner.assertRaisesRegex(Refusal,'pending'): self.coordinate()
        self.owner.assertEqual(self.close_handoff()['host_case'],'replaced-checks')


@unittest.skipIf(getattr(negative_fixture.NativeNegative,'__unittest_skip__',False),'optional cryptography required')
class NativeReplaced(unittest.TestCase):
    fixture=negative_fixture.NativeNegative.fixture
    prepared=negative_fixture.NativeNegative.prepared
    connected=negative_fixture.NativeNegative.connected
    configured=negative_fixture.NativeNegative.configured
    exercise=negative_fixture.NativeNegative.exercise
    prepare=negative_fixture.NativeNegative.prepare

    def test_seventh_closes_genuine_replacement_and_preserves_original_six(self):
        def check(*args):
            import trial_controller,trial_launch
            f=Replaced(self,args); f.seventh()
            self.assertEqual(f.admission.worker['files']['.ai/scripts/lifecycle.py'],EXPORT['.ai/scripts/lifecycle.py'])
            self.assertEqual(f.admission.worker['files'][REPLACEMENT],EXPORT[REPLACEMENT])
            with patch.object(merge_transport,'isolated',side_effect=AssertionError('negative dispatched')):
                f.rejected(); f.host()
                self.assertEqual(f.run('broker')['state'],'host-denied')
                terminal=f.finalize(); self.assertEqual(f.observe()['binding'],terminal)
            self.assertIn('negative-permissive-script',f.events)
            self.assertIn('negative-box-clean',f.events); self.assertIn('negative-disk-clean',f.events)
            self.assertEqual(f.merges,[]); self.assertEqual(len(f.attempts),5)
            self.assertEqual(f.admission.record,f.original); self.assertEqual(f.origin.binding(),f.production)
            self.assertEqual(len(f.admission.value['history']),6)
            self.assertEqual(len(f.admission.value['candidates']['value']['candidates']),16)
            self.assertEqual({v['submitted']['tree'] for v in f.admission.value['candidates']['value']['candidates']},
                             {f.admission.value['worker']['submitted']['tree']})
            self.assertEqual(terminal['fence']['completed'][:-1],f.prior_terminal['fence']['completed'])
            self.assertIsNone(terminal['deployment']['qualification'])
            for run,raw in f.prior.items(): self.assertEqual(f.runs[run].raw,raw)
            for ref,revision in f.prior_refs.items(): self.assertEqual(f.origin.api.refs[ref],revision)
            for name,saved in f.prior_journals.items(): self.assertEqual(f.native.provision.store(f.native.provision.root/name).read(),saved)
            for name in trial_controller.CASE_CHAIN[:6]:
                saved=f.native.provision.store(f.native.provision.root/trial_controller.case_journal('trial-case-read-staging',dict(name=name))).read()
                self.assertIn(saved['value']['credential']['token'],f.revoked)
            f.clock[0]+=1000
            trial_launch.revoke(f.native.provision,f.origin_factory,name='replaced-checks')
            self.assertIn(f.case_token,f.revoked)
        self.exercise(continuation=check,export_files=EXPORT)

    def test_original_binary_only_export_cannot_establish_replaced_checks(self):
        def check(*args):
            f=Replaced(self,args); f.seventh(); f.run('verify')
            for purpose in ('admin','reader','issuer','coding','merge'): f.run('proof',purpose)
            f.run('publication-controls')
            with self.assertRaisesRegex(Refusal,'replacement missing'): f.run('publish')
            with self.assertRaises(Refusal): f.host()
            self.assertEqual(len(f.attempts),4)
            self.assertFalse(any(a['name'].startswith('trial-publication-') for a in f.remote.artifacts))
            self.assertIsNotNone(f.registry.binding()['fence']['pending'])
        self.exercise(continuation=check)

    def test_every_owned_completion_is_required_before_seventh_selection(self):
        import trial_controller
        for name in trial_controller.CASE_CHAIN[:6]:
            def check(*args):
                f=Replaced(self,args); f.through_sixth()
                store=f.native.provision.store(f.native.provision.root/trial_controller.case_journal('trial-controller',dict(name=name)))
                saved=store.read(); value=copy.deepcopy(saved['value'])
                value['terminal']['binding']['fence']['completed'][-1]['receipt_digest']='0'*64
                store.write(saved,value)
                with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open('prompt','replaced-checks',f.source)
                self.assertIsNone(f.native.provision.store(f.native.provision.root/'trial-controller-replaced-checks').read())
            with self.subTest(name=name): self.exercise(continuation=check,export_files=EXPORT)

    def test_failed_observation_and_external_prerequisites_are_required(self):
        def check(*args):
            f=Replaced(self,args); f.seventh(); f.run('verify')
            for purpose in ('admin','reader','issuer','coding','merge'): f.run('proof',purpose)
            f.run('publication-controls')
            artifact,member,saved=f.artifact('evidence-')
            changes=(lambda v:v['result'].update(cleanup_complete=False),
                     lambda v:v['result']['report']['outcomes'][0].update(status='success'),
                     lambda v:v['result']['report'].update(generation=True),
                     lambda v:v['result']['report']['snapshot'].update(head='0'*40),
                     lambda v:v['result']['report']['execution'].update(run_id=111))
            for change in changes:
                value=copy.deepcopy(saved); change(value); f.remote.replace(artifact['id'],value,member)
                with self.assertRaises(Refusal): f.run('publish')
            f.remote.replace(artifact['id'],saved,member)
            proof=next(a for a in f.remote.artifacts if a['name'].startswith('proof-reader-'))
            f.remote.artifacts.remove(proof)
            with self.assertRaises(Refusal): f.run('publish')
            f.remote.artifacts.append(proof)
            reviews=f.reviews
            for wrong in ([],[dict(reviews[0],user=dict(id=999,type='User'))]):
                f.reviews=wrong
                with self.assertRaises(Refusal): f.run('publish')
            f.reviews=reviews
            self.assertFalse(any(a['name'].startswith('trial-publication-') for a in f.remote.artifacts))
            self.assertEqual(len(f.attempts),4)
        self.exercise(continuation=check,export_files=EXPORT)

    def test_old_capabilities_and_all_eighteen_late_history_refs_block_effects(self):
        def check(*args):
            import trial_controller,trial_case,trial_launch
            from registry import Registry,trial_reference
            f=Replaced(self,args); f.seventh(); f.rejected()
            old=[f.api.secrets['AGENTIC_TRIAL_ORIGIN_TOKEN']]
            for name in trial_controller.CASE_CHAIN[:6]:
                token=f.native.provision.store(f.native.provision.root/trial_controller.case_journal('trial-case-read-staging',dict(name=name))).read()['value']['credential']['token']
                self.assertIn(token,f.revoked); old.append(token)
            for token in old:
                # Test identity rejection independently of transport revocation.
                f.revoked.discard(token)
                with self.assertRaises(Refusal): f.run('proof','reader',change=lambda env:env.update(**{trial_case.CaseReadStaging.NAME:token}))
                env=f.job('trial case ready','trial_case_ready'); env[trial_case.CaseReadStaging.NAME]=token
                with self.assertRaises(Refusal): trial_launch.consume(f.registry,Registry(f.origin_factory(token),f.origin.coordinates),env,f.ready_hint,lambda:f.clock[0])
                env=f.job('trial case handoff','trial_case_handoff')
                env.update(GITHUB_REPOSITORY=f.p['authority_repository'],GITHUB_TOKEN='case-actions-read',**{trial_case.CaseReadStaging.NAME:token})
                with self.assertRaises(Refusal): service._case_producer(env,f.hint,'fixture-node','handoff',clock=lambda:f.clock[0],
                    api_factory=lambda token:f.api if token=='case-actions-read' else f.origin_factory(token),uploader_factory=lambda *a:f.upload)
                f.revoked.add(token)
            for entry in f.admission.value['history']:
                prior,_=trial_case.read(f.origin,entry['revision'],lambda:f.clock[0])
                for value in (prior,dict(prior,execution=None),dict(prior,kind='trial-case-ready',execution=None)):
                    ref=trial_reference(value); revision=f.origin.api.refs[ref]
                    pages=f.api.pages; armed=[]
                    def move(path,collection=None):
                        result=pages(path,collection)
                        if path.endswith('/runs/113/artifacts') and not armed:
                            armed.append(True); f.origin.api.refs[ref]='0'*40
                        return result
                    f.api.pages=move
                    with self.assertRaises(Refusal): f.host()
                    f.api.pages=pages; f.origin.api.refs[ref]=revision
                    self.assertTrue(armed)
            self.assertEqual(len(f.attempts),4)
            self.assertFalse(any(a['name'].startswith('trial-host-intent-') for a in f.remote.artifacts))
        self.exercise(continuation=check,export_files=EXPORT)

    def test_unknown_publication_and_host_uploads_are_never_replayed(self):
        for prefix in ('trial-publication-intent-','trial-publication-denial-','trial-host-intent-','trial-host-denial-'):
            def check(*args):
                f=Replaced(self,args); f.seventh(); upload=f.upload; effects=[]
                def lose(name,raw):
                    result=upload(name,raw)
                    if name.startswith(prefix):
                        effects.append(name)
                        if prefix.endswith('denial-'):
                            item=next(a for a in f.remote.artifacts if a['id']==result)
                            f.remote.artifacts.remove(item); f.remote.raw.pop(result)
                        raise OSError('fixture unknown acknowledgement')
                    return result
                f.upload=lose
                if prefix.startswith('trial-publication-'):
                    with self.assertRaises(OSError): f.rejected()
                    job=next(j for j in f.remote.jobs if j['name'].startswith('publish ('))
                    job.update(status='in_progress',conclusion=None,completed_at=None)
                    with self.assertRaisesRegex(Refusal,'never replay'): f.run('publish')
                else:
                    f.rejected()
                    with self.assertRaises(OSError): f.host()
                    with self.assertRaisesRegex(Refusal,'never replay'): f.host()
                with self.assertRaises(Refusal): f.run('broker')
                with self.assertRaises(Refusal): f.finalize()
                self.assertEqual(len(effects),1)
                self.assertIsNotNone(f.registry.binding()['fence']['pending'])
            with self.subTest(prefix=prefix): self.exercise(continuation=check,export_files=EXPORT)

    def test_wrong_denial_category_and_unknown_host_request_do_not_count(self):
        for fault in ('wrong','unknown'):
            def check(*args):
                f=Replaced(self,args); f.seventh(); f.rejected(); f.host_fault=fault
                with self.assertRaises(OSError if fault=='unknown' else Refusal): f.host()
                with self.assertRaises(Refusal): f.run('broker')
                with self.assertRaises(Refusal): f.finalize()
                self.assertFalse(any(a['name'].startswith('trial-host-denial-') for a in f.remote.artifacts))
                self.assertIsNotNone(f.registry.binding()['fence']['pending'])
            with self.subTest(fault=fault): self.exercise(continuation=check,export_files=EXPORT)

    def test_retained_substitutions_cannot_clear_named_fence(self):
        def check(*args):
            f=Replaced(self,args); f.seventh(); f.rejected(); f.host(); f.run('broker')
            for prefix,changes in (
                ('trial-publication-denial-',(lambda v:v.update(observed=float(v['observed'])),
                    lambda v:v['snapshot'].update(run_attempt=True),lambda v:v['intent']['inputs'].update(evidence_digest='0'*64),
                    lambda v:v.update(refusal='unrelated failure'))),
                ('trial-host-denial-',(lambda v:v['observation'].update(http_status=True),
                    lambda v:v['observation'].update(denied_obligation='other'),lambda v:v['snapshot'].update(run_attempt=True),
                    lambda v:v['observation']['publication'].update(digest='0'*64)))):
                artifact,member,saved=f.artifact(prefix)
                for change in changes:
                    value=copy.deepcopy(saved); change(value); f.remote.replace(artifact['id'],value,member)
                    with self.assertRaises(Refusal): f.finalize()
                    self.assertIsNotNone(f.registry.binding()['fence']['pending'])
                f.remote.replace(artifact['id'],saved,member)
            artifact,_,_=f.artifact('trial-publication-denial-'); f.remote.artifacts.remove(artifact)
            with self.assertRaises(Refusal): f.finalize()
            self.assertFalse(any(a['name'].startswith('trial-case-terminal-') for a in f.remote.artifacts))
        self.exercise(continuation=check,export_files=EXPORT)

    def test_genuine_generic_session_receipt_does_not_close_seventh(self):
        def check(*args):
            from test_authority_broker_evidence import stamp
            f=Replaced(self,args); f.seventh(); f.rejected()
            name='broker ('+str(f.admission.candidate['submitted']['pr'])+')'
            env=f.job(name,'broker')
            env.update({'AGENTIC_'+p.upper()+'_PRIVATE_KEY':f.api.secrets['AGENTIC_'+p.upper()+'_PRIVATE_KEY'] for p in ('merge','reader')})
            with self.assertRaises(Refusal): service._trial_producer(f.admission,env,f.admission.request,'fixture-node','broker',
                app_factory=f.apps,token_factory=f.tokens,uploader_factory=lambda *a:f.upload,sleeper=f.sleeper)
            next(j for j in f.remote.jobs if j['name']==name).update(status='completed',conclusion='failure',completed_at=stamp(f.clock[0]))
            self.assertTrue(any(a['name'].endswith('-not-submitted') for a in f.remote.artifacts))
            self.assertFalse(any(a['name'].startswith('trial-host-denial-') for a in f.remote.artifacts))
            with self.assertRaises(Refusal): f.finalize()
            self.assertIsNotNone(f.registry.binding()['fence']['pending'])
        self.exercise(continuation=check,export_files=EXPORT)

    def test_late_target_movement_after_blocking_terminal_admission_blocks_writes(self):
        def check(*args):
            from registry import Registry
            f=Replaced(self,args); f.seventh(); f.rejected(); f.host(); f.run('broker')
            finalize=Registry.finalize_operation; tokens=f.tokens; post=f.api.post
            armed=[]; writes=[]
            def scoped(token):
                result=tokens(token); get=result.get
                def read(path):
                    value=get(path)
                    if armed and path=='/repos/'+f.p['repository']: f.source.refs['main']='0'*40
                    return value
                result.get=read; return result
            def write(path,body):
                if armed and '/git/' in path: writes.append(path)
                return post(path,body)
            def close(registry,*args,**kwargs):
                armed.append(True); return finalize(registry,*args,**kwargs)
            f.tokens=scoped; f.api.post=write
            with patch.object(Registry,'finalize_operation',close),self.assertRaises(Refusal): f.finalize()
            self.assertTrue(armed); self.assertEqual(writes,[])
            self.assertFalse(any(a['name'].startswith('trial-case-terminal-') for a in f.remote.artifacts))
            self.assertIsNotNone(f.registry.binding()['fence']['pending'])
            return f.source.refs['main']
        self.exercise(continuation=check,export_files=EXPORT)

    def test_history_move_in_session_exception_and_receipt_inventory_blocks_upload(self):
        for boundary in ('exception','receipt'):
            def check(*args):
                import broker_session,trial_case
                from merge_receipts import ActionsReceipts
                from registry import trial_reference
                f=Replaced(self,args); f.seventh(); f.rejected()
                prior,_=trial_case.read(f.origin,f.admission.value['history'][5]['revision'],lambda:f.clock[0])
                reference=trial_reference(dict(prior,kind='trial-case-ready',execution=None))
                collect=broker_session.Session._collect; matches=ActionsReceipts._matches; moved=[]
                def collecting(session,op):
                    try: return collect(session,op)
                    except Refusal as error:
                        self.assertIn('rendezvous timed out',str(error))
                        moved.append(True); f.origin.api.refs[reference]='0'*40; raise
                def inventory(store,kind):
                    result=matches(store,kind)
                    if kind=='not-submitted':
                        moved.append(True); f.origin.api.refs[reference]='0'*40
                    return result
                target,attribute,replacement=(broker_session.Session,'_collect',collecting) if boundary=='exception' else (ActionsReceipts,'_matches',inventory)
                name='broker ('+str(f.admission.candidate['submitted']['pr'])+')'
                env=f.job(name,'broker')
                env.update({'AGENTIC_'+p.upper()+'_PRIVATE_KEY':f.api.secrets['AGENTIC_'+p.upper()+'_PRIVATE_KEY'] for p in ('merge','reader')})
                with patch.object(target,attribute,replacement),self.assertRaises(Refusal):
                    service._trial_producer(f.admission,env,f.admission.request,'fixture-node','broker',
                        app_factory=f.apps,token_factory=f.tokens,uploader_factory=lambda *a:f.upload,sleeper=f.sleeper)
                self.assertTrue(moved)
                self.assertFalse(any(a['name'].endswith('-not-submitted') for a in f.remote.artifacts))
                self.assertIsNotNone(f.registry.binding()['fence']['pending'])
            with self.subTest(boundary=boundary): self.exercise(continuation=check,export_files=EXPORT)
