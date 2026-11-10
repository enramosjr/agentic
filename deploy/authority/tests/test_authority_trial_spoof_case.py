"""Ninth reservation observes foreign source checks through the existing API fixture."""
import backend_test_support
import copy
import unittest
from unittest.mock import patch

import merge_transport
import service
from trusted_ci_policy import Refusal
import test_authority_trial_forged_case as forged_fixture
import test_authority_trial_negative_case as negative_fixture
from test_authority_broker_evidence import stamp


class Spoof(forged_fixture.Forged):
    def through_eighth(self):
        import trial_controller
        self.eighth(); self.rejected(); self.host(); self.run('broker'); self.finalize(); self.observe()
        self.original=copy.deepcopy(self.admission.record)
        self.production=self.origin.binding()
        self.prior={run:copy.deepcopy(remote.raw) for run,remote in self.runs.items()}
        self.prior_terminal=self.registry.binding()
        self.prior_refs=copy.deepcopy(self.origin.api.refs)
        self.prior_journals={trial_controller.case_journal(base,dict(name=name)):
            self.native.provision.store(self.native.provision.root/trial_controller.case_journal(base,dict(name=name))).read()
            for name in trial_controller.CASE_CHAIN[:8] for base in ('trial-controller','trial-case-publication')}

    def ninth(self):
        self.through_eighth()
        self.second('spoofed-source',117,'fresh-ninth-case')
        with self.owner.assertRaisesRegex(Refusal,'pending'): self.coordinate()
        self.owner.assertEqual(self.close_handoff()['host_case'],'spoofed-source')
        # Hostile check input enters ONLY the source API transport, never an
        # authority report, task, role outcome, receipt or qualification artifact.
        self.spoof=dict(id=999,name=self.p['check_name'],app=dict(id=999),status='completed',
                        conclusion='success',head_sha=self.admission.request['snapshot']['merge'])
        self.checks.append(self.spoof)

    def host(self,change=None,selected=None,app_factory=None):
        if self.admission.candidate['name']!='spoofed-source':
            return super().host(change,selected,app_factory)
        env=self.job('trial host denial','trial_host_denial')
        env.update(GITHUB_REPOSITORY=self.p['authority_repository'],GITHUB_TOKEN='case-actions-read',
            AGENTIC_MERGE_PRIVATE_KEY=self.api.secrets['AGENTIC_MERGE_PRIVATE_KEY'],
            **{__import__('trial_case').CaseReadStaging.NAME:self.case_token})
        if change: change(env)
        result=service._case_producer(env,self.hint,'fixture-node','host-denial',clock=lambda:self.clock[0],
            api_factory=lambda token:self.api if token=='case-actions-read' else self.origin_factory(token),
            app_factory=app_factory or self.apps,token_factory=self.tokens,uploader_factory=lambda *a:self.upload,
            host_case=selected or self.admission.candidate['name'])
        self.remote.jobs[-1].update(status='completed',conclusion='success',completed_at=stamp(self.clock[0]))
        return result

    def observed(self):
        for purpose in ('admin','reader','issuer','coding','merge'): self.run('proof',purpose)
        self.run('publication-controls'); self.run('publish')

    def run(self,role,purpose=None,change=None):
        if self.admission.candidate['name']=='spoofed-source':
            # Retry a pre-effect refusal within the same running fixture job.
            # No intent, outcome, report or artifact is synthesized here; the
            # real producer must reject every independently changed input.
            name=('publication controls' if role=='publication-controls' else role)
            name+=' ('+(purpose or str(self.admission.candidate['submitted']['pr']))+')'
            for job in self.remote.jobs:
                if job['name']==name:
                    job.update(status='in_progress',conclusion=None,completed_at=None)
        return super().run(role,purpose,change)


