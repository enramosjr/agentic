"""Held producers for the ordered host-negative qualification prefix.

Consumes independently prepared PRs and closed verifier/publication observations.
It makes real protected-update attempts; it never creates candidate reviews or a
qualification receipt. The fresh-broker suffix and native trial orchestration are
separate unfinished producers. Public execution remains release-held.
"""
import copy
from urllib.parse import quote

import authority_release
import checks
from app_proofs import identity_record
from authority_github import Readers, current_snapshot
from authority_protocol import validate_deployment
from provenance import authenticated_document, validate_evidence
from registry import DOCUMENT
from trusted_ci_github import GitHub, HostRefusal, independent_approval
from trusted_ci_policy import digest, object_fields, positive, require, sha, validate_snapshot
from trusted_ci_qualification import CASES, check_mutations, check_negative


HOST_CASES = (*(name for name in CASES if name != 'positive'), 'human-update', 'coding-update')
FIELDS = ('name snapshot evidence coordinates expected_failure mutations prior').split()
ACCEPTANCE = ('direct-push', 'missing-approval', 'human-update', 'coding-update')
NEGATIVE = ('bad-acceptance', 'replaced-checks', 'forged-records')
STALE = ('new-head', 'new-base', 'policy-transition')


def negative_evidence(value, d, snapshot, revision, job_id, criterion):
    """Authenticate failed observations separately from success-only admission.

    The caller authenticates the closed job/archive first. This cannot be used by
    publication or broker authorization, whose validate_evidence remains strict.
    """
    validate_deployment(d)
    object_fields(value, ('schema_version', 'kind', 'registry_revision', 'result'), 'negative authority evidence')
    require(type(value['schema_version']) is int and value['schema_version'] == 2 and
            d['adapter'] == 'github-actions' and value['kind'] == 'actions' and
            sha(revision) and value['registry_revision'] == revision and positive(job_id),
            'negative authority registry or adapter differs')
    result = value['result']
    object_fields(result, ('schema_version', 'report', 'cleanup_complete', 'enforcement_active'), 'negative execution result')
    require(type(result['schema_version']) is int and result['schema_version'] == 2 and
            result['cleanup_complete'] is True and result['enforcement_active'] is False,
            'negative verifier cleanup did not complete')
    report = result['report']
    object_fields(report, ('schema_version', 'deployment_digest', 'generation', 'snapshot', 'adapter',
                           'execution', 'outcomes'), 'negative execution report')
    require(type(report['schema_version']) is int and report['schema_version'] == 2 and
            report['deployment_digest'] == digest(d) and type(report['generation']) is int and
            report['generation'] == d['generation'] and report['adapter'] == d['adapter'],
            'negative verifier deployment differs')
    execution = report['execution']
    object_fields(execution, ('run_id', 'attempt', 'job_id', 'account', 'resource'), 'negative execution')
    resource = 'github-actions:' + d['policy']['authority_repository'] + ':' + d['policy']['workflow']
    require(all(positive(execution[k]) for k in ('run_id', 'attempt', 'job_id')) and
            execution == dict(run_id=snapshot['run_id'], attempt=snapshot['run_attempt'], job_id=job_id,
                              account=d['account'], resource=resource) and d['resources']['actions_resource'] == resource,
            'negative verifier execution differs')
    check_negative(dict(schema_version=1, snapshot=report['snapshot'], outcomes=report['outcomes']),
                   d['policy'], snapshot, criterion)
    return report


