"""Exact local source-transition contracts; no live GitHub effects."""
import backend_test_support
import copy
import json
import unittest

import submission
from test_authority_submission import SubmissionHost, fixture
from trusted_ci_policy import Refusal,digest


class ExpiredCleanupContracts(unittest.TestCase):
    """Cleanup guard components; native publication and identity I/O are modeled."""
    def fixture(self, context):
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import Mock
        from trial_handoff import Native
        from trial_setup import Provision
        p=dict(repository='owner/source',repository_id=1,target='main')
        before=dict(deployment=dict(expires=110,policy=p))
        record=dict(created=10,expires=100,task_id='a'*32,pair=dict(authority_repository='owner/authority',authority_repository_id=2),
            origin=dict(owner=7,scope='scope',binding=dict(fence=dict(pending=dict(execution_deadline=90)))))
        prior=dict(revision='b'*40); history=[]
        preview=dict(issued=20,expires=90,record_digest=digest(record))
        claim=dict(schema_version=1,kind='native-trial-context-intent',name='new-base',record_digest=digest(record),
                   preview=copy.deepcopy(preview),before=before,prior=prior,history=history)
        rule=dict(name='owned',target='branch',enforcement='active',conditions={},rules=[],bypass_actors=[])
        preview['rules']={key:dict(rule,id=i+1) for i,key in enumerate(('acceptance','updates'))}
        claim['preview']=copy.deepcopy(preview)
        value=dict(record=record,name='new-base',before=before,preview=preview,prior=prior,history=history,
            provisioning=dict(owner='retained'),workflow={},candidates={},phase='intent-started',effects={},policy=None,
            intent=dict(kind=claim['kind'],revision='c'*40),credential=dict(token='retained-token',revoked=False))
        if not context:
            case=dict(history=history,request=dict(operation='retained'),certificate=dict(expires=80),execution=dict(credential=dict(expires=70)))
            claim=dict(schema_version=1,kind='native-trial-revocation-intent',name='revoked-qualification',
                record_digest=digest(record),case_digest=digest(case),request_digest=digest(case['request']),issued=20,expires=70,preview={})
            value=dict(record=record,binding=before,case=case,claim=claim,provisioning=value['provisioning'],
                intent=dict(kind=claim['kind'],revision='c'*40),credential=value['credential'])
        class Memory:
            def __init__(self, document): self.document=copy.deepcopy(document)
            def read(self): return copy.deepcopy(self.document)
            def write(self, expected, data):
                if expected!=self.document: raise Refusal('changed owner')
                self.document=dict(value=copy.deepcopy(data)); return self.read()
        key='trial-context-new-base' if context else 'trial-native-revocation'
        stores={key:Memory(dict(value=value)),'trial':Memory(value['provisioning']),
                'trial-workflow':Memory({}),'trial-candidates':Memory({})}
        c=Provision.__new__(Provision); c.root=Path('synthetic-cleanup'); c.document=value['provisioning']; c.clock=lambda:101
        c.store=lambda path:stores[Path(path).name]
        c.session=SimpleNamespace(owner=7,scope='scope',registry=SimpleNamespace(unchanged=Mock()))
        native=Native.__new__(Native); native.provision=c
        native.registry=SimpleNamespace(api=object(),coordinates=dict(repository='owner/authority',repository_id=2,registry_branch='agentic-registry'),read=lambda:before['deployment'])
        def get(path):
            if '/rulesets/' in path:
                return copy.deepcopy(preview['rules']['acceptance' if '/1?' in path else 'updates'])
            return dict(id=1,private=True,owner=dict(id=7),default_branch='main')
        record['pair']['identities']=dict(owner_id=7,apps=dict(admin=dict(id=3)))
        # Rebind the record digest after completing the modeled identity record.
        claim['record_digest']=digest(record)
        if context:
            claim['preview']['record_digest']=digest(record); value['preview']['record_digest']=digest(record)
        stores[key]=Memory(dict(value=value))
        token=Mock(); factory=Mock(return_value=token)
        return native,stores[key],claim,SimpleNamespace(get=get),factory,token

    def run_cleanup(self, context, native, claim, operator, factory, reader=None, history=None):
        from unittest.mock import patch
        from contextlib import ExitStack
        import trial_broker_case,trial_transition
        def original_event(original,record,entries,clock,authority): self.assertEqual(clock(),20)
        with ExitStack() as stack:
            stack.enter_context(patch.object(__import__('trial_storage'),'install'))
            stack.enter_context(patch.object(trial_transition,'read_native',side_effect=reader or (lambda *a:copy.deepcopy(claim))))
            stack.enter_context(patch.object(__import__('trial_case'),'history_guard',side_effect=history or original_event))
            stack.enter_context(patch.object(__import__('configuration').SetupConfigurationSession,'_native_identity'))
            stack.enter_context(patch.object(trial_broker_case,'_revocation_identity'))
            if context: return trial_transition.cleanup_context(native,'new-base',operator,object(),factory)
            return trial_broker_case.cleanup_revocation(native,operator,object(),factory)

    def test_expired_cleanup_uses_authenticated_original_event_and_exact_token(self):
        for context in (False,True):
            with self.subTest(context=context):
                native,journal,claim,operator,factory,token=self.fixture(context)
                self.run_cleanup(context,native,claim,operator,factory)
                factory.assert_called_once_with('retained-token')
                token.fetch.assert_called_once_with('/installation/token',method='DELETE',binary=True)
                self.assertTrue(journal.read()['value']['credential']['revoked'])

    def test_substituted_intent_or_invalid_event_blocks_cleanup(self):
        for context in (False,True):
            for fault in ('kind','schema','record','prior','history','case','request','issued','boolean-issued','future','expires','missing','pointer','evidence'):
                if context and fault in ('case','request') or not context and fault=='prior': continue
                with self.subTest(context=context,fault=fault):
                    native,journal,claim,operator,factory,token=self.fixture(context)
                    if fault=='kind': claim['kind']='other'
                    if fault=='schema': claim['schema_version']=True
                    if fault=='record': claim['record_digest']='0'*64
                    if fault=='prior': claim['prior']={}
                    if fault=='history':
                        if context: claim['history']=[{}]
                        else: journal.document['value']['case']['history']=[{}]
                    if fault=='case': claim['case_digest']='0'*64
                    if fault=='request': claim['request_digest']='0'*64
                    event=claim['preview'] if context else claim
                    if fault=='issued': event['issued']=1
                    if fault=='boolean-issued': event['issued']=True
                    if fault=='future': native.provision.clock=lambda:19
                    if fault=='expires': event['expires']=200
                    if context and fault in ('issued','boolean-issued','future','expires'):
                        journal.document['value']['preview']=copy.deepcopy(claim['preview'])
                    if not context: journal.document['value']['claim']=copy.deepcopy(claim)
                    if fault=='missing': journal.document['value']['intent']=None
                    def refused(*args): raise Refusal('changed immutable evidence')
                    with self.assertRaises(Refusal):
                        self.run_cleanup(context,native,claim,operator,factory,reader=refused if fault=='pointer' else None,
                                         history=refused if fault=='evidence' else None)
                    factory.assert_not_called(); token.fetch.assert_not_called()


