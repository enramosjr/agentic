"""Tenth original reservation with separately closed historical preparation."""
import backend_test_support
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import merge_transport
import service
from trusted_ci_policy import Refusal, digest
import test_authority_trial_spoof_case as spoof_fixture


class NewHead(spoof_fixture.Spoof):
    TRANSITION_CASES = ('new-head',)
    def __init__(self, owner, args):
        super().__init__(owner, args)
        from test_authority_trial_transition import TransitionHost
        get, post, tokens = self.source.get, self.source.post, self.tokens
        def read(path):
            value = get(path)
            if path == '/repos/' + self.p['repository']: value['node_id'] = 'fixture-source-node'
            return value
        self.source.get = read
        self.source.post = lambda path, data: TransitionHost.post(self.source, path, data) if path == '/graphql' else post(path, data)
        def factory(token):
            scoped = tokens(token); get, post = scoped.get, scoped.post
            scoped.get = lambda path: self.source.get(path) if path == '/repos/' + self.p['repository'] else get(path)
            scoped.post = lambda path, data: self.source.post(path, data) if path == '/graphql' or path.startswith('/repos/'+self.p['repository']+'/git/') else post(path, data)
            return scoped
        self.tokens = factory
        self.preparer.token_factory = factory

    def ready(self, *args, **kwargs):
        if kwargs.get('name') == 'new-head': kwargs['phase'] = getattr(self, 'phase', None)
        return super().ready(*args, **kwargs)

    def observe(self, phase=None):
        if phase is None: return super().observe()
        import trial_controller
        from test_authority_broker_evidence import stamp
        job=next(j for j in self.remote.jobs if j['name']=='finalize')
        job.update(status='completed',conclusion='success',completed_at=stamp(self.clock[0]))
        artifact=next(a for a in self.remote.artifacts if a['name'].startswith('trial-case-terminal-'))
        location=dict(run_id=self.remote.run['id'],attempt=1,job_id=job['id'],artifact_id=artifact['id'])
        # Supply the actual local source API transport to the public owner API.
        with patch.object(self.native.provision,'api',self.source):
            return trial_controller.Native(self.preparer).observe_terminal('prompt','new-head',location,phase='prior')

    def through_ninth(self):
        self.ninth(); self.observed(); self.host(); self.run('broker'); self.finalize(); self.observe()
        import trial_controller
        self.prior = {run:copy.deepcopy(remote.raw) for run,remote in self.runs.items()}
        self.prior_refs = copy.deepcopy(self.origin.api.refs)
        self.prior_terminal = self.registry.binding()
        self.prior_journals = {trial_controller.case_journal(base,dict(name=name)):
            self.native.provision.store(self.native.provision.root/trial_controller.case_journal(base,dict(name=name))).read()
            for name in trial_controller.CASE_CHAIN[:9] for base in ('trial-controller','trial-case-publication')}

    def historical(self, complete=True):
        self.through_ninth()
        self.original = copy.deepcopy(self.admission.record)
        self.production = self.origin.binding()
        self.phase = 'prior'
        self.second('new-head', 119, 'fresh-tenth-prior')
        with self.owner.assertRaisesRegex(Refusal, 'pending'): self.coordinate()
        self.owner.assertEqual(self.close_handoff()['host_case'], 'none')
        if not complete: return
        self.run('verify')
        for purpose in ('admin','reader','issuer','coding','merge'): self.run('proof', purpose)
        self.run('publication-controls'); self.run('publish')

    def current(self, observed=True):
        self.historical()
        self.old_candidate = copy.deepcopy(self.admission.candidate)
        self.old_snapshot = copy.deepcopy(self.admission.request['snapshot'])
        with self.owner.assertRaisesRegex(Refusal, 'historical preparation never authorizes dispatch'):
            self.run('broker')
        next(j for j in self.remote.jobs if j['name'].startswith('broker ('))['conclusion'] = 'failure'
        self.finalize(); self.observe(phase='prior')
        self.phase = None
        self.second('new-head', 121, 'fresh-tenth-current')
        with self.owner.assertRaisesRegex(Refusal, 'pending'): self.coordinate()
        self.owner.assertEqual(self.close_handoff()['host_case'], 'new-head')
        if observed: self.observed()

    def run(self, role, purpose=None, change=None):
        if self.admission.candidate['name'] in self.TRANSITION_CASES:
            name=('publication controls' if role=='publication-controls' else role)+' ('+(purpose or str(self.admission.candidate['submitted']['pr']))+')'
            for job in self.remote.jobs:
                if job['name']==name: job.update(status='in_progress',conclusion=None,completed_at=None)
        return super().run(role,purpose,change)

    def host(self, change=None, selected=None, app_factory=None):
        if self.admission.candidate['name'] not in self.TRANSITION_CASES:
            return super().host(change, selected, app_factory)
        import trial_case
        from test_authority_broker_evidence import stamp
        env = self.job('trial host denial', 'trial_host_denial')
        env.update(GITHUB_REPOSITORY=self.p['authority_repository'], GITHUB_TOKEN='case-actions-read',
            AGENTIC_MERGE_PRIVATE_KEY=self.api.secrets['AGENTIC_MERGE_PRIVATE_KEY'],
            **{trial_case.CaseReadStaging.NAME:self.case_token})
        if change: change(env)
        value = service._case_producer(env, self.hint, 'fixture-node', 'host-denial', clock=lambda:self.clock[0],
            api_factory=lambda token:self.api if token=='case-actions-read' else self.origin_factory(token),
            app_factory=app_factory or self.apps, token_factory=self.tokens, uploader_factory=lambda *a:self.upload,
            host_case=selected or self.admission.candidate['name'])
        self.remote.jobs[-1].update(status='completed',conclusion='success',completed_at=stamp(self.clock[0]))
        return value

    def verify(self, source, d, s, job_id, guard, clock):
        if self.admission.candidate['name'] not in self.TRANSITION_CASES:
            return super().verify(source, d, s, job_id, guard, clock)
        events = self.events
        expected = (Path(__file__).resolve().parents[3]/'.ai/scripts/lifecycle.py').read_bytes()
        class Disk:
            name = 'local-historical-verifier'
            def __init__(self, *a, **kw): pass
            def __enter__(self): events.append('historical-disk-open'); return self
            def __exit__(self, *a): events.append('historical-disk-clean')
        class Box:
            def __init__(self, candidate, *a, **kw):
                self.script = (candidate/'.ai/scripts/lifecycle.py').read_bytes()
                self.prepared = False; self.state = None; self.assurance = 'VERIFIED'
            def __enter__(self): return self
            def __exit__(self, *a): events.append('historical-box-clean')
            def run(self, argv, **kw):
                # Model only OCI command responses. The pinned controller runs
                # every obligation and derives the report from these responses.
                if argv[0] == 'git': return 0, ''
                if argv[:2] == ['touch', '/source/forged-result']: return 1, 'read-only source'
                if '.ai/scripts/lifecycle.py' in argv:
                    if self.script != expected: return 0, ''  # Hostile bytes cannot deny.
                    args = argv[2:]
                    if args[:2] == ['tier', 'L2']: self.prepared = False; return 0, ''
                    if args[:2] == ['tier', 'L1']: self.prepared = False; return 0, ''
                    if args[:2] == ['stage', 'plan']: self.prepared = True; return 0, ''
                    if args[:1] == ['stage']: return 0, ''
                    if args[:1] == ['gate']: return (0, 'OK') if self.prepared else (1, 'intent missing')
                    if args[:1] == ['assure']:
                        if '--run' in args:
                            if self.state == 'bad': self.assurance = 'FAILED'; return 1, ''
                            self.assurance = 'VERIFIED'; return 0, ''
                        state = 'INVALID' if self.state == 'invalid' else 'STALE' if self.state == 'bad' and self.assurance != 'FAILED' else self.assurance
                        return (0 if state == 'VERIFIED' else 1), json.dumps(dict(requirements=[dict(id='TRUST-R1',status=state)]))
                    raise AssertionError(argv)
                if '.ai/scripts/okf.py' in argv or '.ai/scripts/install.py' in argv: return 0, ''
                if argv[:3] == ['python3', '-I', '-c']:
                    script = argv[3]
                    if 'json.loads(sys.argv[1])' in script:
                        files = json.loads(argv[4])
                        if 'input.txt' in files: self.state = files['input.txt']
                        if 'knowledge/capabilities/trust.md' in files and '``' in files['knowledge/capabilities/trust.md']: self.state = 'invalid'
                        return 0, ''
                    if 'print("preserved")' in script: return 0, 'preserved'
                    if any(marker in script for marker in ('shutil.copytree', '/work/adopter', 'os.getuid()')): return 0, ''
                raise AssertionError(('unmodeled OCI request', argv))
        return service._verify_actions(source, d, s, job_id, guard, clock,
            disk_factory=Disk, box_factory=Box, image_loader=lambda *a: None)


