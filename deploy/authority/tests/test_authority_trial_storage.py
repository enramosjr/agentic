"""Private snapshot identity, freshness and bounded predecessor traversal."""
import backend_test_support
import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace
from contextlib import contextmanager
import unittest
import tempfile
import subprocess
import sys

from authority_private import MAX_STATE
from trusted_ci_policy import Refusal,digest
import trial_storage


@contextmanager
def bounded_native_writes(owner):
    """Model the exact physical wire cap; filesystem acceptance is separate."""
    from unittest.mock import patch
    from test_authority_trial_setup import Journal as NativeJournal
    write=NativeJournal.write; sizes={}
    def checked(journal,expected,value):
        name=str(getattr(journal,'root','unlabeled'))
        envelope=dict(schema_version=1,generation=1 if expected is None else expected['generation']+1,value=value)
        size=len((json.dumps(envelope,sort_keys=True,allow_nan=False)+'\n').encode())
        owner.assertLessEqual(size,MAX_STATE,name+' complete protected envelope exceeds limit')
        sizes[name]=max(sizes.get(name,0),size)
        return write(journal,expected,value)
    with patch.object(NativeJournal,'write',checked): yield sizes


class Journal:
    def __init__(self): self.raw=None
    def read(self): return None if self.raw is None else json.loads(self.raw)
    def write(self,expected,value):
        if self.read()!=expected: raise Refusal('CAS changed')
        document=dict(schema_version=1,generation=1 if expected is None else expected['generation']+1,value=value)
        raw=(json.dumps(document,sort_keys=True,allow_nan=False)+'\n').encode()
        if len(raw)>MAX_STATE: raise Refusal('state exceeds limit')
        self.raw=raw
        return self.read()