class CompletionPin(unittest.TestCase):
    def state(self):
        before=dict(binding='b'*12000); after=dict(binding='a'*12000)
        return dict(name='new-base',record=dict(task_id='a'*32),before=before,
            steps=[dict(before=before,documents={},after=after)],source=dict(base='b'*40),
            intent=dict(kind='native-trial-context-intent',revision='c'*40),terminal=dict(result=dict(restored=True)),padding='p'*60000)

    def test_exact_public_preimage_with_timestamp_pin_fits_without_duplicate(self):
        import trial_transition
        from authority_private import MAX_STATE
        value=self.state()
        original=dict(schema_version=1,kind='native-trial-context-complete',task_id=value['record']['task_id'],execution=None,
            record_digest=digest(value['record']),name=value['name'],intent=value['intent'],before=value['before'],
            after=value['steps'][-1]['after'],steps=copy.deepcopy(value['steps']),source=value['source'],
            result=value['terminal']['result'],completed=1234)
        self.assertGreater(len(json.dumps(dict(value,completion_preimage=original)).encode()),MAX_STATE)
        complete=trial_transition._context_completion(value,1234)
        self.assertEqual(json.dumps(complete,sort_keys=True),json.dumps(original,sort_keys=True))
        self.assertEqual(trial_transition._context_completion(value,9999),original)
        self.assertEqual(value['completion_pin'],dict(completed=1234,digest=digest(original)))
        self.assertLess(len(json.dumps(dict(schema_version=1,generation=1,value=value)).encode()),MAX_STATE)

    def test_every_reconstruction_refuses_changed_retained_inputs_or_pin(self):
        import trial_transition
        for field in ('before','steps','source','result','time','digest'):
            value=self.state(); trial_transition._context_completion(value,1234)
            if field=='before': value['before']=dict(changed=True)
            if field=='steps': value['steps'][-1]['after']=dict(changed=True)
            if field=='source': value['source']=dict(changed=True)
            if field=='result': value['terminal']['result']=dict(changed=True)
            if field=='time': value['completion_pin']['completed']+=1
            if field=='digest': value['completion_pin']['digest']='0'*64
            with self.subTest(field=field),self.assertRaises(Refusal): trial_transition._context_completion(value)


