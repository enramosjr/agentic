"""Fourth-case evidence through native engines; external boundaries are modeled."""
import backend_test_support
import copy
import unittest
from unittest.mock import patch

import authority_release
import broker_finalize
import merge_transport
import service
import trial_broker_case
import trial_case
import trial_controller
import trial_launch
import test_authority_trial_missing_terminal as missing_fixture
from trusted_ci_policy import Refusal, digest
from test_authority_broker_evidence import stamp


class Holds(unittest.TestCase):
    def test_observation_hold_precedes_transport(self):
        class NoIO:
            def __getattr__(self, name): raise AssertionError(name)
        with self.assertRaises(authority_release.Held):
            trial_controller.Native(NoIO()).observe_terminal('prompt', 'expired-proof', {})


@unittest.skipIf(getattr(missing_fixture.MissingTerminal, '__unittest_skip__', False), 'optional cryptography required')
class ExpiredTerminal(unittest.TestCase):
    fixture = missing_fixture.MissingTerminal.fixture
    prepared = missing_fixture.MissingTerminal.prepared
    connected = missing_fixture.MissingTerminal.connected
    configured = missing_fixture.MissingTerminal.configured
    exercise = missing_fixture.MissingTerminal.exercise
    prepare = missing_fixture.MissingTerminal.prepare
    forbidden = missing_fixture.MissingTerminal.forbidden
    collector = missing_fixture.MissingTerminal.collector
    document = missing_fixture.MissingTerminal.document
    closed = missing_fixture.MissingTerminal.closed

    def fourth(self, args):
        f = missing_fixture.MissingTerminal.pending(self, args)
        f.finalize(); f.observe()
        trial_launch.revoke(f.native.provision, f.origin_factory, name='missing-approval')
        f.second('expired-proof', 107, 'fresh-fourth-case')
        with self.assertRaisesRegex(Refusal, 'pending'): f.coordinate()
        f.close_handoff(); f.published()
        f.sleeper = lambda seconds:f.clock.__setitem__(0, f.clock[0]+seconds)
        return f

    def pending(self, args):
        f=self.fourth(args)
        with patch.object(merge_transport, 'isolated', side_effect=AssertionError('negative dispatched')):
            self.assertEqual(f.run('broker')['refusal'], 'proof_expired')
        return f

    def readiness(self, f):
        a=next(a for a in f.remote.artifacts if a['name'].endswith('-not-submitted'))
        f.remote.artifacts.append(dict(a,id=999999,name=a['name'].replace('-not-submitted','-control-ready')))

    def test_readiness_conflict_blocks_original_outcome_and_finalization(self):
        def check(*args):
            f=self.fourth(args); upload=f.upload
            def conflict(name,raw):
                result=upload(name,raw)
                if name.endswith('-not-submitted'): self.readiness(f)
                return result
            f.upload=conflict
            with self.assertRaises(Refusal): f.run('broker')
            self.assertFalse(any(a['name'].startswith('trial-broker-denial-') for a in f.remote.artifacts))
            self.assertIsNotNone(f.registry.binding()['fence']['pending'])
        self.exercise(continuation=check)

    def test_readiness_conflict_blocks_finalization(self):
        def finalize(*args):
            f=self.pending(args); before=f.registry.binding(); self.readiness(f)
            with self.assertRaises(Refusal): f.finalize()
            self.assertEqual(f.registry.binding(),before)
            self.assertFalse(any(a['name'].startswith('trial-case-terminal-') for a in f.remote.artifacts))
        self.exercise(continuation=finalize)

    def journal(self, f):
        return f.native.provision.store(f.native.provision.root / 'trial-controller-expired-proof')

    def observe(self, f, location):
        with self.forbidden(f), patch.object(service, '_source_token', side_effect=AssertionError('terminal mint')):
            return trial_controller.Native(f.preparer)._observe_terminal('prompt', 'expired-proof', location, f.source)

    def history(self, f, location):
        prior = self.journal(f).read()['value']
        publication = f.native.provision.store(f.native.provision.root / 'trial-case-publication-expired-proof').read()['value']
        return prior['history'] + [dict(revision=publication['revision_bound'], terminal=location)]

    def validate(self, f, location):
        _, _, terminal = self.document(f, 'trial-case-terminal-')
        from provenance import authenticated_document
        proof = authenticated_document(f.api, terminal['before']['deployment'], location, 'trial-case-terminal',
                                       f.admission.record['task_id'], f.clock[0])
        return trial_broker_case.expired_terminal(f.api, f.admission.record, self.case(f),
                                                terminal, proof, f.clock[0])

    def case(self, f):
        publication=f.native.provision.store(f.native.provision.root/'trial-case-publication-expired-proof').read()['value']
        case,record=trial_case.read(f.origin,publication['revision_bound'],lambda:f.clock[0])
        self.assertEqual(record,f.admission.record)
        return case

    def test_receipt_creation_cannot_postdate_denial(self):
        def check(*args):
            f=self.pending(args); issued=f.clock[0]; f.clock[0]+=10
            broker=next(j for j in f.remote.jobs if j['name'].startswith('broker ('))
            broker['completed_at']=stamp(f.clock[0])
            receipt=next(a for a in f.remote.artifacts if a['name'].endswith('-not-submitted'))
            receipt['created_at']=stamp(issued+1)
            f.finalize()
            job=next(j for j in f.remote.jobs if j['name']=='finalize')
            job.update(status='completed',conclusion='success',completed_at=stamp(f.clock[0]))
            artifact=next(a for a in f.remote.artifacts if a['name'].startswith('trial-case-terminal-'))
            location=dict(run_id=107,attempt=1,job_id=job['id'],artifact_id=artifact['id'])
            with self.assertRaises(Refusal): self.observe(f,location)
            with self.assertRaises(Refusal):
                trial_case.baseline(f.origin,f.native.registry,f.admission.record,self.history(f,location),lambda:f.clock[0])
        self.exercise(continuation=check)

    def test_original_events_require_retained_credential_windows(self):
        def check(*args):
            f,location=self.closed(args); case=self.case(f)
            _,_,terminal=self.document(f,'trial-case-terminal-')
            from provenance import authenticated_document
            proof=authenticated_document(f.api,terminal['before']['deployment'],location,'trial-case-terminal',
                                         f.admission.record['task_id'],f.clock[0])
            for field in ('launch','execution'):
                value=copy.deepcopy(case)
                value[field]['credential']['expires']=terminal['completed']-1
                with self.subTest(field=field), self.assertRaises(Refusal):
                    trial_broker_case.expired_terminal(f.api,f.admission.record,value,terminal,proof,f.clock[0])
            # The short capability may expire after its actual events; this
            # grants history only, while certificate/record/deployment stay live.
            f.clock[0]=max(case[k]['credential']['expires'] for k in ('launch','execution'))+1
            self.assertLess(f.clock[0],case['certificate']['expires'])
            self.assertFalse(self.validate(f,location)['request_sent'])
        self.exercise(continuation=check)

    def test_connected_fourth_evidence_cleanup_and_fifth_selection(self):
        def check(*args):
            f, location = self.closed(args); original = f.origin.binding()
            _, _, terminal = self.document(f, 'trial-case-terminal-')
            self.assertEqual(terminal['schema_version'], 2)
            self.assertNotIn('host_receipt', terminal)
            self.assertEqual(digest(terminal['recovery']), terminal['after']['fence']['completed'][-1]['receipt_digest'])
            result = self.validate(f, location)
            self.assertFalse(result['request_sent']); self.assertEqual(result['broker_refusal'], 'proof_expired')
            observed = self.observe(f, location)
            token = f.case_token
            trial_launch.revoke(f.native.provision, f.origin_factory, name='expired-proof')
            self.assertIn(token, f.revoked)
            f.second('authority-outage', 109, 'fresh-fifth-case')
            history = f.admission.value['history']
            self.assertEqual(len(history), 4)
            cases = [trial_case.read(f.origin, e['revision'], lambda:f.clock[0])[0] for e in history]
            self.assertEqual([c['candidate']['name'] for c in cases], list(trial_controller.CASE_CHAIN[:4]))
            for field in ('pr', 'head', 'task_id'):
                self.assertEqual(len({c['candidate']['submitted'][field] for c in cases}), 4)
            self.assertEqual(f.origin.binding(), original)
            self.assertEqual(observed['binding'], terminal['after'])
            self.assertEqual(f.source.refs['main'], terminal['before']['fence']['pending']['base'])
            self.assertEqual(len(f.attempts), 3); self.assertEqual(f.merges, [])
            self.assertFalse(f.remote.artifacts)
            self.assertEqual(f.admission.binding['deployment']['state'], 'qualification')
            self.assertIsNone(f.admission.binding['deployment']['qualification'])
        self.exercise(continuation=check)

    def test_legacy_terminal_refused_by_both_consumers(self):
        def check(*args):
            f, location = self.closed(args); before = self.journal(f).read()
            identity, member, value = self.document(f, 'trial-case-terminal-')
            value.update(schema_version=1); value.pop('recovery', None); value.pop('broker_receipt', None)
            f.remote.replace(identity, value, member)
            with self.assertRaises(Refusal): self.observe(f, location)
            with self.assertRaises(Refusal):
                trial_case.baseline(f.origin, f.native.registry, f.admission.record, self.history(f, location), lambda:f.clock[0])
            self.assertEqual(self.journal(f).read(), before)
        self.exercise(continuation=check)

    def test_original_proofs_and_exact_refusal_fail_closed(self):
        def check(*args):
            f, location = self.closed(args); self.validate(f, location)
            for prefix, faults in (
                ('trial-broker-denial-', ('code','purpose','proof_digest','expires','observed','receipt_digest','job_id','schema','intent')),
                ('proof-admin-', ('capability','binding','unexpired','issued')),
                ('publication-controls-', ('publication',))):
                identity, member, saved = self.document(f, prefix)
                metadata = copy.deepcopy(next(a for a in f.remote.artifacts if a['id']==identity)); raw=f.remote.raw[identity]
                for fault in faults:
                    value=copy.deepcopy(saved)
                    if fault=='code': value['refusal']['code']='readback_unavailable'
                    if fault=='purpose': value['refusal']['observation']['purpose']='merge'
                    if fault=='proof_digest': value['refusal']['observation']['proof_digest']='0'*64
                    if fault=='expires': value['refusal']['observation']['expires']+=1
                    if fault=='observed': value['refusal']['observation']['observed']=value['intent']['issued']
                    if fault=='receipt_digest': value['receipt_digest']='0'*64
                    if fault=='job_id': value['job_id']=float(value['job_id'])
                    if fault=='schema': value['schema_version']=True
                    if fault=='intent': value['intent']['proofs_digest']='0'*64
                    if fault=='capability': value['result']['expires']=1
                    if fault=='binding': value['operation_id']='0'*32
                    if fault=='unexpired': value['expires']+=1000
                    if fault=='issued': value['issued']=value['expires']
                    if fault=='publication': value['operation_id']='0'*32
                    f.remote.replace(identity,value,member)
                    with self.subTest(fault=fault), self.assertRaises(Refusal): self.validate(f, location)
                    with self.subTest(history=fault), self.assertRaises(Refusal):
                        trial_case.baseline(f.origin, f.native.registry, f.admission.record, self.history(f, location), lambda:f.clock[0])
                    f.remote.raw[identity]=raw; next(a for a in f.remote.artifacts if a['id']==identity).update(metadata)
        self.exercise(continuation=check)

    def test_chain_inventory_intervals_and_current_prerequisites(self):
        def check(*args):
            f, location = self.closed(args); before=self.journal(f).read()
            identity, member, terminal=self.document(f, 'trial-case-terminal-')
            artifacts, raw=copy.deepcopy(f.remote.artifacts), copy.deepcopy(f.remote.raw)
            pages=f.api.pages
            for fault in ('request','certificate','envelope','receipt','producer','recovery','interval','failed-broker',
                          'gate','dispatch','outcome','host-denied','control-ready','missing','duplicate','oversized'):
                value=copy.deepcopy(terminal)
                f.remote.artifacts[:]=copy.deepcopy(artifacts); f.remote.raw.clear(); f.remote.raw.update(raw)
                broker=next(j for j in f.remote.jobs if j['name'].startswith('broker ('))
                if fault=='request': value['request_digest']='0'*64
                if fault=='certificate': value['certificate_digest']='0'*64
                if fault=='envelope': value['recovery']['operation_digest']='0'*64
                if fault=='receipt': value['broker_receipt']['issued']+=1
                if fault=='producer': value['recovery']['producer']['id']+=1
                if fault=='recovery': value['recovery']['recovery']['job_id']+=1
                if fault=='interval': value['completed']=1
                if fault=='failed-broker': broker['conclusion']='timed_out'
                if fault in ('gate','dispatch','outcome','host-denied','control-ready'):
                    a=next(a for a in f.remote.artifacts if a['name'].endswith('-not-submitted'))
                    f.remote.artifacts.append(dict(a,id=999999,name=a['name'].replace('-not-submitted','-'+fault)))
                if fault=='missing': f.remote.artifacts[:]=[a for a in f.remote.artifacts if not a['name'].startswith('trial-broker-denial-')]
                f.remote.replace(identity,value,member)
                def inventory(path, collection=None):
                    entries=pages(path,collection)
                    if collection=='artifacts' and '/runs/107/' in path:
                        if fault=='duplicate': return entries+[dict(entries[0])]
                        if fault=='oversized': return [dict(entries[0],id=i+1) for i in range(10001)]
                    return entries
                with self.subTest(fault=fault), patch.object(f.api,'pages',side_effect=inventory), self.assertRaises(Refusal):
                    self.observe(f,location)
                self.assertEqual(self.journal(f).read(),before); broker['conclusion']='success'
            f.remote.artifacts[:]=artifacts; f.remote.raw.clear(); f.remote.raw.update(raw)
            source_pages=f.source.pages
            for part in ('check-runs','rules/branches','reviews'):
                def missing(path,*pos): return [] if part in path else source_pages(path,*pos)
                with self.subTest(current=part), patch.object(f.source,'pages',side_effect=missing), self.assertRaises(Refusal):
                    self.observe(f,location)
                self.assertEqual(self.journal(f).read(),before)
            target=f.source.refs['main']; f.source.refs['main']='0'*40
            with self.assertRaises(Refusal): self.observe(f,location)
            with patch.object(f.source,'pages',side_effect=AssertionError('historical source freshness')):
                self.assertEqual(trial_case.baseline(f.origin,f.native.registry,f.admission.record,self.history(f,location),lambda:f.clock[0]),terminal['after'])
            f.source.refs['main']=target
            f.clock[0]=before['value']['certificate']['expires']
            with self.assertRaises(Refusal):
                trial_case.baseline(f.origin,f.native.registry,f.admission.record,self.history(f,location),lambda:f.clock[0])
        self.exercise(continuation=check)

    def test_raw_native_ack_loss_blocks_fifth_and_cleanup_survives_expiry(self):
        def check(*args):
            f,location=self.closed(args); journal=self.journal(f); write=type(journal.raw).write
            def uncertain(instance,*pos,**kw):
                result=write(instance,*pos,**kw)
                if instance.root==journal.raw.root: raise OSError('fourth root ACK lost')
                return result
            with patch.object(type(journal.raw),'write',new=uncertain), self.assertRaisesRegex(OSError,'ACK lost'):
                self.observe(f,location)
            f.native.provision._controller_acknowledgements.clear()
            with self.assertRaises(Refusal): self.observe(f,location)
            with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open('prompt','authority-outage',f.source)
            f.clock[0]=f.admission.record['expires']+1
            trial_launch.revoke(f.native.provision,f.origin_factory,name='expired-proof')
            self.assertIn(f.case_token,f.revoked)
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
            with self.assertRaises(Refusal): instances[-1]._expired_evidence(request['operation_id'],request['sequence'],f.native.registry.binding())
        self.exercise(continuation=check)

    def test_export_exact_acknowledged_and_not_stale(self):
        def check(*args):
            f=self.pending(args); instances=[]; finalize=broker_finalize.Finalizer._finalize
            def track(instance,*pos,**kw): instances.append(instance); return finalize(instance,*pos,**kw)
            with patch.object(broker_finalize.Finalizer,'_finalize',new=track): result=f.finalize()
            instance=instances[-1]; request=f.admission.request
            evidence=instance._expired_evidence(request['operation_id'],request['sequence'],result)
            evidence['broker_receipt']['issued']=1
            self.assertNotEqual(instance._expired_evidence(request['operation_id'],request['sequence'],result),evidence)
            for op,seq,value in (('0'*32,request['sequence'],result),(request['operation_id'],request['sequence']+1,result),
                                 (request['operation_id'],request['sequence'],{})):
                with self.assertRaises(Refusal): instance._expired_evidence(op,seq,value)
            with self.assertRaises(Refusal): instance._finalize('invalid',1,1)
            with self.assertRaises(Refusal): instance._expired_evidence(request['operation_id'],request['sequence'],result)
        self.exercise(continuation=check)


if __name__ == '__main__': unittest.main()
