"""Idempotent additive GitHub controls. Call through the held bootstrap boundary."""
from __future__ import annotations

import copy
import re
from pathlib import Path
import sys
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.ai/scripts'))
from authority_protocol import validate_deployment
from trusted_ci_policy import digest, positive, require, sha
from trusted_ci_github import contents
from trusted_ci_deployment import check_owners
from merge_controls import check_rules
from configuration import require_session


def desired_rules(d):
    p, nonce = d['policy'], d['resources']['operation_id']
    common = {'target': 'branch', 'enforcement': 'active',
              'conditions': {'ref_name': {'include': ['refs/heads/' + p['target']], 'exclude': []}}}
    acceptance = dict(copy.deepcopy(common), name='AGENTIC-acceptance-' + nonce + '-' + p['epoch'], bypass_actors=[], rules=[
        {'type': 'pull_request', 'parameters': {'required_approving_review_count': 1,
            'dismiss_stale_reviews_on_push': True, 'require_last_push_approval': True,
            'require_code_owner_review': True, 'required_review_thread_resolution': True,
            'allowed_merge_methods': ['merge']}},
        {'type': 'required_status_checks', 'parameters': {'strict_required_status_checks_policy': True,
            'required_status_checks': [{'context': p['check_name'], 'integration_id': p['app_id']}]}},
        {'type': 'deletion'}, {'type': 'non_fast_forward'}])
    updates = dict(copy.deepcopy(common), name='AGENTIC-updates-' + nonce + '-' + p['epoch'],
        bypass_actors=[{'actor_type': 'Integration', 'actor_id': d['apps']['merge'],
                        'bypass_mode': 'pull_request'}], rules=[{'type': 'update'}])
    return {'acceptance': acceptance, 'updates': updates}


def canonical(rule):
    return {key: copy.deepcopy(rule[key]) for key in
            ('name', 'target', 'enforcement', 'conditions', 'rules', 'bypass_actors')}


class Reconciler:
    def __init__(self, api, journal, now, session=None):
        self.api, self.journal, self.now = api, journal, now
        self.session = session

    def save(self, resources, state='setup'):
        old = self.journal.read()
        require(old is not None, 'approved deployment journal required')
        new = copy.deepcopy(old)
        new['resources'].update(resources)
        new['state'], new['qualification'] = state, None
        if old != new:
            new['generation'] += 1
            require_session(self.session, 'rules', old['policy']['repository'])
            self.session.write_configuration(digest(old), new)
        return new

    def preview(self):
        d = validate_deployment(self.journal.read())
        require(self.now() < d['expires'], 'deployment intent expired')
        require('operation_id' in d['resources'], 'stable rule ownership nonce required before preview')
        require(re.fullmatch('[0-9a-f]{32}', d['resources']['operation_id']), 'invalid reconciliation identity')
        p, root = d['policy'], '/repos/' + d['policy']['repository']
        repo = self.api.get(root)
        authority = self.api.get('/repos/' + p['authority_repository'])
        require(repo['id'] == p['repository_id'] and repo['default_branch'] == p['target'] and
                repo.get('allow_merge_commit') is True, 'target identity or merge capability differs')
        require(authority['id'] == p['authority_repository_id'] and authority.get('private') is True,
                'private independent authority required')
        base = self.api.get(root + '/branches/' + p['target'])['commit']['sha']
        require(sha(base), 'target revision unavailable')
        owners = contents(self.api, p['repository'], '.github/CODEOWNERS', base).decode('utf-8')
        names = re.findall('@([A-Za-z0-9-]+)', owners)
        identities = {name: self.api.get('/users/' + name)['id'] for name in names}
        check_owners(owners, identities, p)
        rules = []
        for item in self.api.pages(root + '/rulesets?includes_parents=true'):
            if 'rules' not in item or 'bypass_actors' not in item:
                url = urlsplit(item['_links']['self']['href'])
                require(url.scheme == 'https' and url.netloc == 'api.github.com' and
                        url.path.startswith(('/repos/', '/orgs/', '/enterprises/')), 'invalid ruleset readback source')
                item = self.api.get(url.path)
            rules.append(item)
        operations = []
        for kind, body in desired_rules(d).items():
            matches = [r for r in rules if r['name'] == body['name']]
            require(len(matches) <= 1, 'ambiguous owned control')
            known = d['resources'].get(kind + '_rule')
            if matches:
                existing = matches[0]
                require(positive(existing['id']) and (known is None or known == str(existing['id'])),
                        'owned control identity changed')
                # A prepared operation may have committed before its response was
                # received. Exact body + private operation nonce fences recovery.
                require(canonical(existing) == body, 'owned control drift; explicit repair preview required')
                operations.append({'kind': kind, 'action': 'observe', 'id': existing['id'], 'body': body})
            else:
                require(known is None, 'owned control was removed; explicit repair required')
                operations.append({'kind': kind, 'action': 'create', 'id': None, 'body': body})
        return {'schema_version': 2, 'deployment_digest': digest(d), 'repository_id': repo['id'],
                'base': base, 'observed_digest': digest(rules), 'owners_digest': digest(owners),
                'operations': operations, 'enforcement_active': False}

    def apply(self, approval):
        require_session(self.session, 'rules', self.journal.read()['policy']['repository'])
        plan = self.preview()
        require(digest(plan) == approval, 'fresh exact protection preview approval required')
        d = self.journal.read()
        root = '/repos/' + d['policy']['repository']
        for operation in plan['operations']:
            if operation['action'] == 'create':
                require_session(self.session, 'rules', d['policy']['repository'])
                observed = self.api.post(root + '/rulesets', operation['body'])
                require(canonical(observed) == operation['body'] and positive(observed['id']),
                        'provider created different protection')
                identity = observed['id']
            else:
                identity = operation['id']
            d = self.save({operation['kind'] + '_rule': str(identity)})
        effective = self.api.pages(root + '/rules/branches/' + d['policy']['target'])
        ids = {r['ruleset_id'] for r in effective}
        owned = []
        for item in self.api.pages(root + '/rulesets?includes_parents=true'):
            if item['id'] not in {int(d['resources'][k + '_rule']) for k in ('acceptance', 'updates')}:
                continue
            if 'rules' not in item or 'bypass_actors' not in item:
                url = urlsplit(item['_links']['self']['href'])
                require(url.scheme == 'https' and url.netloc == 'api.github.com' and url.path.startswith('/repos/'),
                        'invalid owned control source')
                item = self.api.get(url.path)
            owned.append(item)
        require(len(owned) == 2 and {r['id'] for r in owned} <= ids, 'effective owned controls unavailable')
        check_rules(d, owned)
        d = self.save({}, state='qualification')
        return {'state': 'qualification', 'enforcement_active': False,
                'deployment_digest': digest(d), 'controls_digest': digest(owned)}
