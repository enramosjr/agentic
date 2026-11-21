"""Read-only v2 control facts. These facts alone never establish task isolation."""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path
import re
import sys
from urllib.parse import quote, unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.ai/scripts'))
from authority_protocol import validate_deployment
from trusted_ci_deployment import check_owners
from merge_controls import check_rules
from trusted_ci_policy import digest, positive, require, sha


def owners_file(api, root, revision):
    tree = api.get(root + '/git/commits/' + revision)['tree']['sha']
    for index, name in enumerate(('.github', 'CODEOWNERS')):
        require(sha(tree), 'CODEOWNERS tree identity unavailable')
        response = api.get(root + '/git/trees/' + tree)
        require(response.get('truncated') is False and isinstance(response.get('tree'), list),
                'complete CODEOWNERS path readback required')
        matches = [entry for entry in response['tree'] if entry['path'] == name]
        require(len(matches) == 1, 'independent CODEOWNERS path unavailable')
        entry = matches[0]
        require(sha(entry['sha']), 'CODEOWNERS object identity unavailable')
        if index == 0:
            require(entry['type'] == 'tree' and entry['mode'] == '040000', 'CODEOWNERS parent must be a directory')
            tree = entry['sha']
        else:
            require(entry['type'] == 'blob' and entry['mode'] in ('100644', '100755'), 'CODEOWNERS must be a regular Git file')
    blob = api.get(root + '/git/blobs/' + entry['sha'])
    require(blob.get('sha') == entry['sha'] and blob.get('encoding') == 'base64' and
            isinstance(blob.get('content'), str) and len(blob['content']) <= 96 * 1024, 'bounded CODEOWNERS blob required')
    raw = base64.b64decode(blob['content'], validate=False)
    require(len(raw) <= 64 * 1024 and hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == entry['sha'],
            'CODEOWNERS content identity differs')
    return raw.decode('utf-8')


def observe(api, deployment):
    d = validate_deployment(deployment)
    p, resources = d['policy'], d['resources']
    root = '/repos/' + p['repository']
    repo = api.get(root)
    authority = api.get('/repos/' + p['authority_repository'])
    require(repo['id'] == p['repository_id'] and repo['default_branch'] == p['target'] and
            repo.get('allow_merge_commit') is True, 'target identity or merge capability differs')
    require(authority['id'] == p['authority_repository_id'] and authority.get('private') is True,
            'independent private authority unavailable')
    base = api.get(root + '/branches/' + p['target'])['commit']['sha']
    require(sha(base), 'target base revision unavailable')
    effective = api.pages(root + '/rules/branches/' + p['target'])
    ids = {r['ruleset_id'] for r in effective}
    require(ids and all(positive(identity) for identity in ids) and
            not any(r['type'] == 'merge_queue' for r in effective), 'effective controls unavailable or unsupported')
    owned = [resources.get(key + '_rule', '') for key in ('acceptance', 'updates')]
    require(all(isinstance(v, str) and re.fullmatch('[1-9][0-9]{0,19}', v) for v in owned) and
            len(set(owned)) == 2 and {int(v) for v in owned} <= ids, 'registered controls are not effective')
    details = []
    for item in api.pages(root + '/rulesets?includes_parents=true'):
        if item['id'] not in ids:
            continue
        if 'rules' not in item or 'bypass_actors' not in item:
            url = urlsplit(item['_links']['self']['href'])
            require(url.scheme == 'https' and url.netloc == 'api.github.com' and
                    url.path.startswith(('/repos/', '/orgs/', '/enterprises/')) and
                    not any(v in ('.', '..') for v in unquote(url.path).split('/')),
                    'invalid effective ruleset readback source')
            detail = api.get(url.path)
            require(detail['id'] == item['id'], 'effective ruleset identity changed')
            item = detail
        require(isinstance(item.get('rules'), list) and isinstance(item.get('bypass_actors'), list),
                'complete administrative rules and bypass visibility required')
        details.append(item)
    require(len(details) == len(ids) and {r['id'] for r in details} == ids, 'incomplete effective control inventory')
    check_rules(d, details)
    owners = owners_file(api, root, base)
    logins = re.findall('@([A-Za-z0-9-]+)', owners)
    identities = {name: api.get('/users/' + name)['id'] for name in logins}
    check_owners(owners, identities, p)
    bot = resources.get('coding_bot_id', '')
    slug = resources.get('coding_slug', '')
    require(isinstance(bot, str) and re.fullmatch('[1-9][0-9]{0,19}', bot) and
            p['coding_actors'] == [int(bot)] and re.fullmatch('[a-z0-9][a-z0-9-]{0,99}', slug),
            'registered coding App bot identity required')
    actor = api.get('/users/' + quote(slug + '[bot]', safe=''))
    require(actor['id'] == int(bot) and actor.get('type') == 'Bot', 'coding App bot identity changed')
    collaborators = api.pages(root + '/collaborators?affiliation=all')
    human_ids = set(p['reviewers'])
    actual_humans = set()
    for actor in collaborators:
        permissions = actor.get('permissions', {})
        if actor['id'] == int(bot):
            require(actor.get('type') == 'Bot' and actor.get('role_name') in ('write', 'read', 'triage') and
                    permissions.get('admin') is False, 'coding App has administrative or unclassified collaborator access')
        elif actor['id'] in human_ids:
            require(actor.get('type') == 'User' and permissions.get('push') is True, 'independent human reviewer lacks access')
            actual_humans.add(actor['id'])
        else:
            require(not permissions.get('push') and not permissions.get('admin'), 'unclassified target writer')
    require(actual_humans == human_ids, 'independent human actors unavailable')
    required = {}
    for rule in effective:
        if rule['type'] != 'required_status_checks':
            continue
        checks = rule['parameters']['required_status_checks']
        require(isinstance(checks, list) and len(checks) <= 100, 'bounded required-check inventory required')
        for check in checks:
            context, integration = check.get('context'), check.get('integration_id')
            require(isinstance(context, str) and 0 < len(context) <= 100 and
                    not any(ord(c) < 32 for c in context) and
                    (integration is None or type(integration) is int and integration >= 0),
                    'required-check source unavailable')
            required[(context, integration)] = {'context': context, 'integration_id': integration}
    # Conservative initial readback: unknown target automation cannot establish
    # separation merely because the managed worker itself has no credentials.
    # No remote configuration is changed. Future qualified strategies may preserve
    # target Actions; selecting or disabling them requires a separate exact preview.
    actions = api.get(root + '/actions/permissions')
    require(actions.get('enabled') is False, 'indirect credential path unverified: target Actions strategy is not qualified')
    hooks = api.pages(root + '/hooks')
    require(all(hook.get('active') is False for hook in hooks),
            'indirect credential path unverified: target webhook automation')
    require(api.get(root + '/branches/' + p['target'])['commit']['sha'] == base, 'target moved during control readback')
    return {'schema_version': 2, 'deployment_digest': digest(d), 'generation': d['generation'], 'base': base,
        'controls_digest': digest(sorted(details, key=lambda value: value['id'])),
        'owners_digest': digest(owners), 'access_digest': digest(collaborators),
        'automation_digest': digest({'actions': actions, 'hooks': hooks}),
        'coding_bot_id': int(bot), 'required_checks': sorted(required.values(),
            key=lambda c: (c['context'], -1 if c['integration_id'] is None else c['integration_id'])),
        'isolation_established': False, 'enforcement_active': False}
