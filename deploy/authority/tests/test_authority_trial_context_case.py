"""Finite native disposable contexts; local transports and real protected history."""
import backend_test_support
import copy
import unittest
import time
from unittest.mock import patch

import trial_case
import trial_controller
import bootstrap
from trusted_ci_policy import Refusal
from trusted_ci_policy import digest
import test_authority_trial_new_head_case as previous
from test_authority_trial_host_case import Sequential

NATIVE_MINT = bootstrap.installation_token


class Context(previous.NewHead):
    TRANSITION_CASES = ('new-head', 'new-base', 'policy-transition', 'human-update')

    def observe(self, phase=None):
        return Sequential.observe(self, phase)

    def ready(self, *args, **kwargs):
        if kwargs.get('name') in ('new-base', 'policy-transition', 'human-update'):
            kwargs['phase'] = getattr(self, 'phase', None)
        return super().ready(*args, **kwargs)

    def through_tenth(self):
        self.current(); self.host(); self.run('broker'); self.finalize(); self.observe()
        self.tenth = self.native.provision.store(self.native.provision.root/'trial-controller-new-head').read()['value']
        self.tenth_binding = self.registry.binding()

    def prior_case(self, name, run):
        self.phase = 'prior'
        self.second(name, run, 'fresh-'+name+'-prior')
        with self.owner.assertRaisesRegex(Refusal, 'pending'): self.coordinate()
        self.owner.assertEqual(self.close_handoff()['host_case'], 'none')
        self.run('verify')
        for purpose in ('admin','reader','issuer','coding','merge'): self.run('proof',purpose)
        self.run('publication-controls'); self.run('publish')
        with self.owner.assertRaisesRegex(Refusal, 'historical preparation never authorizes dispatch'): self.run('broker')
        next(j for j in self.remote.jobs if j['name'].startswith('broker ('))['conclusion'] = 'failure'
        self.finalize(); self.observe(phase='prior')

    def context_transport(self):
        from test_authority_transition import TransitionHost as Target
        outer = self
        target = Target()
        target.rules = copy.deepcopy(self.source.pages('/repos/'+self.p['repository']+'/rulesets?includes_parents=true'))
        original_get, original_pages, original_post = self.source.get, self.source.pages, self.source.post
        get_api, pages_api = self.api.get, self.api.pages
        fetch_api, fetch_source = self.api.fetch, self.source.fetch
        class Operator:
            def get(self,path):
                if '/rulesets/' in path and outer.p['repository']+'/' in path:
                    identity=int(path.rsplit('/',1)[1].split('?')[0])
                    if not any(v['id']==identity for v in target.rules):
                        raise __import__('trusted_ci_github').HostRefusal(404)
                    return target.get(path.replace(outer.p['repository'],'owner/project'))
                if path=='/repos/'+outer.p['repository']:
                    return dict(get_api(path),**original_get(path))
                if path.startswith('/repos/'+outer.p['repository']+'/') and any(v in path for v in ('/git/','/pulls/','/branches/')):
                    return original_get(path)
                return get_api(path)
            def pages(self,path,collection=None):
                if outer.p['repository']+'/' in path and ('/rulesets' in path or '/rules/branches/' in path):
                    return target.pages(path.replace(outer.p['repository'],'owner/project'),collection)
                return original_pages(path,collection) if any(v in path for v in ('/reviews','/check-runs','/pulls?')) else pages_api(path,collection)
            def post(self,path,data):
                if path.endswith('/rulesets'):
                    return target.post(path.replace(outer.p['repository'],'owner/project'),data)
                return original_post(path,data)
            def fetch(self,path,method='GET',data=None,**kw):
                if method=='GET':
                    if outer.p['authority_repository']+'/' in path: return fetch_api(path,method=method,**kw)
                    return fetch_source(path,method=method,**kw)
                if method=='PUT' and '/rulesets/' in path:
                    record=next(v for v in target.rules if v['id']==int(path.rsplit('/',1)[1]))
                    record.update(copy.deepcopy(data)); target.events.append(('put',record['id']))
                    return copy.deepcopy(record)
                if method=='DELETE' and '/rulesets/' in path:
                    return target.fetch(path.replace(outer.p['repository'],'owner/project'),method=method,**kw)
                raise AssertionError((path,method))
        operator=Operator()
        self.native.provision.api=operator
        self.source.pages=operator.pages
        self.api.pages=lambda path,collection=None:operator.pages(path,collection) if self.p['repository']+'/' in path and ('/rulesets' in path or '/rules/branches/' in path) else pages_api(path,collection)
        def cas(path,data):
            if path!='/graphql' or data['variables']['input']['refUpdates'][0]['name']!='refs/heads/main':
                return original_post(path,data)
            value=data['variables']['input']; update,=value['refUpdates']
            admin=self.admission.record['pair']['identities']['apps']['admin']['id']
            for rule in target.rules:
                if rule['name'].startswith('AGENTIC-'):
                    if not any(a==dict(actor_type='Integration',actor_id=admin,bypass_mode='always') for a in rule['bypass_actors']):
                        raise __import__('trusted_ci_github').HostRefusal(403,'protected_update')
            self.owner.assertEqual(value['repositoryId'],'fixture-source-node')
            self.owner.assertIs(update['force'],False)
            if outer.source.refs['main']!=update['beforeOid']: return dict(errors=[dict(message='moved')])
            self.source.writes.append((path,copy.deepcopy(data)))
            self.source.refs['main']=update['afterOid']
            return dict(data=dict(updateRefs=dict(clientMutationId=value['clientMutationId'])))
        self.source.post=cas
        tokens=self.tokens
        def current_tokens(token):
            scoped=tokens(token); pages,get=scoped.pages,scoped.get
            scoped.pages=lambda path,collection=None:operator.pages(path,collection) if outer.p['repository']+'/' in path and (
                '/rulesets' in path or '/rules/branches/' in path) else pages(path,collection)
            scoped.get=lambda path:operator.get(path) if outer.p['repository']+'/' in path and '/branches/' in path else get(path)
            return scoped
        self.tokens=current_tokens; self.preparer.token_factory=current_tokens
        return operator,target

    def advance_case(self, name, prior_run, current_run):
        self.prior_case(name,prior_run)
        if not hasattr(self,'operator'):
            self.operator,self.target=self.context_transport()
        old=self.admission.request['snapshot']
        admin=self.apps(self.d['apps']['admin'],self.api.secrets['AGENTIC_ADMIN_PRIVATE_KEY'])
        with patch.object(bootstrap,'installation_token',NATIVE_MINT):
            link=trial_controller.Native(self.preparer).transition_context('prompt',name,self.operator,admin,digest,self.tokens)
        self.d=self.registry.read(); self.p=self.d['policy']; self.phase=None
        self.second(name,current_run,'fresh-'+name+'-current')
        with self.owner.assertRaisesRegex(Refusal,'pending'): self.coordinate()
        self.owner.assertEqual(self.close_handoff()['host_case'],name)
        self.observed(); self.host()
        self.owner.assertEqual(self.run('broker')['state'],'host-denied')
        result=self.finalize(); self.owner.assertEqual(self.observe()['binding'],result)
        self.owner.assertEqual(self.admission.request['snapshot']['head'],old['head'])
        self.owner.assertNotEqual(self.admission.request['snapshot']['base'],old['base'])
        return link

    def human_ready(self):
        self.through_tenth(); self.advance_case('new-base',123,125)
        self.advance_case('policy-transition',127,129)
        self.phase=None; self.second('human-update',131,'fresh-human-current')
        with self.owner.assertRaisesRegex(Refusal,'pending'): self.coordinate()
        self.owner.assertEqual(self.close_handoff()['host_case'],'human-update')
        self.run('verify')
        for purpose in ('admin','reader','issuer','coding','merge'): self.run('proof',purpose)
        self.run('publication-controls'); self.run('publish')
        env=self.job('trial host denial','trial_host_denial')
        env.update(GITHUB_REPOSITORY=self.p['authority_repository'],GITHUB_TOKEN='case-actions-read',
            AGENTIC_READER_PRIVATE_KEY=self.api.secrets['AGENTIC_READER_PRIVATE_KEY'],
            **{trial_case.CaseReadStaging.NAME:self.case_token})
        return env

    def human_transport(self, attempts, fault=None):
        from trusted_ci_github import HostRefusal
        outer=self
        class Human:
            def get(self,path):
                outer.owner.assertEqual(path,'/user')
                return dict(id=outer.p['reviewers'][0],type='User')
            def fetch(self,path,method,data):
                outer.owner.assertEqual(method,'PATCH')
                outer.owner.assertEqual(path,'/repos/'+outer.p['repository']+'/git/refs/heads/main')
                outer.owner.assertEqual(data,dict(sha=outer.admission.request['snapshot']['merge'],force=False))
                # This source API models the actual non-bypass update gate.
                updates=next(r for r in outer.target.rules if r['name'].startswith('AGENTIC-updates-'))
                outer.owner.assertEqual(updates['bypass_actors'],[dict(actor_type='Integration',actor_id=outer.d['apps']['merge'],bypass_mode='pull_request')])
                attempts.append((path,method,copy.deepcopy(data)))
                if fault=='unknown': raise OSError('unknown human HTTP result')
                raise HostRefusal(405 if fault=='wrong-status' else 403,'protected_update')
        return Human()

    def consume_human(self, env):
        return __import__('service')._case_producer(env,self.hint,'fixture-node','host-denial',clock=lambda:self.clock[0],
            api_factory=lambda token:self.api if token=='case-actions-read' else self.origin_factory(token),
            app_factory=self.apps,token_factory=self.tokens,uploader_factory=lambda *a:self.upload,host_case='human-update',
            sleeper=getattr(self,'sleeper',time.sleep))


