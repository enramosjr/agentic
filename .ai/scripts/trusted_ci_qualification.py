"""Actual protected-host probes. Only an independently authorized disposable target."""
from __future__ import annotations

import io
import hashlib
import zipfile
from pathlib import PurePosixPath

from trusted_ci_policy import digest, loads, object_fields, positive, require, sha, validate_snapshot
from trusted_ci_github import (HostRefusal, artifact_report, authority_run, contents,
                               current_snapshot, independent_approval, repo_path)

CASES = ('bad-acceptance', 'replaced-checks', 'forged-records', 'spoofed-source',
         'missing-approval', 'direct-push', 'new-head', 'new-base', 'policy-transition', 'positive')


def check_negative(report, p, expected, criterion):
    object_fields(report, ('schema_version', 'snapshot', 'outcomes'), 'negative report')
    require(report['schema_version'] == 1 and report['snapshot'] == expected, 'negative proof snapshot mismatch')
    validate_snapshot(report['snapshot'], p)
    outcomes = report['outcomes']
    require(isinstance(outcomes, list) and len(outcomes) == len(p['checks']) and
            [o['id'] for o in outcomes] == p['checks'], 'negative proof coverage mismatch')
    for outcome in outcomes:
        object_fields(outcome, ('id', 'status'), 'negative outcome')
        require(outcome['status'] in ('success', 'failure', 'not_run'), 'invalid negative outcome')
    require(criterion in p['checks'] and any(o['id'] == criterion and o['status'] == 'failure' for o in outcomes),
            'required criterion did not actually fail')


def check_mutations(api, p, case, snapshot):
    mutations = case['mutations']
    require(isinstance(mutations, list) and mutations, 'reviewed mutation identities required')
    paths = []
    for mutation in mutations:
        object_fields(mutation, ('path', 'sha256'), 'mutation')
        name = mutation['path']
        require(isinstance(name, str) and name and not PurePosixPath(name).is_absolute() and
                '..' not in PurePosixPath(name).parts and '.git' not in PurePosixPath(name).parts and
                '\\' not in name and ':' not in name and name not in paths, 'invalid mutation path')
        paths.append(name)
        raw = contents(api, p['repository'], name, snapshot['head'])
        require(hashlib.sha256(raw).hexdigest() == mutation['sha256'], 'prepared mutation bytes changed')
        try:
            baseline = contents(api, p['repository'], name, snapshot['base'])
        except HostRefusal as exc:
            require(exc.status == 404, 'baseline mutation lookup unavailable')
        else:
            require(raw != baseline, 'fixture contains no actual mutation')
    if case['name'] == 'replaced-checks':
        require(any(n.startswith(('.ai/scripts/tests/', '.github/workflows/')) for n in paths),
                'candidate test/workflow replacement missing')
    if case['name'] == 'forged-records':
        require(any(n.startswith('knowledge/history/lifecycle/') for n in paths), 'forged receipt fixture missing')


