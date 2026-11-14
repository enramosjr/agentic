"""Held native preparation of distinct candidates from an exact CLOSED trial.

Candidates reserve the ordered inventory; they are not completed case inputs,
task admission, a trial certificate, case outcomes or qualification receipts.
Production entrypoints remain ACTIVE-only. No review endpoint is called.
"""
import copy
import time

import authority_release
from coding_parent import _FencedSource
from controls import observe
from qualification_cases import HOST_CASES
from qualification_broker import CASES as BROKER_CASES
from service import _source_token
import submission
from trial_handoff import Native
from trusted_ci_github import GitHub
from trusted_ci_policy import digest, object_fields, positive, require

CASES = (*HOST_CASES, *BROKER_CASES)


class Prepare:
    def __init__(self, native, coding, token_factory=GitHub, origin_token_factory=GitHub):
        self.native, self.coding = native, coding
        self.token_factory, self.origin_token_factory = token_factory, origin_token_factory

    def run(self, prompt):
        authority_release.authorize('qualify-live')  # Before any native/storage/API access.
        return self._run(prompt)

    def _run(self, prompt, source=None):
        require(type(self.native) is Native, 'actual native completed trial required')
        n, c = self.native, self.native.provision
        source = source or c.api
        worker = n.observe(prompt, source, self.origin_token_factory)
        completed = n._completion(prompt, source)
        require(completed['result'] == worker, 'closed trial changed during candidate preparation')
        r, proof, files = completed['record'], completed['proof'], completed['files']
        binding, origin = r['trial'], r['origin']['binding']
        d, p = binding['deployment'], binding['deployment']['policy']
        require(d['adapter'] == 'github-actions' and d['state'] == 'qualification' and d['qualification'] is None,
                'unqualified disposable Actions trial required')
        from trial_specimen import strict
        eligibility=None
        if strict(files):
            eligibility_document=c.store(c.root/'trial-eligibility').read()
            require(eligibility_document is not None and eligibility_document['value']['phase']=='complete','strict worker eligibility required before any reservation')
            eligibility=eligibility_document['value']['link']
            from trial_eligibility import authenticate
            authenticate(c.session.registry,r,worker,eligibility,c.clock,source,n.registry.api)
        intent = dict(kind='native-trial-candidates', revision=completed['retained']['value']['revision_bound'],
            record_digest=digest(r), worker=worker, artifact_digest=proof['artifact_digest'],
            export_digest=digest(submission.export_manifest(files)), cases=list(CASES))
        if eligibility is not None: intent['eligibility']=eligibility
        journal = c.store(c.root / 'trial-candidates')
        document = journal.read()
        session, original, trial = c.session, c.session.registry, n.registry
        provisioned = copy.deepcopy(c.document)

        def live(force=False):
            if eligibility is not None:
                require(c.store(c.root/'trial-eligibility').read()==eligibility_document,'owned strict worker eligibility changed')
                from trial_eligibility import authenticate
                authenticate(original,r,worker,eligibility,c.clock)
            require(r['created'] <= c.clock() < min(r['expires'], d['expires'], origin['fence']['pending']['execution_deadline']),
                    'native case preparation expired')
            require(journal.read() == document and c.store(c.root / 'trial-workflow').read() == completed['retained'],
                    'native case preparation journal changed')
            require(c.session is session and session.registry is original and n.registry is trial and
                    session.owner == r['origin']['owner'] and session.scope == r['origin']['scope'] and
                    c.store(c.root / 'trial').read() == provisioned,
                    'native case owner or provisioning changed')
            session._owned(origin)
            if force:
                # Immutable handoff, release inventories and worker blobs were
                # authenticated above. Reobserve their live pointers, rather than
                # recursively redownloading them inside every mutation budget.
                original_branch = original.unchanged(origin)
                trial_branch = trial.unchanged(binding)
                repo = source.get('/repos/' + p['repository'])
                require(repo.get('id') == p['repository_id'] and repo.get('private') is True and
                        repo.get('owner', {}).get('id') == r['pair']['identities']['owner_id'] and
                        repo.get('default_branch') == p['target'], 'disposable source identity changed')
                require(submission.existing_ref(source, '/repos/' + p['repository'], p['target']) == r['pair']['fixture_revision'],
                        'trial target moved during candidate preparation')
                require(original.ref(original.coordinates['registry_branch']) == origin['branch_head'] and
                        original.ref(original_branch) == origin['software_revision'] and
                        original.ref('agentic-trial-' + r['task_id']) == r['execution']['publication_revision'] and
                        original.ref('agentic-trial-' + r['task_id'] + '-execution') == intent['revision'],
                        'original handoff moved during final trial observation')
                require(trial.ref(trial.coordinates['registry_branch']) == binding['branch_head'] and
                        trial.ref(trial_branch) == binding['software_revision'],
                        'trial moved during final original observation')
                live()

        live(True)
        if document is None:
            issued = c.clock()
            requests = [dict(schema_version=2, task_id=digest(dict(intent=intent, name=name))[:32],
                configuration_revision=binding['configuration_revision'], deployment_digest=binding['deployment_digest'],
                base=r['pair']['fixture_revision'], issued=issued,
                run_id=r['execution']['handshake']['run_id'], attempt=1) for name in CASES]
            document = journal.write(None, dict(intent=intent, issued=issued, requests=requests, candidates=[], pending=None))
        state = copy.deepcopy(document['value'])
        object_fields(state, ('intent', 'issued', 'requests', 'candidates', 'pending'), 'retained native candidates')
        require(positive(state['issued']) and r['created'] <= state['issued'] <= c.clock(), 'retained candidate time differs')
        expected = [dict(schema_version=2, task_id=digest(dict(intent=intent, name=name))[:32],
            configuration_revision=binding['configuration_revision'], deployment_digest=binding['deployment_digest'],
            base=r['pair']['fixture_revision'], issued=state['issued'],
            run_id=r['execution']['handshake']['run_id'], attempt=1) for name in CASES]
        require(state['intent'] == intent and state['requests'] == expected and isinstance(state['candidates'], list) and
                len(state['candidates']) <= len(CASES) and
                (state['pending'] is None or type(state['pending']) is int and
                 state['pending'] == len(state['candidates']) < len(CASES)) and
                [v['name'] for v in state['candidates']] == list(CASES[:len(state['candidates'])]),
                'resume only exact retained native case inventory')
        # Re-authenticate completed cases without any source-write capability.
        with _source_token('coding', self.coding, n.registry.api, d, r['pair']['identities'],
                           binding['configuration_revision'], c.clock, self.token_factory, lambda:live(True)) as scoped:
            def no_write(): require(False, 'uncertain or completed case permits read-only recovery only')
            readonly = _FencedSource(scoped, live, no_write)
            for index, candidate in enumerate(state['candidates']):
                require(submission._submit(readonly, d, state['requests'][index], files) == candidate['submitted'],
                        'completed case candidate changed')
            for index in range(len(state['candidates']), len(CASES)):
                request = state['requests'][index]
                recovering = state['pending'] is not None
                require(not recovering or state['pending'] == index, 'another case remains pending')
                live(True)
                started, monotonic = c.clock(), time.monotonic()
                facts = observe(c.api, d)
                live(True)
                require(facts['base'] == request['base'], 'case controls belong to another target')
                def authorize():
                    require(started <= c.clock() <= started + 30 and time.monotonic() <= monotonic + 30,
                            'original case control observation expired')
                authorize()
                if not recovering:
                    state['pending'] = index
                    document = journal.write(document, state)
                fenced = _FencedSource(scoped, live, no_write if recovering else authorize)
                submitted = submission._submit(fenced, d, request, files)
                live(True)
                prior = [worker['submitted'], *[v['submitted'] for v in state['candidates']]]
                require(all(submitted['pr'] != v['pr'] and submitted['head'] != v['head'] for v in prior) and
                        submitted['tree'] == worker['submitted']['tree'], 'distinct exact trial candidate required')
                candidate=dict(name=CASES[index], submitted=submitted, controls_digest=digest(facts))
                if eligibility is not None: candidate['eligibility']=eligibility
                state['candidates'].append(candidate)
                state['pending'] = None
                document = journal.write(document, state)
            live(True)
        return dict(worker=worker, candidates=copy.deepcopy(state['candidates']),
                    cases_executed=False, hosted_qualified=False, enforcement_active=False)
