"""Read-only inspection of independently administered merge controls."""
from __future__ import annotations

from datetime import datetime, timezone
import re
from urllib.parse import urlparse

from trusted_ci_policy import (digest, loads, object_fields, positive, require,
                               sha, validate_policy)
from trusted_ci_github import authority_run, contents, repo_path


def check_rules(p, rulesets):
    require(isinstance(rulesets, list) and rulesets, 'effective rules unavailable')
    acceptance, restrictions = [], []
    for ruleset in rulesets:
        require(ruleset.get('enforcement') == 'active', 'nonactive ruleset cannot authorize')
        rules = {r['type']: r for r in ruleset['rules']}
        bypass = ruleset['bypass_actors']
        if 'update' in rules:
            require(bypass, 'no authorized independent merge identity')
            for actor in bypass:
                require(actor.get('actor_type') == 'User' and actor.get('actor_id') in p['merge_actors'] and
                        actor.get('bypass_mode') == 'pull_request', 'unsafe protected-update bypass')
            restrictions.append(ruleset)
        if 'pull_request' in rules and 'required_status_checks' in rules:
            require(not bypass, 'acceptance rules must have no bypass actors')
            review = rules['pull_request']['parameters']
            require(type(review.get('required_approving_review_count')) is int and
                    review['required_approving_review_count'] >= 1, 'independent host approval required')
            for key in ('dismiss_stale_reviews_on_push', 'require_last_push_approval',
                        'require_code_owner_review', 'required_review_thread_resolution'):
                require(review.get(key) is True, 'missing review protection: ' + key)
            checks = rules['required_status_checks']['parameters']
            require(checks.get('strict_required_status_checks_policy') is True, 'strict current-base checks required')
            entries = [x for x in checks['required_status_checks'] if x['context'] == p['check_name']]
            require(len(entries) == 1 and entries[0].get('integration_id') == p['app_id'], 'wrong required App source')
            require('deletion' in rules and 'non_fast_forward' in rules, 'branch safety protections required')
            acceptance.append(ruleset)
    require(acceptance and restrictions, 'separate acceptance and protected-update rules required')
    require(all(r['id'] != a['id'] for r in restrictions for a in acceptance), 'update bypass cannot waive acceptance')


def check_owners(text, identities, p):
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#')]
    require(len(lines) == 1, 'CODEOWNERS must contain one global owner rule')
    words = lines[0].split()
    require(len(words) >= 2 and words[0] == '*' and all(re.fullmatch('@[A-Za-z0-9-]+', x) for x in words[1:]),
            'global independent CODEOWNERS required')
    owners = [identities.get(x[1:]) for x in words[1:]]
    require(all(x in p['reviewers'] and x not in p['coding_actors'] for x in owners), 'unapproved code owner')


def timestamp(value):
    require(isinstance(value, str) and re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ', value),
            'UTC timestamp required')
    return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)


def check_access(a, p, now=None):
    object_fields(a, ('schema_version', 'repository_id', 'authority_repository_id', 'policy_digest',
                      'app_id', 'coding_actors', 'reviewers', 'merge_actors', 'approved_by',
                      'credential_separation', 'issued_at', 'expires_at', 'issuer_permissions'), 'access attestation')
    require(type(a['schema_version']) is int and a['schema_version'] == 1, 'unsupported access attestation')
    for key in ('repository_id', 'authority_repository_id', 'app_id', 'coding_actors', 'reviewers', 'merge_actors'):
        require(a[key] == p[key], 'attested identity mismatch: ' + key)
    require(a['policy_digest'] == digest(p) and a['approved_by'] in p['reviewers'] and
            a['credential_separation'] is True, 'independent credential separation unverified')
    permissions = a['issuer_permissions']
    require(permissions == dict(checks='write', contents='read', pull_requests='read', metadata='read'),
            'issuer must have only check-write and source/review read permissions')
    now = now or datetime.now(timezone.utc)
    issued, expiry = timestamp(a['issued_at']), timestamp(a['expires_at'])
    require(issued <= now < expiry and 0 < (expiry - issued).total_seconds() <= 31 * 86400,
            'access attestation expired, future or overlong')


