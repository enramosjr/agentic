"""Strict positive prerequisites; hostile exports never become positive fixtures."""
import backend_test_support
import copy
import unittest

from trusted_ci_policy import Refusal


class SpecimenContracts(unittest.TestCase):
    def test_mutations_are_exact_and_do_not_change_the_original_export(self):
        from trial_specimen import mutate, RECIPES
        original = {'result.bin': dict(content=b'original\n', executable=True),
                    '.ai/scripts/lifecycle.py': dict(content=b'real lifecycle\n', executable=False)}
        saved = copy.deepcopy(original)
        for name, recipe in RECIPES.items():
            result = mutate(original, name)
            self.assertEqual(original, saved)
            self.assertEqual(result['result.bin'], original['result.bin'])
            self.assertEqual(result['.ai/scripts/lifecycle.py'],
                             dict(content=b'import sys\nsys.exit(0)\n', executable=False))
            self.assertEqual(set(result), set(original) | set(recipe))
            for path, item in recipe.items(): self.assertEqual(result[path], item)
        with self.assertRaises(Refusal): mutate(original, 'positive')

    def test_mutation_authentication_rejects_extra_bytes_modes_or_wrong_case(self):
        from trial_specimen import mutate, validate_mutation
        original = {'result.bin': dict(content=b'original\n', executable=False)}
        value = mutate(original, 'forged-records')
        validate_mutation(original, value, 'forged-records')
        for fault in ('content', 'mode', 'extra', 'case'):
            changed = copy.deepcopy(value)
            if fault == 'content': changed['result.bin']['content'] = b'other'
            if fault == 'mode': changed['result.bin']['executable'] = True
            if fault == 'extra': changed['unexpected'] = dict(content=b'x', executable=False)
            with self.subTest(fault=fault), self.assertRaises(Refusal):
                validate_mutation(original, changed, 'replaced-checks' if fault == 'case' else 'forged-records')

    def test_specimen_identity_and_delta_are_explicit(self):
        from trial_specimen import compose, SPECIMEN, manifest
        kit = {'.ai/scripts/lifecycle.py': dict(content=b'real\n', executable=True)}
        baseline, worker = compose(kit)
        self.assertEqual(baseline['.agentic.json']['content'], b'{"repository_kind":"adopter"}\n')
        self.assertNotIn('result.bin', baseline)
        self.assertEqual(worker['result.bin'], dict(content=SPECIMEN, executable=False))
        self.assertEqual(worker['.ai/scripts/lifecycle.py'], kit['.ai/scripts/lifecycle.py'])
        self.assertNotEqual(manifest(baseline), manifest(worker))
        with self.assertRaises(Refusal): compose(dict(kit, **{'.agentic.json':dict(content=b'framework', executable=False)}))