class TransitionHost(SubmissionHost):
    def fetch(self, path, **kwargs):
        if '/git/blobs/' in path: return self.get(path)
        return super().fetch(path, **kwargs)

    def get(self, path):
        value = super().get(path)
        if path == '/repos/owner/project': value['node_id'] = 'fixture-source-node'
        return value

    def post(self, path, data):
        if path != '/graphql': return super().post(path, data)
        self.writes.append((path, copy.deepcopy(data)))
        value = data['variables']['input']
        if value['repositoryId'] != 'fixture-source-node': raise Refusal('foreign node')
        update, = value['refUpdates']
        branch = update['name'].removeprefix('refs/heads/')
        if self.refs[branch] != update['beforeOid'] or update['force'] is not False:
            return dict(errors=[dict(message='source moved')])
        self.refs[branch] = update['afterOid']
        next(p for p in self.prs if p['head']['ref'] == branch)['head']['sha'] = update['afterOid']
        if self.fail_after == '/graphql': raise OSError('unknown ref acknowledgement')
        return dict(data=dict(updateRefs=dict(clientMutationId=value['clientMutationId'])))


class Advance(unittest.TestCase):
    def test_strict_same_tree_prior_is_immutable_after_current_head_advances(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        import trial_transition
        from trusted_ci_policy import digest
        d,request,files=fixture(); host=TransitionHost()
        reservation=submission._submit(host,d,request,files)
        tree=reservation['tree']; link=dict(kind='native-trial-eligibility',revision='a'*40)
        reserved=dict(name='new-head',submitted=reservation,controls_digest='b'*64,eligibility=link)
        worker=dict(submitted=reservation)
        record=dict(trial=dict(deployment=d),pair=dict(fixture_revision=request['base']),expires=2000,
                    origin=dict(binding=dict(fence=dict(pending=dict(execution_deadline=1300)))))
        history=[dict(revision=str(i),terminal={}) for i in range(9)]
        prior_intent=trial_transition._intent(record,worker,reserved,history,'prior',tree,reservation,None,1001,'c'*64,None,link)
        prior=submission._advance(host,d,reservation,tree,digest(prior_intent),1001)
        prior_candidate=dict(reserved,submitted=prior,transition=dict(intent=prior_intent))
        entry=dict(revision='d'*40,terminal={}); accepted={}
        current_intent=trial_transition._intent(record,worker,reserved,history,'current',tree,prior,entry,1002,'e'*64,accepted)
        current=submission._advance(host,d,prior,tree,digest(current_intent),1002)
        candidate=dict(reserved,submitted=current,transition=dict(intent=current_intent))
        old=dict(candidate=prior_candidate,history=history)
        original=SimpleNamespace(blob=lambda *args:(dict(candidate={}),None))
        registry=SimpleNamespace(api=None)
        writes=copy.deepcopy(host.writes)
        with patch.object(__import__('trial_case'),'read',return_value=(old,record)),\
             patch.object(__import__('trial_eligibility'),'select',return_value=tree),\
             patch.object(trial_transition,'prior_acceptance',return_value=accepted):
            self.assertEqual(trial_transition.validate(candidate,record,worker,history,host,original,registry,lambda:1003),files)
            self.assertNotEqual(prior['head'],current['head'])
            metadata=host.commits[prior['head']]
            for field,value in (('message','foreign intent'),('parents',[dict(sha=request['base'])]),
                                ('author',dict(name='foreign')),('tree',dict(sha='f'*40))):
                saved=copy.deepcopy(metadata[field]); metadata[field]=value
                with self.subTest(field=field),self.assertRaises(Refusal):
                    trial_transition.validate(candidate,record,worker,history,host,original,registry,lambda:1003)
                metadata[field]=saved
            host.refs[current['branch']]=prior['head']
            next(pr for pr in host.prs if pr['number']==current['pr'])['head']['sha']=prior['head']
            with self.assertRaises(Refusal):
                trial_transition.validate(candidate,record,worker,history,host,original,registry,lambda:1003)
        self.assertEqual(host.writes,writes,'retained authentication must never mutate source')

    def test_finite_context_and_human_references_never_alias_cases_or_origin(self):
        from registry import trial_reference
        refs = set()
        for name in ('new-base','policy-transition'):
            for kind in ('native-trial-context-intent','native-trial-context-complete'):
                refs.add(trial_reference(dict(kind=kind,task_id='1'*32,name=name,execution=None)))
        for kind in ('native-trial-human-intent','native-trial-human-result'):
            refs.add(trial_reference(dict(kind=kind,task_id='1'*32,name='human-update',execution=None)))
        self.assertEqual(len(refs),6)
        with self.assertRaises(Refusal):
            trial_reference(dict(kind='unknown-native-claim',task_id='1'*32,execution=None))

    def test_target_transition_is_empty_exact_cas_and_unknown_recovery_is_read_only(self):
        d, request, _ = fixture(); host = TransitionHost()
        host.refs['main'] = request['base']
        host.commits[request['base']]['sha'] = request['base']
        post = host.post
        def send(path, data):
            if path != '/graphql': return post(path, data)
            host.writes.append((path, copy.deepcopy(data)))
            value = data['variables']['input']; update, = value['refUpdates']
            self.assertEqual(update['name'], 'refs/heads/main')
            self.assertEqual(update['beforeOid'], request['base'])
            self.assertIs(update['force'], False)
            if host.refs['main'] != update['beforeOid']: return dict(errors=[dict(message='moved')])
            host.refs['main'] = update['afterOid']
            raise OSError('unknown target acknowledgement')
        host.post = send
        admin = dict(id=d['apps']['admin'], actor_id=23, slug='fixture-admin', installation_id=33)
        with self.assertRaisesRegex(OSError, 'unknown target'):
            submission._advance_target(host, d, request['base'], admin, 'a'*64, 1001)
        writes = copy.deepcopy(host.writes)
        result = submission._advance_target(host, d, request['base'], admin, 'a'*64, 1001, recover=True)
        self.assertEqual(result['base'], host.refs['main'])
        self.assertEqual(result['tree'], host.commits[request['base']]['tree']['sha'])
        self.assertEqual(result['parents'], [request['base']])
        self.assertEqual(host.writes, writes)
        host.refs['main'] = request['base']
        with self.assertRaisesRegex(Refusal, 'unknown.*never replay'):
            submission._advance_target(host, d, request['base'], admin, 'a'*64, 1001, recover=True)
        self.assertEqual(host.writes, writes)

    def test_all_native_transition_entrypoints_preserve_release_hold(self):
        from trial_controller import Native
        native=Native(None)
        for call in (lambda:native.open_prior('prompt'),
                     lambda:native.observe_terminal('prompt','new-head',{},phase='prior'),
                     lambda:native.recover_terminal('prompt','new-head',phase='prior'),
                     lambda:native.transition_context('prompt','new-base',None,None,None),
                     lambda:native.human_attempt('prompt',None)):
            with self.assertRaisesRegex(Refusal,'qualify-live blocked'): call()
        with self.assertRaisesRegex(Refusal,'bootstrap blocked'): native.cleanup_context('new-base',None,None)

    def test_target_movement_during_admission_blocks_commit_creation(self):
        d,request,_=fixture(); host=TransitionHost(); host.refs['main']=request['base']
        host.commits[request['base']]['sha']=request['base']
        admin=dict(id=d['apps']['admin'],actor_id=23,slug='fixture-admin',installation_id=33)
        def move(): host.refs['main']='f'*40
        with self.assertRaises(Refusal):
            submission._advance_target(host,d,request['base'],admin,'a'*64,1001,before_effect=move)
        self.assertEqual(host.writes,[])

    def test_exact_append_preserves_modes_and_recovers_unknown_ref_without_replay(self):
        d, request, files = fixture(); host = TransitionHost()
        original = submission._submit(host, d, request, files)
        tree = host.commits[request['base']]['tree']['sha']
        host.fail_after = '/graphql'
        with self.assertRaisesRegex(OSError, 'unknown ref'):
            submission._advance(host, d, original, tree, 'a'*64, 1001)
        writes = copy.deepcopy(host.writes)
        old = submission._advance(host, d, original, tree, 'a'*64, 1001, recover=True)
        self.assertNotEqual(old['head'], original['head'])
        self.assertEqual(host.commits[old['head']]['parents'], [dict(sha=original['head'])])
        self.assertEqual(host.writes, writes)
        host.fail_after = None
        current = submission._advance(host, d, old, original['tree'], 'b'*64, 1002)
        self.assertEqual(current['tree'], original['tree'])
        self.assertEqual(current['export_digest'], original['export_digest'])
        self.assertEqual(current['pr'], original['pr'])
        self.assertNotEqual(current['head'], original['head'])

    def test_unknown_commit_does_not_repeat_and_foreign_source_cannot_be_adopted(self):
        d, request, files = fixture(); host = TransitionHost()
        original = submission._submit(host, d, request, files)
        tree = host.commits[request['base']]['tree']['sha']
        host.fail_after = '/git/commits'
        with self.assertRaises(OSError): submission._advance(host, d, original, tree, 'a'*64, 1001)
        writes = copy.deepcopy(host.writes)
        with self.assertRaises(Refusal): submission._advance(host, d, original, tree, 'a'*64, 1001, recover=True)
        self.assertEqual(host.writes, writes)
        for issued in (True, 1001.0):
            with self.assertRaises(Refusal): submission._advance(host, d, original, tree, 'a'*64, issued)
