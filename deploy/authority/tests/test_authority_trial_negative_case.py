"""Sixth original reservation retains genuine verifier and issuer failures."""
import backend_test_support
import copy
import unittest
from unittest.mock import patch

import service
import merge_transport
from trusted_ci_github import HostRefusal
from trusted_ci_policy import Refusal
import test_authority_trial_outage_case as outage_fixture


class Negative(outage_fixture.Outage):
    def through_fifth(self):
        self.fifth(); self.run('broker'); self.finalize(); self.observe()
        self.original=copy.deepcopy(self.admission.record)
        self.production=self.origin.binding()
        self.prior={run:copy.deepcopy(remote.raw) for run,remote in self.runs.items()}
        self.prior_terminal=self.registry.binding()

    def sixth(self):
        self.through_fifth()
        self.second('bad-acceptance',111,'fresh-sixth-case')
        with self.owner.assertRaisesRegex(Refusal,'pending'): self.coordinate()
        self.owner.assertEqual(self.close_handoff()['host_case'],'bad-acceptance')
        pages=self.source.pages
        def checks(path,collection=None):
            value=pages(path,collection)
            if '/check-runs' in path:
                return [v for v in value if v['head_sha']==path.split('/commits/')[1].split('/')[0]]
            return value
        self.source.pages=checks
        get=self.source.get
        def contents(path):
            if '/contents/' in path:
                import base64
                from urllib.parse import urlsplit,parse_qs,unquote
                parsed=urlsplit(path); ref=parse_qs(parsed.query)['ref'][0]
                name=unquote(parsed.path.split('/contents/')[1])
                tree=self.source.trees[self.source.commits[ref]['tree']['sha']]
                if name not in tree: raise HostRefusal(404)
                return dict(encoding='base64',content=base64.b64encode(self.source.blobs[tree[name][1]]).decode())
            return get(path)
        self.source.get=contents
        tokens=self.tokens
        def factory(token):
            scoped=tokens(token); fetch=scoped.fetch
            original_get=scoped.get
            scoped.get=lambda path:contents(path) if '/contents/' in path else original_get(path)
            def send(path,**kw):
                if path.endswith('/merge'):
                    self.owner.assertTrue(any(a['name'].startswith('trial-host-intent-') for a in self.remote.artifacts))
                    self.attempts.append((path,(),kw))
                    if getattr(self,'host_fault',None)=='unknown': raise OSError('unknown host effect')
                    category='required_review' if getattr(self,'host_fault',None)=='wrong' else 'required_check'
                    raise HostRefusal(403,category,self.p['check_name'] if category=='required_check' else None)
                return fetch(path,**kw)
            scoped.fetch=send
            return scoped
        self.tokens=factory

    def verify(self,source,d,s,job_id,guard,clock):
        if self.admission.candidate['name'] not in ('bad-acceptance','replaced-checks'):
            return super().verify(source,d,s,job_id,guard,clock)
        events=self.events
        class Disk:
            name='local-negative-fixture'
            def __init__(self,*a,**kw): pass
            def __enter__(self): events.append('negative-disk-open'); return self
            def __exit__(self,*a): events.append('negative-disk-clean')
        class Box:
            def __init__(self,candidate,*a,**kw): self.candidate=candidate
            def __enter__(self): return self
            def __exit__(self,*a): events.append('negative-box-clean')
            def run(self,argv,**kw):
                # Model only OCI command responses for these exact initial bytes.
                # The actual pinned controller still evaluates every assertion.
                if '.ai/scripts/lifecycle.py' in argv:
                    script=self.candidate/'.ai/scripts/lifecycle.py'
                    if script.exists():
                        assert script.read_bytes()==b'import sys\nsys.exit(0)\n'
                        events.append('negative-permissive-script'); return 0,''
                    events.append('negative-missing-script'); return 2,'file not found'
                return 0,''
        return service._verify_actions(source,d,s,job_id,guard,clock,disk_factory=Disk,box_factory=Box,
            image_loader=lambda *a:None)

    def rejected(self):
        self.run('verify')
        for purpose in ('admin','reader','issuer','coding','merge'): self.run('proof',purpose)
        self.run('publication-controls')
        self.run('publish')

    def artifact(self,prefix):
        import io,json,zipfile
        artifact=next(a for a in self.remote.artifacts if a['name'].startswith(prefix))
        with zipfile.ZipFile(io.BytesIO(self.remote.raw[artifact['id']])) as archive:
            member=archive.namelist()[0]; value=json.loads(archive.read(member))
        return artifact,member,value

    def host(self,change=None,selected=None,app_factory=None):
        if self.admission.candidate['name'] not in ('bad-acceptance','replaced-checks'):
            return super().host(change,selected,app_factory)
        # The existing fixture's host helper selects the key by case name.
        env=self.job('trial host denial','trial_host_denial')
        env.update(GITHUB_REPOSITORY=self.p['authority_repository'],GITHUB_TOKEN='case-actions-read',
            AGENTIC_MERGE_PRIVATE_KEY=self.api.secrets['AGENTIC_MERGE_PRIVATE_KEY'],
            **{__import__('trial_case').CaseReadStaging.NAME:self.case_token})
        if change: change(env)
        result=service._case_producer(env,self.hint,'fixture-node','host-denial',clock=lambda:self.clock[0],
            api_factory=lambda token:self.api if token=='case-actions-read' else self.origin_factory(token),
            app_factory=app_factory or self.apps,token_factory=self.tokens,uploader_factory=lambda *a:self.upload,
            host_case=selected or self.admission.candidate['name'])
        from test_authority_broker_evidence import stamp
        self.remote.jobs[-1].update(status='completed',conclusion='success',completed_at=stamp(self.clock[0]))
        return result


