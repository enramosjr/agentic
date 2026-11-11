"""Native certificate revocation, never a hosted qualification receipt."""
import backend_test_support
import unittest
import io
from unittest.mock import patch

import trial_controller
from trusted_ci_github import GitHub
from trusted_ci_policy import Refusal
import test_authority_trial_context_case as context_fixture


class Revocation(context_fixture.Context):
    TRANSITION_CASES = (*context_fixture.Context.TRANSITION_CASES, 'revoked-qualification')

    def upload(self,name,raw):
        identity=super().upload(name,raw)
        if self.admission.candidate['name']=='revoked-qualification' and name.endswith('-control-ready'):
            self.run('controls')
            for purpose in ('admin','reader','issuer','coding','merge'): self.run('final-proof',purpose)
        return identity

    def fourteenth(self):
        env=self.human_ready()
        trial_controller.Native(self.preparer).human_attempt('prompt',self.human_transport([]))
        self.consume_human(env)
        job=next(j for j in self.remote.jobs if j['name']=='trial host denial')
        job.update(status='completed',conclusion='success',completed_at=__import__('test_authority_broker_evidence').stamp(self.clock[0]))
        self.run('broker'); self.finalize(); self.observe()
        self.second('revoked-qualification',133,'fresh-fourteenth-case')
        with self.owner.assertRaisesRegex(Refusal,'pending'): self.coordinate()
        self.owner.assertEqual(self.close_handoff()['host_case'],'none')
        self.published()

    def deletion_transport(self):
        factory=self.tokens
        self.deletes=[]; self.cleaned=[]
        outer=self
        fetch=self.api.fetch
        def download(path,**kwargs):
            try: return fetch(path,**kwargs)
            except StopIteration:
                # The modeled provider reports an absent archive as HTTP 404.
                raise __import__('trusted_ci_github').HostRefusal(404) from None
        self.api.fetch=download
        def tokens(token):
            if token != 'native-revocation-token': return factory(token)
            class DeleteOnly:
                def pages(self,path,collection=None):
                    outer.owner.assertEqual(path,'/installation/repositories')
                    return [dict(id=outer.p['authority_repository_id'])]
                def fetch(self,path,method='GET',expected_status=None,**kwargs):
                    if path=='/installation/token':
                        outer.cleaned.append(token); return b''
                    artifact=next(a for a in outer.remote.artifacts if a['name'].startswith('trial-case-certificate-'))
                    outer.owner.assertEqual((path,method,expected_status),('/repos/'+outer.p['authority_repository']+'/actions/artifacts/'+str(artifact['id']),'DELETE',204))
                    outer.deletes.append(artifact['id']); outer.remote.artifacts.remove(artifact)
                    return None
            return DeleteOnly()
        self.tokens=tokens
        self.admin=self.apps(self.d['apps']['admin'],self.api.secrets['AGENTIC_ADMIN_PRIVATE_KEY'])
        post=self.admin.post
        def mint(path,data):
            outer.owner.assertEqual(data,dict(repository_ids=[outer.p['authority_repository_id']],permissions=dict(actions='write')))
            outer.mints=getattr(outer,'mints',0)+1
            if getattr(outer,'revocation_fault',None)=='mint-ack':
                post(path,data); raise OSError('unknown native mint')
            return dict(post(path,data),token='native-revocation-token')
        self.admin.post=mint

    def delete(self):
        with patch.object(__import__('bootstrap'),'installation_token',context_fixture.NATIVE_MINT):
            return trial_controller.Native(self.preparer).revoke_certificate('prompt',self.operator,self.admin,self.tokens)