class ComponentContracts(unittest.TestCase):
    def fixture(self): return SnapshotContracts.fixture(self)

    def large(self):
        candidate=dict(name='bad-acceptance',transition=dict(intent=dict(manifests='x'*85865)))
        return dict(storage_version=2,kind='native-trial-controller',name='bad-acceptance',phase='ready',
            candidate=candidate,certificate=None,terminal=None,history=[],
            transition_ownership=dict(mutation=dict(generation=1,value=dict(claim=candidate['transition']['intent']))))

    def test_mutation_and_certificate_fields_fit_without_changing_logical_bytes(self):
        c,journals=self.fixture(); value=self.large(); key='trial-controller-bad-acceptance'
        with self.assertRaisesRegex(Refusal,'exceeds limit'): c.store(c.root/key).write(None,value)
        trial_storage.install(c)
        journal=c.store(c.root/key)
        first=trial_storage.write_controller(c,key,journal,None,value)
        first_physical=journal.physical(first)
        self.assertEqual(first['value'],value)
        self.assertEqual(journal.read(),first)
        value=dict(value,certificate=dict(candidate=value['candidate'],request_digest='d'*64),phase='bound')
        second=trial_storage.write_controller(c,key,journal,first,value)
        self.assertEqual(second['value'],value)
        self.assertEqual(json.dumps(journal.read()['value'],sort_keys=True),json.dumps(value,sort_keys=True))
        self.assertTrue(all(len(j.path.read_bytes() if hasattr(j,'path') else j.raw)<=MAX_STATE for j in journals.values()))
        physical=journal.physical(second)
        self.assertEqual(physical['value']['candidate'],first_physical['value']['candidate'])
        self.assertEqual(c._controller_acknowledgements[key][-1],digest(physical))

    def test_component_reference_fields_are_bound_to_the_selected_physical_root(self):
        for field,replacement in (('namespace_digest','0'*64),('journal','trial-controller'),('field','terminal'),
                ('created_generation',99),('value_digest','0'*64),('component_digest','0'*64),('version',True)):
            c,_=self.fixture(); trial_storage.install(c); key='trial-controller-bad-acceptance'; journal=c.store(c.root/key)
            document=trial_storage.write_controller(c,key,journal,None,self.large())
            physical=journal.physical(document); modified=copy.deepcopy(physical['value'])
            modified['candidate'][field]=replacement
            journal.raw.write(physical,modified)
            with self.subTest(field=field),self.assertRaises(Refusal): journal.read()

    def test_expected_cas_and_ack_bind_physical_refs_and_unknown_root_stays_held(self):
        from unittest.mock import patch
        c,_=self.fixture(); factory=c.store; trial_storage.install(c); key='trial-controller-bad-acceptance'; journal=c.store(c.root/key)
        first=trial_storage.write_controller(c,key,journal,None,self.large()); physical=journal.physical(first)
        with patch.object(journal.raw,'write',wraps=journal.raw.write) as cas:
            second=trial_storage.write_controller(c,key,journal,first,dict(first['value'],phase='bound'))
        self.assertEqual(cas.call_count,1)
        self.assertEqual(cas.call_args.args[0],physical)
        self.assertEqual(cas.call_args.args[1]['candidate'],physical['value']['candidate'])
        write=journal.raw.write
        def unknown(expected,value):
            write(expected,value)
            raise OSError('root persisted but acknowledgement unavailable')
        with patch.object(journal.raw,'write',side_effect=unknown),self.assertRaises(OSError):
            trial_storage.write_controller(c,key,journal,second,dict(second['value'],phase='closing'))
        visible=journal.read()
        with self.assertRaises(Refusal): trial_storage.acknowledged(c,key,journal,visible)
        fresh=SimpleNamespace(root=c.root,store=factory,session=c.session,document=c.document)
        trial_storage.install(fresh); restarted=fresh.store(fresh.root/key)
        with self.assertRaises(Refusal): trial_storage.acknowledged(fresh,key,restarted,restarted.read())

    def test_component_substitution_and_orphan_ack_refuse(self):
        c,journals=self.fixture(); trial_storage.install(c); key='trial-controller-bad-acceptance'; journal=c.store(c.root/key)
        document=trial_storage.write_controller(c,key,journal,None,self.large())
        physical=journal.physical(document)
        reference=physical['value']['candidate']
        component=c.store(c.root/('trial-component-'+reference['component_digest']))
        retained=component.read(); component.write(retained,retained['value'])
        with self.assertRaises(Refusal): journal.read()

    def test_publication_reuses_controller_refs_with_exact_public_bytes_across_phases(self):
        c,journals=self.fixture(); trial_storage.install(c); key='trial-controller-bad-acceptance'; controller=c.store(c.root/key)
        value=self.large(); value.update(certificate=dict(candidate=value['candidate']),phase='bound')
        root=trial_storage.write_controller(c,key,controller,None,value)
        initial=dict(kind='trial-case-handoff',schema_version=1,candidate=value['candidate'],certificate=value['certificate'],request={})
        state=dict(phase='publication-started',initial=initial,execution=None,revision=None,revision_bound=None)
        public_before=json.dumps(initial,sort_keys=True,allow_nan=False).encode()
        before_components={name for name in journals if 'trial-component-' in name}
        publication=c.store(c.root/'trial-case-publication-bad-acceptance')
        document=publication.write(None,state)
        self.assertEqual(json.dumps(publication.read()['value']['initial'],sort_keys=True,allow_nan=False).encode(),public_before)
        self.assertEqual({name for name in journals if 'trial-component-' in name},before_components)
        physical=controller.physical(root)
        self.assertEqual(publication.raw.read()['value']['initial']['candidate'],physical['value']['candidate'])
        trial_storage.write_controller(c,key,controller,root,dict(value,phase='terminal',terminal=dict(binding={})))
        self.assertEqual(publication.read(),document)

    def test_publication_refuses_substitution_and_rechecks_both_roots(self):
        from unittest.mock import patch
        for fault in ('logical-field','source-root','publication-root'):
            c,_=self.fixture(); trial_storage.install(c); key='trial-controller-bad-acceptance'; controller=c.store(c.root/key)
            value=self.large(); value.update(certificate=dict(candidate=value['candidate']),phase='bound')
            root=trial_storage.write_controller(c,key,controller,None,value)
            state=dict(phase='published',initial=dict(kind='trial-case-handoff',candidate=value['candidate'],certificate=value['certificate']))
            publication=c.store(c.root/'trial-case-publication-bad-acceptance')
            if fault=='logical-field':
                state['initial']['candidate']=dict(name='substituted')
                with self.assertRaises(Refusal): publication.write(None,state)
                self.assertIsNone(publication.raw.read())
                continue
            document=publication.write(None,state); physical=controller.physical(root)
            component=c.store(c.root/('trial-component-'+physical['value']['candidate']['component_digest']))
            component=getattr(component,'raw',component)
            read=component.read; changed=[]
            def during_read():
                result=read()
                if not changed:
                    target=controller.raw if fault=='source-root' else publication.raw
                    retained=target.read(); target.write(retained,dict(retained['value'],phase='changed'))
                    changed.append(True)
                return result
            with patch.object(component,'read',side_effect=during_read),self.assertRaises(Refusal): publication.read()
            self.assertTrue(changed)

    def completed_context(self):
        c,_=self.fixture(); factory=c.store; trial_storage.install(c)
        key='trial-controller-new-base-prior'
        source=dict(storage_version=2,kind='native-trial-controller',name='new-base',phase='terminal',
            candidate=dict(name='new-base',transition=dict(intent=dict(phase='prior'))),certificate=None,terminal=dict(binding={}),
            record=dict(task_id='a'*32,data='r'*9000),workflow=dict(data='w'*1000),candidates=dict(data='c'*20000),provisioning=dict(data='p'*8000))
        controller=c.store(c.root/key); terminal=trial_storage.write_controller(c,key,controller,None,source)
        value=dict(name='new-base',phase='complete',mutable='m'*100000,before={},steps=[dict(before={},documents={},after={})],
            source={},intent=dict(kind='native-trial-context-intent',revision='c'*40),terminal=dict(result=dict(restored=True)),
            completion=dict(kind='native-trial-context-complete',revision='d'*40),
            **{field:copy.deepcopy(source[field]) for field in ('record','workflow','candidates','provisioning')})
        from trial_transition import _context_completion
        _context_completion(value,1234)
        journal=c.store(c.root/'trial-context-new-base'); document=journal.write(None,value)
        return c,factory,controller,journal,document,value

    def test_context_echo_and_owned_physical_copy_fit_without_active_ack_for_cleanup(self):
        c,factory,controller,journal,document,value=self.completed_context()
        self.assertEqual(document['value'],value)
        self.assertLessEqual(len(journal.raw.path.read_bytes() if hasattr(journal.raw,'path') else journal.raw.raw),MAX_STATE)
        other=dict(generation=1,value=dict(retained='o'*60000))
        before={'trial-context-new-base':journal.raw.read(),'trial-transition-new-base-current':other}
        self.assertGreater(len(json.dumps(before).encode()),MAX_STATE)
        owned=trial_storage.ownership(c,{'trial-context-new-base':document,'trial-transition-new-base-current':other},create=True)
        reference=owned['trial-context-new-base']
        self.assertEqual((reference['journal_kind'],reference['case_phase']),('trial-context','complete'))
        self.assertEqual(trial_storage.resolve(c,reference),document)
        self.assertEqual(trial_storage.ownership(c,{'trial-context-new-base':document,'trial-transition-new-base-current':other}),owned)
        archived=c.store(c.root/('trial-snapshot-'+reference['snapshot_digest'])).read()
        self.assertEqual(archived['generation'],1)
        self.assertEqual(archived['value']['document'],journal.raw.read())
        with self.assertRaises(Refusal):
            list(trial_storage.predecessors(c,dict(storage_version=2,history=[{}]*11,previous=reference)))
        self.assertLess(len(json.dumps(owned).encode()),MAX_STATE)
        fresh=SimpleNamespace(root=c.root,store=factory,session=c.session,document=c.document)
        trial_storage.install(fresh); cleanup=fresh.store(fresh.root/'trial-context-new-base')
        retained=cleanup.read(); updated=cleanup.write(retained,dict(retained['value'],cleanup=True))
        self.assertTrue(updated['value']['cleanup'])
        with self.assertRaises(Refusal): trial_storage.resolve(c,reference)

    def test_context_snapshot_substitution_unknown_ack_and_midread_change_refuse(self):
        from unittest.mock import patch
        c,_,controller,journal,document,_=self.completed_context()
        key='trial-context-new-base'; reference=trial_storage.pin(c,key,document)
        for field,replacement in (('case_phase','current'),('case_name','positive'),('journal_kind','trial-controller'),
                ('namespace_digest','0'*64),('source_generation',document['generation']+1)):
            changed=dict(reference,**{field:replacement})
            with self.subTest(field=field),self.assertRaises(Refusal): trial_storage.resolve(c,changed)
        physical=controller.raw.read()
        component=c.store(c.root/('trial-component-'+physical['value']['candidate']['component_digest']))
        component=getattr(component,'raw',component)
        read=component.read; changed=[]
        def during_read():
            retained=read()
            if not changed:
                current=journal.raw.read(); journal.raw.write(current,dict(current['value'],changed=True)); changed.append(True)
            return retained
        with patch.object(component,'read',side_effect=during_read),self.assertRaises(Refusal): trial_storage.resolve(c,reference)
        self.assertTrue(changed)
        c,factory,_,journal,document,_=self.completed_context()
        _,reference=trial_storage._snapshot(c,key,document)
        archive=c.store(c.root/('trial-snapshot-'+reference['snapshot_digest'])); write=archive.write
        def lost(expected,value):
            write(expected,value)
            raise OSError('unknown context archive acknowledgement')
        with patch.object(archive,'write',side_effect=lost),self.assertRaises(OSError): trial_storage.pin(c,key,document)
        fresh=SimpleNamespace(root=c.root,store=factory,session=c.session,document=c.document)
        trial_storage.install(fresh)
        with self.assertRaises(Refusal): trial_storage.pin(fresh,key,document)

    def test_unknown_component_ack_poison_prevents_root_publication_and_adoption(self):
        c,journals=self.fixture(); original=c.store
        def factory(path):
            journal=original(path)
            if Path(path).name.startswith('trial-component-'):
                write=journal.write
                def lost(expected,value):
                    write(expected,value)
                    raise OSError('unknown component acknowledgement')
                journal.write=lost
            return journal
        c.store=factory; trial_storage.install(c); key='trial-controller-bad-acceptance'; journal=c.store(c.root/key)
        with self.assertRaises(OSError): trial_storage.write_controller(c,key,journal,None,self.large())
        self.assertIsNone(journal.read())
        with self.assertRaises(Refusal): trial_storage.write_controller(c,key,journal,None,self.large())
        self.assertIsNone(journal.read())
        fresh=SimpleNamespace(root=c.root,store=original,session=c.session,document=c.document)
        trial_storage.install(fresh); restarted=fresh.store(fresh.root/key)
        with self.assertRaises(Refusal): trial_storage.write_controller(fresh,key,restarted,None,self.large())
        self.assertIsNone(restarted.read())

    def test_context_pin_and_midread_source_or_context_changes_refuse(self):
        from unittest.mock import patch
        for fault in ('pin','source','context'):
            c,_=self.fixture(); trial_storage.install(c); key='trial-controller-new-base-prior'
            source=dict(storage_version=2,kind='native-trial-controller',name='new-base',phase='terminal',
                candidate=dict(name='new-base',transition=dict(intent=dict(phase='prior'))),certificate=None,terminal={},
                record={},workflow={},candidates={},provisioning={})
            controller=c.store(c.root/key); root=trial_storage.write_controller(c,key,controller,None,source)
            journal=c.store(c.root/'trial-context-new-base')
            document=journal.write(None,dict(name='new-base',phase='approved',record={},workflow={},candidates={},provisioning={}))
            if fault=='pin':
                physical=journal.raw.read(); modified=copy.deepcopy(physical['value'])
                modified['_context_source']['digest']='0'*64
                journal.raw.write(physical,modified)
                with self.assertRaises(Refusal): journal.read()
                continue
            physical=controller.physical(root)
            component=c.store(c.root/('trial-component-'+physical['value']['candidate']['component_digest']))
            component=getattr(component,'raw',component)
            read=component.read; changed=[]
            def during_read():
                result=read()
                if not changed:
                    target=controller.raw if fault=='source' else journal.raw
                    retained=target.read(); target.write(retained,dict(retained['value'],phase='changed'))
                    changed.append(True)
                return result
            with patch.object(component,'read',side_effect=during_read),self.assertRaises(Refusal): journal.read()
            self.assertTrue(changed)