class HostCases:
    def __init__(self, registry, source, authority, identities, coding, merger, human, clock, token_factory=GitHub):
        self.registry, self.source, self.authority, self.identities = registry, source, authority, identities
        self.coding, self.merger, self.human, self.clock = coding, merger, human, clock
        self.token_factory = token_factory
        self.started = False

    def run(self, manifest):
        authority_release.authorize('qualify-live')  # Before any transport access.
        return self._run(manifest)

    def _guard(self):
        require(self.registry.binding() == self.binding and self.clock() < self.d['expires'],
                'host qualification configuration changed or expired')

    def _success(self, snapshot, locator, coordinates, d=None):
        d = self.d if d is None else d
        proof = authenticated_document(self.authority, d, locator, 'evidence', snapshot['pr'], self.clock())
        validate_evidence(proof['document'], d, snapshot, coordinates['configuration_revision'], proof['job_id'], self.clock())
        require(coordinates['evidence_job_id'] == proof['job_id'] and
                coordinates['evidence_digest'] == digest(proof['document']), 'acceptance evidence binding differs')
        check = checks.current(self.source, d, snapshot, coordinates, self.clock())
        return dict(proof=proof, check=check, coordinates=coordinates)

    def _prerequisites(self, case):
        name, s, p = case['name'], case['snapshot'], self.d['policy']
        root = '/repos/' + p['repository']
        pr = self.source.get(root + '/pulls/' + str(s['pr']))
        require(pr.get('mergeable') is True, 'unresolved or conflicted fixture cannot establish a denial')
        entries = self.source.pages(root + '/commits/' + s['merge'] + '/check-runs?filter=all', 'check_runs')
        success = [c for c in entries if c.get('name') == p['check_name'] and
                   c.get('app', {}).get('id') == p['app_id'] and c.get('status') == 'completed' and
                   c.get('conclusion') == 'success']
        evidence = dict(snapshot=s, checks=entries)
        if name in ACCEPTANCE:
            evidence['acceptance'] = self._success(s, case['evidence'], case['coordinates'])
        else:
            require(not success, 'negative fixture already has authoritative success')
        if name in NEGATIVE:
            proof = authenticated_document(self.authority, self.d, case['evidence'], 'evidence', s['pr'], self.clock())
            negative_evidence(proof['document'], self.d, s, self.binding['configuration_revision'],
                              proof['job_id'], case['expected_failure'])
            check_mutations(self.source, p, case, s)
            evidence['negative'] = proof
            evidence['mutations'] = case['mutations']
        rules = self.source.pages(root + '/rules/branches/' + quote(p['target'], safe=''))
        obligations = [v for rule in rules if rule['type'] == 'required_status_checks'
                       for v in rule['parameters']['required_status_checks']]
        require(any(v['context'] == p['check_name'] and v.get('integration_id') == p['app_id'] for v in obligations),
                'current exact issuer obligation missing')
        for obligation in obligations:
            if (obligation['context'], obligation.get('integration_id')) == (p['check_name'], p['app_id']):
                continue
            require(any(c.get('name') == obligation['context'] and
                        c.get('app', {}).get('id') == obligation.get('integration_id') and
                        c.get('head_sha') == s['merge'] and c.get('status') == 'completed' and
                        c.get('conclusion') == 'success' for c in entries),
                    'another host obligation did not pass on this merge')
        evidence['rules'] = rules
        if name == 'missing-approval':
            reviews = self.source.pages(root + '/pulls/' + str(s['pr']) + '/reviews')
            require(not any(r['state'] == 'APPROVED' and r['commit_id'] == s['head'] for r in reviews),
                    'missing-approval fixture has candidate approval')
        else:
            reviews = independent_approval(self.source, p, pr, human=True)
        evidence['reviews'] = reviews
        if name == 'spoofed-source':
            require(any(c.get('name') == p['check_name'] and c.get('app', {}).get('id') != p['app_id'] and
                        c.get('status') == 'completed' and c.get('conclusion') == 'success' and
                        c.get('head_sha') == s['merge'] for c in entries), 'actual spoofed issuer success missing')
        if name in STALE:
            prior = case['prior']
            object_fields(prior, ('deployment', 'snapshot', 'evidence', 'coordinates', 'registry_revision'), 'prior acceptance')
            old = validate_deployment(prior['deployment'])
            old_s = validate_snapshot(prior['snapshot'], old['policy'])
            revision = prior['coordinates']['configuration_revision']
            require(sha(prior['registry_revision']) and
                    self.registry.blob(prior['registry_revision'], DOCUMENT) == (old, revision) and
                    all(old['policy'][k] == p[k] for k in ('repository', 'repository_id', 'authority_repository',
                                                        'authority_repository_id', 'target')) and
                    old_s['pr'] == s['pr'] and old_s['merge'] != s['merge'], 'prior authority or candidate differs')
            commit = self.source.get(root + '/git/commits/' + old_s['merge'])
            require(commit.get('sha') == old_s['merge'] and
                    [v['sha'] for v in commit['parents']] == [old_s['base'], old_s['head']],
                    'prior success is not bound to actual parents')
            require((s['head'] != old_s['head'] and s['base'] == old_s['base']) if name == 'new-head' else
                    (s['base'] != old_s['base'] and s['head'] == old_s['head']), 'stale fixture changed wrong coordinates')
            require((old['policy']['epoch'] != p['epoch'] and digest(old['policy']) != digest(p)) if name == 'policy-transition'
                    else old == self.d, 'prior policy transition differs')
            evidence['prior'] = self._success(old_s, prior['evidence'], prior['coordinates'], old)
        return evidence

    def _run(self, manifest):
        require(not self.started, 'host case attempt already started; never replay')
        self.started = True
        self.binding = copy.deepcopy(self.registry.binding())
        self.d = validate_deployment(self.binding['deployment'])
        identity_record(self.d, self.identities)
        require(self.d['state'] in ('qualification', 'active') and self.d['adapter'] == 'github-actions',
                'current Actions qualification configuration required; cloud case producers remain held')
        manifest = copy.deepcopy(manifest)
        object_fields(manifest, ('repository_id', 'configuration_revision', 'deployment_digest', 'cases'), 'host case manifest')
        cases, p = manifest['cases'], self.d['policy']
        require(manifest['repository_id'] == p['repository_id'] and
                manifest['configuration_revision'] == self.binding['configuration_revision'] and
                manifest['deployment_digest'] == self.binding['deployment_digest'] == digest(self.d), 'host case configuration differs')
        require(isinstance(cases, list) and len(cases) == len(HOST_CASES), 'complete ordered host prefix required')
        for case in cases:
            object_fields(case, FIELDS, 'prepared host case')
            validate_snapshot(case['snapshot'], p)
        require([c['name'] for c in cases] == list(HOST_CASES) and
                len({c['snapshot']['pr'] for c in cases}) == len(cases) and
                len({c['snapshot']['head'] for c in cases}) == len(cases), 'distinct ordered host PRs and heads required')
        # Installation tokens do not implement GET /user. Authenticate each App
        # through the existing own-App proof/mint boundary, not the legacy probe's
        # user-token assumption. The human's independently supplied token is read
        # only here; no review submission endpoint is called.
        human = self.human.get('/user')
        actor_ids = dict(coding=self.identities['apps']['coding']['actor_id'],
                         merge=self.identities['apps']['merge']['actor_id'], human=human['id'])
        require(actor_ids['human'] in p['reviewers'] and human.get('type') == 'User',
                'host probe actor identity differs')
        readers, root = Readers(self.source, self.authority, self.d), '/repos/' + p['repository']
        records, observations = [], []
        for case in cases:
            self._guard()
            s, name = case['snapshot'], case['name']
            def snapshot():
                return current_snapshot(readers, self.d, s['pr'], s['run_id'], s['run_attempt'])
            require(snapshot() == s, 'prepared host case moved')
            evidence = self._prerequisites(case)
            commit = self.source.get(root + '/git/commits/' + s['merge'])
            require(commit.get('sha') == s['merge'] and sha(commit['tree']['sha']) and
                    [v['sha'] for v in commit['parents']] == [s['base'], s['head']],
                    'current merge parents or tree differ')
            evidence['synthetic_commit'] = copy.deepcopy(commit)
            before = self.source.get(root + '/git/ref/heads/' + quote(p['target'], safe=''))['object']['sha']
            require(before == s['base'] and snapshot() == s, 'target or candidate moved before host attempt')
            self._guard()
            direct = name in ('direct-push', 'human-update', 'coding-update')
            purpose = 'human' if name == 'human-update' else 'coding' if direct else 'merge'
            actor = self.human if purpose == 'human' else self.coding if purpose == 'coding' else self.merger
            request = dict(path=root + ('/git/refs/heads/' + quote(p['target'], safe='') if direct else
                                       '/pulls/' + str(s['pr']) + '/merge'),
                           method='PATCH' if direct else 'PUT',
                           data=dict(sha=s['merge'], force=False) if direct else dict(sha=s['head'], merge_method='merge'))
            expected = 'protected_update' if direct else 'required_review' if name == 'missing-approval' else 'required_check'
            def send(scoped):
                require(snapshot() == s and self.source.get(root + '/git/ref/heads/' +
                        quote(p['target'], safe=''))['object']['sha'] == before, 'host case moved during credential admission')
                self._guard()
                try:
                    scoped.fetch(request['path'], request['method'], request['data'])
                except HostRefusal as error:
                    return error.status, error.category, error.obligation
                return None, None, None
            if purpose == 'human':
                require(self.human.get('/user') == human, 'human probe identity changed')
                status, category, obligation = send(actor)
            else:
                from service import _source_token
                with _source_token(purpose, actor, self.authority, self.d, self.identities,
                                   self.binding['configuration_revision'], self.clock,
                                   self.token_factory, self._guard) as scoped:
                    status, category, obligation = send(scoped)
            after = self.source.get(root + '/git/ref/heads/' + quote(p['target'], safe=''))['object']['sha']
            require(before == after and snapshot() == s, 'negative host probe changed target or candidate')
            self._guard()
            require(type(status) is int and status in (403, 405, 422) and category == expected and
                    obligation == (p['check_name'] if expected == 'required_check' else None),
                    'host did not establish the intended denial')
            evidence.update(request=request, actor_id=actor_ids[purpose], before=before, after=after,
                            http_status=status, denial_category=category, denied_obligation=obligation)
            records.append(dict(name=name, pr=s['pr'], head=s['head'], base=s['base'], merge=s['merge'],
                tree=commit['tree']['sha'], before=before, after=after, actor_id=actor_ids[purpose], request_sent=True,
                http_status=status, denial_category=category, denied_obligation=obligation, broker_refusal=None,
                merge_commit=None, merge_parents=[], merge_tree=None, evidence_digest=digest(evidence)))
            observations.append(evidence)
        return dict(cases=records, observations=observations, hosted_qualified=False, enforcement_active=False)
