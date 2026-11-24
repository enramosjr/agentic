"""Sixth CLOSED evidence; GitHub and OCI transport boundaries are modeled."""
import backend_test_support
import copy
import unittest
from unittest.mock import patch

import authority_release
import broker_finalize
import merge_transport
import service
import trial_case
import trial_controller
import trial_host_case
import trial_launch
import test_authority_trial_host_case as host_fixture
import test_authority_trial_negative_case as negative_fixture
import test_authority_trial_outage_terminal as outage_fixture
from trusted_ci_policy import Refusal, digest


class Sixth(negative_fixture.Negative):
    # The authentic fifth fixture installs its own outage transport/producer hook.
    upload = host_fixture.Sequential.upload

    def through_fifth(self):
        # OutageTerminal.pending has already executed the authentic first five.
        value = self.native.provision.store(self.native.provision.root/'trial-controller-authority-outage').read()['value']
        self.owner.assertEqual(value['phase'], 'terminal')
        self.owner.assertEqual(len(value['history']), 4)


class Holds(unittest.TestCase):
    def test_observation_hold_precedes_transport(self):
        class NoIO:
            def __getattr__(self, name): raise AssertionError(name)
        with self.assertRaises(authority_release.Held):
            trial_controller.Native(NoIO()).observe_terminal('prompt', 'bad-acceptance', {})