class SnapshotContracts(unittest.TestCase):
    def fixture(self):
        journals={}
        def store(path): return journals.setdefault(str(path),Journal())
        c=SimpleNamespace(root=Path('/private/trial'),store=store,
            session=SimpleNamespace(owner='owner',scope='scope'),
            document=None)
        c.document=store(c.root/'trial').write(None,dict(storage_version=2,storage_id='a'*32,preview={}))
        return c,journals

    def terminal(self,c,name='direct-push',history=None,previous=None):
        from trial_controller import case_journal
        trial_storage.install(c)
        value=dict(storage_version=2,kind='native-trial-controller',name=name,phase='terminal',
            candidate=dict(name=name),history=history or [],terminal=dict(binding={}),payload='x'*20000)
        if previous is not None: value['previous']=previous
        key=case_journal('trial-controller',value['candidate'])
        return key,c.store(c.root/key).write(None,value)

    def test_complete_chain_stays_bounded_and_each_call_rereads_live_sources(self):
        from trial_controller import CASE_CHAIN
        c,journals=self.fixture(); history=[]; previous=None
        for name in CASE_CHAIN[:15]:
            key,document=self.terminal(c,name,history,previous)
            previous=trial_storage.pin(c,key,document)
            history=history+[dict(revision=name,terminal={})]
        value=dict(storage_version=2,history=history,previous=previous)
        self.assertEqual(len(list(trial_storage.predecessors(c,value))),15)
        self.assertTrue(all(len(j.raw)<=MAX_STATE for j in journals.values()))
        first=c.store(c.root/'trial-controller').read()
        first['value']['payload']='changed'
        c.store(c.root/'trial-controller').write(c.store(c.root/'trial-controller').read(),first['value'])
        with self.assertRaises(Refusal): list(trial_storage.predecessors(c,value))

    def test_reference_substitutions_and_archive_generation_refuse(self):
        for field,replacement in (('namespace_digest','0'*64),('journal_kind','../escape'),
                ('case_name','coding-update'),('case_phase','ready'),('source_generation',2),('snapshot_digest','0'*64)):
            c,_=self.fixture(); key,document=self.terminal(c); reference=trial_storage.pin(c,key,document)
            reference[field]=replacement
            with self.subTest(field=field),self.assertRaises(Refusal): trial_storage.resolve(c,reference)
        c,journals=self.fixture(); key,document=self.terminal(c); reference=trial_storage.pin(c,key,document)
        archive=next(j for path,j in journals.items() if 'trial-snapshot-' in path)
        retained=archive.read(); archive.write(retained,retained['value'])
        with self.assertRaises(Refusal): trial_storage.resolve(c,reference)

    def test_live_root_changed_during_archive_component_read_refuses(self):
        from unittest.mock import patch
        c,_=self.fixture(); key,document=self.terminal(c)
        reference=trial_storage.pin(c,key,document)
        self.assertEqual(trial_storage.resolve(c,reference),document)
        controller=c.store(c.root/key); physical=controller.physical(document)
        component=c.store(c.root/('trial-component-'+physical['value']['candidate']['component_digest']))
        component=getattr(component,'raw',component)
        read=component.read; changed=[]
        def during_read():
            retained=read()
            if not changed:
                live=controller.raw.read()
                controller.raw.write(live,dict(live['value'],payload='changed during archive resolution'))
                changed.append(True)
            return retained
        with patch.object(component,'read',side_effect=during_read),self.assertRaises(Refusal):
            trial_storage.resolve(c,reference)
        self.assertTrue(changed)

    def test_missing_archive_live_journal_and_wrong_order_refuse(self):
        for fault in ('archive','live','order','legacy'):
            c,journals=self.fixture(); key,document=self.terminal(c); reference=trial_storage.pin(c,key,document)
            value=dict(storage_version=2,history=[dict(revision='r',terminal={})],previous=reference)
            if fault=='archive': next(j for p,j in journals.items() if 'trial-snapshot-' in p).raw=None
            if fault=='live': c.store(c.root/key).raw.raw=None
            if fault=='order': value['history'].append(dict(revision='s',terminal={}))
            if fault=='legacy': value.pop('storage_version')
            with self.subTest(fault=fault),self.assertRaises(Refusal): list(trial_storage.predecessors(c,value))

    def test_unknown_archive_ack_stops_without_root_write(self):
        c,journals=self.fixture(); key,document=self.terminal(c); factory=c.store
        def store(path):
            journal=factory(path)
            if 'trial-snapshot-' in str(path):
                write=journal.write
                def uncertain(expected,value):
                    write(expected,value)
                    raise OSError('persistence acknowledgement unknown')
                journal.write=uncertain
            return journal
        c.store=store
        with self.assertRaises(OSError): trial_storage.pin(c,key,document)
        self.assertEqual(factory(c.root/key).read(),document)
        # A new context must not convert orphan visibility into an acknowledged pin.
        fresh=SimpleNamespace(**vars(c)); fresh.store=factory
        with self.assertRaises(Refusal):
            reference=trial_storage.pin(fresh,key,document)
            factory(c.root/'new-authoritative-root').write(None,dict(previous=reference))
        self.assertIsNone(factory(c.root/'new-authoritative-root').read())

    def test_existing_archive_is_exact_and_root_cas_is_not_rebased(self):
        c,_=self.fixture(); key,document=self.terminal(c)
        reference=trial_storage.pin(c,key,document)
        with self.assertRaises(Refusal): trial_storage.pin(c,key,document)
        journal=c.store(c.root/'next'); expected=journal.write(None,dict(previous=reference))
        journal.write(expected,dict(previous=reference,phase='winner'))
        with self.assertRaises(Refusal): journal.write(expected,dict(previous=reference,phase='loser'))

    def test_root_ack_is_exact_and_unknown_write_cannot_resume(self):
        c,_=self.fixture(); key='trial-controller'; journal=c.store(c.root/key)
        value=dict(storage_version=2,kind='native-trial-controller',name='direct-push',phase='ready')
        document=trial_storage.write_controller(c,key,journal,None,value)
        trial_storage.acknowledged(c,key,journal,document)
        fresh=SimpleNamespace(root=c.root,store=c.store,session=c.session,document=c.document)
        with self.assertRaises(Refusal): trial_storage.acknowledged(fresh,key,journal,document)
        changed=journal.write(document,dict(value,phase='bound'))
        with self.assertRaises(Refusal): trial_storage.acknowledged(c,key,journal,changed)
        write=journal.write
        def uncertain(expected,value):
            write(expected,value)
            raise OSError('unknown root acknowledgement')
        journal.write=uncertain
        with self.assertRaises(OSError): trial_storage.write_controller(c,key,journal,changed,dict(value,phase='closing'))
        with self.assertRaises(Refusal): trial_storage.acknowledged(c,key,journal,journal.read())
        fresh=SimpleNamespace(root=c.root,store=c.store,session=c.session,document=c.document)
        with self.assertRaises(Refusal): trial_storage.acknowledged(fresh,key,journal,journal.read())