@unittest.skipIf(getattr(context_fixture.NativeContext,'__unittest_skip__',False),'optional cryptography required')
class NativeRevocation(unittest.TestCase):
    fixture=context_fixture.NativeContext.fixture
    prepared=context_fixture.NativeContext.prepared
    connected=context_fixture.NativeContext.connected
    configured=context_fixture.NativeContext.configured
    exercise=context_fixture.NativeContext.exercise
    prepare=context_fixture.NativeContext.prepare

    def test_real_preload_native_delete_closed_refusal_and_terminal(self):
        def check(*args):
            import trial_broker_case
            f=Revocation(self,args); f.fourteenth(); f.deletion_transport()
            target_before=f.source.refs['main']
            self.assertEqual(len(f.admission.value['history']),13)
            # A missing-before-preload artifact cannot become a revocation case.
            artifact=next(a for a in f.remote.artifacts if a['name'].startswith('trial-case-certificate-'))
            f.remote.artifacts.remove(artifact)
            with self.assertRaises(Refusal): f.run('broker')
            self.assertFalse(any(a['name'].startswith('trial-broker-intent-') for a in f.remote.artifacts))
            f.remote.artifacts.append(artifact)
            live=trial_broker_case.live_certificate(f.fresh[-1],f.api)
            for field,bad in (('digest','sha256:'+'0'*64),('expired',True),('id',1)):
                saved=artifact[field]; artifact[field]=bad
                with self.assertRaises(Refusal): trial_broker_case.live_certificate(f.fresh[-1],f.api)
                artifact[field]=saved
            self.assertEqual(trial_broker_case.live_certificate(f.fresh[-1],f.api),live)
            broker=next(j for j in f.remote.jobs if j['name'].startswith('broker ('))
            broker.update(status='in_progress',conclusion=None,completed_at=None)
            with self.assertRaisesRegex(Refusal,'preload'): f.delete()
            self.assertEqual(f.deletes,[])
            upload=f.upload; links=[]; markers=[]
            post=f.origin.api.post
            def lost_result_ack(path,body):
                result=post(path,body)
                if path.endswith('/git/refs') and body['ref'].endswith('-revocation-result'):
                    raise OSError('unknown native publication acknowledgement')
                return result
            f.origin.api.post=lost_result_ack
            def schedule(name,raw):
                identity=upload(name,raw)
                if name.endswith('-trial-preloaded'): markers.append(identity)
                return identity
            f.upload=schedule
            def publish_while_waiting(seconds):
                self.assertEqual(len(markers),1); self.assertEqual(links,[])
                with self.assertRaisesRegex(OSError,'unknown native publication'): f.delete()
                # Independent exact readback resolves publication uncertainty.
                from registry import trial_reference
                kind='native-trial-revocation-result'
                reference=trial_reference(dict(kind=kind,name='revoked-qualification',task_id=f.admission.record['task_id'],execution=None))
                links.append(dict(kind=kind,revision=f.origin.ref(reference)))
            f.sleeper=publish_while_waiting
            result=f.run('broker')
            self.assertEqual(result['refusal'],'trial_certificate_revoked')
            self.assertEqual(len(f.deletes),1); self.assertEqual(len(f.cleaned),1)
            self.assertEqual(len(links),1); self.assertEqual(f.merges,[])
            with self.assertRaises(Refusal): f.delete()
            with self.assertRaises(Refusal): trial_broker_case.live_certificate(f.fresh[-1],f.api)
            # A late moved native publication prevents terminal registry writes.
            from registry import trial_reference
            result=__import__('trial_transition').read_native(f.origin,links[0],f.admission.record)
            reference=trial_reference(result); saved=f.origin.api.refs[reference]
            f.origin.api.refs[reference]=result['intent']['revision']
            before=f.registry.binding()
            with self.assertRaises(Refusal): f.finalize()
            self.assertEqual(f.registry.binding(),before)
            f.origin.api.refs[reference]=saved
            terminal=f.finalize(); self.assertEqual(f.observe()['binding'],terminal)
            self.assertIsNone(terminal['fence']['pending'])
            self.assertEqual(terminal['fence']['completed'][-1]['kind'],'not-submitted')
            self.assertIsNone(terminal['deployment']['qualification'])
            publication=f.native.provision.store(f.native.provision.root/'trial-case-publication-revoked-qualification').read()
            observed=f.native.provision.store(f.native.provision.root/'trial-controller-revoked-qualification').read()['value']['terminal']
            history=f.admission.value['history']+[dict(revision=publication['value']['revision_bound'],terminal=observed['locator'])]
            from registry import Registry
            import trial_case
            reader=f.origin_factory(f.case_token); get=reader.get
            def original_only(path):
                self.assertFalse('/repos/'+f.p['authority_repository']+'/' in path)
                return get(path)
            reader.get=original_only
            restricted=Registry(reader,f.origin.coordinates)
            trial_case.history_guard(restricted,f.admission.record,history,lambda:f.clock[0],f.api)
            self.assertEqual(trial_case.baseline(restricted,f.registry,f.admission.record,history,lambda:f.clock[0]),terminal)
            f.origin.api.refs[reference]=result['intent']['revision']
            with self.assertRaises(Refusal): trial_case.history_guard(restricted,f.admission.record,history,lambda:f.clock[0],f.api)
            with self.assertRaises(Refusal): trial_case.baseline(restricted,f.registry,f.admission.record,history,lambda:f.clock[0])
            f.origin.api.refs[reference]=saved
            self.assertEqual(f.source.refs['main'],target_before)
            return f.source.refs['main']
        self.exercise(continuation=check,export_files=context_fixture.previous.spoof_fixture.forged_fixture.EXPORT)

    def test_unknown_native_effects_never_repeat_or_release_the_fence(self):
        for fault in ('mint-ack','delete-ack','result-ack','expired-last-read'):
            def check(*args):
                f=Revocation(self,args); f.fourteenth(); f.deletion_transport(); f.revocation_fault=fault
                if fault=='delete-ack':
                    tokens=f.tokens
                    def factory(token):
                        scoped=tokens(token)
                        if token=='native-revocation-token':
                            fetch=scoped.fetch
                            def lose(path,**kwargs):
                                result=fetch(path,**kwargs)
                                if '/actions/artifacts/' in path: raise OSError('unknown native DELETE')
                                return result
                            scoped.fetch=lose
                        return scoped
                    f.tokens=factory
                if fault=='result-ack':
                    post=f.origin.api.post
                    def lose(path,body):
                        result=post(path,body)
                        if path.endswith('/git/refs') and body['ref'].endswith('-revocation-result'):
                            raise OSError('unknown native result publication')
                        return result
                    f.origin.api.post=lose
                if fault=='expired-last-read':
                    get=f.admin.get
                    def expire(path):
                        result=get(path)
                        retained=f.native.provision.store(f.native.provision.root/'trial-native-revocation').read()
                        if path=='/repos/'+f.p['authority_repository']+'/installation' and retained is not None and retained['value']['delete_started']:
                            f.clock[0]=f.admission.record['expires']+1
                        return result
                    f.admin.get=expire
                upload=f.upload
                def schedule(name,raw):
                    result=upload(name,raw)
                    if name.endswith('-trial-preloaded'): f.delete()
                    return result
                f.upload=schedule
                with self.assertRaises(Refusal if fault=='expired-last-read' else OSError): f.run('broker')
                effects=(getattr(f,'mints',0),len(f.deletes))
                with self.assertRaises(Refusal): f.delete()
                with self.assertRaises(Refusal): f.finalize()
                f.clock[0]=f.admission.record['expires']+1
                native=trial_controller.Native(f.preparer)
                native.cleanup_certificate(f.operator,f.admin,f.tokens)
                self.assertEqual((getattr(f,'mints',0),len(f.deletes)),effects)
                self.assertEqual(effects,(1,0 if fault in ('mint-ack','expired-last-read') else 1))
                self.assertEqual(len(f.cleaned),0 if fault=='mint-ack' else 1)
                self.assertEqual(f.merges,[]); self.assertIsNotNone(f.registry.binding()['fence']['pending'])
                return f.source.refs['main']
            with self.subTest(fault=fault):
                self.exercise(continuation=check,export_files=context_fixture.previous.spoof_fixture.forged_fixture.EXPORT)


