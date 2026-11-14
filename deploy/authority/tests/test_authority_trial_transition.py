"""Exact local source-transition contracts; no live GitHub effects."""
import backend_test_support
import copy
import json
import unittest

import submission
from test_authority_submission import SubmissionHost, fixture
from trusted_ci_policy import Refusal,digest


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