@unittest.skipUnless(os.name=='posix','actual Linux protected Store coverage')
class ProtectedSnapshotContracts(SnapshotContracts):
    def fixture(self):
        from authority_private import Store
        folder=tempfile.TemporaryDirectory(prefix='native-snapshot-')
        self.addCleanup(folder.cleanup)
        journals={}
        def store(path):
            return journals.setdefault(str(path),Store(Path(folder.name)/Path(path).name))
        c=SimpleNamespace(root=Path(folder.name),store=store,
            session=SimpleNamespace(owner='owner',scope='scope'),document=None)
        c.document=store(c.root/'trial').write(None,dict(storage_version=2,storage_id='a'*32,preview={}))
        return c,journals

    def test_complete_chain_stays_bounded_and_each_call_rereads_live_sources(self):
        # Exercise the same acceptance assertions against actual protected files.
        from trial_controller import CASE_CHAIN
        c,journals=self.fixture(); history=[]; previous=None
        for name in CASE_CHAIN[:15]:
            key,document=self.terminal(c,name,history,previous)
            previous=trial_storage.pin(c,key,document)
            history=history+[dict(revision=name,terminal={})]
        value=dict(storage_version=2,history=history,previous=previous)
        self.assertEqual(len(list(trial_storage.predecessors(c,value))),15)
        self.assertTrue(all(len(j.path.read_bytes())<=MAX_STATE for j in journals.values()))
        journal=c.store(c.root/'trial-controller'); document=journal.read()
        changed=dict(document['value'],payload='changed'); journal.write(document,changed)
        with self.assertRaises(Refusal): list(trial_storage.predecessors(c,value))

    def test_missing_archive_live_journal_and_wrong_order_refuse(self):
        for fault in ('archive','live','order','legacy'):
            c,journals=self.fixture(); key,document=self.terminal(c); reference=trial_storage.pin(c,key,document)
            value=dict(storage_version=2,history=[dict(revision='r',terminal={})],previous=reference)
            if fault=='archive': next(j for p,j in journals.items() if 'trial-snapshot-' in p).path.unlink()
            if fault=='live': c.store(c.root/key).raw.path.unlink()
            if fault=='order': value['history'].append(dict(revision='s',terminal={}))
            if fault=='legacy': value.pop('storage_version')
            with self.subTest(fault=fault),self.assertRaises(Refusal): list(trial_storage.predecessors(c,value))

    def test_acknowledged_active_root_is_held_in_a_separate_process(self):
        c,_=self.fixture(); key='trial-controller'; journal=c.store(c.root/key)
        document=trial_storage.write_controller(c,key,journal,None,dict(storage_version=2,phase='ready'))
        trial_storage.acknowledged(c,key,journal,document)
        program='''import sys
sys.path[:0]=sys.argv[2:]
from pathlib import Path
from types import SimpleNamespace
from authority_private import Store
from trusted_ci_policy import Refusal
import trial_storage
root=Path(sys.argv[1]); journal=Store(root/'trial-controller')
c=SimpleNamespace(root=root,store=Store,document=Store(root/'trial').read(),session=SimpleNamespace(owner='owner',scope='scope'))
try: trial_storage.acknowledged(c,'trial-controller',journal,journal.read())
except Refusal: print('active restart HELD')
else: raise SystemExit('active restart incorrectly resumed')
'''
        result=subprocess.run([sys.executable,'-I','-c',program,str(c.root),
            str(backend_test_support.ROOT/'deploy/authority'),str(backend_test_support.ROOT/'.ai/scripts')],
            capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),'active restart HELD')


@unittest.skipUnless(os.name=='posix','actual Linux protected Store coverage')
class ProtectedComponentContracts(ComponentContracts):
    fixture=ProtectedSnapshotContracts.fixture
