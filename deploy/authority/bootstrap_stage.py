"""Human-side registration preflight; does not activate enforcement or change rules.

Run the frozen, independently reviewed bundle outside all coding-agent access.
This early stage exists to qualify GitHub's manifest callback before dependent
onboarding work. It creates a NEW private authority and retains registered keys
only in its secrets. A partial run is never treated as completed setup.
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.ai' / 'scripts'))
from trusted_ci_policy import Refusal, digest, positive, require
import authority_release
from bootstrap import (Gh, PERMISSIONS, app_api, await_installation,
                       installation_token, register_app, revoke_token)


def install_and_verify(app, account_id, repository_id, forbidden_repository=None):
    from trusted_ci_github import GitHub, HostRefusal
    installation = await_installation(app, account_id)
    api = app_api(app['id'], app['pem'])
    info = api.get('/app')
    require(info['id'] == app['id'], 'App identity changed')
    permissions = dict(info['permissions'])
    require(permissions.pop('metadata', 'read') == 'read', 'App metadata permission changed')
    expected = dict(app['permissions'])
    require(expected.pop('metadata', 'read') == 'read' and permissions == expected,
            'installed App permissions changed')
    token = installation_token(api, installation, [repository_id], permissions)
    try:
        visible = GitHub(token).pages('/installation/repositories', 'repositories')
        require([r['id'] for r in visible] == [repository_id], 'installed token repository scope changed')
        if 'administration' not in permissions:
            try:
                unexpected = api.post('/app/installations/' + str(installation) + '/access_tokens',
                    {'repository_ids': [repository_id], 'permissions': {'administration': 'write'}})
            except HostRefusal as error:
                require(error.status == 422 and error.category == 'permission_scope',
                        'administration mint probe failed for an unexpected reason')
            else:
                revoke_token(unexpected)
                raise Refusal('non-administrative App minted an administrative token')
        if forbidden_repository is not None:
            try:
                unexpected = api.post('/app/installations/' + str(installation) + '/access_tokens',
                    {'repository_ids': [forbidden_repository], 'permissions': {'contents': 'write'}})
            except HostRefusal as error:
                require(error.status == 422 and error.category == 'repository_scope',
                        'authority-access probe failed for an unexpected reason')
            else:
                revoke_token(unexpected)
                raise Refusal('installation grants authority write access; select only the coding fixture')
    finally:
        revoke_token({'token': token})
    return installation


def preview(gh, repository):
    require(isinstance(repository, str) and
            re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,99}/[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', repository),
            'owner/new-authority-name required')
    owner, name = repository.split('/')
    user = gh.api('/user')
    require(positive(user.get('id')) and isinstance(user.get('login'), str), 'authenticated GitHub user required')
    organization = None
    account = user
    if user['login'].lower() != owner.lower():
        membership = gh.api('/user/memberships/orgs/' + owner)
        require(membership['state'] == 'active' and membership['role'] == 'admin',
                'organization owner consent required')
        account = gh.api('/orgs/' + owner)
        require(positive(account.get('id')), 'organization identity required')
        organization = account['login']
    return {'kind': 'registration-preview', 'repository': account['login'] + '/' + name,
            'coding_fixture': account['login'] + '/' + name + '-coding-probe',
            'account_id': account['id'], 'actor_id': user['id'], 'organization': organization,
            'private': True, 'apps': PERMISSIONS,
            'actions': ['create new private authority and separate coding-fixture repositories',
                        'register five purpose-specific Apps with browser consent',
                        'encrypt and store App keys in authority-only secrets'],
            'cost_owner': account['login'], 'billable_types': ['GitHub repository storage'],
            'enforcement_qualified': False, 'target_rules_changed': False}


def apply(gh, repository, approval, registrar=register_app, installer=install_and_verify):
    proposed = preview(gh, repository)
    require(approval == digest(proposed), 'exact registration preview approval required')
    repository = proposed['repository']
    owner, name = repository.split('/')
    endpoint = '/orgs/' + owner + '/repos' if proposed['organization'] else '/user/repos'
    created = gh.api(endpoint, 'POST', {'name': name, 'private': True, 'auto_init': True,
                                      'description': 'AGENTIC authority setup; enforcement not yet qualified'})
    require(created.get('full_name') == repository and positive(created.get('id')) and
            created.get('private') is True and created.get('owner', {}).get('id') == proposed['account_id'],
            'created authority ownership/privacy differs from consent')
    fixture_name = proposed['coding_fixture'].split('/')[1]
    fixture = gh.api(endpoint, 'POST', {'name': fixture_name, 'private': True, 'auto_init': True,
                                      'description': 'AGENTIC disposable coding scope qualification fixture'})
    require(fixture.get('full_name') == proposed['coding_fixture'] and positive(fixture.get('id')) and
            fixture['id'] != created['id'] and fixture.get('private') is True and
            fixture.get('owner', {}).get('id') == proposed['account_id'], 'coding fixture ownership/privacy mismatch')
    result = {'kind': 'registration-preflight', 'state': 'setup', 'repository': repository,
              'repository_id': created['id'], 'coding_fixture': proposed['coding_fixture'],
              'coding_fixture_id': fixture['id'], 'account_id': proposed['account_id'],
              'preview_digest': approval, 'apps': {}, 'enforcement_qualified': False}
    revision = None

    def record():
        nonlocal revision
        body = {'message': 'Record incomplete authority bootstrap stage',
                'content': base64.b64encode((json.dumps(result, sort_keys=True) + '\n').encode()).decode()}
        if revision is not None:
            body['sha'] = revision
        response = gh.api('/repos/' + repository + '/contents/bootstrap.json', 'PUT', body)
        revision = response['content']['sha']

    record()
    for purpose in ('admin', 'reader', 'issuer', 'coding', 'merge'):
        app = registrar(purpose, gh, proposed['organization'])
        require(app.get('owner', {}).get('id') == proposed['account_id'] and positive(app.get('id')) and
                app['id'] not in [v['id'] for v in result['apps'].values()], 'registered App owner/domain mismatch')
        gh.secret(repository, 'AGENTIC_' + purpose.upper() + '_PRIVATE_KEY', app['pem'])
        result['apps'][purpose] = {'id': app['id'], 'slug': app['slug'],
                                   'permissions': dict(PERMISSIONS[purpose])}
        record()
        target = fixture['id'] if purpose in ('coding', 'issuer', 'merge') else created['id']
        installation = installer(app, proposed['account_id'], target,
                                 created['id'] if purpose in ('coding', 'merge') else None)
        require(positive(installation) and installation not in [v.get('installation_id')
                for v in result['apps'].values()], 'invalid or substituted installation')
        result['apps'][purpose]['installation_id'] = installation
        record()
    result['registration_received'] = True
    record()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('preview', 'apply'))
    parser.add_argument('--repository', required=True, help='a NEW adopter-owned private authority repository')
    parser.add_argument('--approve', help='digest of the current preview; applies only to registration resources')
    args = parser.parse_args(argv)
    try:
        authority_release.authorize('bootstrap')
        gh = Gh()
        if args.operation == 'preview':
            result = preview(gh, args.repository)
            print(json.dumps({'preview': result, 'approval_digest': digest(result)}, indent=2, sort_keys=True))
        else:
            print(json.dumps(apply(gh, args.repository, args.approve), sort_keys=True))
        return 0
    except authority_release.Held:
        print(json.dumps(authority_release.status()), file=sys.stderr)
        return 1
    except (Refusal, OSError, KeyError, ValueError, TypeError):
        # Never relay GitHub, browser callback, private key or subprocess payloads.
        print(json.dumps({'state': 'unverified', 'error': 'Registration stage incomplete; '
                          'retain any created authority resources for trusted recovery. '
                          'No enforcement was activated.'}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