class RevocationInventory(unittest.TestCase):
    def test_live_entrypoint_is_held_before_native_access(self):
        import authority_release
        native=trial_controller.Native(None)
        with self.assertRaises(authority_release.Held): native.revoke_certificate('prompt',None,None)
        # Removing the hold reaches admission instead of satisfying this check.
        with patch.object(authority_release,'authorize',return_value=None),self.assertRaises(Refusal) as error:
            native.revoke_certificate('prompt',None,None)
        self.assertNotIsInstance(error.exception,authority_release.Held)

    def test_artifact_ids_do_not_reuse_deleted_observation_slots(self):
        from types import SimpleNamespace
        from test_authority_trial_host_case import Sequential
        remote=SimpleNamespace(run=dict(id=133),artifacts=[],raw={})
        def replace(identity,value,member):
            remote.raw[identity]=b'archive'
            next(a for a in remote.artifacts if a['id']==identity)['digest']='sha256:archive'
        remote.replace=replace
        fixture=Sequential.__new__(Sequential)
        fixture.remote,fixture.p,fixture.clock=remote,dict(authority_repository_id=702,workflow_sha='a'*40),[1400]
        first=Sequential.upload(fixture,'trial-broker-intent-1-1',b'{}')
        second=Sequential.upload(fixture,'trial-broker-denial-1-1',b'{}')
        remote.artifacts[:]=[a for a in remote.artifacts if a['id']!=first]
        third=Sequential.upload(fixture,'trial-broker-intent-2-1',b'{}')
        self.assertNotEqual(third,second)
        self.assertTrue(all('digest' in a for a in remote.artifacts))

    def test_certificate_locator_uses_the_existing_handoff_job(self):
        import service
        class Authority:
            def pages(self,*args): return [dict(id=7,name='trial-case-certificate-'+('a'*32)+'-1')]
        with patch.object(__import__('provenance'),'execution_job',return_value=dict(id=9)) as job:
            location=service._locator(Authority(),dict(policy=dict(authority_repository='owner/authority')),133,1,'trial-case-certificate','a'*32)
        self.assertEqual(job.call_args.args[4],'trial case handoff')
        self.assertEqual(location['artifact_id'],7)

    def test_exact_delete_status_fails_closed(self):
        outer=self
        class Opener:
            def __init__(self,status,raw): self.status,self.raw=status,raw
            def open(self,request,timeout):
                outer.assertEqual(request.full_url,'https://api.github.com/repos/owner/repo/actions/artifacts/1')
                outer.assertEqual(request.method,'DELETE')
                outer.assertIsNone(request.data)
                outer.assertEqual(timeout,30)
                response=io.BytesIO(self.raw); response.status=self.status; return response
        for status,raw in ((200,b'null'),(202,b'null'),(200,b'')):
            with self.subTest(status=status),self.assertRaises(Refusal):
                GitHub('token',Opener(status,raw)).fetch('/repos/owner/repo/actions/artifacts/1',method='DELETE',expected_status=204)
        self.assertIsNone(GitHub('token',Opener(204,b'')).fetch('/repos/owner/repo/actions/artifacts/1',method='DELETE',expected_status=204))

    def test_fourteenth_reservation_is_after_the_genuine_thirteen(self):
        self.assertEqual(trial_controller.CASE_CHAIN[-2:], ('human-update', 'revoked-qualification'))
        self.assertEqual(len(trial_controller.CASE_CHAIN), 14)


if __name__ == '__main__':
    unittest.main()