def probe(api, coding, merger, p, manifest, reference_controls):
    """Drive prepared hostile PR fixtures and real merge/ref API requests.

    Fixture setup is independently reviewed authority material, never candidate
    reports. Each negative probe checks the discriminating host state first.
    """
    object_fields(manifest, ('schema_version', 'qualification_repository_id', 'cases'), 'qualification manifest')
    require(manifest['schema_version'] == 1 and manifest['qualification_repository_id'] == p['repository_id'],
            'qualification target mismatch')
    require(api.get(repo_path(p))['id'] == p['repository_id'], 'disposable target identity changed')
    require(coding.get('/user')['id'] in p['coding_actors'], 'wrong qualification coding identity')
    require(merger.get('/user')['id'] in p['merge_actors'], 'wrong qualification merge identity')
    cases = manifest['cases']
    require(isinstance(cases, list) and [c['name'] for c in cases] == list(CASES), 'complete ordered case inventory required')
    require(len({c['pr'] for c in cases}) == len(CASES) and len({c['head'] for c in cases}) == len(CASES),
            'qualification cases must use distinct prepared PRs and revisions')
    outcomes = []
    root = repo_path(p)
    for case in cases:
        object_fields(case, ('name', 'pr', 'head', 'prior_merge', 'prior_head', 'prior_base',
                             'negative_run_id', 'negative_attempt', 'expected_failure', 'mutations'), 'probe case')
        require(positive(case['pr']) and sha(case['head']), 'invalid prepared fixture identity')
        s = current_snapshot(api, p, case['pr'], 1, 1)
        require(s['head'] == case['head'], 'prepared fixture changed')
        pr = api.get(root + '/pulls/' + str(case['pr']))
        require(pr.get('mergeable') is True, 'conflicted or unresolved fixture cannot qualify a governance denial')
        checks = api.pages(root + '/commits/' + s['merge'] + '/check-runs', 'check_runs')
        own = [c for c in checks if c['name'] == p['check_name'] and c['app']['id'] == p['app_id']]
        success = [c for c in own if c['status'] == 'completed' and c['conclusion'] == 'success']
        if case['name'] in ('positive', 'direct-push', 'missing-approval'):
            require(success, 'probe needs completed trusted acceptance to isolate authorization')
        else:
            require(not success, 'negative acceptance fixture unexpectedly has authoritative success')
        if case['name'] in ('bad-acceptance', 'replaced-checks', 'forged-records'):
            require(positive(case['negative_run_id']) and positive(case['negative_attempt']), 'trusted negative execution required')
            expected = dict(s, run_id=case['negative_run_id'], run_attempt=case['negative_attempt'])
            negative = artifact_report(api, p, case['negative_run_id'], case['negative_attempt'], case['pr'], negative=True)
            check_negative(negative, p, expected, case['expected_failure'])
            check_mutations(api, p, case, s)
        rules = api.pages(root + '/rules/branches/' + p['target'])
        for rule in rules:
            if rule['type'] == 'required_status_checks':
                for obligation in rule['parameters']['required_status_checks']:
                    if obligation['context'] == p['check_name']:
                        continue
                    require(any(c['name'] == obligation['context'] and
                                c['app']['id'] == obligation.get('integration_id') and
                                c['status'] == 'completed' and c['conclusion'] == 'success' for c in checks),
                            'other host checks must pass to isolate the denial reason')
        if case['name'] == 'missing-approval':
            reviews = api.pages(root + '/pulls/' + str(case['pr']) + '/reviews')
            require(not any(r['state'] == 'APPROVED' and r['commit_id'] == s['head'] for r in reviews),
                    'missing-approval fixture still has an approval')
        else:
            independent_approval(api, p, pr)
        if case['name'] == 'spoofed-source':
            require(any(c['name'] == p['check_name'] and c['app']['id'] != p['app_id'] and
                        c['conclusion'] == 'success' for c in checks), 'actual spoofed source fixture required')
        if case['name'] in ('new-head', 'new-base', 'policy-transition'):
            require(sha(case['prior_merge']) and case['prior_merge'] != s['merge'], 'prior merge identity required')
            prior = api.pages(root + '/commits/' + case['prior_merge'] + '/check-runs', 'check_runs')
            require(any(c['name'] == p['check_name'] and c['app']['id'] == p['app_id'] and
                        c['conclusion'] == 'success' for c in prior), 'real prior trusted success required')
            prior_parents = api.get(root + '/git/commits/' + case['prior_merge'])['parents']
            require([parent['sha'] for parent in prior_parents] == [case['prior_base'], case['prior_head']],
                    'prior freshness fields are not bound to the actual merge parents')
            if case['name'] == 'new-head':
                require(s['head'] != case['prior_head'] and s['base'] == case['prior_base'],
                        'new-head probe must change only the head binding')
            else:
                require(s['base'] != case['prior_base'] and s['head'] == case['prior_head'],
                        'new-base probe must preserve the head binding')
                if case['name'] == 'policy-transition':
                    prior_marker = loads(contents(api, p['repository'], '.agentic-trusted-ci.json', case['prior_base']))
                    require(prior_marker.get('epoch') != p['epoch'] and prior_marker.get('policy_digest') != digest(p),
                            'policy-transition fixture has no actual changed epoch')
        before = api.get(root + '/git/ref/heads/' + p['target'])['object']['sha']
        require(before == s['base'], 'target moved before hosted probe')
        require(current_snapshot(api, p, case['pr'], 1, 1) == s, 'fixture moved before protected update')
        status, merged, category, obligation = 0, False, 'positive', None
        try:
            if case['name'] == 'direct-push':
                coding.fetch(root + '/git/refs/heads/' + p['target'], 'PATCH', dict(sha=s['merge'], force=False))
            else:
                result = merger.fetch(root + '/pulls/' + str(case['pr']) + '/merge', 'PUT',
                                      dict(sha=s['head'], merge_method='merge'))
                merged = result.get('merged') is True
        except HostRefusal as exc:
            status, category, obligation = exc.status, exc.category, exc.obligation
        after = api.get(root + '/git/ref/heads/' + p['target'])['object']['sha']
        if case['name'] == 'positive':
            require(merged and after != before, 'positive hosted merge did not update target')
        else:
            require(current_snapshot(api, p, case['pr'], 1, 1) == s, 'fixture moved during protected update')
            expected_category = ('protected_update' if case['name'] == 'direct-push' else
                                 'required_review' if case['name'] == 'missing-approval' else 'required_check')
            require(category == expected_category and before == after,
                    'host did not explicitly deny protected update')
            require(category != 'required_check' or obligation == p['check_name'],
                    'host denied a different required check')
        outcomes.append(dict(name=case['name'], before=before, after=after, http_status=status,
                             denial_category=category, denied_obligation=obligation,
                             head=s['head'], merge=s['merge'], result='pass'))
    return dict(schema_version=1, reference_controls_digest=reference_controls,
                qualification_repository_id=p['repository_id'], cases=outcomes)