@unittest.skipIf(getattr(spoof_fixture.NativeSpoof, '__unittest_skip__', False), 'optional cryptography required')
class NativeNewHead(unittest.TestCase):
    prepared = spoof_fixture.NativeSpoof.prepared
    connected = spoof_fixture.NativeSpoof.connected
    configured = spoof_fixture.NativeSpoof.configured
    exercise = spoof_fixture.NativeSpoof.exercise
    prepare = spoof_fixture.NativeSpoof.prepare

    def fixture(self):
        import test_authority_trial_setup as setup_fixture
        original = setup_fixture.TrialProvisionContracts.fixture
        def seed(helper):
            result = original(helper)
            root = Path(__file__).resolve().parents[3]
            # Seed the approved source before provisioning/freezing the ORIGINAL
            # trial. Later transitions read only this immutable source tree.
            result[0].fixture_files.update({'.ai/scripts/'+p.name: p.read_bytes()
                for p in (root/'.ai/scripts').glob('*.py')})
            return result
        with patch.object(setup_fixture.TrialProvisionContracts, 'fixture', seed):
            return spoof_fixture.NativeSpoof.fixture(self)

    def test_tenth_uses_genuine_same_pr_prior_acceptance(self):
        def check(*args):
            import trial_controller
            f = NewHead(self, args)
            with patch.object(merge_transport, 'isolated', side_effect=AssertionError('transition dispatched')):
                f.current(); f.host()
                self.assertEqual(f.run('broker')['state'], 'host-denied')
                terminal = f.finalize(); self.assertEqual(f.observe()['binding'], terminal)
                self.assertEqual(f.admission.record, f.original)
                self.assertEqual(f.origin.binding(), f.production)
                self.assertEqual(f.admission.request['snapshot']['pr'], f.old_snapshot['pr'])
                self.assertNotEqual(f.admission.request['snapshot']['head'], f.old_snapshot['head'])
                self.assertNotEqual(f.admission.request['snapshot']['merge'], f.old_snapshot['merge'])
                self.assertEqual(len(f.admission.value['history']), 9)
                self.assertEqual(len(f.admission.value['candidates']['value']['candidates']), 16)
                self.assertIsNone(terminal['deployment']['qualification'])
                self.assertEqual(f.merges, [])
                for run, raw in f.prior.items(): self.assertEqual(f.runs[run].raw, raw)
                for ref, revision in f.prior_refs.items(): self.assertEqual(f.origin.api.refs[ref], revision)
                for name, saved in f.prior_journals.items(): self.assertEqual(f.native.provision.store(f.native.provision.root/name).read(),saved)
                self.assertEqual(terminal['fence']['completed'][:-2],f.prior_terminal['fence']['completed'])
                for name in trial_controller.CASE_CHAIN[:9]:
                    token=f.native.provision.store(f.native.provision.root/trial_controller.case_journal('trial-case-read-staging',dict(name=name))).read()['value']['credential']['token']
                    self.assertIn(token,f.revoked)
                self.assertIn('fresh-tenth-prior',f.revoked)
                f.clock[0]+=1000
                import trial_launch
                trial_launch.revoke(f.native.provision,f.origin_factory,name='new-head',phase='prior')
                trial_launch.revoke(f.native.provision,f.origin_factory,name='new-head')
                self.assertIn(f.case_token,f.revoked)
        self.exercise(continuation=check, export_files=spoof_fixture.forged_fixture.EXPORT)

    def test_all_nine_owned_completions_are_required_before_historical_preparation(self):
        import trial_controller
        for name in trial_controller.CASE_CHAIN[:9]:
            def check(*args):
                f=NewHead(self,args); f.through_ninth()
                store=f.native.provision.store(f.native.provision.root/trial_controller.case_journal('trial-controller',dict(name=name)))
                saved=store.read(); value=copy.deepcopy(saved['value'])
                value['terminal']['binding']['fence']['completed'][-1]['receipt_digest']='0'*64
                store.write(saved,value)
                writes=copy.deepcopy(f.source.writes)
                with self.assertRaisesRegex(Refusal,'owned.*(completion|terminal)|first native completion'):
                    trial_controller.Native(f.preparer)._open_prior('prompt',f.source)
                self.assertEqual(f.source.writes,writes)
                self.assertIsNone(f.native.provision.store(f.native.provision.root/'trial-transition-new-head-prior').read())
            with self.subTest(name=name): self.exercise(continuation=check,export_files=spoof_fixture.forged_fixture.EXPORT)

    def test_actual_controller_rejects_hostile_bytes_before_old_acceptance(self):
        def check(*args):
            f=NewHead(self,args); f.historical(complete=False)
            f.tar=f.archive(f.admission.candidate['transition']['intent']['reservation']['submitted'])
            with self.assertRaisesRegex(Refusal,'critical acceptance failed'): f.run('verify')
            self.assertFalse(any(a['name'].startswith('evidence-') for a in f.remote.artifacts))
            self.assertFalse(any(c['head_sha']==f.admission.request['snapshot']['merge'] for c in f.checks))
            self.assertIn('historical-box-clean',f.events); self.assertIn('historical-disk-clean',f.events)
        self.exercise(continuation=check,export_files=spoof_fixture.forged_fixture.EXPORT)

    def test_no_acceptance_historical_closure_cannot_advance_current_source(self):
        def check(*args):
            import trial_controller
            f=NewHead(self,args); f.historical(complete=False)
            with self.assertRaisesRegex(Refusal,'historical preparation never authorizes dispatch'): f.run('broker')
            f.finalize(); f.observe(phase='prior')
            writes=copy.deepcopy(f.source.writes)
            with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open('prompt','new-head',f.source)
            self.assertEqual(f.source.writes,writes)
            self.assertIsNone(f.native.provision.store(f.native.provision.root/'trial-transition-new-head-current').read())
        self.exercise(continuation=check,export_files=spoof_fixture.forged_fixture.EXPORT)

    def test_owned_transition_journals_are_not_adopted_after_tampering(self):
        for phase,target in (('prior','trial-transition-new-head-prior'),('current','trial-transition-new-head-prior'),
                             ('current','trial-transition-new-head-current')):
            def check(*args):
                import trial_controller
                f=NewHead(self,args)
                if phase=='prior': f.historical(complete=False)
                else: f.current()
                store=f.native.provision.store(f.native.provision.root/target)
                saved=store.read(); value=copy.deepcopy(saved['value']); value['result']['head']='0'*40
                store.write(saved,value)
                writes=copy.deepcopy(f.source.writes)
                with self.assertRaisesRegex(Refusal,'owned.*(transition|mutation)'): f.admission.guard()
                with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open('prompt','new-head',f.source,phase='prior' if phase=='prior' else None)
                self.assertEqual(f.source.writes,writes)
            with self.subTest(phase=phase,target=target): self.exercise(continuation=check,export_files=spoof_fixture.forged_fixture.EXPORT)

    def test_native_unknown_source_effects_recover_only_exact_acknowledged_ref(self):
        for boundary in ('commit','ref','budget'):
            def check(*args):
                import trial_controller
                f=NewHead(self,args); f.through_ninth(); post=f.source.post
                def send(path,body):
                    value=post(path,body)
                    if boundary=='commit' and path.endswith('/git/commits'): raise OSError('unknown commit')
                    if boundary=='ref' and path=='/graphql': raise OSError('unknown ref')
                    if boundary=='budget' and path.endswith('/git/commits'): f.clock[0]+=31
                    return value
                f.source.post=send
                with self.assertRaises(Refusal if boundary=='budget' else OSError): trial_controller.Native(f.preparer)._open_prior('prompt',f.source)
                writes=copy.deepcopy(f.source.writes)
                f.source.post=post
                if boundary=='ref':
                    recovered=trial_controller.Native(f.preparer)._open_prior('prompt',f.source)
                    self.assertNotEqual(recovered.candidate['submitted']['head'],recovered.candidate['transition']['intent']['reservation']['submitted']['head'])
                else:
                    with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open_prior('prompt',f.source)
                self.assertEqual(f.source.writes,writes)
            with self.subTest(boundary=boundary): self.exercise(continuation=check,export_files=spoof_fixture.forged_fixture.EXPORT)

    def test_source_privacy_and_owner_are_checked_before_transition_effects(self):
        for defect in ('private','owner'):
            def check(*args):
                import trial_controller
                f=NewHead(self,args); f.through_ninth(); get=f.source.get
                def read(path):
                    value=get(path)
                    if path=='/repos/'+f.p['repository']:
                        value=copy.deepcopy(value)
                        if defect=='private': value['private']=False
                        else: value['owner']['id']=999
                    return value
                f.source.get=read; writes=copy.deepcopy(f.source.writes)
                with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open_prior('prompt',f.source)
                self.assertEqual(f.source.writes,writes)
                self.assertIsNone(f.native.provision.store(f.native.provision.root/'trial-controller-new-head-prior').read())
            with self.subTest(defect=defect): self.exercise(continuation=check,export_files=spoof_fixture.forged_fixture.EXPORT)

    def test_changed_owned_historical_terminal_is_not_adopted_by_current_preparation(self):
        def check(*args):
            import trial_controller
            f=NewHead(self,args); f.historical()
            with self.assertRaisesRegex(Refusal,'historical preparation never authorizes dispatch'): f.run('broker')
            f.finalize(); f.observe(phase='prior')
            store=f.native.provision.store(f.native.provision.root/'trial-controller-new-head-prior')
            saved=store.read(); value=copy.deepcopy(saved['value']); value['terminal']['document']['completed']+=1
            store.write(saved,value); writes=copy.deepcopy(f.source.writes)
            with self.assertRaisesRegex(Refusal,'owned historical terminal differs'): trial_controller.Native(f.preparer)._open('prompt','new-head',f.source)
            self.assertEqual(f.source.writes,writes)
            self.assertIsNone(f.native.provision.store(f.native.provision.root/'trial-transition-new-head-current').read())
        self.exercise(continuation=check,export_files=spoof_fixture.forged_fixture.EXPORT)

    def test_same_pr_prior_source_and_closed_evidence_are_required(self):
        def check(*args):
            import qualification_cases,trial_host_case
            from test_authority_broker_evidence import stamp
            f=NewHead(self,args); f.current()
            case=trial_host_case._case(f.admission,f.api)
            probe=qualification_cases.HostCases(f.registry,f.source,f.api,f.admission.record['pair']['identities'],None,None,None,lambda:f.clock[0])
            probe.binding,probe.d=f.admission.binding,f.d
            mutations=(lambda v:v['prior']['snapshot'].update(pr=1),
                lambda v:v['prior']['snapshot'].update(head=v['snapshot']['head']),
                lambda v:v['prior']['snapshot'].update(base='0'*40),
                lambda v:v['prior']['deployment']['policy'].update(epoch='foreign'),
                lambda v:v['prior']['coordinates'].update(task_digest='0'*64),
                lambda v:v['prior']['coordinates'].update(evidence_digest='0'*64),
                lambda v:v['prior']['coordinates'].update(issuer_installation_id=True),
                lambda v:v['prior'].update(registry_revision='0'*40))
            from trusted_ci_github import HostRefusal
            get=f.api.get; missing=[]
            def read(path):
                if path==f.registry.root+'/git/commits/'+'0'*40:
                    missing.append(path); raise HostRefusal(404)
                return get(path)
            with patch.object(f.api,'get',read):
                for mutate in mutations:
                    bad=copy.deepcopy(case); mutate(bad)
                    with self.assertRaises(Refusal): probe._prerequisites(bad)
            self.assertEqual(len(missing),1)
            old_check=next(c for c in f.checks if c['head_sha']==f.old_snapshot['merge'] and c['app']['id']==f.p['app_id'])
            old_check['app']['id']=999
            with self.assertRaises(Refusal): f.host()
            old_check['app']['id']=f.p['app_id']
            commit=f.source.commits[f.old_snapshot['merge']]; parents=commit['parents']; commit['parents']=list(reversed(parents))
            with self.assertRaisesRegex(Refusal,'actual parents'): f.host()
            commit['parents']=parents
            remote=f.runs[119]; job=next(j for j in remote.jobs if j['name'].startswith('verify ('))
            job.update(status='in_progress',conclusion=None,completed_at=None)
            with self.assertRaises(Refusal): f.host()
            job.update(status='completed',conclusion='success',completed_at=stamp(f.clock[0]))
            reviews=f.reviews
            for wrong in ([],[dict(reviews[0],state='DISMISSED')],[dict(reviews[0],commit_id=f.old_snapshot['head'])]):
                f.reviews=wrong
                with self.assertRaises(Refusal): f.host()
            f.reviews=reviews
            pages=f.source.pages; tokens=f.tokens
            def obligations(path,collection=None):
                value=pages(path,collection)
                if '/rules/branches/' in path:
                    value=copy.deepcopy(value)
                    next(r for r in value if r['type']=='required_status_checks')['parameters']['required_status_checks'].append(dict(context='another',integration_id=888))
                return value
            def with_rules(token):
                scoped=tokens(token); original=scoped.pages
                scoped.pages=lambda path,collection=None:obligations(path,collection) if '/rules/branches/' in path else original(path,collection)
                return scoped
            f.source.pages=obligations; f.tokens=with_rules
            with self.assertRaisesRegex(Refusal,'another host obligation'): f.host()
            f.source.pages=pages; f.tokens=tokens
            f.checks.append(dict(old_check,head_sha=f.admission.request['snapshot']['merge']))
            with self.assertRaisesRegex(Refusal,'already has authoritative success'): f.host()
            self.assertFalse(any(a['name'].startswith('trial-host-intent-') for a in f.remote.artifacts))
        self.exercise(continuation=check,export_files=spoof_fixture.forged_fixture.EXPORT)

    def test_prior_success_and_current_review_are_reread_after_host_intent(self):
        for fault in ('old-check','current-review','current-success'):
            def check(*args):
                f=NewHead(self,args); f.current(); upload=f.upload
                def withdraw(name,raw):
                    value=upload(name,raw)
                    if name.startswith('trial-host-intent-'):
                        if fault=='old-check': f.checks[:]=[c for c in f.checks if c['head_sha']!=f.old_snapshot['merge']]
                        elif fault=='current-review': f.reviews=[]
                        else: f.checks.append(dict(id=9999,name=f.p['check_name'],app=dict(id=f.p['app_id']),head_sha=f.admission.request['snapshot']['merge'],status='completed',conclusion='success'))
                    return value
                f.upload=withdraw
                with self.assertRaises(Refusal): f.host()
                with self.assertRaises(Refusal): f.host()
                self.assertEqual(len(f.attempts),7)
                self.assertFalse(any(a['name'].startswith('trial-host-denial-') for a in f.remote.artifacts))
            with self.subTest(fault=fault): self.exercise(continuation=check,export_files=spoof_fixture.forged_fixture.EXPORT)

    def test_new_head_old_capabilities_and_all_twenty_seven_late_history_refs_block_effects(self):
        def check(*args):
            import trial_controller,trial_case,trial_launch
            from registry import Registry,trial_reference
            f=NewHead(self,args); f.current()
            old=[f.api.secrets['AGENTIC_TRIAL_ORIGIN_TOKEN']]
            for name in trial_controller.CASE_CHAIN[:9]:
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
                        if path.endswith('/runs/121/artifacts') and not armed:
                            armed.append(True); f.origin.api.refs[ref]='0'*40
                        return result
                    f.api.pages=move
                    with self.assertRaises(Refusal): f.host()
                    f.api.pages=pages; f.origin.api.refs[ref]=revision
                    self.assertTrue(armed); checked.append(ref)
            self.assertEqual(len(set(checked)),27)
            self.assertEqual(len(f.attempts),7)
            self.assertFalse(any(a['name'].startswith('trial-host-intent-') for a in f.remote.artifacts))
        self.exercise(continuation=check,export_files=spoof_fixture.forged_fixture.EXPORT)

    def test_new_head_unknown_publication_and_host_uploads_never_replay(self):
        for prefix in ('trial-publication-intent-','trial-publication-observation-','trial-host-intent-','trial-host-denial-'):
            def check(*args):
                f=NewHead(self,args); f.current(observed=False); upload=f.upload; effects=[]
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
            with self.subTest(prefix=prefix): self.exercise(continuation=check,export_files=spoof_fixture.forged_fixture.EXPORT)

    def test_new_head_wrong_denial_and_unknown_host_request_do_not_count(self):
        for fault in ('wrong','unknown','obligation','status'):
            def check(*args):
                from trusted_ci_github import HostRefusal
                f=NewHead(self,args); f.current(); f.host_fault=fault
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
            with self.subTest(fault=fault): self.exercise(continuation=check,export_files=spoof_fixture.forged_fixture.EXPORT)

    def test_new_head_retained_substitutions_cannot_clear_named_fence(self):
        def check(*args):
            f=NewHead(self,args); f.current(); f.host(); f.run('broker')
            for prefix,changes in (
                ('trial-publication-observation-',(lambda v:v.update(observed=float(v['observed'])),
                    lambda v:v['snapshot'].update(run_attempt=True),lambda v:v['intent']['inputs'].update(task_digest='0'*64),
                    lambda v:v['observation']['prior']['coordinates'].update(task_digest='0'*64))),
                ('trial-host-denial-',(lambda v:v['observation'].update(http_status=True),
                    lambda v:v['observation'].update(denied_obligation='other'),lambda v:v['snapshot'].update(run_attempt=True),
                    lambda v:v['observation']['publication'].update(digest='0'*64),
                    lambda v:v['observation']['prior']['coordinates'].update(task_digest='0'*64)))):
                artifact,member,saved=f.artifact(prefix)
                for index,change in enumerate(changes):
                    value=copy.deepcopy(saved); change(value); f.remote.replace(artifact['id'],value,member)
                    self.assertNotEqual(digest(value),digest(saved))
                    with self.subTest(prefix=prefix,index=index),self.assertRaises(Refusal): f.finalize()
                    self.assertIsNotNone(f.registry.binding()['fence']['pending'])
                f.remote.replace(artifact['id'],saved,member)
            job=next(j for j in f.remote.jobs if j['name'].startswith('publish ('))
            job.update(status='in_progress',conclusion=None,completed_at=None)
            with self.assertRaises(Refusal): f.finalize()
            job.update(status='completed',conclusion='success',completed_at=__import__('test_authority_broker_evidence').stamp(f.clock[0]))
            artifact,_,_=f.artifact('trial-publication-observation-'); f.remote.artifacts.remove(artifact)
            with self.assertRaises(Refusal): f.finalize()
            self.assertFalse(any(a['name'].startswith('trial-case-terminal-') for a in f.remote.artifacts))
        self.exercise(continuation=check,export_files=spoof_fixture.forged_fixture.EXPORT)

    def test_new_head_generic_session_receipt_cannot_close_tenth(self):
        def check(*args):
            f=NewHead(self,args); f.current()
            name='broker ('+str(f.admission.candidate['submitted']['pr'])+')'
            env=f.job(name,'broker')
            env.update({'AGENTIC_'+p.upper()+'_PRIVATE_KEY':f.api.secrets['AGENTIC_'+p.upper()+'_PRIVATE_KEY'] for p in ('merge','reader')})
            with self.assertRaises(Refusal): service._trial_producer(f.admission,env,f.admission.request,'fixture-node','broker',
                app_factory=f.apps,token_factory=f.tokens,uploader_factory=lambda *a:f.upload,sleeper=f.sleeper)
            next(j for j in f.remote.jobs if j['name']==name).update(status='completed',conclusion='failure',completed_at=__import__('test_authority_broker_evidence').stamp(f.clock[0]))
            self.assertTrue(any(a['name'].endswith('-not-submitted') for a in f.remote.artifacts))
            with self.assertRaises(Refusal): f.finalize()
            self.assertIsNotNone(f.registry.binding()['fence']['pending'])
        self.exercise(continuation=check,export_files=spoof_fixture.forged_fixture.EXPORT)

    def test_new_head_late_target_after_blocking_terminal_admission_blocks_writes(self):
        def check(*args):
            from registry import Registry
            f=NewHead(self,args); f.current(); f.host(); f.run('broker')
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
        self.exercise(continuation=check,export_files=spoof_fixture.forged_fixture.EXPORT)

    def test_new_head_history_move_in_actual_session_exception_and_receipt_inventory_blocks_upload(self):
        for boundary in ('exception','receipt'):
            def check(*args):
                import broker_session,trial_case
                from merge_receipts import ActionsReceipts
                from registry import trial_reference
                f=NewHead(self,args); f.current()
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
                self.assertEqual(len(moved),27)
                self.assertFalse(any(a['name'].endswith('-not-submitted') for a in f.remote.artifacts))
                self.assertIsNotNone(f.registry.binding()['fence']['pending'])
            with self.subTest(boundary=boundary): self.exercise(continuation=check,export_files=spoof_fixture.forged_fixture.EXPORT)