@unittest.skipIf(getattr(outage_fixture.OutageTerminal, '__unittest_skip__', False), 'optional cryptography required')
class BadAcceptanceTerminal(unittest.TestCase):
    fixture = outage_fixture.OutageTerminal.fixture
    prepared = outage_fixture.OutageTerminal.prepared
    connected = outage_fixture.OutageTerminal.connected
    configured = outage_fixture.OutageTerminal.configured
    exercise = outage_fixture.OutageTerminal.exercise
    prepare = outage_fixture.OutageTerminal.prepare
    forbidden = outage_fixture.OutageTerminal.forbidden
    collector = outage_fixture.OutageTerminal.collector
    document = outage_fixture.OutageTerminal.document
    closed = outage_fixture.OutageTerminal.closed
    fourth = outage_fixture.OutageTerminal.fourth
    fifth = outage_fixture.OutageTerminal.fifth

    def pending(self, args, mutated=True):
        with patch.object(host_fixture, 'Sequential', Sixth):
            f = outage_fixture.OutageTerminal.pending(self, args)
        f.finalize(); f.observe()
        trial_launch.revoke(f.native.provision, f.origin_factory, name='authority-outage')
        opening = trial_controller.Native._open
        def approved(native, prompt, name, *pos, **kw):
            if name == 'bad-acceptance':
                if mutated: kw['negative_approve'] = digest
                else: kw.pop('negative_approve',None)
            return opening(native, prompt, name, *pos, **kw)
        with patch.object(trial_controller.Native, '_open', approved): f.sixth()
        with patch.object(merge_transport, 'isolated', side_effect=AssertionError('negative dispatched')):
            f.rejected(); f.host()
            self.assertEqual(f.run('broker')['state'], 'host-denied')
        return f

    def journal(self, f):
        return f.native.provision.store(f.native.provision.root/'trial-controller-bad-acceptance')

    def case(self, f):
        publication = f.native.provision.store(f.native.provision.root/'trial-case-publication-bad-acceptance').read()['value']
        case, record = trial_case.read(f.origin, publication['revision_bound'], lambda:f.clock[0])
        self.assertEqual(record, f.admission.record)
        return case

    def history(self, f, location):
        value = self.journal(f).read()['value']
        publication = f.native.provision.store(f.native.provision.root/'trial-case-publication-bad-acceptance').read()['value']
        return value['history']+[dict(revision=publication['revision_bound'], terminal=location)]

    def observe(self, f, location):
        with self.forbidden(f), patch.object(service, '_source_token', side_effect=AssertionError('terminal mint')):
            return trial_controller.Native(f.preparer)._observe_terminal('prompt', 'bad-acceptance', location, f.source)

    def validate(self, f, location):
        from provenance import authenticated_document
        _, _, terminal = self.document(f, 'trial-case-terminal-')
        proof = authenticated_document(f.api, terminal['before']['deployment'], location, 'trial-case-terminal',
                                       f.admission.record['task_id'], f.clock[0])
        return trial_host_case.bad_acceptance_terminal(f.api, f.admission.record, self.case(f), terminal, proof,
                                                       f.clock[0], original=f.origin)

    def test_connected_sixth_cleanup_and_seventh_selection(self):
        def check(*args):
            f, location = self.closed(args); original = f.origin.binding()
            _, _, terminal = self.document(f, 'trial-case-terminal-')
            self.assertEqual(terminal['schema_version'], 2)
            self.assertNotIn('broker_receipt', terminal)
            self.assertEqual(digest(terminal['recovery']), terminal['after']['fence']['completed'][-1]['receipt_digest'])
            outcome = self.validate(f, location)['document']['record']
            self.assertTrue(outcome['request_sent']); self.assertIsNone(outcome['broker_refusal'])
            self.assertEqual((outcome['denial_category'], outcome['denied_obligation']), ('required_check', f.p['check_name']))
            self.observe(f, location)
            token = f.case_token
            trial_launch.revoke(f.native.provision, f.origin_factory, name='bad-acceptance')
            self.assertIn(token, f.revoked)
            f.second('replaced-checks', 113, 'fresh-seventh-case')
            history = f.admission.value['history']
            self.assertEqual(len(history), 6)
            cases = [trial_case.read(f.origin, e['revision'], lambda:f.clock[0])[0] for e in history]
            self.assertEqual([c['candidate']['name'] for c in cases], list(trial_controller.CASE_CHAIN[:6]))
            for field in ('pr', 'head', 'task_id'):
                self.assertEqual(len({c['candidate']['submitted'][field] for c in cases}), 6)
            self.assertEqual(f.origin.binding(), original)
            self.assertEqual(f.source.refs['main'], terminal['before']['fence']['pending']['base'])
            self.assertEqual(len(f.attempts), 4); self.assertEqual(f.merges, [])
            self.assertIsNone(f.admission.binding['deployment']['qualification'])
            self.assertEqual(f.admission.binding['deployment']['state'], 'qualification')
            self.assertFalse(f.remote.artifacts)
        self.exercise(continuation=check)

    def test_export_is_exact_acknowledged_and_not_stale(self):
        def check(*args):
            f = self.pending(args); instances = []; finalize = broker_finalize.Finalizer._finalize
            def track(instance, *pos, **kw): instances.append(instance); return finalize(instance, *pos, **kw)
            with patch.object(broker_finalize.Finalizer, '_finalize', track): result = f.finalize()
            instance = instances[-1]; r = f.admission.request
            value = instance._negative_evidence(r['operation_id'], r['sequence'], result)
            value['host_receipt']['issued'] = 1
            self.assertNotEqual(instance._negative_evidence(r['operation_id'], r['sequence'], result), value)
            for op, seq, saved in (('0'*32,r['sequence'],result), (r['operation_id'],r['sequence']+1,result),
                                   (r['operation_id'],r['sequence'],{})):
                with self.assertRaises(Refusal): instance._negative_evidence(op,seq,saved)
            with self.assertRaises(Refusal): instance._finalize('invalid',1,1)
            with self.assertRaises(Refusal): instance._negative_evidence(r['operation_id'],r['sequence'],result)
        self.exercise(continuation=check)

    def test_legacy_terminal_refused_by_both_consumers(self):
        def check(*args):
            f, location = self.closed(args); before = self.journal(f).read()
            identity, member, value = self.document(f, 'trial-case-terminal-')
            value.update(schema_version=1); value.pop('recovery',None); value.pop('host_receipt',None)
            f.remote.replace(identity,value,member)
            with self.assertRaises(Refusal): self.observe(f,location)
            with self.assertRaises(Refusal):
                trial_case.baseline(f.origin,f.native.registry,f.admission.record,self.history(f,location),lambda:f.clock[0])
            self.assertEqual(self.journal(f).read(),before)
        self.exercise(continuation=check)

    def test_original_export_remains_legacy_and_cannot_progress(self):
        def check(*args):
            f=self.pending(args,mutated=False); f.finalize()
            job=next(j for j in f.remote.jobs if j['name']=='finalize')
            from test_authority_broker_evidence import stamp
            job.update(status='completed',conclusion='success',completed_at=stamp(f.clock[0]))
            identity,_,value=self.document(f,'trial-case-terminal-')
            self.assertEqual(value['schema_version'],1); self.assertNotIn('recovery',value)
            location=dict(run_id=111,attempt=1,job_id=job['id'],artifact_id=identity)
            with self.assertRaises(Refusal): self.observe(f,location)
            with self.assertRaises(Refusal):
                trial_case.baseline(f.origin,f.native.registry,f.admission.record,self.history(f,location),lambda:f.clock[0])
            with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open('prompt','replaced-checks',f.source)
        self.exercise(continuation=check)

    def test_terminal_and_inventory_mutations_fail_closed(self):
        def check(*args):
            from test_authority_broker_evidence import stamp
            f,location=self.closed(args); self.validate(f,location); before=self.journal(f).read()
            identity,member,terminal=self.document(f,'trial-case-terminal-')
            artifacts,raw=copy.deepcopy(f.remote.artifacts),copy.deepcopy(f.remote.raw)
            pages=f.api.pages
            for fault in ('schema','extra','request','certificate','envelope','receipt','producer','recovery','interval',
                          'gate','control-ready','not-submitted','dispatch','outcome','missing-host','receipt-late','duplicate','oversized'):
                f.remote.artifacts[:]=copy.deepcopy(artifacts); f.remote.raw.clear(); f.remote.raw.update(raw)
                value=copy.deepcopy(terminal)
                if fault=='schema': value['schema_version']=True
                if fault=='extra': value['broker_receipt']={}
                if fault=='request': value['request_digest']='0'*64
                if fault=='certificate': value['certificate_digest']='0'*64
                if fault=='envelope': value['recovery']['operation_digest']='0'*64
                if fault=='receipt': value['host_receipt']['issued']+=1
                if fault=='producer': value['recovery']['producer']['id']+=1
                if fault=='recovery': value['recovery']['recovery']['job_id']+=1
                if fault=='interval': value['completed']=1
                if fault in ('gate','control-ready','not-submitted','dispatch','outcome'):
                    a=next(a for a in f.remote.artifacts if a['name'].endswith('-host-denied'))
                    f.remote.artifacts.append(dict(a,id=999999,name=a['name'].replace('-host-denied','-'+fault)))
                if fault=='missing-host': f.remote.artifacts[:]=[a for a in f.remote.artifacts if not a['name'].startswith('trial-host-denial-')]
                if fault=='receipt-late':
                    next(a for a in f.remote.artifacts if a['name'].endswith('-host-denied'))['created_at']=stamp(f.clock[0]+1)
                f.remote.replace(identity,value,member)
                def inventory(path,collection=None):
                    entries=pages(path,collection)
                    if collection=='artifacts' and '/runs/111/' in path:
                        if fault=='duplicate': return entries+[dict(entries[0])]
                        if fault=='oversized': return [dict(entries[0],id=i+1) for i in range(10001)]
                    return entries
                with self.subTest(fault=fault),patch.object(f.api,'pages',side_effect=inventory),self.assertRaises(Refusal): self.validate(f,location)
                with self.subTest(native=fault),patch.object(f.api,'pages',side_effect=inventory),self.assertRaises(Refusal): self.observe(f,location)
                self.assertEqual(self.journal(f).read(),before)
            f.remote.artifacts[:]=artifacts; f.remote.raw.clear(); f.remote.raw.update(raw)
        self.exercise(continuation=check)

    def test_host_verifier_and_publication_mutations_fail_closed(self):
        def check(*args):
            f,location=self.closed(args); self.validate(f,location); before=self.journal(f).read()
            for prefix,faults in (
                    ('trial-host-denial-',('actor','request','status','boolean-status','category','obligation','parents','tree','record','intent','negative','mutation','publication','rules','reviews','success')),
                    ('evidence-',('success','criterion','generation','cleanup','execution')),
                    ('trial-publication-denial-',('refusal','intent','task','controls','proofs','observed')),
                    ('publication-controls-',('binding',)),
                    ('proof-merge-',('expired','binding'))):
                identity,member,saved=self.document(f,prefix)
                metadata=copy.deepcopy(next(a for a in f.remote.artifacts if a['id']==identity)); raw=f.remote.raw[identity]
                for fault in faults:
                    value=copy.deepcopy(saved)
                    if prefix=='trial-host-denial-':
                        o=value['observation']
                        if fault=='actor': o['actor_id']+=1
                        if fault=='request': o['request']['data']['sha']='0'*40
                        if fault=='status': o['http_status']=500
                        if fault=='boolean-status': o['http_status']=True
                        if fault=='category': o['denial_category']='required_review'
                        if fault=='obligation': o['denied_obligation']='other-check'
                        if fault=='parents': o['synthetic_commit']['parents'].reverse()
                        if fault=='tree': o['synthetic_commit']['tree']['sha']='0'*40
                        if fault=='record': value['record']['request_sent']=False
                        if fault=='intent': value['intent']['issued']+=1000
                        if fault=='negative': o['negative']['job_id']+=1
                        if fault=='mutation': o['mutations'][0]['sha256']='0'*64
                        if fault=='publication': o['publication']['digest']='0'*64
                        if fault=='rules': o['rules']=[]
                        if fault=='reviews': o['reviews']=[]
                        if fault=='success': o['checks'].append(dict(name=f.p['check_name'],app=dict(id=f.p['app_id']),status='completed',conclusion='success'))
                    elif prefix=='evidence-':
                        result=value['result']; report=result['report']
                        if fault=='success': report['outcomes'][0]['status']='success'
                        if fault=='criterion': report['outcomes'][0]['id']='other'
                        if fault=='generation': report['generation']=True
                        if fault=='cleanup': result['cleanup_complete']=False
                        if fault=='execution': report['execution']['run_id']=109
                    elif prefix=='trial-publication-denial-':
                        if fault=='refusal': value['refusal']='other failure'
                        if fault=='intent': value['intent']['issued']+=1000
                        if fault=='task': value['intent']['inputs']['task_digest']='0'*64
                        if fault=='controls': value['intent']['inputs']['controls_digest']='0'*64
                        if fault=='proofs': value['intent']['inputs']['proofs']['merge']['artifact_id']+=1
                        if fault=='observed': value['observed']=1
                    elif prefix=='proof-merge-':
                        if fault=='expired': value['expires']=value['completed']
                        if fault=='binding': value['sequence']+=1
                    elif fault=='binding': value['configuration_revision']='0'*40
                    f.remote.replace(identity,value,member)
                    with self.subTest(prefix=prefix,fault=fault),self.assertRaises(Refusal): self.validate(f,location)
                    with self.subTest(native=prefix,fault=fault),self.assertRaises(Refusal): self.observe(f,location)
                    self.assertEqual(self.journal(f).read(),before)
                    f.remote.raw[identity]=raw
                    next(a for a in f.remote.artifacts if a['id']==identity).update(metadata)
        self.exercise(continuation=check)

    test_original_worker_receipt_semantics_fail_closed = outage_fixture.OutageTerminal.test_original_worker_receipt_semantics_fail_closed

    def test_mutation_export_and_native_refs_fail_closed(self):
        def check(*args):
            import trial_mutation
            from registry import trial_reference
            f,location=self.closed(args); self.validate(f,location); before=self.journal(f).read()
            case=self.case(f); candidate=case['candidate']; event=f.clock[0]
            for fault in ('approval','before','after','mode','reservation','history','link'):
                value=copy.deepcopy(candidate); claim=value['transition']['intent']
                if fault=='approval': claim['approval']='0'*64
                if fault=='before': claim['preview']['before'].clear()
                if fault=='after': claim['preview']['after'].clear()
                if fault=='mode': claim['preview']['after']['.ai/scripts/lifecycle.py']['mode']='100755'
                if fault=='reservation': claim['reservation']['submitted']['head']='0'*40
                if fault=='history': claim['preview']['history']=[]
                if fault=='link': value['transition']['links'][trial_mutation.RESULT]['revision']=value['transition']['links'][trial_mutation.INTENT]['revision']
                with self.subTest(fault=fault),self.assertRaises(Refusal):
                    trial_mutation._documents(value,f.admission.record,case['worker'],case['history'],f.origin,event)
            ref=f.origin.ref
            for role in (trial_mutation.INTENT,trial_mutation.RESULT):
                key=trial_reference(dict(kind=role,name='bad-acceptance',task_id=f.admission.record['task_id'],execution=None))
                def moved(name): return '0'*40 if name==key else ref(name)
                with patch.object(f.origin,'ref',side_effect=moved),self.subTest(role=role),self.assertRaises(Refusal): self.validate(f,location)
                with patch.object(f.origin,'ref',side_effect=moved),self.subTest(native=role),self.assertRaises(Refusal): self.observe(f,location)
            reservation=candidate['transition']['intent']['reservation']['submitted']
            commit=f.source.commits[reservation['head']]; message=commit['message']; commit['message']+='changed'
            with self.assertRaises(Refusal): self.observe(f,location)
            commit['message']=message
            tree=f.source.trees[candidate['submitted']['tree']]; path='.ai/scripts/lifecycle.py'; item=tree[path]
            tree[path]=('100755',item[1])
            with self.assertRaises(Refusal): self.observe(f,location)
            tree[path]=item
            self.assertEqual(self.journal(f).read(),before)
        self.exercise(continuation=check)

    def test_late_evidence_removal_and_broker_conflicts_fail_closed(self):
        def check(*args):
            import broker_evidence
            f,location=self.closed(args); self.validate(f,location); before=self.journal(f).read()
            artifacts=copy.deepcopy(f.remote.artifacts); readback=broker_evidence._artifact_readback
            for fault in ('host-intent','publication','dispatch'):
                for consume in (self.validate,self.observe):
                    f.remote.artifacts[:]=copy.deepcopy(artifacts); changed=[]
                    def race(authority,d,references):
                        if not changed and any(r['role']=='trial-case-terminal' for r in references):
                            changed.append(fault)
                            if fault=='dispatch':
                                a=next(a for a in f.remote.artifacts if a['name'].endswith('-host-denied'))
                                f.remote.artifacts.append(dict(a,id=999999,name=a['name'].replace('-host-denied','-dispatch')))
                            else:
                                prefix='trial-host-intent-' if fault=='host-intent' else 'trial-publication-denial-'
                                f.remote.artifacts[:]=[a for a in f.remote.artifacts if not a['name'].startswith(prefix)]
                        return readback(authority,d,references)
                    with patch.object(broker_evidence,'_artifact_readback',side_effect=race),self.assertRaises(Refusal): consume(f,location)
                    self.assertEqual(changed,[fault]); self.assertEqual(self.journal(f).read(),before)
            f.remote.artifacts[:]=artifacts
        self.exercise(continuation=check)

    def test_history_expiry_and_current_native_prerequisites_are_separate(self):
        def check(*args):
            f,location=self.closed(args); case=self.case(f); before=self.journal(f).read()
            from provenance import authenticated_document
            _,_,terminal=self.document(f,'trial-case-terminal-')
            proof=authenticated_document(f.api,terminal['before']['deployment'],location,'trial-case-terminal',f.admission.record['task_id'],f.clock[0])
            for field in ('launch','execution'):
                value=copy.deepcopy(case); value[field]['credential']['expires']=terminal['completed']-1
                with self.subTest(field=field),self.assertRaises(Refusal):
                    trial_host_case.bad_acceptance_terminal(f.api,f.admission.record,value,terminal,proof,f.clock[0],original=f.origin)
            pages=f.source.pages
            for part in ('rules/branches','reviews'):
                def missing(path,*pos): return [] if part in path else pages(path,*pos)
                with patch.object(f.source,'pages',side_effect=missing),self.subTest(current=part),self.assertRaises(Refusal): self.observe(f,location)
                self.assertEqual(self.journal(f).read(),before)
            f.clock[0]=max(case[k]['credential']['expires'] for k in ('launch','execution'))+1
            self.assertLess(f.clock[0],case['certificate']['expires'])
            with self.assertRaises(Refusal): self.observe(f,location)
            with patch.object(f.source,'pages',side_effect=AssertionError('historical freshness')),patch.object(service,'_source_token',side_effect=AssertionError('historical mint')):
                self.validate(f,location)
                self.assertEqual(trial_case.baseline(f.origin,f.native.registry,f.admission.record,self.history(f,location),lambda:f.clock[0]),terminal['after'])
            f.clock[0]=case['certificate']['expires']
            with self.assertRaises(Refusal): self.validate(f,location)
        self.exercise(continuation=check)

    def test_historical_source_reads_cannot_hide_late_conflicts(self):
        def check(*args):
            f,location=self.closed(args); history=self.history(f,location)
            artifacts=copy.deepcopy(f.remote.artifacts); read=trial_host_case._bad_source
            for fault in ('host-intent','dispatch'):
                f.remote.artifacts[:]=copy.deepcopy(artifacts); changed=[]
                def race(*pos,**kw):
                    result=read(*pos,**kw); changed.append(fault)
                    if fault=='host-intent':
                        f.remote.artifacts[:]=[a for a in f.remote.artifacts if not a['name'].startswith('trial-host-intent-')]
                    else:
                        a=next(a for a in f.remote.artifacts if a['name'].endswith('-host-denied'))
                        f.remote.artifacts.append(dict(a,id=999999,name=a['name'].replace('-host-denied','-dispatch')))
                    return result
                with patch.object(trial_host_case,'_bad_source',side_effect=race),self.assertRaises(Refusal):
                    trial_case.history_guard(f.origin,f.admission.record,history,lambda:f.clock[0],f.api,f.source)
                self.assertEqual(changed,[fault])
            f.remote.artifacts[:]=artifacts
        self.exercise(continuation=check)

    def test_finalizer_ack_loss_cannot_export_or_publish(self):
        def check(*args):
            import registry
            f=self.pending(args); instances=[]; finalize=broker_finalize.Finalizer._finalize; write=registry.Registry.finalize_operation
            def track(instance,*pos,**kw): instances.append(instance); return finalize(instance,*pos,**kw)
            def uncertain(instance,*pos,**kw): write(instance,*pos,**kw); raise OSError('finalizer ACK lost')
            with patch.object(broker_finalize.Finalizer,'_finalize',track),patch.object(registry.Registry,'finalize_operation',uncertain):
                with self.assertRaisesRegex(OSError,'ACK lost'): f.finalize()
            self.assertFalse(any(a['name'].startswith('trial-case-terminal-') for a in f.remote.artifacts))
            r=f.admission.request
            with self.assertRaises(Refusal): instances[-1]._negative_evidence(r['operation_id'],r['sequence'],f.native.registry.binding())
        self.exercise(continuation=check)

    def test_native_ack_loss_blocks_seventh_and_cleanup_survives_expiry(self):
        def check(*args):
            f,location=self.closed(args); journal=self.journal(f); write=type(journal.raw).write
            def uncertain(instance,*pos,**kw):
                result=write(instance,*pos,**kw)
                if instance.root==journal.raw.root: raise OSError('sixth root ACK lost')
                return result
            with patch.object(type(journal.raw),'write',uncertain),self.assertRaisesRegex(OSError,'ACK lost'): self.observe(f,location)
            f.native.provision._controller_acknowledgements.clear()
            with self.assertRaises(Refusal): self.observe(f,location)
            with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open('prompt','replaced-checks',f.source)
            f.clock[0]=f.admission.record['expires']+1
            trial_launch.revoke(f.native.provision,f.origin_factory,name='bad-acceptance')
            self.assertIn(f.case_token,f.revoked)
        self.exercise(continuation=check)


if __name__ == '__main__': unittest.main()