def variable(api, p, name):
    value = api.get('/repos/' + p['authority_repository'] + '/actions/variables/' + name)
    require(value.get('name') == name and isinstance(value.get('value'), str), 'authority configuration unavailable')
    return value['value']


def inspect(api, p, qualification=True, policy_variable='AGENTIC_POLICY_JSON'):
    """All methods on this path are GET. Authority provenance is not a local claim."""
    validate_policy(p)
    root = repo_path(p)
    repo = api.get(root)
    require(repo['id'] == p['repository_id'] and repo['default_branch'] == p['target'], 'target identity mismatch')
    require(api.get('/repos/' + p['authority_repository'])['id'] == p['authority_repository_id'], 'authority mismatch')
    require(policy_variable in ('AGENTIC_POLICY_JSON', 'AGENTIC_QUALIFICATION_POLICY_JSON'), 'unsupported policy source')
    require(loads(variable(api, p, policy_variable)) == p, 'local policy differs from authority policy')
    branch = api.get(root + '/branches/' + p['target'])
    base = branch['commit']['sha']
    require(sha(base), 'invalid target revision')
    require(loads(contents(api, p['repository'], '.agentic-trusted-ci.json', base)) ==
            dict(epoch=p['epoch'], policy_digest=digest(p)), 'target policy activation missing')
    effective = api.pages(root + '/rules/branches/' + p['target'])
    ids = {r['ruleset_id'] for r in effective}
    summaries = api.pages(root + '/rulesets?includes_parents=true')
    details = []
    for summary in summaries:
        if summary['id'] not in ids:
            continue
        url = urlparse(summary['_links']['self']['href'])
        require(url.scheme == 'https' and url.netloc == 'api.github.com' and
                url.path.startswith(('/repos/', '/orgs/', '/enterprises/')), 'invalid ruleset source')
        details.append(api.get(url.path))
    require(ids and ids == {r['id'] for r in details}, 'incomplete effective rule inventory')
    require(not any(r.get('type') == 'merge_queue' for r in effective), 'merge queues unsupported')
    check_rules(p, details)
    owners = contents(api, p['repository'], '.github/CODEOWNERS', base).decode('utf-8')
    logins = re.findall('@([A-Za-z0-9-]+)', owners)
    identities = {name: api.get('/users/' + name)['id'] for name in logins}
    check_owners(owners, identities, p)
    collaborators = api.pages(root + '/collaborators?affiliation=all')
    actual = {c['id'] for c in collaborators}
    require(set(p['coding_actors'] + p['reviewers'] + p['merge_actors']) <= actual, 'configured actors unavailable')
    for actor in collaborators:
        if actor['id'] in p['coding_actors']:
            require(actor.get('role_name') in ('write', 'read', 'triage') and
                    not actor.get('permissions', {}).get('admin'), 'coding identity has administrative or unknown access')
        elif actor.get('permissions', {}).get('push'):
            require(actor['id'] in p['reviewers'] + p['merge_actors'], 'unclassified writer identity')
    access_key = 'AGENTIC_ACCESS_REF' if policy_variable == 'AGENTIC_POLICY_JSON' else 'AGENTIC_QUALIFICATION_ACCESS_REF'
    access_ref = variable(api, p, access_key)
    require(sha(access_ref), 'immutable authority access attestation required')
    access = loads(contents(api, p['authority_repository'], 'access-attestation.json', access_ref))
    check_access(access, p)
    controls = digest(dict(policy=digest(p), rules=details, owners=owners, access=access))
    result = dict(schema_version=1, repository_id=p['repository_id'], target=base,
                  policy_digest=digest(p), controls_digest=controls,
                  semantics_digest=digest(dict(rules=sorted(
                      [dict(rules=r['rules'], bypass_actors=r['bypass_actors']) for r in details], key=digest),
                      owners=sorted(identities.values()))),
                  state='configured; hosted qualification required')
    if qualification:
        from trusted_ci_qualification import read_qualification
        read_qualification(api, p, controls)
        result['state'] = 'qualified enforcement'
    return result
