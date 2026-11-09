"""Fresh job admissions consume authenticated case data, never native objects."""
import backend_test_support
import copy
import json
import unittest
from unittest.mock import patch

import merge_transport
import service
import trial_case
import app_proofs
from test_authority_app_proofs import AppAPI
from test_authority_broker_evidence import stamp
from trusted_ci_policy import Refusal
import test_authority_trial_controller as controller_fixture


class Fresh(controller_fixture.Connected):
    hosted_constructor = staticmethod(trial_case.Hosted.__init__)
    def stage(self,fault=None,lifetime=500):
        self.publication = trial_case.Publication(self.admission)
        hint = self.publication.publish('prompt')
        d = self.admission.record['origin']['binding']['deployment']
        root = AppAPI(d,app_proofs.load_identities(d),'reader')
        post = root.post
        def mint(*args):
            value = post(*args)
            if fault == 'mint': raise OSError('case token mint acknowledgement unknown')
            return dict(value,token='fresh-case-'+value['token'],expires_at=stamp(self.clock[0]+lifetime))
        root.post = mint
        self.reader=root
        def tokens(token):
            parent = root.token_api(token.removeprefix('fresh-case-'))
            outer = self
            class Read:
                def __init__(self): self.token = token
                def get(self,path):
                    if token in self.revoked: raise Refusal('revoked fixture case token')
                    return outer.origin.api.get(path)
                def pages(self,*args): return parent.pages(*args)
                def fetch(self,*args,**kwargs):
                    result = parent.fetch(*args,**kwargs)
                    self.revoked.add(token)
                    return result
            Read.revoked = self.revoked
            return Read()
        self.revoked = set()
        self.staging = trial_case.CaseReadStaging(self.publication,root,tokens)
        if fault == 'secret': self.api.lost_secret=True
        self.credential = self.staging.run()
        self.origin_factory = tokens
        self.case_token = self.api.secrets[trial_case.CaseReadStaging.NAME]
        self.assert_fresh = self.case_token != self.api.secrets['AGENTIC_TRIAL_ORIGIN_TOKEN']
        return hint

    def handoff(self, lost_bind=False, lifetime=500):
        hint=self.stage(lifetime=lifetime)
        env = self.job('trial case handoff','trial_case_handoff')
        env.update(GITHUB_REPOSITORY=self.p['authority_repository'],GITHUB_TOKEN='case-actions-read',
                   **{trial_case.CaseReadStaging.NAME:self.case_token})
        location = service._case_producer(env,hint,'fixture-node','handoff',clock=lambda:self.clock[0],
            api_factory=lambda token:self.api if token=='case-actions-read' else self.origin_factory(token),uploader_factory=lambda *a:self.upload)
        next(j for j in self.remote.jobs if j['name']=='trial case handoff').update(status='completed',conclusion='success',completed_at=stamp(self.clock[0]))
        if lost_bind:
            post=self.origin.api.post; writes=[]
            def send(path,body):
                result=post(path,body)
                if path.endswith('/git/refs') and body['ref'].endswith('-case-execution'):
                    writes.append(copy.deepcopy(body)); raise OSError('lost case binding acknowledgement')
                return result
            self.origin.api.post=send
            with self.owner.assertRaises(OSError): self.publication.bind(self.credential,location)
            self.publication=trial_case.Publication(self.admission)
            self.hint=self.publication.bind(self.credential,location)
            self.owner.assertEqual(len(writes),1)
            self.origin.api.post=post
        else:
            self.hint = self.publication.bind(self.credential,location)
        self.fresh = []

    def run(self,role,purpose=None,change=None):
        key = purpose+'_'+role.replace('-','_') if purpose else role.replace('-','_')
        name = ('publication controls' if role == 'publication-controls' else 'final proof' if role == 'final-proof' else role)
        name += ' ('+(purpose or str(self.admission.candidate['submitted']['pr']))+')'
        env = self.job(name,key)
        purposes = [purpose] if purpose else ['merge','reader'] if role == 'broker' else ['admin'] if role in ('controls','publication-controls') else ['issuer'] if role == 'publish' else ['reader']
        env.update({'AGENTIC_'+p.upper()+'_PRIVATE_KEY':self.api.secrets['AGENTIC_'+p.upper()+'_PRIVATE_KEY'] for p in purposes})
        env.update(GITHUB_REPOSITORY=self.p['authority_repository'],GITHUB_TOKEN='case-actions-read',
                   **{trial_case.CaseReadStaging.NAME:self.case_token})
        if change is not None: change(env)
        construct = self.hosted_constructor
        def observe(value,*args,**kwargs):
            construct(value,*args,**kwargs)
            self.fresh.append(value)
        try:
            with patch.object(trial_case.Hosted,'__init__',observe):
                return service._case_producer(env,self.hint,'fixture-node',role,clock=lambda:self.clock[0],
                    api_factory=lambda token:self.api if token=='case-actions-read' else self.origin_factory(token),
                    app_factory=self.apps,token_factory=self.tokens,uploader_factory=lambda *a:self.upload,
                    verifier=self.verify,sleeper=getattr(self,'sleeper',lambda s:None))
        finally:
            next(j for j in self.remote.jobs if j['name']==name).update(status='completed',conclusion='success',completed_at=stamp(self.clock[0]))

    def finalize(self):
        env = self.job('finalize','finalize')
        env.update(GITHUB_REPOSITORY=self.p['authority_repository'],GITHUB_TOKEN='case-actions-read',
                   AGENTIC_ADMIN_PRIVATE_KEY=self.api.secrets['AGENTIC_ADMIN_PRIVATE_KEY'],
                   **{trial_case.CaseReadStaging.NAME:self.case_token})
        return service._case_producer(env,self.hint,'fixture-node','finalize',clock=lambda:self.clock[0],
            api_factory=lambda token:self.api if token=='case-actions-read' else self.origin_factory(token),
            app_factory=self.apps,token_factory=self.tokens)