@unittest.skipIf(getattr(negative_fixture.NativeNegative,'__unittest_skip__',False),'optional cryptography required')
class NativeSpoof(unittest.TestCase):
    fixture=negative_fixture.NativeNegative.fixture
    prepared=negative_fixture.NativeNegative.prepared
    connected=negative_fixture.NativeNegative.connected
    configured=negative_fixture.NativeNegative.configured
    exercise=negative_fixture.NativeNegative.exercise
    prepare=negative_fixture.NativeNegative.prepare

    def test_ninth_closes_observed_spoof_preserving_original_eight(self):
        def check(*args):
            import trial_controller,trial_launch
            f=Spoof(self,args); f.ninth()
            with patch.object(merge_transport,'isolated',side_effect=AssertionError('spoof dispatched')), \
                    patch.object(service,'_publish_bound',side_effect=AssertionError('spoof published genuine issuer')):
                f.observed(); f.host()
                self.assertEqual(f.run('broker')['state'],'host-denied')
                terminal=f.finalize(); self.assertEqual(f.observe()['binding'],terminal)
            self.assertEqual(f.merges,[]); self.assertEqual(len(f.attempts),7)
            self.assertEqual(f.admission.record,f.original); self.assertEqual(f.origin.binding(),f.production)
            self.assertEqual(len(f.admission.value['history']),8)
            self.assertEqual(len(f.admission.value['candidates']['value']['candidates']),16)
            self.assertEqual(terminal['fence']['completed'][:-1],f.prior_terminal['fence']['completed'])
            self.assertIsNone(terminal['deployment']['qualification'])
            self.assertEqual(terminal['deployment']['state'],'qualification')
            for run,raw in f.prior.items(): self.assertEqual(f.runs[run].raw,raw)
            for ref,revision in f.prior_refs.items(): self.assertEqual(f.origin.api.refs[ref],revision)
            for name,saved in f.prior_journals.items(): self.assertEqual(f.native.provision.store(f.native.provision.root/name).read(),saved)
            for name in trial_controller.CASE_CHAIN[:8]:
                saved=f.native.provision.store(f.native.provision.root/trial_controller.case_journal('trial-case-read-staging',dict(name=name))).read()
                self.assertIn(saved['value']['credential']['token'],f.revoked)
            _,_,publication=f.artifact('trial-publication-observation-')
            self.assertIn(f.spoof,publication['observation']['checks'])
            self.assertNotIn('refusal',publication)
            self.assertFalse(any(a['name'].startswith(('evidence-','trial-publication-denial-')) for a in f.remote.artifacts))
            self.assertFalse(any(c['head_sha']==f.spoof['head_sha'] and c['app']['id']==f.p['app_id'] for c in f.checks))
            f.clock[0]+=1000
            trial_launch.revoke(f.native.provision,f.origin_factory,name='forged-records')
            trial_launch.revoke(f.native.provision,f.origin_factory,name='spoofed-source')
            self.assertIn(f.case_token,f.revoked)
        self.exercise(continuation=check,export_files=forged_fixture.EXPORT)

    def test_all_eight_owned_completions_are_required_before_ninth_selection(self):
        import trial_controller
        for name in trial_controller.CASE_CHAIN[:8]:
            def check(*args):
                f=Spoof(self,args); f.through_eighth()
                store=f.native.provision.store(f.native.provision.root/trial_controller.case_journal('trial-controller',dict(name=name)))
                saved=store.read(); value=copy.deepcopy(saved['value'])
                value['terminal']['binding']['fence']['completed'][-1]['receipt_digest']='0'*64
                store.write(saved,value)
                with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open('prompt','spoofed-source',f.source)
                self.assertIsNone(f.native.provision.store(f.native.provision.root/'trial-controller-spoofed-source').read())
            with self.subTest(name=name): self.exercise(continuation=check,export_files=forged_fixture.EXPORT)

    def test_foreign_check_and_every_external_prerequisite_are_required(self):
        def check(*args):
            f=Spoof(self,args); f.ninth()
            for purpose in ('admin','reader','issuer','coding','merge'): f.run('proof',purpose)
            f.run('publication-controls')
            saved=copy.deepcopy(f.spoof)
            for defect in ({'name':'other'},{'head_sha':'0'*40},{'status':'in_progress'},
                           {'conclusion':'failure'},{'app':dict(id=f.p['app_id'])},
                           {'app':{}},{'app':dict(id=True)},{'app':dict(id=999.0)}):
                f.spoof.clear(); f.spoof.update(saved,**defect)
                with self.subTest(defect=defect),self.assertRaisesRegex(Refusal,'actual spoofed issuer success missing|already has authoritative success'): f.run('publish')
            f.spoof.clear(); f.spoof.update(saved)
            f.checks.remove(f.spoof)
            with self.assertRaisesRegex(Refusal,'actual spoofed issuer success missing'): f.run('publish')
            f.checks.append(f.spoof)
            authoritative=dict(saved,app=dict(id=f.p['app_id'])); f.checks.append(authoritative)
            with self.assertRaisesRegex(Refusal,'already has authoritative success'): f.run('publish')
            f.checks.remove(authoritative)
            reviews=f.reviews
            for wrong in ([],[dict(reviews[0],state='DISMISSED')],
                          [dict(reviews[0],user=dict(id=999,type='User'))],
                          [dict(reviews[0],commit_id='0'*40)]):
                f.reviews=wrong
                with self.assertRaisesRegex(Refusal,'approval|review|human'): f.run('publish')
            f.reviews=reviews
            proof=next(a for a in f.remote.artifacts if a['name'].startswith('proof-reader-'))
            f.remote.artifacts.remove(proof)
            with self.assertRaises(Refusal): f.run('publish')
            f.remote.artifacts.append(proof)
            pages=f.source.pages
            def obligations(path,collection=None):
                value=pages(path,collection)
                if '/rules/branches/' in path:
                    value=copy.deepcopy(value)
                    next(r for r in value if r['type']=='required_status_checks')['parameters']['required_status_checks'].append(
                        dict(context='another-obligation',integration_id=888))
                return value
            f.source.pages=obligations
            tokens=f.tokens
            def with_rules(token):
                scoped=tokens(token); pages=scoped.pages
                scoped.pages=lambda path,collection=None:obligations(path,collection) if '/rules/branches/' in path else pages(path,collection)
                return scoped
            f.tokens=with_rules
            with self.assertRaisesRegex(Refusal,'another host obligation'): f.run('publish')
            f.tokens=tokens
            f.source.pages=pages
            self.assertFalse(any(a['name'].startswith('trial-publication-') for a in f.remote.artifacts))
            self.assertEqual(len(f.attempts),6)
        self.exercise(continuation=check,export_files=forged_fixture.EXPORT)

    def test_old_capabilities_and_all_twenty_four_late_history_refs_block_effects(self):
        def check(*args):
            import trial_controller,trial_case,trial_launch
            from registry import Registry,trial_reference
            f=Spoof(self,args); f.ninth(); f.observed()
            old=[f.api.secrets['AGENTIC_TRIAL_ORIGIN_TOKEN']]
            for name in trial_controller.CASE_CHAIN[:8]:
                token=f.native.provision.store(f.native.provision.root/trial_controller.case_journal('trial-case-read-staging',dict(name=name))).read()['value']['credential']['token']
                self.assertIn(token,f.revoked); old.append(token)
            for token in old:
                f.revoked.discard(token)
                with self.assertRaises(Refusal): f.run('proof','reader',change=lambda env:env.update(**{trial_case.CaseReadStaging.NAME:token}))
                env=f.job('trial case ready','trial_case_ready'); env[trial_case.CaseReadStaging.NAME]=token
                with self.assertRaises(Refusal): trial_launch.consume(f.registry,Registry(f.origin_factory(token),f.origin.coordinates),env,f.ready_hint,lambda:f.clock[0])
                env=f.job('trial case handoff','trial_case_handoff')
                env.update(GITHUB_REPOSITORY=f.p['authority_repository'],GITHUB_TOKEN='case-actions-read',**{trial_case.CaseReadStaging.NAME:token})
                with self.assertRaises(Refusal): service._case_producer(env,f.hint,'fixture-node','handoff',clock=lambda:f.clock[0],
                    api_factory=lambda token:f.api if token=='case-actions-read' else f.origin_factory(token),uploader_factory=lambda *a:f.upload)
                f.revoked.add(token)
            checked=[]
            for entry in f.admission.value['history']:
                prior,_=trial_case.read(f.origin,entry['revision'],lambda:f.clock[0])
                for value in (prior,dict(prior,execution=None),dict(prior,kind='trial-case-ready',execution=None)):
                    ref=trial_reference(value); revision=f.origin.api.refs[ref]
                    pages=f.api.pages; armed=[]
                    def move(path,collection=None):
                        result=pages(path,collection)
                        if path.endswith('/runs/117/artifacts') and not armed:
                            armed.append(True); f.origin.api.refs[ref]='0'*40
                        return result
                    f.api.pages=move
                    with self.assertRaises(Refusal): f.host()
                    f.api.pages=pages; f.origin.api.refs[ref]=revision
                    self.assertTrue(armed); checked.append(ref)
            self.assertEqual(len(set(checked)),24)
            self.assertEqual(len(f.attempts),6)
            self.assertFalse(any(a['name'].startswith('trial-host-intent-') for a in f.remote.artifacts))
        self.exercise(continuation=check,export_files=forged_fixture.EXPORT)

    def test_spoof_and_review_are_reread_after_durable_host_intent(self):
        for fault in ('check','approval','issuer'):
            def check(*args):
                f=Spoof(self,args); f.ninth(); f.observed(); upload=f.upload
                def withdraw(name,raw):
                    result=upload(name,raw)
                    if name.startswith('trial-host-intent-'):
                        if fault=='check': f.checks.remove(f.spoof)
                        elif fault=='approval': f.reviews=[]
                        else: f.checks.append(dict(f.spoof,app=dict(id=f.p['app_id'])))
                    return result
                f.upload=withdraw
                with self.assertRaises(Refusal): f.host()
                with self.assertRaises(Refusal): f.host()
                self.assertEqual(len(f.attempts),6)
                self.assertFalse(any(a['name'].startswith('trial-host-denial-') for a in f.remote.artifacts))
            with self.subTest(fault=fault): self.exercise(continuation=check,export_files=forged_fixture.EXPORT)

    def test_unknown_publication_and_host_uploads_never_replay(self):
        for prefix in ('trial-publication-intent-','trial-publication-observation-','trial-host-intent-','trial-host-denial-'):
            def check(*args):
                f=Spoof(self,args); f.ninth(); upload=f.upload; effects=[]
                def lose(name,raw):
                    result=upload(name,raw)
                    if name.startswith(prefix):
                        effects.append(name)
                        if prefix in ('trial-publication-observation-','trial-host-denial-'):
                            item=next(a for a in f.remote.artifacts if a['id']==result)
                            f.remote.artifacts.remove(item); f.remote.raw.pop(result)
                        raise OSError('fixture unknown acknowledgement')
                    return result
                f.upload=lose
                if prefix.startswith('trial-publication-'):
                    with self.assertRaises(OSError): f.observed()
                    job=next(j for j in f.remote.jobs if j['name'].startswith('publish ('))
                    job.update(status='in_progress',conclusion=None,completed_at=None)
                    with self.assertRaisesRegex(Refusal,'never replay'): f.run('publish')
                else:
                    f.observed()
                    with self.assertRaises(OSError): f.host()
                    with self.assertRaisesRegex(Refusal,'never replay'): f.host()
                with self.assertRaises(Refusal): f.run('broker')
                with self.assertRaises(Refusal): f.finalize()
                self.assertEqual(len(effects),1)
                self.assertIsNotNone(f.registry.binding()['fence']['pending'])
            with self.subTest(prefix=prefix): self.exercise(continuation=check,export_files=forged_fixture.EXPORT)

    def test_wrong_denial_and_unknown_host_request_do_not_count(self):
        for fault in ('wrong','unknown','obligation','status'):
            def check(*args):
                from trusted_ci_github import HostRefusal
                f=Spoof(self,args); f.ninth(); f.observed(); f.host_fault=fault
                tokens=f.tokens
                def factory(token):
                    scoped=tokens(token); fetch=scoped.fetch
                    def send(path,**kw):
                        try: return fetch(path,**kw)
                        except HostRefusal as error:
                            if path.endswith('/merge') and fault in ('obligation','status'):
                                raise HostRefusal(401 if fault=='status' else 403,'required_check','other' if fault=='obligation' else f.p['check_name'])
                            raise
                    scoped.fetch=send; return scoped
                f.tokens=factory
                with self.assertRaises(OSError if fault=='unknown' else Refusal): f.host()
                with self.assertRaises(Refusal): f.run('broker')
                with self.assertRaises(Refusal): f.finalize()
                self.assertFalse(any(a['name'].startswith('trial-host-denial-') for a in f.remote.artifacts))
                self.assertIsNotNone(f.registry.binding()['fence']['pending'])
            with self.subTest(fault=fault): self.exercise(continuation=check,export_files=forged_fixture.EXPORT)

    def test_retained_substitutions_cannot_clear_named_fence(self):
        def check(*args):
            f=Spoof(self,args); f.ninth(); f.observed(); f.host(); f.run('broker')
            for prefix,changes in (
                ('trial-publication-observation-',(lambda v:v.update(observed=float(v['observed'])),
                    lambda v:v['snapshot'].update(run_attempt=True),lambda v:v['intent']['inputs'].update(task_digest='0'*64),
                    lambda v:v['observation']['checks'].clear())),
                ('trial-host-denial-',(lambda v:v['observation'].update(http_status=True),
                    lambda v:v['observation'].update(denied_obligation='other'),lambda v:v['snapshot'].update(run_attempt=True),
                    lambda v:v['observation']['publication'].update(digest='0'*64),
                    lambda v:v['observation']['checks'].clear()))):
                artifact,member,saved=f.artifact(prefix)
                for change in changes:
                    value=copy.deepcopy(saved); change(value); f.remote.replace(artifact['id'],value,member)
                    with self.assertRaises(Refusal): f.finalize()
                    self.assertIsNotNone(f.registry.binding()['fence']['pending'])
                f.remote.replace(artifact['id'],saved,member)
            job=next(j for j in f.remote.jobs if j['name'].startswith('publish ('))
            job.update(status='in_progress',conclusion=None,completed_at=None)
            with self.assertRaises(Refusal): f.finalize()
            job.update(status='completed',conclusion='success',completed_at=stamp(f.clock[0]))
            artifact,_,_=f.artifact('trial-publication-observation-'); f.remote.artifacts.remove(artifact)
            with self.assertRaises(Refusal): f.finalize()
            self.assertFalse(any(a['name'].startswith('trial-case-terminal-') for a in f.remote.artifacts))
        self.exercise(continuation=check,export_files=forged_fixture.EXPORT)

    def test_generic_session_receipt_cannot_close_ninth(self):
        def check(*args):
            f=Spoof(self,args); f.ninth(); f.observed()
            name='broker ('+str(f.admission.candidate['submitted']['pr'])+')'
            env=f.job(name,'broker')
            env.update({'AGENTIC_'+p.upper()+'_PRIVATE_KEY':f.api.secrets['AGENTIC_'+p.upper()+'_PRIVATE_KEY'] for p in ('merge','reader')})
            with self.assertRaises(Refusal): service._trial_producer(f.admission,env,f.admission.request,'fixture-node','broker',
                app_factory=f.apps,token_factory=f.tokens,uploader_factory=lambda *a:f.upload,sleeper=f.sleeper)
            next(j for j in f.remote.jobs if j['name']==name).update(status='completed',conclusion='failure',completed_at=stamp(f.clock[0]))
            self.assertTrue(any(a['name'].endswith('-not-submitted') for a in f.remote.artifacts))
            with self.assertRaises(Refusal): f.finalize()
            self.assertIsNotNone(f.registry.binding()['fence']['pending'])
        self.exercise(continuation=check,export_files=forged_fixture.EXPORT)

    def test_late_target_after_blocking_terminal_admission_blocks_writes(self):
        def check(*args):
            from registry import Registry
            f=Spoof(self,args); f.ninth(); f.observed(); f.host(); f.run('broker')
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
        self.exercise(continuation=check,export_files=forged_fixture.EXPORT)

    def test_history_move_in_actual_session_exception_and_receipt_inventory_blocks_upload(self):
        for boundary in ('exception','receipt'):
            def check(*args):
                import broker_session,trial_case
                from merge_receipts import ActionsReceipts
                from registry import trial_reference
                f=Spoof(self,args); f.ninth(); f.observed()
                references=[]
                for entry in f.admission.value['history']:
                    prior,_=trial_case.read(f.origin,entry['revision'],lambda:f.clock[0])
                    references.extend(trial_reference(value) for value in
                        (prior,dict(prior,execution=None),dict(prior,kind='trial-case-ready',execution=None)))
                # Warm the real Session rendezvous without supplying acceptance.
                # It then fails on the actually absent verifier job, without
                # consuming a fresh120s window for each independent ref race.
                f.job('controls ('+str(f.admission.candidate['submitted']['pr'])+')','controls')
                for purpose in ('admin','reader','issuer','coding','merge'): f.job('final proof ('+purpose+')',purpose+'_final_proof')
                collect=broker_session.Session._collect; matches=ActionsReceipts._matches; moved=[]
                def collecting(session,op):
                    try: return collect(session,op)
                    except Refusal:
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
                for reference in references:
                    revision=f.origin.api.refs[reference]
                    with patch.object(target,attribute,replacement),self.assertRaises(Refusal):
                        service._trial_producer(f.admission,env,f.admission.request,'fixture-node','broker',
                            app_factory=f.apps,token_factory=f.tokens,uploader_factory=lambda *a:f.upload,sleeper=f.sleeper)
                    self.assertEqual(f.origin.api.refs[reference],'0'*40)
                    f.origin.api.refs[reference]=revision
                self.assertEqual(len(moved),24)
                self.assertFalse(any(a['name'].endswith('-not-submitted') for a in f.remote.artifacts))
                self.assertIsNotNone(f.registry.binding()['fence']['pending'])
            with self.subTest(boundary=boundary): self.exercise(continuation=check,export_files=forged_fixture.EXPORT)