@unittest.skipIf(getattr(outage_fixture.NativeOutage,'__unittest_skip__',False),'optional cryptography required')
class NativeNegative(unittest.TestCase):
    fixture=outage_fixture.NativeOutage.fixture
    prepared=outage_fixture.NativeOutage.prepared
    connected=outage_fixture.NativeOutage.connected
    configured=outage_fixture.NativeOutage.configured
    exercise=outage_fixture.NativeOutage.exercise
    prepare=outage_fixture.NativeOutage.prepare

    def test_sixth_selection_reauthenticates_all_five_owned_completions(self):
        for name in ('direct-push','coding-update','missing-approval','expired-proof','authority-outage'):
            def check(*args):
                import trial_controller
                f=Negative(self,args); f.through_fifth()
                store=f.native.provision.store(f.native.provision.root/trial_controller.case_journal('trial-controller',dict(name=name)))
                saved=store.read(); value=copy.deepcopy(saved['value'])
                value['terminal']['binding']['fence']['completed'][-1]['receipt_digest']='0'*64
                store.write(saved,value)
                with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open('prompt','bad-acceptance',f.source)
                self.assertIsNone(f.native.provision.store(f.native.provision.root/'trial-controller-bad-acceptance').read())
            with self.subTest(name=name): self.exercise(continuation=check)

    def test_invalid_failed_evidence_and_missing_publication_prerequisites_do_not_count(self):
        def check(*args):
            f=Negative(self,args); f.sixth(); f.run('verify')
            for purpose in ('admin','reader','issuer','coding','merge'): f.run('proof',purpose)
            f.run('publication-controls')
            artifact,member,saved=f.artifact('evidence-')
            changes=(lambda v:v['result'].update(cleanup_complete=False),
                     lambda v:v['result']['report']['outcomes'][0].update(status='success'),
                     lambda v:v['result']['report'].update(generation=True),
                     lambda v:v['result']['report']['snapshot'].update(head='0'*40),
                     lambda v:v['result']['report']['execution'].update(run_id=109))
            for change in changes:
                value=copy.deepcopy(saved); change(value); f.remote.replace(artifact['id'],value,member)
                with self.assertRaises(Refusal): f.run('publish')
                self.assertFalse(any(a['name'].startswith('trial-publication-') for a in f.remote.artifacts))
            f.remote.replace(artifact['id'],saved,member)
            proof=next(a for a in f.remote.artifacts if a['name'].startswith('proof-reader-'))
            f.remote.artifacts.remove(proof)
            with self.assertRaises(Refusal): f.run('publish')
            f.remote.artifacts.append(proof)
            reviews=f.reviews; f.reviews=[]
            with self.assertRaises(Refusal): f.run('publish')
            f.reviews=reviews
            self.assertFalse(any(a['name'].startswith('trial-publication-') for a in f.remote.artifacts))
            with self.assertRaises(Refusal): f.host()
            self.assertEqual(len(f.attempts),3)
            self.assertIsNotNone(f.registry.binding()['fence']['pending'])
        self.exercise(continuation=check)

    def test_unknown_publication_and_host_effects_never_replay_or_close(self):
        for prefix in ('trial-publication-intent-','trial-publication-denial-','trial-host-intent-','trial-host-denial-'):
            def check(*args):
                f=Negative(self,args); f.sixth(); upload=f.upload; effects=[]
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
                    # The fixture's run helper closes jobs in finally. Recreate
                    # the still-running producer after an interrupted upload.
                    job=next(j for j in f.remote.jobs if j['name'].startswith('publish ('))
                    job.update(status='in_progress',conclusion=None,completed_at=None)
                    with self.assertRaisesRegex(Refusal,'never replay'): f.run('publish')
                else:
                    f.rejected()
                    with self.assertRaises(OSError): f.host()
                    with self.assertRaisesRegex(Refusal,'never replay'): f.host()
                with self.assertRaises(Refusal): f.run('broker')
                with self.assertRaises(Refusal): f.finalize()
                self.assertEqual(effects,[prefix+str(f.admission.request['snapshot']['pr'])+'-1'] if prefix.startswith('trial-publication-') else
                                 [prefix+f.admission.record['task_id']+'-1'])
                self.assertIsNotNone(f.registry.binding()['fence']['pending'])
            with self.subTest(prefix=prefix): self.exercise(continuation=check)

    def test_wrong_host_category_and_unknown_request_are_not_named_negatives(self):
        for fault in ('wrong','unknown'):
            def check(*args):
                f=Negative(self,args); f.sixth(); f.rejected(); f.host_fault=fault
                with self.assertRaises(OSError if fault=='unknown' else Refusal): f.host()
                with self.assertRaises(Refusal): f.run('broker')
                with self.assertRaises(Refusal): f.finalize()
                self.assertFalse(any(a['name'].startswith('trial-host-denial-') for a in f.remote.artifacts))
                self.assertIsNotNone(f.registry.binding()['fence']['pending'])
            with self.subTest(fault=fault): self.exercise(continuation=check)

    def test_retained_evidence_substitution_and_boolean_bindings_keep_the_fence(self):
        def check(*args):
            f=Negative(self,args); f.sixth(); f.rejected(); f.host(); f.run('broker')
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
        self.exercise(continuation=check)

    def test_all_prior_capabilities_and_late_ready_pending_execution_refs_block_effects(self):
        def check(*args):
            import trial_controller,trial_case,trial_launch
            from registry import Registry,trial_reference
            f=Negative(self,args); f.sixth(); f.rejected()
            for name in trial_controller.CASE_CHAIN[:5]:
                token=f.native.provision.store(f.native.provision.root/trial_controller.case_journal('trial-case-read-staging',dict(name=name))).read()['value']['credential']['token']
                self.assertIn(token,f.revoked); f.revoked.discard(token)
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
                        if path.endswith('/runs/111/artifacts') and not armed:
                            armed.append(True); f.origin.api.refs[ref]='0'*40
                        return result
                    f.api.pages=move
                    with self.assertRaises(Refusal): f.host()
                    f.api.pages=pages; f.origin.api.refs[ref]=revision
                    self.assertTrue(armed)
            self.assertEqual(len(f.attempts),3)
            self.assertFalse(any(a['name'].startswith('trial-host-intent-') for a in f.remote.artifacts))
            self.assertIsNotNone(f.registry.binding()['fence']['pending'])
        self.exercise(continuation=check)

    def test_target_movement_during_final_blocking_admission_prevents_terminal_writes(self):
        def check(*args):
            from registry import Registry
            f=Negative(self,args); f.sixth(); f.rejected(); f.host(); f.run('broker')
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
        self.exercise(continuation=check)

    def test_genuine_session_no_dispatch_receipt_cannot_close_the_named_host_case(self):
        def check(*args):
            from test_authority_broker_evidence import stamp
            f=Negative(self,args); f.sixth(); f.rejected()
            name='broker ('+str(f.admission.candidate['submitted']['pr'])+')'
            env=f.job(name,'broker')
            env.update({'AGENTIC_'+p.upper()+'_PRIVATE_KEY':f.api.secrets['AGENTIC_'+p.upper()+'_PRIVATE_KEY'] for p in ('merge','reader')})
            with self.assertRaises(Refusal):
                service._trial_producer(f.admission,env,f.admission.request,'fixture-node','broker',
                    app_factory=f.apps,token_factory=f.tokens,uploader_factory=lambda *a:f.upload,sleeper=f.sleeper)
            next(j for j in f.remote.jobs if j['name']==name).update(status='completed',conclusion='failure',completed_at=stamp(f.clock[0]))
            self.assertFalse(any(a['name'].startswith('trial-host-denial-') for a in f.remote.artifacts))
            self.assertTrue(any(a['name'].endswith('-not-submitted') for a in f.remote.artifacts))
            with self.assertRaises(Refusal): f.finalize()
            self.assertIsNotNone(f.registry.binding()['fence']['pending'])
        self.exercise(continuation=check)

    def test_sixth_closes_only_real_failed_acceptance_and_required_check_denial(self):
        def check(*args):
            import trial_launch,trial_controller
            f=Negative(self,args); f.sixth()
            with patch.object(merge_transport,'isolated',side_effect=AssertionError('negative dispatched')):
                f.rejected(); self.assertFalse(any(c['head_sha']==f.admission.request['snapshot']['merge'] for c in f.checks))
                self.assertIn('negative-missing-script',f.events)
                self.assertIn('negative-box-clean',f.events); self.assertIn('negative-disk-clean',f.events)
                f.host(); self.assertEqual(f.run('broker')['state'],'host-denied')
                terminal=f.finalize(); self.assertEqual(f.observe()['binding'],terminal)
            self.assertEqual(f.merges,[]); self.assertEqual(len(f.attempts),4)
            self.assertEqual(f.admission.record,f.original); self.assertEqual(f.origin.binding(),f.production)
            self.assertEqual(len(f.admission.value['history']),5)
            self.assertEqual(len(f.admission.value['candidates']['value']['candidates']),16)
            self.assertEqual(terminal['fence']['completed'][:-1],f.prior_terminal['fence']['completed'])
            self.assertEqual([r['kind'] for r in terminal['fence']['completed'][-6:]],['not-submitted']*6)
            self.assertIsNone(terminal['deployment']['qualification'])
            for run,raw in f.prior.items(): self.assertEqual(f.runs[run].raw,raw)
            for name in trial_controller.CASE_CHAIN[:5]:
                saved=f.native.provision.store(f.native.provision.root/trial_controller.case_journal('trial-case-read-staging',dict(name=name))).read()
                self.assertIn(saved['value']['credential']['token'],f.revoked)
            f.clock[0]+=1000
            trial_launch.revoke(f.native.provision,f.origin_factory,name='bad-acceptance')
            self.assertIn(f.case_token,f.revoked)
        self.exercise(continuation=check)
