"""Held ordered broker suffix over independently prepared real Session inputs.

No trial admission, receipt production, native scheduling or restart coordinator
is supplied here. Source fixtures use explicitly synthetic ACTIVE regression
configurations; this is not an initial-qualification bridge.
"""
import copy
from urllib.parse import quote

import authority_release
from app_proofs import identity_record
from authority_github import Readers, current_snapshot
from authority_protocol import validate_deployment
from broker_refusal import BrokerRefusal
from broker_session import Session
from merge_receipts import ActionsReceipts
from merge_window import MergeSource, recover_merged
from qualification_cases import HOST_CASES
from qualification_record import BROKER_DENIALS
from trusted_ci_github import GitHub
from trusted_ci_policy import digest, positive, require, sha

CASES = (*BROKER_DENIALS, 'positive')


class BrokerCases:
    def __init__(self, sessions, merge_app=None, token_factory=GitHub):
        self.sessions, self.merge_app, self.token_factory = sessions, merge_app, token_factory
        self.started = False

    def run(self, prefix):
        authority_release.authorize('qualify-live')  # Before any transport access.
        return self._run(prefix)

    def _run(self, prefix):
        require(not self.started, 'broker cases already started; never replay')
        self.started = True
        require(isinstance(prefix, list) and [v['name'] for v in prefix] == list(HOST_CASES),
                'ordered host-prefix coordinate reservation required')
        require(isinstance(self.sessions, list) and [name for name, _ in self.sessions] == list(CASES) and
                all(type(session) is Session for _, session in self.sessions),
                'ordered real broker sessions required')
        reserved = [(v['pr'], v['head']) for v in prefix]
        bindings = []
        for _, session in self.sessions:
            binding = copy.deepcopy(session.registry.binding())
            d = validate_deployment(binding['deployment'])
            identity_record(d, session.identities)
            require(d['state'] == 'active' and d['adapter'] == 'github-actions', 'existing active Actions regression required')
            op = binding['fence']['pending']
            require(op is not None and op['kind'] == 'merge', 'prepared pending broker required')
            reserved.append((op['pr'], op['head']))
            bindings.append(binding)
        require(all(positive(pr) and sha(head) for pr, head in reserved) and
                len({pr for pr, _ in reserved}) == len(reserved) == len({head for _, head in reserved}),
                'full ordered inventory requires distinct PRs and heads')
        first = bindings[0]
        require(all(all(b[k] == first[k] for k in ('configuration_revision', 'deployment_digest', 'deployment'))
                    for b in bindings), 'broker suffix configuration differs')
        results = [self._case(name, session, binding) for (name, session), binding in zip(self.sessions, bindings)]
        return dict(cases=[record for record, _ in results], observations=[observation for _, observation in results],
                    hosted_qualified=False, enforcement_active=False)

    def _case(self, name, session, binding):
        d, op = binding['deployment'], binding['fence']['pending']
        p, source, clock = d['policy'], session.source, session.clock
        root = '/repos/' + p['repository']
        target = root + '/git/ref/heads/' + quote(p['target'], safe='')
        snapshot = current_snapshot(Readers(source, session.authority, d), d, op['pr'], op['run_id'], op['attempt'])
        require(all(op[k] == snapshot[k] for k in ('pr', 'head', 'base', 'merge')), 'prepared broker snapshot differs')
        commit = copy.deepcopy(source.get(root + '/git/commits/' + snapshot['merge']))
        require(commit.get('sha') == snapshot['merge'] and sha(commit['tree']['sha']) and
                [v['sha'] for v in commit['parents']] == [snapshot['base'], snapshot['head']],
                'actual synthetic broker commit differs')
        before = source.get(target)['object']['sha']
        require(before == snapshot['base'] and session.registry.binding() == binding, 'broker fixture moved before attempt')
        original, requests = session.merger, []
        class MeasuredMerge:
            def merge(self, repository, pr, head, timeout=30):
                require(not requests and (repository, pr, head, timeout) == (p['repository'], op['pr'], op['head'], 30),
                        'one exact broker merge request required')
                requests.append(dict(method='PUT', path=root + '/pulls/' + str(pr) + '/merge',
                                     body=dict(sha=head, merge_method='merge'), timeout=timeout))
                return merger.merge(repository, pr, head, timeout)
        refusal, outcome = None, None
        from service import _source_token
        def guard():
            require(session.registry.binding() == binding and clock() < d['expires'],
                    'broker case moved before merger credential admission')
        # Authenticate the actual own-App root and source-only token; final App
        # capability reports alone do not authenticate the token used for HTTP.
        with _source_token('merge', self.merge_app, session.authority, d, session.identities,
                           binding['configuration_revision'], clock, self.token_factory, guard) as scoped:
            merger = MergeSource(scoped.token, p['repository'], p['repository_id'])
            session.merger = MeasuredMerge()
            try:
                try:
                    outcome = session._run()
                except BrokerRefusal as error:
                    refusal = dict(code=error.code, observation=error.observation)
            finally:
                session.merger = original
        after = source.get(target)['object']['sha']
        evidence = dict(binding=binding, snapshot=snapshot, synthetic=commit, before=before, after=after,
                        actor=session.identities['apps']['merge']['actor_id'], requests=requests, refusal=refusal,
                        outcome=outcome)
        merged, parents, tree = None, [], None
        if name == 'positive':
            require(refusal is None and isinstance(outcome, dict) and outcome.get('state') == 'submitted' and
                    len(requests) == 1, 'fresh broker did not establish positive submission')
            store = ActionsReceipts(session.authority, session.registry.binding, session.job_id, clock, recovery=True)
            locator = store.find_for_recovery('dispatch')
            require(locator is not None, 'authenticated actual broker dispatch required')
            dispatch = store.authenticate(locator)
            require(dispatch['gate']['tree'] == commit['tree']['sha'], 'authorized tree differs from intended fixture')
            pr = copy.deepcopy(source.get(root + '/pulls/' + str(op['pr'])))
            actual = copy.deepcopy(source.get(root + '/git/commits/' + str(pr.get('merge_commit_sha'))))
            recovered = recover_merged(dispatch['gate'], pr, actual)
            merged, parents, tree = recovered['merge_commit'], [v['sha'] for v in actual['parents']], actual['tree']['sha']
            require(after == merged != before and tree == commit['tree']['sha'] and session.registry.binding() == binding,
                    'positive target or configuration differs')
            evidence.update(dispatch=dispatch, dispatch_locator=locator, recovery=recovered, pr=pr, actual=actual)
        else:
            require(refusal is not None and refusal['code'] == BROKER_DENIALS[name] and not requests and
                    outcome is None and after == before, 'broker did not establish the intended pre-dispatch refusal')
            current = session.registry.binding()
            if name == 'context-transition':
                require(current['configuration_revision'] != binding['configuration_revision'] and
                        current['deployment']['policy']['epoch'] != p['epoch'], 'actual configuration transition missing')
                evidence['current'] = current
                # Changed ownership cannot upload an old-context terminal receipt.
                # The existing fence remains held for independent pinned recovery.
            else:
                require(current == binding, 'unexpected broker context change')
                store = ActionsReceipts(session.authority, session.registry.binding, session.job_id, clock, recovery=True)
                locator = store.find_for_recovery('not-submitted')
                require(locator is not None and store.find_for_recovery('dispatch') is None,
                        'positive no-dispatch broker receipt required')
                evidence.update(terminal=store.authenticate(locator), terminal_locator=locator)
            require(current_snapshot(Readers(source, session.authority, d), d, op['pr'], op['run_id'], op['attempt']) == snapshot,
                    'negative candidate changed')
        record = dict(name=name, pr=op['pr'], head=op['head'], base=op['base'], merge=op['merge'], tree=commit['tree']['sha'],
            before=before, after=after, actor_id=evidence['actor'], request_sent=bool(requests),
            http_status=200 if requests else None, denial_category=None, denied_obligation=None,
            broker_refusal=None if name == 'positive' else refusal['code'], merge_commit=merged,
            merge_parents=parents, merge_tree=tree, evidence_digest=digest(evidence))
        return record, evidence
