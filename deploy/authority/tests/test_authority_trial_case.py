"""Fresh job admissions consume authenticated case data, never native objects."""
import backend_test_support
import copy
import json
import unittest
from unittest.mock import patch

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

    # Fresh positive producers, one actual merge and native recovery now live in
    # the required strict16 runtime lane. Ordinary review denial and uncertain
    # merge mechanics remain in broker_evidence/broker_finalize component tests.

    def test_public_entrypoint_holds_before_access(self):
        import authority_release
        with self.assertRaises(authority_release.Held): service.case_producer(None,None,None,None)

    def test_substituted_execution_capability_and_certificate_fail_before_outputs(self):
        def check(*args):
            f=Fresh(self,args); f.prepare(name='direct-push'); f.handoff()
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
                f=Fresh(self,args); f.prepare(name='direct-push')
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
                f=Fresh(self,args); f.prepare(name='direct-push')
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
            from test_authority_trial_host_case import HostFixture
            f=HostFixture(self,args); f.prepared_host(); f.host(); f.run('broker')
            artifact=next(a for a in f.remote.artifacts if a['name'].endswith('-host-denied'))
            expiry=f.launch.document['value']['credential']['expires']
            fetch=f.api.fetch; writes=[]; post=f.api.post
            def late(path,**kwargs):
                value=fetch(path,**kwargs)
                if path.endswith('/actions/artifacts/'+str(artifact['id'])+'/zip'):
                    f.clock[0]=expiry+1
                return value
            def write(path,body): writes.append(path); return post(path,body)
            f.api.fetch,f.api.post=late,write
            pending=f.registry.binding()
            with self.assertRaisesRegex(Refusal,'expired'): f.finalize()
            self.assertEqual(writes,[])
            self.assertEqual(f.registry.binding(),pending)
        from test_authority_trial_launch import Launch
        with patch.object(self,'prepared',lambda:Launch.prepared(self)):
            self.exercise(continuation=check)

    def test_consumed_delegation_and_blocking_guard_bound_semantic_gate_window(self):
        # Semantic validation of genuine first-case Hosted data cannot dispatch:
        # _dispatch separately rejects this negative reservation before reads.
        import merge_window
        from test_authority_merge_window import gate
        for fault in ('short-delegation','late-guard','broken-clock-control'):
            def check(*args):
                f=Fresh(self,args); f.prepare(name='direct-push')
                f.handoff(lifetime=50 if fault=='short-delegation' else 500)
                f.run('verify')
                a=f.fresh[-1]; b=a.binding; p=b['deployment']['policy']; now=f.clock[0]
                q=a.qualification(b); g=gate()
                for key in ('operation_id','repository_id','target','configuration_revision','deployment_digest',
                            'pr','head','base','merge','workflow_sha','run_id','attempt'):
                    g[key]=b['fence']['pending'][key]
                g.update(sequence=b['fence']['sequence'],authority_repository_id=p['authority_repository_id'],
                    epoch=p['epoch'],check_name=p['check_name'],qualification_digest=q['qualification_digest'],
                    tree=a.candidate['submitted']['tree'],issued=now,expires=now+120,
                    readback_started=now,readback_completed=now)
                g['valid_until']={key:now+150 for key in merge_window.EXPIRING}
                g['valid_until']['deployment']=b['deployment']['expires']
                g['valid_until']['qualification']=q['expires']
                if fault=='short-delegation':
                    self.assertEqual(q['expires'],f.credential['expires'])
                    with self.assertRaisesRegex(Refusal,'dispatch safety window'):
                        merge_window._validate(g,b,now,a,clock=lambda:f.clock[0])
                else:
                    self.assertIs(merge_window._validate(g,b,now,a,clock=lambda:f.clock[0]),g)
                    guard=a.guard
                    def late(*args,**kwargs):
                        result=guard(*args,**kwargs); f.clock[0]+=31; return result
                    with patch.object(a,'guard',late):
                        if fault=='late-guard':
                            with self.assertRaisesRegex(Refusal,'stale, future or too short'):
                                merge_window._validate(g,b,now,a,clock=lambda:f.clock[0])
                        else:
                            # Deliberately omitting the dispatch clock reproduces
                            # the stale sample; historical-only semantics pass.
                            self.assertIs(merge_window._validate(g,b,now,a),g)
                self.assertEqual(f.merges,[])
                self.assertIsNotNone(f.registry.binding()['fence']['pending'])
            with self.subTest(fault=fault): self.exercise(continuation=check)

if __name__ == '__main__': unittest.main()
