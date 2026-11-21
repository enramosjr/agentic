"""Real native context interruption and history boundaries; remote APIs are fixtures."""
import backend_test_support
import copy
import io
import json
import unittest
import zipfile
from contextlib import contextmanager, ExitStack
from unittest.mock import patch

import trial_broker_context as context
import trial_controller
from registry import trial_reference
from trusted_ci_policy import Refusal
from test_authority_broker_evidence import stamp
import test_authority_trial_broker_context_case as context_fixture


class FinalizerMintGuard(unittest.TestCase):
    def test_fresh_guard_precedes_administrative_token_post(self):
        from types import SimpleNamespace
        import service
        effects=[]
        def mint(*args):
            effects.append(args)
            raise AssertionError('observed token mint')
        def expired():
            raise Refusal('configuration deadline expired during readback')
        root=SimpleNamespace(post=mint)
        identities=dict(apps=dict(admin=dict(installation_id=7)))
        binding=dict(deployment=dict(policy=dict(authority_repository_id=456)))
        with self.assertRaisesRegex(Refusal,'deadline expired'):
            with service._admin_authority(root,None,None,binding,identities,None,before_effect=expired):
                self.fail('expired context borrowed a writer')
        self.assertEqual(effects,[])
        with self.assertRaisesRegex(AssertionError,'observed token mint'):
            with service._admin_authority(root,None,None,binding,identities,None):
                self.fail('fault control did not reach mint')
        self.assertEqual(len(effects),1)