@unittest.skipIf(getattr(controller_fixture.TrialController,'__unittest_skip__',False), 'optional cryptography required')
class TrialCase(unittest.TestCase):
    fixture = controller_fixture.TrialController.fixture
    prepared = controller_fixture.TrialController.prepared
    connected = controller_fixture.TrialController.connected
    configured = controller_fixture.TrialController.configured
    exercise = controller_fixture.TrialController.exercise
    prepare = controller_fixture.TrialController.prepare

    def test_separate_case_producers_complete_and_recover(self):
        def check(*args):
            import trial_case
            f = Fresh(self, args)
            f.prepare()
            f.handoff()
            self.assertTrue(f.assert_fresh)
            self.assertEqual(set(f.hint),{'origin','revision'})
            f.published()
            with patch.object(merge_transport,'isolated',side_effect=f.transport): result=f.run('broker')
            self.assertEqual(result['state'],'submitted')
            terminal=f.finalize()
            self.assertEqual(terminal['fence']['completed'][-1]['kind'],'merged')
            self.assertIsNone(terminal['fence']['pending'])
            self.assertEqual(len(f.merges),1)
            self.assertEqual(len({id(a) for a in f.fresh}),len(f.fresh))
            self.assertGreaterEqual(len(f.fresh),15)
            for value in f.fresh:
                for name in ('native','provision','journal','session'): self.assertFalse(hasattr(value,name))
            f.staging.revoke()
            self.assertIn(f.case_token,f.revoked)
            with self.assertRaises(Refusal): f.run('broker')
            return f.source.refs['main']
        self.exercise(continuation=check)

    def test_withdrawn_review_denies_and_fresh_terminal_role_closes_without_merge(self):
        def check(*args):
            f=Fresh(self,args); f.prepare(); f.handoff(); f.published()
            f.reviews=[]
            with patch.object(merge_transport,'isolated',side_effect=AssertionError('denial dispatched')),self.assertRaisesRegex(Refusal,'independent approval'):
                f.run('broker')
            self.assertEqual(f.merges,[])
            self.assertTrue(any(a['name'].endswith('-not-submitted') for a in f.remote.artifacts))
            self.assertFalse(any(a['name'].endswith('-dispatch') for a in f.remote.artifacts))
            next(j for j in f.remote.jobs if j['name'].startswith('broker ('))['conclusion']='failure'
            result=f.finalize()
            self.assertEqual(result['fence']['completed'][-1]['kind'],'not-submitted')
            self.assertIsNone(result['fence']['pending'])
            with self.assertRaises(Refusal): f.finalize()
        self.exercise(continuation=check)

    def test_unknown_merge_recovers_with_only_published_data_and_no_native_owner(self):
        def check(*args):
            f=Fresh(self,args); f.prepare(); f.handoff(lost_bind=True); f.published(); f.lose_merge_ack=True
            with patch.object(merge_transport,'isolated',side_effect=f.transport): result=f.run('broker')
            self.assertEqual(result['state'],'unknown'); self.assertEqual(len(f.merges),1)
            # Recovery reads authenticated remote state in a newly constructed
            # producer. Any accidental native access must fail this regression.
            with patch.object(f.admission,'guard',side_effect=AssertionError('native owner reached from fresh job')):
                result=f.finalize()
            self.assertEqual(result['fence']['completed'][-1]['kind'],'merged')
            self.assertEqual(len(f.merges),1)
            return f.source.refs['main']
        self.exercise(continuation=check)

    def test_public_entrypoint_holds_before_access(self):
        import authority_release
        with self.assertRaises(authority_release.Held): service.case_producer(None,None,None,None)

    def test_substituted_execution_capability_and_certificate_fail_before_outputs(self):
        def check(*args):
            f=Fresh(self,args); f.prepare(); f.handoff()
            before=len(f.remote.artifacts)
            for change in (
                lambda env:env.update(GITHUB_RUN_ID='100'),
                lambda env:env.update(GITHUB_SHA='0'*40),
                lambda env:env.update(GITHUB_RUN_ATTEMPT='2'),
                lambda env:env.update(AGENTIC_MODEL_VAULT_KEY='another-purpose'),
                lambda env:env.update(AGENTIC_TRIAL_ORIGIN_TOKEN=f.api.secrets['AGENTIC_TRIAL_ORIGIN_TOKEN']),
                lambda env:env.update(**{trial_case.CaseReadStaging.NAME:f.api.secrets['AGENTIC_TRIAL_ORIGIN_TOKEN']}),
            ):
                with self.assertRaises(Refusal): f.run('verify',change=change)
                self.assertEqual(len(f.remote.artifacts),before)
            # A different same-scope fresh token is not the consumed token.
            other='fresh-case-SYNTHETIC-TOKEN-0-substitution'
            class Other:
                token=other
                def get(self,path): return f.origin.api.get(path)
                def pages(self,*args): return [{'id':f.origin.coordinates['repository_id']}]
            factory=f.origin_factory; f.origin_factory=lambda token:Other()
            with self.assertRaisesRegex(Refusal,'exact fresh consumed'): f.run('verify')
            f.origin_factory=factory
            # Even a transport-authenticated CLOSED archive must bind this case
            # and the exact new token; the old handshake is insufficient.
            artifact=next(a for a in f.remote.artifacts if a['name'].startswith('trial-case-handoff-'))
            import io,zipfile
            with zipfile.ZipFile(io.BytesIO(f.remote.raw[artifact['id']])) as archive:
                value=json.loads(archive.read('trial-case-handoff.json'))
            value['token_digest']='0'*64
            f.remote.replace(artifact['id'],value,'trial-case-handoff.json')
            with self.assertRaisesRegex(Refusal,'closed case consumer'): f.run('verify')
            self.assertEqual(len(f.remote.artifacts),before)
        self.exercise(continuation=check)

    def test_uncertain_case_publication_recovers_only_exact_committed_ref(self):
        for committed in (True,False):
            def check(*args):
                f=Fresh(self,args); f.prepare()
                publication=trial_case.Publication(f.admission)
                send=f.origin.api.post; writes=[]
                def post(path,body):
                    if path.endswith('/git/refs') and body['ref'].endswith('-case'):
                        writes.append(copy.deepcopy(body))
                        if committed: send(path,body)
                        raise OSError('case ref acknowledgement unknown')
                    return send(path,body)
                f.origin.api.post=post
                with self.assertRaises(OSError): publication.publish('prompt')
                # Fresh coordinator retains only its protected ownership journal.
                resumed=trial_case.Publication(f.admission)
                if committed:
                    hint=resumed.publish('prompt')
                    self.assertEqual(trial_case.read(f.origin,hint['revision'],lambda:f.clock[0])[0]['kind'],'trial-case-handoff')
                else:
                    from trusted_ci_github import HostRefusal
                    with self.assertRaises((Refusal,HostRefusal)): resumed.publish('prompt')
                self.assertEqual(len(writes),1)
            with self.subTest(committed=committed): self.exercise(continuation=check)

    def test_unknown_case_mint_and_secret_write_never_repeat_effects(self):
        for fault in ('mint','secret'):
            def check(*args):
                f=Fresh(self,args); f.prepare()
                with self.assertRaises(OSError): f.stage(fault)
                if fault == 'mint':
                    with self.assertRaisesRegex(Refusal,'mint remains unknown'): f.staging.run()
                    self.assertNotIn(trial_case.CaseReadStaging.NAME,f.api.secret_writes)
                else:
                    value=f.staging.run()
                    self.assertEqual(value['token_digest'],__import__('trusted_ci_policy').digest(f.api.secrets[trial_case.CaseReadStaging.NAME]))
                    self.assertEqual(f.api.secret_writes.count(trial_case.CaseReadStaging.NAME),1)
                self.assertEqual(len(f.reader.visible),1)
            with self.subTest(fault=fault): self.exercise(continuation=check)

    def test_terminal_artifact_read_cannot_outlive_consumed_case_delegation(self):
        def check(*args):
            f=Fresh(self,args); f.prepare(); f.handoff(); f.published(); f.reviews=[]
            with self.assertRaises(Refusal): f.run('broker')
            artifact=next(a for a in f.remote.artifacts if a['name'].endswith('-not-submitted'))
            fetch=f.api.fetch; writes=[]; post=f.api.post
            def late(path,**kwargs):
                value=fetch(path,**kwargs)
                if path.endswith('/actions/artifacts/'+str(artifact['id'])+'/zip'):
                    f.clock[0]=f.credential['expires']+1
                return value
            def write(path,body): writes.append(path); return post(path,body)
            f.api.fetch,f.api.post=late,write
            pending=f.registry.binding()
            with self.assertRaisesRegex(Refusal,'expired'): f.finalize()
            self.assertEqual(writes,[])
            self.assertEqual(f.registry.binding(),pending)
        self.exercise(continuation=check)

    def test_consumed_case_delegation_retains_dispatch_sixty_second_margin(self):
        def check(*args):
            f=Fresh(self,args); f.prepare(); f.handoff(lifetime=50); f.published()
            with patch.object(merge_transport,'isolated',side_effect=f.transport):
                try: result=f.run('broker')
                except Refusal: result=None
            self.assertEqual(f.merges,[])
            if result is not None: self.assertNotEqual(result['state'],'submitted')
            self.assertIsNotNone(f.registry.binding()['fence']['pending'])
        self.exercise(continuation=check)


if __name__ == '__main__': unittest.main()