@unittest.skipIf(getattr(previous.NativeNewHead, '__unittest_skip__', False), 'optional cryptography required')
class NativeContext(unittest.TestCase):
    def fixture(self):
        from test_authority_reconcile import Host
        original=Host.__init__
        def controls(host):
            original(host)
            # Establish the ORIGINAL disposable fixture with a foreign rule
            # that permits fast-forward empty commits. No later step removes it.
            host.rules[0].update(target='branch',conditions=dict(ref_name=dict(include=['refs/heads/main'],exclude=[])),
                                 rules=[dict(type='non_fast_forward')])
        with patch.object(Host,'__init__',controls):
            return previous.NativeNewHead.fixture(self)
    prepared = previous.NativeNewHead.prepared
    connected = previous.NativeNewHead.connected
    configured = previous.NativeNewHead.configured
    def exercise(self,*args,**kwargs):
        with patch.object(__import__('merge_transport'),'isolated',side_effect=AssertionError('native context dispatched a broker merge')):
            return previous.NativeNewHead.exercise(self,*args,**kwargs)
    prepare = previous.NativeNewHead.prepare
    # Use the existing frozen original trial and source/controller fixtures.
    def test_ten_history_replay_includes_historical_preparation(self):
        def check(*args):
            f = Context(self, args); f.through_tenth()
            publication = f.native.provision.store(f.native.provision.root/'trial-case-publication-new-head').read()
            history = f.tenth['history'] + [dict(revision=publication['value']['revision_bound'], terminal=f.tenth['terminal']['locator'])]
            self.assertEqual(trial_case.baseline(f.origin, f.registry, f.admission.record, history, lambda:f.clock[0]), f.tenth_binding)
        self.exercise(continuation=check, export_files=previous.spoof_fixture.forged_fixture.EXPORT)

    def test_eleventh_prior_uses_genuine_same_pr_acceptance(self):
        def check(*args):
            import trial_transition
            f = Context(self,args); f.through_tenth(); f.prior_case('new-base',123)
            entry = trial_transition.prior_entry(f.native.provision,'new-base')
            accepted = trial_transition.prior_acceptance(f.origin,f.api,f.admission.record,entry,lambda:f.clock[0])
            self.assertEqual(accepted['snapshot']['pr'],f.admission.candidate['submitted']['pr'])
            self.assertEqual(accepted['snapshot']['head'],f.admission.candidate['submitted']['head'])
            self.assertTrue(any(c['head_sha']==accepted['snapshot']['merge'] and c['conclusion']=='success' for c in f.checks))
            self.assertEqual(f.merges,[])
        self.exercise(continuation=check,export_files=previous.spoof_fixture.forged_fixture.EXPORT)

    def test_new_base_native_context_restores_original_gates(self):
        def check(*args):
            import trial_transition
            f=Context(self,args); f.through_tenth(); f.prior_case('new-base',123)
            operator,target=f.context_transport(); rules=copy.deepcopy(target.rules)
            old=f.source.refs['main']; production=f.origin.binding()
            admin=f.apps(f.d['apps']['admin'],f.api.secrets['AGENTIC_ADMIN_PRIVATE_KEY'])
            with patch.object(bootstrap,'installation_token',NATIVE_MINT):
                result=trial_controller.Native(f.preparer).transition_context('prompt','new-base',operator,admin,digest,f.tokens)
            value=trial_transition.read_native(f.origin,result,f.admission.record)
            self.assertNotEqual(f.source.refs['main'],old)
            self.assertEqual(target.rules,rules)
            self.assertEqual(value['source']['base'],f.source.refs['main'])
            self.assertEqual(value['after'],f.registry.binding())
            self.assertEqual(f.origin.binding(),production)
            self.assertIsNone(value['after']['deployment']['qualification'])
            old_head=f.admission.candidate['submitted']['head']
            f.phase=None
            f.second('new-base',125,'fresh-new-base-current')
            with self.assertRaisesRegex(Refusal,'pending'): f.coordinate()
            self.assertEqual(f.close_handoff()['host_case'],'new-base')
            f.observed(); f.host()
            self.assertEqual(f.run('broker')['state'],'host-denied')
            terminal=f.finalize(); self.assertEqual(f.observe()['binding'],terminal)
            self.assertEqual(f.admission.candidate['submitted']['head'],old_head)
            self.assertEqual(f.admission.request['snapshot']['base'],value['source']['base'])
            self.assertEqual(f.merges,[])
            return f.source.refs['main']
        self.exercise(continuation=check,export_files=previous.spoof_fixture.forged_fixture.EXPORT)

    def test_policy_transition_uses_actual_owned_configuration_engine(self):
        import json
        from authority_private import MAX_STATE
        from test_authority_trial_setup import Journal
        write=Journal.write; measured={}
        def bounded(journal,expected,state):
            name=getattr(getattr(journal,'root',None),'name',None)
            envelope=dict(schema_version=1,generation=1 if expected is None else expected['generation']+1,value=state)
            size=len((json.dumps(envelope,sort_keys=True,allow_nan=False)+'\n').encode())
            self.assertLessEqual(size,MAX_STATE,str(name)+' complete protected envelope exceeds limit')
            if name in ('trial-context-new-base','trial-context-policy-transition'):
                measured[name]=max(measured.get(name,0),size)
            return write(journal,expected,state)
        def check(*args):
            import trial_transition
            f=Context(self,args); f.through_tenth(); f.advance_case('new-base',123,125)
            old=copy.deepcopy(f.registry.binding())
            link=f.advance_case('policy-transition',127,129)
            value=trial_transition.read_native(f.origin,link,f.admission.record)
            self.assertEqual(f.d['generation'],old['deployment']['generation']+1)
            self.assertNotEqual(f.p['epoch'],old['deployment']['policy']['epoch'])
            self.assertEqual(value['after']['deployment'],f.d)
            self.assertEqual(f.merges,[])
            self.assertEqual(len(f.admission.value['history']),11)
            self.assertIsNone(f.d['qualification'])
            return f.source.refs['main']
        with patch.object(Journal,'write',bounded):
            self.exercise(continuation=check,export_files=previous.spoof_fixture.forged_fixture.EXPORT)
        self.assertEqual(set(measured),{'trial-context-new-base','trial-context-policy-transition'})

    def test_three_native_context_cases_finish_with_separate_human_transport(self):
        def check(*args):
            f=Context(self,args); env=f.human_ready()
            attempts=[]
            human=f.human_transport(attempts)
            native=trial_controller.Native(f.preparer)
            waiting=[]
            def publish_while_waiting(seconds):
                self.assertEqual(attempts,[])
                self.assertFalse(any(a['name'].startswith('trial-host-intent-') for a in f.remote.artifacts))
                waiting.append(True)
                native.human_attempt('prompt',human)
            f.sleeper=publish_while_waiting
            f.consume_human(env)
            self.assertEqual(len(attempts),1); self.assertEqual(len(waiting),1)
            with self.assertRaisesRegex(Refusal,'never replay'): native.human_attempt('prompt',human)
            job=next(j for j in f.remote.jobs if j['name']=='trial host denial')
            job.update(status='completed',conclusion='success',completed_at=__import__('test_authority_broker_evidence').stamp(f.clock[0]))
            self.assertEqual(f.run('broker')['state'],'host-denied')
            terminal=f.finalize(); self.assertEqual(f.observe()['binding'],terminal)
            _,_,outcome=f.artifact('trial-host-denial-')
            self.assertEqual(outcome['origin'],'native-human-observation')
            self.assertEqual(outcome['observation']['actor_id'],f.p['reviewers'][0])
            self.assertEqual(len(f.admission.value['history']),12)
            self.assertEqual(len(f.admission.value['candidates']['value']['candidates']),16)
            publication=f.native.provision.store(f.native.provision.root/'trial-case-publication-human-update').read()
            history=f.admission.value['history']+[dict(revision=publication['value']['revision_bound'],
                terminal=f.native.provision.store(f.native.provision.root/'trial-controller-human-update').read()['value']['terminal']['locator'])]
            self.assertEqual(trial_case.baseline(f.origin,f.registry,f.admission.record,history,lambda:f.clock[0]),terminal)
            self.assertIsNone(terminal['deployment']['qualification'])
            self.assertEqual(f.merges,[])
            return f.source.refs['main']
        self.exercise(continuation=check,export_files=previous.spoof_fixture.forged_fixture.EXPORT)

    def test_native_unknown_effects_never_replay_and_expired_cleanup_restores_gates(self):
        for fault in ('source-ack','completion-ack','expired-rule-ack'):
            def check(*args):
                f=Context(self,args); f.through_tenth(); f.prior_case('new-base',123)
                operator,target=f.context_transport(); original_rules=copy.deepcopy(target.rules)
                old=f.source.refs['main']; writes=[]
                admin=f.apps(f.d['apps']['admin'],f.api.secrets['AGENTIC_ADMIN_PRIVATE_KEY'])
                native=trial_controller.Native(f.preparer)
                if fault=='source-ack':
                    post=f.source.post
                    def lose(path,data):
                        value=post(path,data)
                        if path=='/graphql' and data['variables']['input']['refUpdates'][0]['name']=='refs/heads/main':
                            writes.append(path); raise OSError('unknown source acknowledgement')
                        return value
                    f.source.post=lose
                elif fault=='completion-ack':
                    post=f.origin.api.post
                    def lose(path,data):
                        value=post(path,data)
                        if path.endswith('/git/refs') and data['ref'].endswith('-new-base-context-complete'):
                            writes.append(path); raise OSError('unknown completion acknowledgement')
                        return value
                    f.origin.api.post=lose
                else:
                    fetch=operator.fetch
                    def lose(path,**kw):
                        value=fetch(path,**kw)
                        if kw.get('method')=='PUT' and any(a.get('bypass_mode')=='always' for a in kw['data']['bypass_actors']):
                            writes.append(path); f.clock[0]=f.admission.record['expires']+1
                            raise OSError('unknown expired rule acknowledgement')
                        return value
                    operator.fetch=lose
                with patch.object(bootstrap,'installation_token',NATIVE_MINT):
                    with self.assertRaises(OSError):
                        native.transition_context('prompt','new-base',operator,admin,digest,f.tokens)
                    source_writes=copy.deepcopy(f.source.writes)
                    self.assertEqual(target.rules,original_rules)
                    if fault=='expired-rule-ack':
                        with self.assertRaises(Refusal): native.transition_context('prompt','new-base',operator,admin,digest,f.tokens)
                        self.assertTrue(native.cleanup_context('new-base',operator,admin,f.tokens)['restored'])
                        self.assertEqual(f.source.refs['main'],old)
                    else:
                        f.clock[0]+=1
                        link=native.transition_context('prompt','new-base',operator,admin,digest,f.tokens)
                        self.assertEqual(__import__('trial_transition').read_native(f.origin,link,f.admission.record)['source']['base'],f.source.refs['main'])
                        self.assertNotEqual(f.source.refs['main'],old)
                    self.assertEqual(f.source.writes,source_writes)
                self.assertEqual(len(writes),1)
                self.assertEqual(target.rules,original_rules)
                return f.source.refs['main']
            with self.subTest(fault=fault):
                self.exercise(continuation=check,export_files=previous.spoof_fixture.forged_fixture.EXPORT)

    def test_context_rechecks_old_acceptance_and_final_source_after_blocking_reads(self):
        for fault in ('withdrawn-issuer','inventory-base'):
            def check(*args):
                f=Context(self,args); f.through_tenth(); f.prior_case('new-base',123)
                operator,target=f.context_transport(); rules=copy.deepcopy(target.rules)
                before=f.registry.binding(); base=f.source.refs['main']; armed=[]
                admin=f.apps(f.d['apps']['admin'],f.api.secrets['AGENTIC_ADMIN_PRIVATE_KEY'])
                approve=digest
                if fault=='withdrawn-issuer':
                    def approve(value):
                        head=f.admission.request['snapshot']['merge']
                        removed=[c for c in f.checks if c['head_sha']==head]
                        self.assertTrue(removed)
                        f.checks[:]=[c for c in f.checks if c['head_sha']!=head]
                        armed.append(True)
                        return digest(value)
                else:
                    old=f.source.get('/repos/'+f.p['repository']+'/git/commits/'+base)
                    actor=f.admission.record['pair']['identities']['apps']['admin']
                    author=dict(name=actor['slug']+'[bot]',email='external@example.invalid',date='1970-01-01T00:21:40Z')
                    external=f.source.post('/repos/'+f.p['repository']+'/git/commits',dict(message='external target advance',
                        tree=old['tree']['sha'],parents=[base],author=author,committer=author))['sha']
                    pages=operator.pages
                    def move(path,collection=None):
                        result=pages(path,collection)
                        document=f.native.provision.store(f.native.provision.root/'trial-context-new-base').read()
                        if '/rulesets?' in path and document is not None and document['value']['phase']=='source-started' and not armed:
                            armed.append(True)
                            f.source.post('/graphql',dict(query='mutation($input:UpdateRefsInput!){updateRefs(input:$input){clientMutationId}}',
                                variables=dict(input=dict(repositoryId='fixture-source-node',clientMutationId='external',
                                    refUpdates=[dict(name='refs/heads/main',beforeOid=base,afterOid=external,force=False)]))))
                        return result
                    operator.pages=move
                writes=copy.deepcopy(f.source.writes)
                with patch.object(bootstrap,'installation_token',NATIVE_MINT),self.assertRaises(Refusal):
                    trial_controller.Native(f.preparer).transition_context('prompt','new-base',operator,admin,approve,f.tokens)
                self.assertTrue(armed)
                self.assertEqual(target.rules,rules)
                if fault=='withdrawn-issuer':
                    self.assertEqual(f.source.writes,writes)
                    self.assertEqual(f.registry.binding(),before)
                else:
                    self.assertEqual(len(f.source.writes),len(writes)+1)
                    self.assertEqual(f.source.writes[-1][0],'/graphql')
                    self.assertEqual(f.source.writes[-1][1]['variables']['input']['clientMutationId'],'external')
                return f.source.refs['main']
            with self.subTest(fault=fault):
                self.exercise(continuation=check,export_files=previous.spoof_fixture.forged_fixture.EXPORT)

    def test_policy_unknown_create_delete_and_registry_writes_are_not_replayed(self):
        for fault in ('create-ack','delete-ack','registry-ack','create-unknown','delete-unknown'):
            def check(*args):
                f=Context(self,args); f.through_tenth(); f.advance_case('new-base',123,125)
                f.prior_case('policy-transition',127)
                operator,target=f.operator,f.target; events=[]
                admin=f.apps(f.d['apps']['admin'],f.api.secrets['AGENTIC_ADMIN_PRIVATE_KEY'])
                native=trial_controller.Native(f.preparer)
                post,fetch=operator.post,operator.fetch
                if fault.startswith('create'):
                    def lose(path,data):
                        if path.endswith('/rulesets') and not events:
                            events.append(('create',copy.deepcopy(data)))
                            if fault=='create-ack': post(path,data)
                            raise OSError('unknown policy create')
                        return post(path,data)
                    operator.post=lose
                elif fault.startswith('delete'):
                    def lose(path,**kw):
                        if '/rulesets/' in path and kw.get('method')=='DELETE' and not events:
                            events.append(('delete',path))
                            if fault=='delete-ack': fetch(path,**kw)
                            raise OSError('unknown policy delete')
                        return fetch(path,**kw)
                    operator.fetch=lose
                else:
                    api_fetch=f.api.fetch
                    def lose(path,**kw):
                        result=api_fetch(path,**kw)
                        document=f.native.provision.store(f.native.provision.root/'trial-context-policy-transition').read()
                        if path.endswith('/git/refs/heads/agentic-registry') and kw.get('method')=='PATCH' and document is not None and (
                                document['value']['policy'] is not None and document['value']['policy'].get('registry_started')) and not events:
                            events.append(('registry',path))
                            raise OSError('unknown policy registry')
                        return result
                    f.api.fetch=lose
                with patch.object(bootstrap,'installation_token',NATIVE_MINT):
                    with self.assertRaises(OSError):
                        native.transition_context('prompt','policy-transition',operator,admin,digest,f.tokens)
                    source_writes=copy.deepcopy(f.source.writes); count=len(target.events)
                    f.clock[0]+=1
                    if fault.endswith('unknown'):
                        with self.assertRaisesRegex(Refusal,'unknown.*never replay'):
                            native.transition_context('prompt','policy-transition',operator,admin,digest,f.tokens)
                        self.assertIsNotNone(f.registry.binding()['fence']['pending'])
                        self.assertEqual(len(target.events),count)
                    else:
                        link=native.transition_context('prompt','policy-transition',operator,admin,digest,f.tokens)
                        value=__import__('trial_transition').read_native(f.origin,link,f.admission.record)
                        self.assertEqual(value['after'],f.registry.binding())
                        self.assertIsNone(value['after']['fence']['pending'])
                        self.assertNotEqual(value['after']['deployment']['policy']['epoch'],f.p['epoch'])
                    self.assertEqual(f.source.writes,source_writes)
                self.assertEqual(len(events),1)
                self.assertEqual(f.merges,[])
                return f.source.refs['main']
            with self.subTest(fault=fault):
                self.exercise(continuation=check,export_files=previous.spoof_fixture.forged_fixture.EXPORT)

    def test_human_late_cancellation_acceptance_and_unknown_results_cannot_close(self):
        for fault in ('cancelled','withdrawn-issuer','unknown','wrong-status'):
            def check(*args):
                f=Context(self,args); env=f.human_ready(); attempts=[]
                native=trial_controller.Native(f.preparer)
                with self.assertRaisesRegex(Refusal,'actual.*human transport'):
                    native.human_attempt('prompt',dict(id=f.p['reviewers'][0],type='User'))
                for identity in (dict(id=f.p['reviewers'][0],type='Bot'),dict(id=float(f.p['reviewers'][0]),type='User')):
                    human=f.human_transport(attempts); human.get=lambda path:identity
                    with self.assertRaises(Refusal): native.human_attempt('prompt',human)
                with self.assertRaises(Refusal): native.human_attempt('prompt',f.operator)
                self.assertIsNone(f.native.provision.store(f.native.provision.root/'trial-native-human').read())
                if fault in ('cancelled','withdrawn-issuer'):
                    post=f.origin.api.post
                    def withdraw(path,data):
                        result=post(path,data)
                        if path.endswith('/git/refs') and data['ref'].endswith('-human-update-human-intent'):
                            if fault=='cancelled':
                                job=next(j for j in f.remote.jobs if j['name']=='trial host denial')
                                job.update(status='completed',conclusion='cancelled')
                            else:
                                merge=f.admission.request['snapshot']['merge']
                                self.assertTrue(any(c['head_sha']==merge for c in f.checks))
                                f.checks[:]=[c for c in f.checks if c['head_sha']!=merge]
                        return result
                    f.origin.api.post=withdraw
                before=f.registry.binding()
                with self.assertRaises((Refusal,OSError)):
                    native.human_attempt('prompt',f.human_transport(attempts,fault))
                self.assertEqual(len(attempts),0 if fault in ('cancelled','withdrawn-issuer') else 1)
                with self.assertRaisesRegex(Refusal,'never replay'):
                    native.human_attempt('prompt',f.human_transport(attempts))
                def expire(seconds): f.clock[0]=f.admission.value['certificate']['expires']+1
                f.sleeper=expire
                with self.assertRaises(Refusal): f.consume_human(env)
                with self.assertRaises(Refusal): f.run('broker')
                with self.assertRaises(Refusal): f.finalize()
                self.assertEqual(f.registry.binding(),before)
                self.assertFalse(any(a['name'].startswith('trial-host-denial-') for a in f.remote.artifacts))
                self.assertEqual(f.merges,[])
                return f.source.refs['main']
            with self.subTest(fault=fault):
                self.exercise(continuation=check,export_files=previous.spoof_fixture.forged_fixture.EXPORT)

    def test_all_predecessor_capabilities_and_late_refs_fail_before_host_and_receipt_effects(self):
        def check(*args):
            from registry import trial_reference,TRIAL
            from test_authority_broker_evidence import stamp
            f=Context(self,args); env=f.human_ready(); original=f.admission.record
            entries=list(f.admission.value['history']); seen=[]; refs=set(); tokens=[f.api.secrets['AGENTIC_TRIAL_ORIGIN_TOKEN']]
            while entries:
                entry=entries.pop(0)
                if entry['revision'] in seen: continue
                seen.append(entry['revision'])
                prior=f.origin.blob(entry['revision'],TRIAL)[0]
                for value in (prior,dict(prior,execution=None),dict(prior,kind='trial-case-ready',execution=None)):
                    refs.add(trial_reference(value))
                journal=f.native.provision.store(f.native.provision.root/trial_controller.case_journal('trial-case-read-staging',prior['candidate'])).read()
                self.assertEqual(journal['value']['phase'],'revoked')
                tokens.append(journal['value']['credential']['token'])
                transition=prior['candidate'].get('transition')
                if transition is not None and transition['intent']['phase']=='current': entries.append(transition['intent']['prior'])
                if 'context' in prior['candidate']:
                    complete=__import__('trial_transition').read_native(f.origin,prior['candidate']['context'],original)
                    refs.add(trial_reference(complete))
                    claim=__import__('trial_transition').read_native(f.origin,complete['intent'],original)
                    refs.add(trial_reference(claim))
            self.assertEqual(len(set(tokens)),16)
            self.assertEqual(len(refs),49)
            for token in tokens:
                revoked=token in f.revoked; f.revoked.discard(token)
                jobs=copy.deepcopy(f.remote.jobs)
                with self.assertRaises(Refusal):
                    f.run('proof','reader',change=lambda value:value.update(**{trial_case.CaseReadStaging.NAME:token}))
                f.remote.jobs[:]=jobs
                if revoked: f.revoked.add(token)
            attempts=[]
            trial_controller.Native(f.preparer).human_attempt('prompt',f.human_transport(attempts))
            self.assertEqual(len(attempts),1)
            human=f.native.provision.store(f.native.provision.root/'trial-native-human').read()['value']
            for link in (human['intent'],human['completion']):
                refs.add(trial_reference(__import__('trial_transition').read_native(f.origin,link,original)))
            self.assertEqual(len(refs),51)
            pages=f.api.pages
            receipt_active=[]
            def exercise_refs(action,prefix,receipt=False):
                for ref in sorted(refs):
                    revision=f.origin.api.refs[ref]; armed=[]
                    def move(path,collection=None):
                        result=pages(path,collection)
                        if path.endswith('/runs/131/artifacts') and not armed and (not receipt or receipt_active):
                            armed.append(True); f.origin.api.refs[ref]=original['origin']['binding']['branch_head']
                        return result
                    f.api.pages=move
                    with self.assertRaises(Refusal): action()
                    f.api.pages=pages; f.origin.api.refs[ref]=revision
                    self.assertTrue(armed)
                    self.assertFalse(any(a['name'].startswith(prefix) for a in f.remote.artifacts))
            exercise_refs(lambda:f.consume_human(env),'trial-host-intent-')
            f.consume_human(env)
            next(j for j in f.remote.jobs if j['name']=='trial host denial').update(status='completed',conclusion='success',completed_at=stamp(f.clock[0]))
            from merge_receipts import ActionsReceipts
            matches=ActionsReceipts._matches
            def inventory(receipts,kind):
                receipt_active.append(True)
                try: return matches(receipts,kind)
                finally: receipt_active.clear()
            with patch.object(ActionsReceipts,'_matches',inventory):
                exercise_refs(lambda:f.run('broker'),'agentic-merge-',receipt=True)
            self.assertEqual(f.run('broker')['state'],'host-denied')
            from registry import Registry
            finalize=Registry.finalize_operation
            post,fetch=f.api.post,f.api.fetch
            effects=[]
            def capture_post(path,data):
                if '/git/' in path: effects.append((path,copy.deepcopy(data)))
                return post(path,data)
            def capture_fetch(path,**kwargs):
                if '/git/' in path and kwargs.get('method','GET')!='GET': effects.append((path,copy.deepcopy(kwargs)))
                return fetch(path,**kwargs)
            f.api.post,f.api.fetch=capture_post,capture_fetch
            terminal_refs=[ref for ref in refs if 'context-' in ref or '-human-' in ref]
            self.assertEqual(len(terminal_refs),6)
            for ref in terminal_refs:
                revision=f.origin.api.refs[ref]; armed=[]
                def move(registry,*args,**kwargs):
                    if registry.coordinates==f.registry.coordinates:
                        armed.append(True); f.origin.api.refs[ref]=original['origin']['binding']['branch_head']
                    return finalize(registry,*args,**kwargs)
                with patch.object(Registry,'finalize_operation',move),self.assertRaises(Refusal): f.finalize()
                f.origin.api.refs[ref]=revision
                self.assertTrue(armed); self.assertEqual(effects,[])
                self.assertIsNotNone(f.registry.binding()['fence']['pending'])
            f.api.post,f.api.fetch=post,fetch
            terminal=f.finalize(); self.assertEqual(f.observe()['binding'],terminal)
            self.assertEqual(len(attempts),1); self.assertEqual(f.merges,[])
            return f.source.refs['main']
        self.exercise(continuation=check,export_files=previous.spoof_fixture.forged_fixture.EXPORT)