@unittest.skipIf(getattr(context_fixture.NativeBrokerContext,'__unittest_skip__',False),'optional cryptography required')
class NativeContextRecovery(unittest.TestCase):
    fixture=context_fixture.NativeBrokerContext.fixture
    prepared=context_fixture.NativeBrokerContext.prepared
    connected=context_fixture.NativeBrokerContext.connected
    configured=context_fixture.NativeBrokerContext.configured
    exercise=context_fixture.NativeBrokerContext.exercise
    prepare=context_fixture.NativeBrokerContext.prepare

    def run_case(self,check):
        self.exercise(continuation=check,
            export_files=context_fixture.revocation_fixture.context_fixture.previous.spoof_fixture.forged_fixture.EXPORT)

    def prepared_context(self,args):
        value=context_fixture.Context(self,args)
        value.fifteenth()
        self.assertEqual(len(value.admission.value['history']),14)
        return value

    def broker(self,f,advance=None):
        scheduled=[]
        def once(seconds):
            self.assertEqual(scheduled,[])
            scheduled.append(True)
            return (advance or f.transition)()
        f.sleeper=once
        result=f.run('broker')
        self.assertEqual(result['refusal'],'configuration_changed')
        self.assertEqual(scheduled,[True])
        return result

    def assert_origin_held(self,f,origin):
        self.assertEqual(f.origin.binding(),origin)
        self.assertIsNotNone(origin['fence']['pending'])
        self.assertEqual(f.merges,[])
        journal=f.native.provision.store(f.native.provision.root/'trial-controller-context-transition').read()
        self.assertEqual(journal['value']['phase'],'bound')

    def test_unknown_host_create_or_delete_ack_is_never_adopted_or_replayed(self):
        for fault in ('create','delete'):
            def check(*args):
                f=self.prepared_context(args); origin=f.origin.binding(); before=f.registry.binding()
                events=len(f.target.events)
                if fault=='create':
                    original=f.target.post
                    def lost(path,body):
                        original(path,body)
                        raise OSError('unknown native create acknowledgement')
                    f.target.post=lost
                else:
                    original=f.target.fetch
                    def lost(path,method='GET',**kwargs):
                        result=original(path,method=method,**kwargs)
                        if method=='DELETE' and '/rulesets/' in path:
                            raise OSError('unknown native delete acknowledgement')
                        return result
                    f.target.fetch=lost
                f.sleeper=lambda seconds:f.transition()
                with self.assertRaisesRegex(OSError,'unknown native'): f.run('broker')
                held=f.registry.binding()
                self.assertEqual(held['fence']['schema_version'],3)
                self.assertEqual(held['fence']['retained']['binding'],before)
                self.assertEqual(held['fence']['completed'],before['fence']['completed'])
                state=f.native.provision.store(f.native.provision.root/context.JOURNAL).read()['value']
                self.assertEqual(state['phase'],'policy-started')
                self.assertEqual(state['effects'][-1]['phase'],'started')
                observed=copy.deepcopy(f.target.events)
                self.assertEqual(len(observed)-events,1 if fault=='create' else 3)
                # The modeled provider already changed inventory. That is not an
                # acknowledgement and cannot admit another engine invocation.
                with self.assertRaises(Refusal): f.transition()
                self.assertEqual(f.target.events,observed)
                self.assertEqual(f.registry.binding(),held)
                self.assertFalse(any(a['name'].endswith('-trial-context-refusal') for a in f.remote.artifacts))
                self.assert_origin_held(f,origin)
                return f.admission.request['snapshot']['base']
            with self.subTest(fault=fault): self.run_case(check)

    def test_exact_context_registry_and_native_result_ack_recover_without_host_replay(self):
        def check(*args):
            f=self.prepared_context(args); origin=f.origin.binding()
            old=f.registry.binding(); events=len(f.target.events)
            fetch=f.api.fetch; post=f.origin.api.post
            writes=[]; publications=[]
            result_ref=trial_reference(dict(kind=context.RESULT,name='context-transition',task_id=f.admission.record['task_id'],execution=None))
            def lost_write(path,method='GET',**kwargs):
                result=fetch(path,method=method,**kwargs)
                if method=='PATCH' and path.endswith('/git/refs/heads/agentic-registry'):
                    current=f.registry.binding()
                    if current['configuration_revision']!=old['configuration_revision'] and not writes:
                        writes.append(current['branch_head'])
                        raise OSError('unknown context Registry acknowledgement')
                return result
            def lost_publication(path,body):
                result=post(path,body)
                if path.endswith('/git/refs') and body.get('ref')=='refs/heads/'+result_ref:
                    publications.append(body['sha'])
                    raise OSError('unknown context result acknowledgement')
                return result
            f.api.fetch=lost_write; f.origin.api.post=lost_publication
            def advance():
                with self.assertRaisesRegex(OSError,'Registry acknowledgement'): f.transition()
                effects=copy.deepcopy(f.target.events)
                self.assertEqual(len(effects)-events,4)
                with self.assertRaisesRegex(OSError,'result acknowledgement'): f.transition()
                self.assertEqual(f.target.events,effects)
                link=f.transition()
                self.assertEqual(link,dict(kind=context.RESULT,revision=publications[0]))
                self.assertEqual(f.target.events,effects)
                return link
            self.broker(f,advance)
            self.assertEqual(len(writes),1); self.assertEqual(len(publications),1)
            self.assertEqual(len(f.target.events)-events,4)
            self.assertEqual(f.registry.binding()['fence']['schema_version'],3)
            self.assert_origin_held(f,origin)
            f.api.fetch=fetch; f.origin.api.post=post
            after=f.finalize()
            self.assertEqual(f.observe()['binding'],after)
            self.assertEqual(len(f.target.events)-events,4)
            self.assertIsNone(after['fence']['pending'])
            return f.admission.request['snapshot']['base']
        self.run_case(check)

    def test_real_service_unknown_mint_ack_cannot_remint_after_marker_deletion(self):
        def check(*args):
            f=self.prepared_context(args); origin=f.origin.binding()
            self.broker(f); held=f.registry.binding()
            apps=f.apps; mints=[]
            def uncertain_root(*args):
                root=apps(*args); post=root.post
                def lost(path,body):
                    result=post(path,body)
                    if path.endswith('/access_tokens'):
                        mints.append((path,copy.deepcopy(body)))
                        raise OSError('unknown real service mint acknowledgement')
                    return result
                root.post=lost
                return root
            f.apps=uncertain_root
            with self.assertRaisesRegex(OSError,'real service mint'): f.finalize()
            self.assertEqual(len(mints),1)
            marker=next(a for a in f.remote.artifacts if a['name'].startswith('trial-context-recovery-intent-'))
            f.remote.artifacts.remove(marker)
            with self.assertRaisesRegex(Refusal,'already attempted'): f.finalize()
            self.assertEqual(len(mints),1)
            self.assertEqual(f.registry.binding(),held)
            self.assertFalse(any(a['name'].startswith('trial-case-terminal-') for a in f.remote.artifacts))
            with self.assertRaises(Refusal): trial_controller.Native(f.preparer).recover_terminal('prompt','context-transition')
            self.assert_origin_held(f,origin)
            return f.admission.request['snapshot']['base']
        self.run_case(check)

    def test_pair_ack_loss_and_unknown_terminal_publication_never_complete_or_replay(self):
        for fault in ('missing','uploaded-failed'):
            def check(*args):
                f=self.prepared_context(args); origin=f.origin.binding()
                self.broker(f)
                fetch=f.api.fetch; upload=f.upload; apps=f.apps
                pairs=[]; terminal_attempts=[]; mints=[]
                def count_roots(*args):
                    root=apps(*args); post=root.post
                    def counted(path,body):
                        if path.endswith('/access_tokens'): mints.append(path)
                        return post(path,body)
                    root.post=counted
                    return root
                def lost_pair(path,method='GET',**kwargs):
                    result=fetch(path,method=method,**kwargs)
                    if method=='PATCH' and path.endswith('/git/refs/heads/agentic-registry'):
                        current=f.registry.binding()
                        if current['fence']['pending'] is None:
                            pairs.append(current['branch_head'])
                            raise OSError('unknown paired terminal acknowledgement')
                    return result
                def lost_terminal(name,raw):
                    if name.startswith('trial-case-terminal-'):
                        terminal_attempts.append(name)
                        if fault=='uploaded-failed': upload(name,raw)
                        raise OSError('unknown terminal artifact publication')
                    return upload(name,raw)
                f.api.fetch=lost_pair; f.upload=lost_terminal; f.apps=count_roots
                with self.assertRaisesRegex(OSError,'terminal artifact publication'): f.finalize()
                self.assertEqual(len(pairs),1); self.assertEqual(len(terminal_attempts),1)
                settled=f.registry.binding(); count=len(mints)
                self.assertIsNone(settled['fence']['pending'])
                self.assertEqual([r['kind'] for r in settled['fence']['completed'][-2:]],['not-submitted','configuration-complete'])
                with self.assertRaises(Refusal): f.finalize()
                self.assertEqual(len(mints),count); self.assertEqual(len(pairs),1)
                self.assertEqual(len(terminal_attempts),1)
                self.assertEqual(f.registry.binding(),settled)
                finalizer=next(j for j in f.remote.jobs if j['name']=='finalize')
                finalizer.update(status='completed',conclusion='failure',completed_at=stamp(f.clock[0]))
                artifact=next((a for a in f.remote.artifacts if a['name'].startswith('trial-case-terminal-')),None)
                if artifact is None:
                    artifact=next(a for a in f.remote.artifacts if a['name'].startswith('trial-context-recovery-intent-'))
                locator=dict(run_id=f.remote.run['id'],attempt=1,job_id=finalizer['id'],artifact_id=artifact['id'])
                with self.assertRaises(Refusal):
                    trial_controller.Native(f.preparer)._observe_terminal('prompt','context-transition',locator,f.source)
                with self.assertRaises(Refusal): trial_controller.Native(f.preparer).recover_terminal('prompt','context-transition')
                self.assert_origin_held(f,origin)
                return f.admission.request['snapshot']['base']
            with self.subTest(fault=fault): self.run_case(check)

    @contextmanager
    def altered_archive(self,f,artifact,change,member):
        raw=f.remote.raw[artifact['id']]; digest=artifact['digest']
        with zipfile.ZipFile(io.BytesIO(raw)) as archive: value=json.loads(archive.read(member))
        change(value)
        f.remote.replace(artifact['id'],value,member)
        try: yield
        finally:
            f.remote.raw[artifact['id']]=raw
            artifact['digest']=digest

    @contextmanager
    def read_only_transports(self,f):
        def reader(fetch):
            def read(path,*args,**kwargs):
                method=kwargs.get('method',args[0] if args else 'GET')
                self.assertEqual(method,'GET','expired recovery attempted a transport mutation')
                return fetch(path,*args,**kwargs)
            return read
        with ExitStack() as patches:
            for api in {id(v):v for v in (f.api,f.origin.api,f.source)}.values():
                if hasattr(api,'post'):
                    patches.enter_context(patch.object(api,'post',side_effect=AssertionError('expired recovery attempted POST')))
                if hasattr(api,'fetch'):
                    patches.enter_context(patch.object(api,'fetch',side_effect=reader(api.fetch)))
            yield

    def test_delayed_closed_terminal_recovers_read_only_after_expiry_and_rejects_tamper(self):
        def check(*args):
            f=self.prepared_context(args); self.broker(f)
            upload=f.upload
            def delayed_terminal(name,raw):
                if name.startswith('trial-case-terminal-'): f.clock[0]+=2
                return upload(name,raw)
            f.upload=delayed_terminal
            after=f.finalize(); f.clock[0]+=3
            observed=f.observe()
            self.assertEqual(observed['binding'],after)
            self.assertLess(observed['document']['completed'],observed['producer']['artifact_created'])
            self.assertLess(observed['producer']['artifact_created'],observed['producer']['job_completed'])
            f.clock[0]=max(f.admission.record['expires'],f.admission.value['certificate']['expires'],
                f.admission.record['origin']['binding']['fence']['pending']['execution_deadline'])+100
            def recover():
                return trial_controller.Native(f.preparer).recover_terminal('prompt','context-transition')
            self.assertEqual(recover(),observed)
            terminal=next(a for a in f.remote.artifacts if a['name'].startswith('trial-case-terminal-'))
            for index in (-2,-1):
                def alter(value,index=index): value['after']['fence']['completed'][index]['receipt_digest']='0'*64
                with self.subTest(pair=index),self.altered_archive(f,terminal,alter,'trial-case-terminal.json'):
                    with self.assertRaisesRegex(Refusal,'paired receipts'): recover()
            refusal=next(a for a in f.remote.artifacts if a['name'].endswith('-trial-context-refusal'))
            with self.altered_archive(f,refusal,lambda value:value.update(prepared_digest='0'*64),'receipt.json'):
                with self.assertRaises(Refusal): recover()
            result_ref=trial_reference(dict(kind=context.RESULT,name='context-transition',task_id=f.admission.record['task_id'],execution=None))
            saved=f.origin.api.refs[result_ref]
            f.origin.api.refs[result_ref]=observed['document']['context']['links'][context.INTENT]['revision']
            try:
                with self.assertRaises(Refusal): recover()
            finally: f.origin.api.refs[result_ref]=saved
            # Read the already authenticated case through its immutable terminal
            # interval; no expired live admission or renewed authority is made.
            import trial_case
            publication=f.native.provision.store(f.native.provision.root/'trial-case-publication-context-transition').read()
            case,_=trial_case.read(f.origin,publication['value']['revision_bound'],lambda:observed['producer']['job_completed'])
            current_ref=trial_reference(case); saved=f.origin.api.refs[current_ref]
            f.origin.api.refs[current_ref]=f.admission.value['history'][-1]['revision']
            try:
                with self.assertRaises(Refusal): recover()
            finally: f.origin.api.refs[current_ref]=saved
            # Read-only recovery must never call an App mint or Registry writer.
            journal=f.native.provision.store(f.native.provision.root/'trial-controller-context-transition')
            retained=journal.read()
            with self.read_only_transports(f),\
                 patch.object(f,'apps',side_effect=AssertionError('expired recovery minted credentials')),\
                 patch.object(f.registry,'finalize_handover',side_effect=AssertionError('expired recovery wrote a terminal')):
                self.assertEqual(recover(),observed)
            self.assertEqual(journal.read(),retained)
            self.assertEqual(f.registry.binding(),after)
            self.assertEqual(f.merges,[])
            return f.admission.request['snapshot']['base']
        self.run_case(check)


if __name__=='__main__':
    unittest.main()
