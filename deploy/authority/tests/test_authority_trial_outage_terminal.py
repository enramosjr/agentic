"""Fifth-case CLOSED evidence; external GitHub and worker boundaries are modeled."""
import backend_test_support
import copy
import unittest
from unittest.mock import patch

import authority_release
import broker_finalize
import broker_session
import merge_transport
import service
import trial_broker_case
import trial_case
import trial_controller
import trial_launch
import test_authority_trial_expired_terminal as expired_fixture
from test_authority_broker_evidence import stamp
from trusted_ci_github import HostRefusal
from trusted_ci_policy import Refusal, digest


class Holds(unittest.TestCase):
    def test_observation_hold_precedes_transport(self):
        class NoIO:
            def __getattr__(self, name): raise AssertionError(name)
        with self.assertRaises(authority_release.Held):
            trial_controller.Native(NoIO()).observe_terminal('prompt', 'authority-outage', {})


@unittest.skipIf(getattr(expired_fixture.ExpiredTerminal, '__unittest_skip__', False), 'optional cryptography required')
class OutageTerminal(unittest.TestCase):
    fixture = expired_fixture.ExpiredTerminal.fixture
    prepared = expired_fixture.ExpiredTerminal.prepared
    connected = expired_fixture.ExpiredTerminal.connected
    configured = expired_fixture.ExpiredTerminal.configured
    exercise = expired_fixture.ExpiredTerminal.exercise
    prepare = expired_fixture.ExpiredTerminal.prepare
    forbidden = expired_fixture.ExpiredTerminal.forbidden
    collector = expired_fixture.ExpiredTerminal.collector
    document = expired_fixture.ExpiredTerminal.document
    closed = expired_fixture.ExpiredTerminal.closed
    fourth = expired_fixture.ExpiredTerminal.fourth

    def fifth(self, args):
        f = expired_fixture.ExpiredTerminal.pending(self, args)
        f.finalize(); f.observe()
        trial_launch.revoke(f.native.provision, f.origin_factory, name='expired-proof')
        f.second('authority-outage', 109, 'fresh-fifth-case')
        with self.assertRaisesRegex(Refusal, 'pending'): f.coordinate()
        f.close_handoff(); f.published()
        f.armed=False; f.reviewed=False; f.failed=[]
        pages, source_pages, upload = f.api.pages, f.source.pages, f.upload
        def reviewed(path, collection=None):
            value=source_pages(path,collection)
            if f.armed and path.endswith('/reviews'): f.reviewed=True
            return value
        def outage(path, collection=None):
            if f.armed and f.reviewed and path.endswith('/runs/109/artifacts'):
                f.armed=False; f.failed.append(path)
                raise HostRefusal(503)
            return pages(path,collection)
        def uploading(name, raw):
            identity=upload(name,raw)
            if name.endswith('-control-ready'):
                f.clock[0]+=1
                f.run('controls')
                for purpose in broker_session.PURPOSES: f.run('final-proof',purpose)
                f.armed=True; f.reviewed=False
            return identity
        f.api.pages=outage; f.source.pages=reviewed; f.upload=uploading
        return f

    def pending(self, args):
        f=self.fifth(args)
        with patch.object(merge_transport, 'isolated', side_effect=AssertionError('negative dispatched')):
            self.assertEqual(f.run('broker')['refusal'], 'readback_unavailable')
        self.assertEqual(len(f.failed),1)
        return f

    def journal(self, f):
        return f.native.provision.store(f.native.provision.root/'trial-controller-authority-outage')

    def observe(self, f, location):
        with self.forbidden(f), patch.object(service, '_source_token', side_effect=AssertionError('terminal mint')):
            return trial_controller.Native(f.preparer)._observe_terminal('prompt','authority-outage',location,f.source)

    def history(self, f, location):
        prior=self.journal(f).read()['value']
        publication=f.native.provision.store(f.native.provision.root/'trial-case-publication-authority-outage').read()['value']
        return prior['history']+[dict(revision=publication['revision_bound'],terminal=location)]

    def case(self, f):
        publication=f.native.provision.store(f.native.provision.root/'trial-case-publication-authority-outage').read()['value']
        case,record=trial_case.read(f.origin,publication['revision_bound'],lambda:f.clock[0])
        self.assertEqual(record,f.admission.record)
        return case

    def validate(self, f, location):
        from provenance import authenticated_document
        _,_,terminal=self.document(f,'trial-case-terminal-')
        proof=authenticated_document(f.api,terminal['before']['deployment'],location,'trial-case-terminal',
                                     f.admission.record['task_id'],f.clock[0])
        return trial_broker_case.outage_terminal(f.api,f.admission.record,self.case(f),terminal,proof,f.clock[0])

    def test_connected_fifth_evidence_cleanup_and_sixth_selection(self):
        def check(*args):
            f,location=self.closed(args); original=f.origin.binding()
            _,_,terminal=self.document(f,'trial-case-terminal-')
            self.assertEqual(terminal['schema_version'],2)
            self.assertNotIn('host_receipt',terminal)
            self.assertEqual(digest(terminal['recovery']),terminal['after']['fence']['completed'][-1]['receipt_digest'])
            result=self.validate(f,location)
            self.assertFalse(result['request_sent']); self.assertEqual(result['broker_refusal'],'readback_unavailable')
            observed=self.observe(f,location); token=f.case_token
            trial_launch.revoke(f.native.provision,f.origin_factory,name='authority-outage')
            self.assertIn(token,f.revoked)
            f.second('bad-acceptance',111,'fresh-sixth-case')
            history=f.admission.value['history']; self.assertEqual(len(history),5)
            cases=[trial_case.read(f.origin,e['revision'],lambda:f.clock[0])[0] for e in history]
            self.assertEqual([c['candidate']['name'] for c in cases],list(trial_controller.CASE_CHAIN[:5]))
            for field in ('pr','head','task_id'):
                self.assertEqual(len({c['candidate']['submitted'][field] for c in cases}),5)
            self.assertEqual(f.origin.binding(),original); self.assertEqual(observed['binding'],terminal['after'])
            self.assertEqual(f.source.refs['main'],terminal['before']['fence']['pending']['base'])
            self.assertEqual(len(f.attempts),3); self.assertEqual(f.merges,[])
            self.assertEqual(f.admission.binding['deployment']['state'],'qualification')
            self.assertIsNone(f.admission.binding['deployment']['qualification'])
            self.assertFalse(f.remote.artifacts)
        self.exercise(continuation=check)

    def test_legacy_fifth_terminal_refused_by_both_consumers(self):
        def check(*args):
            f,location=self.closed(args); before=self.journal(f).read()
            identity,member,value=self.document(f,'trial-case-terminal-')
            value.update(schema_version=1); value.pop('recovery',None); value.pop('broker_receipt',None)
            f.remote.replace(identity,value,member)
            with self.assertRaises(Refusal): self.observe(f,location)
            with self.assertRaises(Refusal):
                trial_case.baseline(f.origin,f.native.registry,f.admission.record,self.history(f,location),lambda:f.clock[0])
            self.assertEqual(self.journal(f).read(),before)
        self.exercise(continuation=check)

    def test_outage_collection_and_refusal_mutations_fail_closed(self):
        def check(*args):
            f,location=self.closed(args); self.validate(f,location)
            for prefix,faults in (
                ('trial-broker-denial-',('code','status','boolean-status','path','job','before','after','observed','receipt',
                    'proof-locators','evidence','task','qualification','nonce','controls','final-proofs','extra')),
                ('proof-admin-',('capability','binding','expired')),
                ('final-proof-merge-',('nonce','binding','expired')),
                ('controls-',('nonce','digest','facts','stale')),
                ('publication-controls-',('binding',))):
                identity,member,saved=self.document(f,prefix)
                metadata=copy.deepcopy(next(a for a in f.remote.artifacts if a['id']==identity)); raw=f.remote.raw[identity]
                for fault in faults:
                    value=copy.deepcopy(saved)
                    if prefix=='trial-broker-denial-':
                        if fault=='code': value['refusal']['code']='proof_expired'
                        if fault=='status': value['refusal']['observation']['status']=500
                        if fault=='boolean-status': value['refusal']['observation']['status']=True
                        if fault=='path': value['refusal']['observation']['path']+='/other'
                        if fault=='job': value['job_id']=float(value['job_id'])
                        if fault in ('before','after'): value[fault]['head']='0'*40
                        if fault=='observed': value['observed']=value['intent']['issued']-1
                        if fault=='receipt': value['receipt_digest']='0'*64
                        c=value['collection']
                        if fault=='proof-locators': c['locators']['proofs']['admin']['artifact_id']+=1
                        if fault=='evidence': c['locators']['evidence']['run_id']+=1
                        if fault=='task': c['locators']['task']['task_id']='0'*32
                        if fault=='qualification': c['locators']['qualification']['digest']='0'*64
                        if fault=='nonce': c['request']['nonce']='0'*32
                        if fault=='controls': c['controls']['artifact_id']+=1
                        if fault=='final-proofs': c['proofs']['merge']['artifact_id']+=1
                        if fault=='extra': c['locators']['other']=None
                    else:
                        if fault=='capability': value['result']['expires']=1
                        if fault=='binding': value['operation_id']='0'*32
                        if fault=='expired': value['expires']=value['completed']
                        if fault=='nonce': value['ready_nonce' if prefix.startswith('final-') else 'nonce']='0'*32
                        if fault=='digest': value['ready_digest']='0'*64
                        if fault=='facts': value['result']['controls_digest']='0'*64
                        if fault=='stale': value['readback_started']-=31
                    f.remote.replace(identity,value,member)
                    with self.subTest(prefix=prefix,fault=fault), self.assertRaises(Refusal): self.validate(f,location)
                    with self.subTest(history=fault), self.assertRaises(Refusal):
                        trial_case.baseline(f.origin,f.native.registry,f.admission.record,self.history(f,location),lambda:f.clock[0])
                    f.remote.raw[identity]=raw; next(a for a in f.remote.artifacts if a['id']==identity).update(metadata)
        self.exercise(continuation=check)

    def test_export_exact_acknowledged_and_not_stale(self):
        def check(*args):
            f=self.pending(args); instances=[]; finalize=broker_finalize.Finalizer._finalize
            def track(instance,*pos,**kw): instances.append(instance); return finalize(instance,*pos,**kw)
            with patch.object(broker_finalize.Finalizer,'_finalize',new=track): result=f.finalize()
            instance=instances[-1]; request=f.admission.request
            evidence=instance._outage_evidence(request['operation_id'],request['sequence'],result)
            evidence['broker_receipt']['issued']=1
            self.assertNotEqual(instance._outage_evidence(request['operation_id'],request['sequence'],result),evidence)
            for op,seq,value in (('0'*32,request['sequence'],result),(request['operation_id'],request['sequence']+1,result),
                                 (request['operation_id'],request['sequence'],{})):
                with self.assertRaises(Refusal): instance._outage_evidence(op,seq,value)
            with self.assertRaises(Refusal): instance._finalize('invalid',1,1)
            with self.assertRaises(Refusal): instance._outage_evidence(request['operation_id'],request['sequence'],result)
        self.exercise(continuation=check)

    def test_original_windows_and_current_prerequisites_are_separate(self):
        def check(*args):
            f,location=self.closed(args); case=self.case(f)
            _,_,terminal=self.document(f,'trial-case-terminal-')
            from provenance import authenticated_document
            proof=authenticated_document(f.api,terminal['before']['deployment'],location,'trial-case-terminal',
                                         f.admission.record['task_id'],f.clock[0])
            for field in ('launch','execution'):
                value=copy.deepcopy(case); value[field]['credential']['expires']=terminal['completed']-1
                with self.subTest(field=field), self.assertRaises(Refusal):
                    trial_broker_case.outage_terminal(f.api,f.admission.record,value,terminal,proof,f.clock[0])
            before=self.journal(f).read(); pages=f.source.pages
            for part in ('check-runs','rules/branches','reviews'):
                def missing(path,*pos): return [] if part in path else pages(path,*pos)
                with self.subTest(current=part), patch.object(f.source,'pages',side_effect=missing), self.assertRaises(Refusal):
                    self.observe(f,location)
                self.assertEqual(self.journal(f).read(),before)
            f.clock[0]=max(case[k]['credential']['expires'] for k in ('launch','execution'))+1
            self.assertLess(f.clock[0],case['certificate']['expires'])
            target=f.source.refs['main']; f.source.refs['main']='0'*40
            with patch.object(f.source,'pages',side_effect=AssertionError('historical source freshness')), \
                 patch.object(service,'_source_token',side_effect=AssertionError('historical mint')):
                self.assertFalse(self.validate(f,location)['request_sent'])
                self.assertEqual(trial_case.baseline(f.origin,f.native.registry,f.admission.record,self.history(f,location),
                                                     lambda:f.clock[0]),terminal['after'])
            f.source.refs['main']=target; f.clock[0]=case['certificate']['expires']
            with self.assertRaises(Refusal): self.validate(f,location)
        self.exercise(continuation=check)

    def test_terminal_chain_readiness_and_inventory_mutations_fail_closed(self):
        def check(*args):
            f,location=self.closed(args); self.validate(f,location); before=self.journal(f).read()
            identity,member,terminal=self.document(f,'trial-case-terminal-')
            artifacts,raw=copy.deepcopy(f.remote.artifacts),copy.deepcopy(f.remote.raw)
            broker=next(j for j in f.remote.jobs if j['name'].startswith('broker (')); pages=f.api.pages
            for fault in ('request','certificate','envelope','receipt','producer','recovery','interval','failure','cancelled','timed_out',
                          'gate','dispatch','outcome','host-denied','missing-ready','ready-replaced','ready-late','receipt-late',
                          'missing-denial','duplicate','oversized'):
                value=copy.deepcopy(terminal)
                f.remote.artifacts[:]=copy.deepcopy(artifacts); f.remote.raw.clear(); f.remote.raw.update(raw)
                if fault=='request': value['request_digest']='0'*64
                if fault=='certificate': value['certificate_digest']='0'*64
                if fault=='envelope': value['recovery']['operation_digest']='0'*64
                if fault=='receipt': value['broker_receipt']['issued']+=1
                if fault=='producer': value['recovery']['producer']['id']+=1
                if fault=='recovery': value['recovery']['recovery']['job_id']+=1
                if fault=='interval': value['completed']=1
                if fault in ('failure','cancelled','timed_out'): broker['conclusion']=fault
                if fault in ('gate','dispatch','outcome','host-denied'):
                    a=next(a for a in f.remote.artifacts if a['name'].endswith('-not-submitted'))
                    f.remote.artifacts.append(dict(a,id=999999,name=a['name'].replace('-not-submitted','-'+fault)))
                if fault=='missing-ready': f.remote.artifacts[:]=[a for a in f.remote.artifacts if not a['name'].endswith('-control-ready')]
                if fault=='missing-denial': f.remote.artifacts[:]=[a for a in f.remote.artifacts if not a['name'].startswith('trial-broker-denial-')]
                if fault=='ready-replaced':
                    a=next(a for a in f.remote.artifacts if a['name'].endswith('-control-ready')); a['digest']='sha256:'+'0'*64
                if fault in ('ready-late','receipt-late'):
                    _,_,denial=self.document(f,'trial-broker-denial-')
                    suffix='-control-ready' if fault=='ready-late' else '-not-submitted'
                    a=next(a for a in f.remote.artifacts if a['name'].endswith(suffix))
                    a['created_at']=stamp((denial['observed'] if fault=='ready-late' else denial['completed'])+1)
                f.remote.replace(identity,value,member)
                def inventory(path,collection=None):
                    entries=pages(path,collection)
                    if collection=='artifacts' and '/runs/109/' in path:
                        if fault=='duplicate': return entries+[dict(entries[0])]
                        if fault=='oversized': return [dict(entries[0],id=i+1) for i in range(10001)]
                    return entries
                with self.subTest(fault=fault), patch.object(f.api,'pages',side_effect=inventory), self.assertRaises(Refusal):
                    self.observe(f,location)
                self.assertEqual(self.journal(f).read(),before); broker['conclusion']='success'
            f.remote.artifacts[:]=artifacts; f.remote.raw.clear(); f.remote.raw.update(raw)
            # Verify all three admissible typed statuses through the same reader.
            identity,member,denial=self.document(f,'trial-broker-denial-')
            for status in (502,503,504):
                denial['refusal']['observation']['status']=status; f.remote.replace(identity,denial,member)
                self.assertEqual(self.validate(f,location)['broker_refusal'],'readback_unavailable')
        self.exercise(continuation=check)

    def test_original_worker_receipt_semantics_fail_closed(self):
        def check(*args):
            import hashlib,io,json,zipfile
            f,location=self.closed(args); self.validate(f,location)
            worker=self.case(f)['worker']['locator']
            index=next(i for i,(a,raw) in enumerate(f.old_artifacts) if a['id']==worker['artifact_id'])
            saved=f.old_artifacts[index]; artifact,raw=saved
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                member=archive.namelist()[0]; receipt=json.loads(archive.read(member))
            for fault in ('schema','kind','request','execution','cleanup','completed','extra'):
                value=copy.deepcopy(receipt)
                if fault=='schema': value['schema_version']=True
                if fault=='kind': value['kind']='other'
                if fault=='request': value['request_digest']='0'*64
                if fault=='execution': value['execution']['job_id']+=1
                if fault=='cleanup': value['cleanup_complete']=False
                if fault=='completed': value['completed']=1
                if fault=='extra': value['other']=None
                stream=io.BytesIO()
                with zipfile.ZipFile(stream,'w') as archive: archive.writestr(zipfile.ZipInfo(member),json.dumps(value))
                changed=dict(artifact,digest='sha256:'+hashlib.sha256(stream.getvalue()).hexdigest())
                f.old_artifacts[index]=(changed,stream.getvalue())
                with self.subTest(fault=fault), self.assertRaises(Refusal): self.validate(f,location)
                f.old_artifacts[index]=saved
        self.exercise(continuation=check)

    def test_finalizer_ack_loss_cannot_export_or_publish(self):
        def check(*args):
            import registry
            f=self.pending(args); instances=[]; finalize=broker_finalize.Finalizer._finalize
            write=registry.Registry.finalize_operation
            def track(instance,*pos,**kw): instances.append(instance); return finalize(instance,*pos,**kw)
            def uncertain(instance,*pos,**kw): write(instance,*pos,**kw); raise OSError('finalizer ACK lost')
            with patch.object(broker_finalize.Finalizer,'_finalize',new=track), patch.object(registry.Registry,'finalize_operation',new=uncertain):
                with self.assertRaisesRegex(OSError,'ACK lost'): f.finalize()
            self.assertFalse(any(a['name'].startswith('trial-case-terminal-') for a in f.remote.artifacts))
            request=f.admission.request
            with self.assertRaises(Refusal): instances[-1]._outage_evidence(request['operation_id'],request['sequence'],f.native.registry.binding())
        self.exercise(continuation=check)

    def test_native_ack_loss_blocks_sixth_and_cleanup_survives_expiry(self):
        def check(*args):
            f,location=self.closed(args); journal=self.journal(f); write=type(journal.raw).write
            def uncertain(instance,*pos,**kw):
                result=write(instance,*pos,**kw)
                if instance.root==journal.raw.root: raise OSError('fifth root ACK lost')
                return result
            with patch.object(type(journal.raw),'write',new=uncertain), self.assertRaisesRegex(OSError,'ACK lost'):
                self.observe(f,location)
            f.native.provision._controller_acknowledgements.clear()
            with self.assertRaises(Refusal): self.observe(f,location)
            with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open('prompt','bad-acceptance',f.source)
            f.clock[0]=f.admission.record['expires']+1
            trial_launch.revoke(f.native.provision,f.origin_factory,name='authority-outage')
            self.assertIn(f.case_token,f.revoked)
        self.exercise(continuation=check)


if __name__ == '__main__': unittest.main()