class RuntimeContracts(unittest.TestCase):
    def test_positive_ready_schedules_real_producer_roles_after_retention_only(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from positive_fixture import Strict,context_fixture
        f=Strict.__new__(Strict)
        events=[]
        f.run=lambda role,purpose=None:events.append((role,purpose))
        def retain(*args):
            events.append('retained')
            return 71
        for case,name,scheduled in (
            ('positive','receipt-control-ready',True),
            ('positive','receipt-outcome',False),
            ('direct-push','receipt-control-ready',False)):
            f.admission=SimpleNamespace(candidate=dict(name=case))
            events.clear()
            with patch.object(context_fixture.Context,'upload',retain):
                self.assertEqual(f.upload(name,b'{}'),71)
            expected=['retained']
            if scheduled:
                expected += [('controls',None),*[( 'final-proof',p) for p in ('admin','reader','issuer','coding','merge')]]
            self.assertEqual(events,expected)
        f.admission=SimpleNamespace(candidate=dict(name='positive'))
        events.clear()
        with patch.object(context_fixture.Context,'upload',side_effect=OSError('lost READY retention')):
            with self.assertRaisesRegex(OSError,'lost READY retention'): f.upload('receipt-control-ready',b'{}')
        self.assertEqual(events,[])

    def test_context_wait_callback_is_scoped_even_when_broker_refuses(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from positive_fixture import Strict
        for existing,success in ((False,False),(True,False),(False,True),(True,True)):
            f=Strict.__new__(Strict)
            f.origin=SimpleNamespace(binding=lambda:{})
            f.registry=SimpleNamespace(read=lambda:dict(expires=4600))
            f.native=SimpleNamespace(provision=SimpleNamespace(preview={}))
            f.eligibility=Mock(); f.transition=Mock(); f.finalize=Mock(); f.observe=Mock()
            historical=Mock(side_effect=AssertionError('historical callback reached'))
            f.fifteenth=lambda:setattr(f,'sleeper',historical)
            prior=Mock(side_effect=AssertionError('prior callback reached'))
            if existing: f.sleeper=prior
            def broker(role):
                self.assertEqual(role,'broker')
                f.sleeper(2)
                if success: return dict(refusal='configuration_changed')
                raise Refusal('scoped broker refusal')
            f.run=broker
            def second(*args):
                self.assertEqual(hasattr(f,'sleeper'),existing)
                if existing: self.assertIs(f.sleeper,prior)
                raise Refusal('scoped broker refusal')
            f.second=second
            with self.subTest(existing=existing,success=success),self.assertRaisesRegex(Refusal,'scoped broker refusal'):
                f.complete()
            f.transition.assert_called_once_with()
            prior.assert_not_called()
            historical.assert_not_called()
            self.assertEqual(hasattr(f,'sleeper'),existing)
            if existing: self.assertIs(f.sleeper,prior)

    def test_strict_source_owner_resolution_uses_the_provider_human_directory(self):
        from unittest.mock import patch
        from urllib.parse import quote
        from positive_fixture import Harness,Strict
        from authority_github import Readers
        from controls import observe
        owner=Harness()
        owner.image='docker.io/library/python@sha256:'+'a'*64
        owner.runtime='podman'
        self.addCleanup(owner.doCleanups)
        def check(*args):
            f=Strict(owner,args)
            readers=Readers(f.source,f.api,f.d)
            writes=copy.deepcopy(f.source.writes); binding=f.registry.binding()
            observe(readers,f.d)
            human=f.api.get('/users/maintainer')
            bot=f.source.get('/users/'+quote(f.d['resources']['coding_slug']+'[bot]',safe=''))
            self.assertEqual(f.source.get('/users/maintainer'),human)
            self.assertNotEqual(human['id'],bot['id'])
            get=f.api.get
            for identity in (bot['id'],999999,None):
                def changed(path):
                    return dict(human,id=identity) if path=='/users/maintainer' else get(path)
                with self.subTest(identity=identity),patch.object(f.api,'get',changed),\
                     self.assertRaisesRegex(Refusal,'unapproved code owner'):
                    observe(readers,f.d)
            root='/repos/'+f.p['repository']; pages=f.api.pages
            with patch.object(f.api,'get',lambda path:dict(enabled=True) if path==root+'/actions/permissions' else get(path)),\
                 self.assertRaisesRegex(Refusal,'target Actions'):
                observe(readers,f.d)
            for suffix,value,diagnostic in (
                ('/collaborators?affiliation=all',[],'independent human actors unavailable'),
                ('/hooks',[dict(active=True)],'target webhook automation')):
                def changed_pages(path,collection=None):
                    return value if path==root+suffix else pages(path,collection)
                with self.subTest(surface=suffix),patch.object(f.api,'pages',changed_pages),\
                     self.assertRaisesRegex(Refusal,diagnostic):
                    observe(readers,f.d)
            f.context_transport()
            observe(readers,f.d)
            self.assertEqual(f.source.writes,writes)
            self.assertEqual(f.registry.binding(),binding)
            self.assertEqual(f.merges,[])
            self.assertIsNone(f.native.provision.store(f.native.provision.root/'trial-positive-approval').read())
        owner.exercise(continuation=check)

    def test_strict_fixture_refuses_a_modeled_positive_store_before_provisioning(self):
        from unittest.mock import patch
        from positive_fixture import Harness
        import test_authority_trial_setup as setup_fixture
        import trial_broker_positive
        with patch.object(trial_broker_positive,'Store',object()),\
             patch.object(setup_fixture.TrialProvisionContracts,'fixture') as provision,\
             self.assertRaisesRegex(Refusal,'actual protected positive-role Store'):
            Harness().fixture()
        provision.assert_not_called()

    def test_fresh_cli_import_keeps_positive_store_real_under_native_fixture(self):
        from pathlib import Path
        import subprocess
        import sys
        script="""
import sys
sys.path.insert(0,'deploy/authority/tests')
from positive_fixture import Harness
from test_authority_private_setup import PrivateSetupContracts
from pathlib import Path
owner=Harness()
owner.image='docker.io/library/python@sha256:'+'a'*64
try:
    owner.fixture()
    import trial_broker_positive as positive
    assert isinstance(positive.Store,type) and positive.Store.__module__=='authority_private', 'positive role captured modeled Store'
    with PrivateSetupContracts().temporary() as parent:
        root=Path(parent)/'actual-positive-role'
        first=positive.Store(root).write(None,{'scope':'synthetic-positive-role'})
        assert positive.Store(root).read()==first, 'fresh real Store did not reconstruct retained disk state'
        assert (root/'model-setup.json').is_file(), 'positive role used modeled memory storage'
finally:
    owner.doCleanups()
"""
        result=subprocess.run([sys.executable,'-c',script],cwd=Path(__file__).resolve().parents[3],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout)

    def test_strict_native_journal_factory_survives_return_from_fixture_setup(self):
        import authority_private
        import private_setup
        import trial_broker_positive
        from positive_fixture import Harness,NativeJournal
        import test_authority_trial_setup as setup_fixture
        original=setup_fixture.Journal
        protected=authority_private.Store
        owner=Harness()
        self.addCleanup(owner.doCleanups)
        owner.image='docker.io/library/python@sha256:'+'a'*64
        result=owner.fixture(); controller=result[0]
        self.assertIs(setup_fixture.Journal,NativeJournal)
        self.assertIsInstance(controller.store(controller.root/'trial-operator'/'registration'),NativeJournal)
        delayed=controller.store(controller.root/'created-after-fixture-return')
        self.assertIsInstance(delayed,NativeJournal)
        self.assertEqual(delayed.root,controller.root/'created-after-fixture-return')
        self.assertIs(controller.store(controller.root/'created-after-fixture-return'),delayed)
        first=delayed.write(None,dict(actual=True))
        self.assertEqual(delayed.read(),first)
        with self.assertRaisesRegex(Refusal,'CAS changed'): delayed.write(None,{})
        self.assertIsNot(private_setup.Store,protected)
        self.assertIs(private_setup.Store(controller.root/'created-after-fixture-return'),delayed)
        private=private_setup.Store(controller.root/'created-through-returned-factory')
        self.assertIsInstance(private,NativeJournal)
        self.assertIs(controller.store(controller.root/'created-through-returned-factory'),private)
        self.assertIsNot(authority_private.Store,protected)
        self.assertIs(trial_broker_positive.Store,protected)
        owner.doCleanups()
        self.assertIs(setup_fixture.Journal,original)
        self.assertIs(authority_private.Store,protected)
        self.assertIs(private_setup.Store,protected)

    def test_serialized_native_fixture_journal_keeps_fresh_snapshots_and_exact_cas(self):
        from positive_fixture import NativeJournal
        journal=NativeJournal()
        self.assertIsNone(journal.read())
        value=dict(nested=dict(items=[1]))
        first=journal.write(None,value)
        value['nested']['items'].append(2)
        first['value']['nested']['items'].append(3)
        expected=dict(schema_version=1,generation=1,value=dict(nested=dict(items=[1])))
        self.assertEqual(journal.read(),expected)
        snapshot=journal.read(); snapshot['value']['nested']['items'].append(4)
        self.assertEqual(journal.read(),expected)
        with self.assertRaisesRegex(Refusal,'CAS changed'): journal.write(snapshot,{})
        self.assertEqual(journal.read(),expected)
        for bad in (dict(value=object()),dict(value=float('nan'))):
            with self.assertRaises((TypeError,ValueError)): journal.write(expected,bad)
            self.assertEqual(journal.read(),expected)
        second=journal.write(expected,dict(next=True))
        self.assertEqual(second,dict(schema_version=1,generation=2,value=dict(next=True)))
        second['value']['next']=False
        self.assertEqual(journal.read()['value'],dict(next=True))

    def test_native_fixture_enforces_actual_store_wire_cap_before_mutation(self):
        from positive_fixture import NativeJournal
        from authority_private import MAX_STATE
        journal=NativeJournal(); before=journal.write(None,dict(ok=True))
        with self.assertRaises(Refusal): journal.write(before,dict(oversized='x'*MAX_STATE))
        self.assertEqual(journal.read(),before)

    def test_positive_finalizer_binds_native_job_before_fresh_service_loses_native_access(self):
        from types import SimpleNamespace
        from unittest.mock import Mock,patch
        import positive_fixture
        f=positive_fixture.Strict.__new__(positive_fixture.Strict)
        f.admission=SimpleNamespace(guard=Mock())
        f.temporary=SimpleNamespace(name='original-job-scratch')
        f.job=Mock()
        events=[]
        def bind(admission,role,temporary):
            admission.guard(); events.append('native-binding')
            self.assertEqual((role,temporary),('finalize','original-job-scratch'))
        def service(fixture):
            with self.assertRaisesRegex(AssertionError,'native owner'): fixture.admission.guard()
            events.append('fresh-service'); return 'settled'
        with patch.object(__import__('trial_broker_positive'),'bind_native_job',side_effect=bind),\
             patch.object(positive_fixture.context_fixture.Context,'finalize',service):
            self.assertEqual(f.finish_positive(),'settled')
        self.assertEqual(events,['native-binding','fresh-service'])

    def test_fresh_budget_is_selected_before_provisioning_without_changing_limits(self):
        from positive_fixture import original_intent
        from test_authority_trial_setup import intent
        before = intent()
        before['resources']['identity_record'] = 'original-native-identities'
        selected = original_intent('cached-image', lambda:before)
        self.assertEqual(selected['expires'], 4600)
        self.assertEqual(selected['policy']['image'], 'cached-image')
        self.assertEqual(selected['policy']['limits'], before['policy']['limits'])
        self.assertEqual(selected['resources'], before['resources'])
        self.assertEqual(before['expires'], 2000)

    def test_pinned_kit_reads_committed_inventory_not_untracked_checkout_files(self):
        from pathlib import Path
        from trial_runtime import pinned_kit
        root = Path(__file__).resolve().parents[3]
        files = pinned_kit(root, '52cf54117323689104abd3c80b62ce0c3d9b93da')
        self.assertIn('.ai/scripts/lifecycle.py', files)
        self.assertNotIn('.agentic.json', files)
        self.assertNotIn('.ai/docs/posix-hook-python-spec.md', files)

    def test_required_runtime_refuses_windows_before_engine_access(self):
        from unittest.mock import patch
        import trial_runtime
        with patch.object(trial_runtime.sys, 'platform', 'win32'), patch.object(trial_runtime.subprocess, 'run') as run:
            with self.assertRaisesRegex(Refusal, 'Linux root'): trial_runtime.preflight('python@sha256:'+'a'*64, 'podman')
            run.assert_not_called()

    def test_image_inspection_requires_the_exact_cached_digest(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        import trial_runtime
        image = 'python@sha256:'+'a'*64
        with patch.object(trial_runtime.sys, 'platform', 'linux'), patch.object(trial_runtime.os, 'geteuid', return_value=0, create=True), \
             patch.object(trial_runtime.shutil, 'which', return_value='/usr/bin/podman'), \
             patch.object(trial_runtime.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='[]')):
            with self.assertRaisesRegex(Refusal, 'cached image'): trial_runtime.preflight(image, 'podman')


class NativeMutationContracts(unittest.TestCase):
    def test_mutation_entrypoint_is_release_held_before_access(self):
        from trial_controller import Native
        with self.assertRaisesRegex(Refusal, 'qualify-live blocked'):
            Native(None).prepare_negative('prompt', 'bad-acceptance', None)


import test_authority_trial_negative_case as negative_fixture


@unittest.skipIf(getattr(negative_fixture.NativeNegative,'__unittest_skip__',False),'optional cryptography required')
class MutationCompositionContracts(unittest.TestCase):
    # Component transition coverage; OCI responses in this legacy fixture are
    # modeled. Only the explicit strict runtime command proves critical execution.
    fixture=negative_fixture.NativeNegative.fixture
    prepared=negative_fixture.NativeNegative.prepared
    connected=negative_fixture.NativeNegative.connected
    configured=negative_fixture.NativeNegative.configured
    exercise=negative_fixture.NativeNegative.exercise
    prepare=negative_fixture.NativeNegative.prepare

    def test_transition_preparation_full_guards_do_not_scale_with_blob_count(self):
        import cProfile
        import types
        from unittest.mock import patch
        import trial_controller,trial_specimen,trial_transition
        from trusted_ci_policy import digest
        guard_code=next(code for code in trial_transition.prepare.__code__.co_consts
                        if isinstance(code,types.CodeType) and code.co_name=='guard')
        opening=trial_controller.Native._open
        counts=[]
        def approved(native,prompt,name,*args,**kwargs):
            if name in trial_specimen.RECIPES: kwargs['negative_approve']=digest
            return opening(native,prompt,name,*args,**kwargs)
        for size in (2,24):
            files={f'file-{i}.bin':dict(content=b'original\n',executable=False) for i in range(size)}
            files['result.bin']=dict(content=b'original\n',executable=False)
            files['.ai/scripts/lifecycle.py']=dict(content=b'import sys\nsys.exit(0)\n',executable=False)
            def check(*args):
                from test_authority_trial_new_head_case import NewHead
                f=NewHead(self,args); profile=cProfile.Profile()
                revision=f.native._completion('prompt',f.source)['record']['pair']['fixture_revision']
                self.assertIn('.ai/scripts/lifecycle.py',f.source.trees[f.source.commits[revision]['tree']['sha']])
                with patch.object(trial_controller.Native,'_open',approved):
                    profile.runcall(f.current,observed=False)
                counts.append(sum(entry.callcount for entry in profile.getstats() if entry.code is guard_code))
                self.assertEqual(f.admission.candidate['transition']['intent']['phase'],'current')
                f.admission.guard()
            from test_authority_trial_new_head_case import NativeNewHead
            # This legacy component needs its trusted historical seed, created
            # before the original trial freezes. The strict seed is unchanged.
            with patch.object(self,'fixture',types.MethodType(NativeNewHead.fixture,self)):
                self.exercise(continuation=check,export_files=files)
        self.assertEqual(len(counts),2)
        self.assertGreater(counts[0],0)
        self.assertEqual(counts[0],counts[1])

    def test_transition_read_and_forced_write_guards_reject_observer_faults(self):
        # Guard-component probes inside one genuine legacy prefix. Temporary
        # negative observations never rewind journals or fork effect attempts.
        from unittest.mock import patch
        import types
        import submission,trial_controller,trial_specimen,trial_transition
        from trusted_ci_policy import digest
        opening=trial_controller.Native._open; actual_prepare=trial_transition.prepare
        actual_advance=submission._advance
        probes=[]
        def approved(native,prompt,name,*args,**kwargs):
            if name in trial_specimen.RECIPES: kwargs['negative_approve']=digest
            return opening(native,prompt,name,*args,**kwargs)
        def check(*args):
            from test_authority_trial_new_head_case import NewHead
            f=NewHead(self,args)
            def prepare(preparer,completed,reservation,history,before,phase,*args):
                if reservation['name']!='new-head' or phase!='current':
                    return actual_prepare(preparer,completed,reservation,history,before,phase,*args)
                c=preparer.native.provision
                def advance(api,*args,**kwargs):
                    if kwargs.get('recover'): return actual_advance(api,*args,**kwargs)
                    root='/repos/'+before['deployment']['policy']['repository']
                    transport=api.api
                    source_writes=copy.deepcopy(f.source.writes)
                    names=('trial','trial-workflow','trial-candidates','trial-eligibility',
                           'trial-controller-spoofed-source','trial-transition-new-head-current',
                           'trial-controller-new-head-prior','trial-case-publication-new-head-prior',
                           'trial-transition-new-head-prior')
                    for name in names:
                        store=c.store(c.root/name)
                        while hasattr(store,'raw') and hasattr(store.raw,'read'): store=store.raw
                        raw=store.read()
                        changed=dict(generation=1,value={}) if raw is None else dict(raw,generation=raw['generation']+1)
                        with self.subTest(local=name),patch.object(store,'read',return_value=changed),\
                             patch.object(transport,'get',side_effect=AssertionError('local fault reached provider')),\
                             self.assertRaises(Refusal):
                            api.get(root)
                        probes.append(name)
                    for field in ('owner','scope'):
                        with self.subTest(field=field),patch.object(c.session,field,'foreign'),\
                             patch.object(transport,'get',side_effect=AssertionError('owner fault reached provider')),\
                             self.assertRaises(Refusal):
                            api.get(root)
                        probes.append(field)
                    store=c.store(c.root/'trial-transition-new-head-current'); raw=store.read()
                    changed=dict(raw,generation=raw['generation']+1)
                    fault_patch=patch.object(store,'read',return_value=changed)
                    get=transport.get
                    def after_read(path):
                        value=get(path); fault_patch.start(); return value
                    try:
                        with patch.object(transport,'get',after_read),self.assertRaises(Refusal): api.get(root)
                    finally: fault_patch.stop()
                    probes.append('post-read-journal')
                    clock_patch=patch.object(c,'clock',return_value=raw['value']['intent']['expires'])
                    def expired(path):
                        value=get(path); clock_patch.start(); return value
                    try:
                        with patch.object(transport,'get',expired),self.assertRaisesRegex(Refusal,'expired'): api.get(root)
                    finally: clock_patch.stop()
                    probes.append('post-read-expiry')
                    for registry in (c.session.registry,preparer.native.registry):
                        read=registry.api.get
                        def foreign(path): return dict(read(path),id=-1) if path==registry.root else read(path)
                        with patch.object(registry.api,'get',foreign),\
                             patch.object(transport,'post',side_effect=AssertionError('remote fault reached source effect')),\
                             self.assertRaises(Refusal):
                            api.post(root+'/git/commits',{})
                        probes.append('remote-registry')
                    with patch.object(trial_transition,'prior_acceptance',return_value=dict(substituted=True)),\
                         patch.object(transport,'post',side_effect=AssertionError('changed acceptance reached source effect')),\
                         self.assertRaisesRegex(Refusal,'prior acceptance'):
                        api.post(root+'/git/commits',{})
                    probes.append('forced-prior-acceptance')
                    owner_patch=patch.object(c.session,'owner','foreign')
                    read=f.source.get; changed_owner=[]
                    def drift_during_full_guard(path):
                        value=read(path)
                        if not changed_owner and path==root+'/git/ref/heads/'+before['deployment']['policy']['target']:
                            owner_patch.start(); changed_owner.append(path)
                        return value
                    try:
                        with patch.object(f.source,'get',drift_during_full_guard),\
                             patch.object(transport,'post',side_effect=AssertionError('post-full-guard drift reached effect')),\
                             self.assertRaises(Refusal):
                            api.post(root+'/git/commits',{})
                    finally: owner_patch.stop()
                    self.assertEqual(len(changed_owner),1)
                    probes.append('post-full-guard-owner')
                    # A narrowly broken read guard admits the same bad journal
                    # observation. It cannot perform any source mutation here.
                    with patch.object(store,'read',return_value=changed),\
                         patch.object(api,'guard',lambda force=False:None),\
                         patch.object(transport,'post',side_effect=AssertionError('broken control wrote source')):
                        self.assertEqual(api.get(root)['id'],before['deployment']['policy']['repository_id'])
                    probes.append('broken-read-control')
                    self.assertEqual(f.source.writes,source_writes)
                    return actual_advance(api,*args,**kwargs)
                with patch.object(submission,'_advance',advance):
                    return actual_prepare(preparer,completed,reservation,history,before,phase,*args)
            with patch.object(trial_controller.Native,'_open',approved),patch.object(trial_transition,'prepare',prepare):
                f.current(observed=False)
            self.assertEqual(f.admission.candidate['transition']['intent']['phase'],'current')
            f.admission.guard()
        from test_authority_trial_new_head_case import NativeNewHead
        with patch.object(self,'fixture',types.MethodType(NativeNewHead.fixture,self)):
            self.exercise(continuation=check)
        self.assertEqual(len(probes),18)

    def test_mutation_preparation_full_guards_do_not_scale_with_blob_count(self):
        from unittest.mock import patch
        import trial_controller,trial_mutation
        from trusted_ci_policy import digest
        counts=[]
        actual=trial_mutation.prepare
        for size in (2,24):
            files={f'file-{i}.bin':dict(content=b'unchanged\n',executable=False) for i in range(size)}
            files['result.bin']=dict(content=b'original\n',executable=False)
            def check(*args):
                from test_authority_trial_new_head_case import NewHead
                f=NewHead(self,args)
                f.through_fifth()
                def prepare(a,*args):
                    guard=a.guard
                    with patch.object(a,'guard',wraps=guard) as audit:
                        result=actual(a,*args)
                        counts.append(audit.call_count)
                        return result
                with patch.object(trial_mutation,'prepare',prepare):
                    f.second('bad-acceptance',111,'fresh-bounded-preparation')
                self.assertTrue(trial_mutation.selected(f.admission.candidate))
                f.admission.guard()
            # Native approval is supplied explicitly; verification stays modeled
            # in this component fixture and cannot establish strict acceptance.
            opening=trial_controller.Native._open
            def approved(native,prompt,name,*args,**kwargs):
                if name=='bad-acceptance': kwargs['negative_approve']=digest
                return opening(native,prompt,name,*args,**kwargs)
            with patch.object(trial_controller.Native,'_open',approved):
                self.exercise(continuation=check,export_files=files)
        self.assertEqual(len(counts),2)
        self.assertEqual(counts[0],counts[1])

    def test_mutation_preparation_read_faults_prevent_further_effects_or_acceptance(self):
        self.preparation_read_faults(('origin','registry','journal','expiry'))

    def test_mutation_preparation_rechecks_historical_proof_after_each_read_batch(self):
        self.preparation_read_faults(('historical-proof',))

    def test_mutation_preparation_source_drift_cannot_advance_accept_or_remint(self):
        self.preparation_read_faults(('source-branch','source-pr'))

    def preparation_read_faults(self,faults):
        from unittest.mock import patch
        from coding_parent import _FencedSource
        import submission,trial_controller,trial_mutation
        from trusted_ci_policy import digest
        actual_prepare=trial_mutation.prepare
        actual_read=submission._read_tree
        opening=trial_controller.Native._open
        for scan in (1,2,3):
            for fault in faults:
                with self.subTest(scan=scan,fault=fault):
                    def check(*args):
                        from test_authority_trial_new_head_case import NewHead
                        f=NewHead(self,args); f.through_fifth()
                        events=[]; captured=[]; triggered=[]; scans=[0]; after=[]; source_states=[]
                        def prepare(a,*args):
                            captured.append(a)
                            journal=a.native.provision.store(a.native.provision.root/'trial-mutation-bad-acceptance')
                            def tree(api,root,revision,guard):
                                scans[0]+=1
                                if scans[0]!=scan: return actual_read(api,root,revision,guard)
                                transport=api
                                while isinstance(transport,_FencedSource): transport=transport.api
                                fetch=transport.fetch
                                def delayed(*args,**kwargs):
                                    if triggered: after.append(args[0])
                                    value=fetch(*args,**kwargs)
                                    if not triggered:
                                        if fault in ('origin','registry'):
                                            registry=a.native.provision.session.registry if fault=='origin' else a.registry
                                            get=registry.api.get
                                            registry.api.get=lambda path:dict(get(path),id=-1) if path==registry.root else get(path)
                                        elif fault=='historical-proof':
                                            from registry import TRIAL,trial_reference
                                            prior=f.origin.blob(a.value['history'][0]['revision'],TRIAL)[0]
                                            f.origin.api.refs[trial_reference(prior)]='0'*40
                                        elif fault=='source-branch':
                                            f.source.refs[a.candidate['submitted']['branch']]='0'*40
                                        elif fault=='source-pr':
                                            pr=next(pr for pr in f.source.prs if pr['number']==a.candidate['submitted']['pr'])
                                            pr['head']['sha']='0'*40
                                        elif fault=='journal': journal.write(journal.read(),dict(interference=True))
                                        else: f.clock[0]=a.record['expires']
                                        triggered.append(len(events))
                                        source_states.append(copy.deepcopy((f.source.refs,f.source.commits,f.origin.api.refs)))
                                    return value
                                with patch.object(transport,'fetch',delayed):
                                    return actual_read(api,root,revision,guard)
                            post=f.source.post; original_post=f.origin.api.post; write=journal.write
                            def effect(call,*args,**kwargs):
                                events.append(args[0] if args else 'journal')
                                return call(*args,**kwargs)
                            with patch.object(submission,'_read_tree',tree),\
                                 patch.object(f.source,'post',lambda *args,**kwargs:effect(post,*args,**kwargs)),\
                                 patch.object(f.origin.api,'post',lambda *args,**kwargs:effect(original_post,*args,**kwargs)),\
                                 patch.object(journal,'write',lambda *args,**kwargs:effect(write,*args,**kwargs)):
                                return actual_prepare(a,*args)
                        def approved(native,prompt,name,*args,**kwargs):
                            if name=='bad-acceptance': kwargs['negative_approve']=digest
                            return opening(native,prompt,name,*args,**kwargs)
                        with patch.object(trial_mutation,'prepare',prepare),patch.object(trial_controller.Native,'_open',approved),\
                             self.assertRaises(Refusal):
                            f.second('bad-acceptance',111,'fresh-read-fault')
                        self.assertEqual(len(captured),1)
                        self.assertEqual(len(triggered),1)
                        if fault in ('source-branch','source-pr'):
                            # Existing preparation may retain intent/materialize
                            # blobs before authenticating the conditional advance.
                            self.assertEqual((f.source.refs,f.source.commits),source_states[0][:2])
                            with patch.object(__import__('service'),'_source_token',side_effect=AssertionError('unknown mutation reminted')),\
                                 self.assertRaises(Refusal):
                                actual_prepare(captured[0],f.preparer,digest)
                            self.assertEqual((f.source.refs,f.source.commits),source_states[0][:2])
                        else:
                            self.assertEqual(len(events),triggered[0])
                            self.assertEqual((f.source.refs,f.source.commits,f.origin.api.refs),source_states[0])
                        if fault in ('journal','expiry'): self.assertEqual(after,[])
                        self.assertFalse(trial_mutation.selected(captured[0].candidate))
                        value=captured[0].native.provision.store(captured[0].native.provision.root/'trial-mutation-bad-acceptance').read()
                        self.assertTrue(value is None or value['value'].get('phase')!='complete')
                    self.exercise(continuation=check)

    def test_preparation_read_expiry_control_exposes_additional_reads_when_broken(self):
        from unittest.mock import patch
        from coding_parent import _FencedSource
        import submission,trial_controller,trial_mutation
        from trusted_ci_policy import digest
        actual_prepare=trial_mutation.prepare; actual_read=submission._read_tree
        opening=trial_controller.Native._open
        files={name:dict(content=b'original\n',executable=False) for name in ('result.bin','extra.bin','another.bin')}
        for broken in (False,True):
            def check(*args):
                from test_authority_trial_new_head_case import NewHead
                f=NewHead(self,args); f.through_fifth()
                expired=[]; after=[]; scans=[]
                def prepare(a,*args):
                    def tree(api,root,revision,guard):
                        scans.append(revision)
                        if len(scans)!=1: return actual_read(api,root,revision,guard)
                        self.assertIsInstance(api,_FencedSource)
                        transport=api.api; fetch=transport.fetch
                        def delayed(path,**kwargs):
                            if expired: after.append(path)
                            value=fetch(path,**kwargs)
                            if not expired:
                                f.clock[0]=a.record['expires']; expired.append(path)
                            return value
                        with patch.object(transport,'fetch',delayed):
                            # Deliberately remove only this read batch's local
                            # checks. The real full boundary still refuses it.
                            return actual_read(transport if broken else api,root,revision,lambda:None if broken else guard())
                    with patch.object(submission,'_read_tree',tree): return actual_prepare(a,*args)
                def approved(native,prompt,name,*args,**kwargs):
                    if name=='bad-acceptance': kwargs['negative_approve']=digest
                    return opening(native,prompt,name,*args,**kwargs)
                writes=copy.deepcopy(f.source.writes); refs=copy.deepcopy(f.source.refs)
                with patch.object(trial_mutation,'prepare',prepare),patch.object(trial_controller.Native,'_open',approved),\
                     self.assertRaisesRegex(Refusal,'expired'):
                    f.second('bad-acceptance',111,'fresh-expiry-sensitivity')
                self.assertEqual(len(expired),1)
                if broken: self.assertGreater(len(after),0)
                else: self.assertEqual(after,[])
                self.assertEqual(f.source.writes,writes); self.assertEqual(f.source.refs,refs)
            self.exercise(continuation=check,export_files=files)

    def test_three_mutation_history_rechecks_six_trees_and_manifests_on_every_guard(self):
        from unittest.mock import patch
        import submission,trial_case,trial_controller,trial_specimen
        from registry import TRIAL
        from trusted_ci_policy import digest
        opening=trial_controller.Native._open
        def approved(native,prompt,name,*args,**kwargs):
            if name in trial_specimen.RECIPES: kwargs['negative_approve']=digest
            return opening(native,prompt,name,*args,**kwargs)
        def check(*args):
            from test_authority_trial_new_head_case import NewHead
            f=NewHead(self,args)
            with patch.object(trial_controller.Native,'_open',approved): f.through_eighth()
            c=f.native.provision
            publication=c.store(c.root/'trial-case-publication-forged-records').read()
            terminal=c.store(c.root/'trial-controller-forged-records').read()['value']['terminal']
            history=f.admission.value['history']+[dict(revision=publication['value']['revision_bound'],terminal=terminal['locator'])]
            candidates=[f.origin.blob(entry['revision'],TRIAL)[0]['candidate'] for entry in history]
            mutations=[candidate for candidate in candidates if candidate['name'] in trial_specimen.RECIPES]
            self.assertEqual(len(mutations),3)
            expected=[tree for candidate in mutations for tree in (
                candidate['transition']['intent']['reservation']['submitted']['tree'],candidate['submitted']['tree'])]
            reads=[]; manifests=[]
            actual_read=submission._read_tree; actual_manifest=submission.export_manifest
            def read(api,root,revision,guard):
                reads.append(revision)
                return actual_read(api,root,revision,guard)
            def manifest(files):
                if 'result.bin' in files: manifests.append(files)
                return actual_manifest(files)
            def guard():
                trial_case.history_guard(f.origin,f.admission.record,history,lambda:f.clock[0],f.api,f.source)
            writes=copy.deepcopy(f.source.writes)
            with patch.object(submission,'_read_tree',read),patch.object(submission,'export_manifest',manifest),\
                 patch.object(trial_specimen,'export_manifest',manifest):
                for _ in range(2):
                    reads.clear(); manifests.clear(); guard()
                    self.assertEqual(reads,expected)
                    self.assertEqual(len(manifests),6)
            settled=f.registry.binding(); retained=copy.deepcopy(terminal)
            bad=mutations[0]; old=bad['transition']['intent']['reservation']['submitted']
            submitted=bad['submitted']; original_tree=f.source.trees[old['tree']]
            current_tree=f.source.trees[submitted['tree']]
            original_blob=original_tree['result.bin'][1]
            current_blob=current_tree['.ai/scripts/lifecycle.py'][1]
            pr=next(pr for pr in f.source.prs if pr['number']==submitted['pr'])
            commit=f.source.commits[submitted['head']]
            from registry import trial_reference
            native_ref=trial_reference(bad['transition']['intent'])
            faults=[
                ('original-blob',f.source.blobs,original_blob,b'corrupt original'),
                ('current-blob',f.source.blobs,current_blob,b'corrupt mutation'),
                ('original-tree',f.source.trees,old['tree'],dict(original_tree,**{'extra.bin':original_tree['result.bin']})),
                ('current-tree',commit['tree'],'sha',old['tree']),
                ('original-mode',original_tree,'result.bin',('100755' if original_tree['result.bin'][0]=='100644' else '100644',original_blob)),
                ('current-mode',current_tree,'.ai/scripts/lifecycle.py',('100755',current_blob)),
                ('pr-identity',pr['user'],'id',pr['user']['id']+1),
                ('pr-branch',pr['head'],'ref','unapproved-branch'),
                ('source-ref',f.source.refs,submitted['branch'],'f'*40),
                ('commit-parent',commit,'parents',[dict(sha='f'*40)]),
                ('commit-identity',commit['committer'],'email','unapproved@example.invalid'),
                ('native-proof',f.origin.api.refs,native_ref,'0'*40),
            ]
            for name,mapping,key,value in faults:
                previous=mapping[key]
                try:
                    mapping[key]=value
                    with self.subTest(fault=name),self.assertRaises(Refusal): guard()
                finally: mapping[key]=previous
            get=f.source.get; delayed=[]; after=[]; now=f.clock[0]
            def late(path):
                if delayed: after.append(path)
                value=get(path)
                if not delayed and path.endswith('/git/commits/'+submitted['head']):
                    delayed.append(path); f.clock[0]=bad['transition']['intent']['expires']
                return value
            with patch.object(f.source,'get',late),self.assertRaisesRegex(Refusal,'expired'):
                guard()
            self.assertTrue(delayed); self.assertEqual(after,[])
            # Deliberately remove metadata-boundary sampling in this frozen-clock
            # component. The final sample still refuses, but subsequent reads leak.
            import coding_parent
            fenced=coding_parent._FencedSource
            class Unsampled(fenced):
                def __init__(self,api,guard,authorize):
                    super().__init__(api,lambda force=False:None,authorize)
            f.clock[0]=now; delayed.clear(); after.clear()
            with patch.object(coding_parent,'_FencedSource',Unsampled),patch.object(f.source,'get',late),\
                 self.assertRaisesRegex(Refusal,'expired'):
                guard()
            self.assertTrue(delayed); self.assertTrue(after)
            self.assertEqual(f.registry.binding(),settled)
            self.assertEqual(c.store(c.root/'trial-controller-forged-records').read()['value']['terminal'],retained)
            self.assertEqual(f.source.writes,writes)
        self.exercise(continuation=check)

    def test_history_rechecks_real_mutation_source_publications_and_elapsed_deadline(self):
        from unittest.mock import patch
        import trial_controller,trial_case,trial_mutation
        from registry import trial_reference
        from trusted_ci_policy import digest
        opening=trial_controller.Native._open
        def approved(native,prompt,name,*args,**kwargs):
            if name=='bad-acceptance': kwargs['negative_approve']=digest
            return opening(native,prompt,name,*args,**kwargs)
        def check(*args):
            from test_authority_trial_new_head_case import NewHead
            f=NewHead(self,args)
            with patch.object(trial_controller.Native,'_open',approved): f.sixth()
            f.rejected(); f.host(); f.run('broker'); f.finalize(); terminal=f.observe()
            c=f.native.provision
            publication=c.store(c.root/'trial-case-publication-bad-acceptance').read()
            history=f.admission.value['history']+[dict(revision=publication['value']['revision_bound'],terminal=terminal['locator'])]
            def guard():
                trial_case.history_guard(f.origin,f.admission.record,history,lambda:f.clock[0],f.api,f.source)
            guard()
            branch=f.admission.candidate['submitted']['branch']; head=f.source.refs[branch]
            f.source.refs[branch]='f'*40
            with self.assertRaises(Refusal): guard()
            with patch.object(trial_mutation,'validate',return_value={}): guard()
            f.source.refs[branch]=head
            ref=trial_reference(dict(kind=trial_mutation.INTENT,name='bad-acceptance',task_id=f.admission.record['task_id'],execution=None))
            revision=f.origin.api.refs[ref]; f.origin.api.refs[ref]='0'*40
            with self.assertRaises(Refusal): guard()
            f.origin.api.refs[ref]=revision
            fetch=f.source.fetch; delayed=[]
            def late(path,**kwargs):
                value=fetch(path,**kwargs)
                if '/git/blobs/' in path and not delayed:
                    delayed.append(path); f.clock[0]=f.admission.candidate['transition']['intent']['expires']
                return value
            writes=copy.deepcopy(f.source.writes)
            with patch.object(f.source,'fetch',late),self.assertRaisesRegex(Refusal,'expired|deadline'):
                guard()
            self.assertTrue(delayed)
            self.assertEqual(f.source.writes,writes)
        self.exercise(continuation=check)

    def test_native_mutation_uses_fenced_source_and_preserves_original_reservation(self):
        from unittest.mock import patch
        import trial_controller
        from trial_specimen import validate_mutation
        from trusted_ci_policy import digest
        opening=trial_controller.Native._open
        def approved(native,prompt,name,*args,**kwargs):
            if name=='bad-acceptance': kwargs['negative_approve']=digest
            return opening(native,prompt,name,*args,**kwargs)
        def check(*args):
            from test_authority_trial_new_head_case import NewHead
            f=NewHead(self,args)
            with patch.object(trial_controller.Native,'_open',approved): f.sixth()
            candidate=f.admission.candidate
            original=candidate['transition']['intent']['reservation']['submitted']
            changed=candidate['submitted']
            self.assertEqual((changed['pr'],changed['branch']),(original['pr'],original['branch']))
            self.assertNotEqual(changed['head'],original['head'])
            self.assertEqual(f.source.commits[changed['head']]['parents'],[dict(sha=original['head'])])
            def files(tree):
                return {name:dict(content=f.source.blobs[blob],executable=mode=='100755')
                        for name,(mode,blob) in f.source.trees[tree].items()}
            validate_mutation(files(original['tree']),files(changed['tree']),'bad-acceptance')
        self.exercise(continuation=check)


class PositiveContracts(unittest.TestCase):
    def test_negative_reservation_cannot_use_the_dispatch_primitive_as_a_positive_alias(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        import merge_window
        read=Mock(side_effect=AssertionError('negative reservation entered dispatch'))
        with self.assertRaisesRegex(Refusal,'positive reservation'):
            merge_window._dispatch({},read,None,None,lambda:100,SimpleNamespace(candidate=dict(name='direct-push')))
        read.assert_not_called()

    def test_positive_approval_is_held_before_access(self):
        from trial_controller import Native
        with self.assertRaisesRegex(Refusal, 'qualify-live blocked'):
            Native(None).approve_positive('prompt', None, None)

    def test_positive_deadline_includes_actual_case_delegation(self):
        from types import SimpleNamespace
        from trial_broker_positive import deadline
        a=SimpleNamespace(record=dict(expires=500,origin=dict(binding=dict(fence=dict(pending=dict(execution_deadline=450))))),
                          binding=dict(deployment=dict(expires=400),fence=dict(pending=dict(execution_deadline=350))),
                          value=dict(certificate=dict(expires=300)),case=dict(execution=dict(credential=dict(expires=200))))
        self.assertEqual(deadline(a),200)


if __name__ == '__main__': unittest.main()