def read_qualification(api, p, controls):
    from trusted_ci_deployment import variable
    value = variable(api, p, 'AGENTIC_QUALIFICATION_RUN')
    require(value.isdigit() and positive(int(value)), 'hosted qualification run required')
    run_id = int(value)
    run = authority_run(api, p, run_id, 1, completed=True)
    root = '/repos/' + p['authority_repository']
    jobs = api.pages(root + '/actions/runs/' + str(run_id) + '/attempts/1/jobs', 'jobs')
    required = [j for j in jobs if j['name'] == 'hosted qualification']
    require(len(required) == 1 and required[0]['conclusion'] == 'success', 'trusted hosted qualification job did not pass')
    artifacts = api.pages(root + '/actions/runs/' + str(run_id) + '/artifacts', 'artifacts')
    entries = [a for a in artifacts if a['name'] == 'hosted-qualification']
    require(len(entries) == 1 and not entries[0]['expired'] and
            entries[0]['workflow_run']['id'] == run_id, 'trusted qualification artifact unavailable')
    artifact = entries[0]
    raw = api.fetch(root + '/actions/artifacts/' + str(artifact['id']) + '/zip', binary=True, limit=1024 * 1024)
    require(artifact.get('digest') == 'sha256:' + hashlib.sha256(raw).hexdigest(), 'qualification artifact digest mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        require(archive.namelist() == ['qualification.json'] and
                archive.getinfo('qualification.json').file_size <= 512 * 1024, 'invalid qualification artifact')
        receipt = loads(archive.read('qualification.json'))
    object_fields(receipt, ('schema_version', 'reference_controls_digest', 'qualification_repository_id', 'cases'),
                  'qualification receipt')
    require(receipt['schema_version'] == 1 and receipt['reference_controls_digest'] == controls and
            positive(receipt['qualification_repository_id']) and
            receipt['qualification_repository_id'] != p['repository_id'], 'qualification not bound to production controls')
    require([c['name'] for c in receipt['cases']] == list(CASES), 'incomplete hosted denial inventory')
    for c in receipt['cases']:
        require(c['result'] == 'pass' and sha(c['before']) and sha(c['after']) and
                (c['before'] != c['after'] if c['name'] == 'positive' else
                 c['before'] == c['after'] and c['denial_category'] ==
                 ('protected_update' if c['name'] == 'direct-push' else
                  'required_review' if c['name'] == 'missing-approval' else 'required_check') and
                 (c['denial_category'] != 'required_check' or c['denied_obligation'] == p['check_name'])),
                'unsuccessful hosted qualification case')
    return receipt
