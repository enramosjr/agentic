"""Candidate-free own-App probes. Authenticate the parent artifact before use."""
from __future__ import annotations

from pathlib import Path
import re
import sys
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.ai/scripts'))
from authority_protocol import validate_deployment
from bootstrap import PERMISSIONS
from trusted_ci_github import GitHub, HostRefusal
from trusted_ci_policy import digest, loads, object_fields, positive, require, sha

TOKEN_PERMISSIONS = {purpose: dict(permissions) for purpose, permissions in PERMISSIONS.items()}
TOKEN_PERMISSIONS['admin'] = {'administration': 'read', 'contents': 'read', 'pull_requests': 'read',
                              'repository_hooks': 'read'}
WRITE_CAPABILITIES = ('administration', 'checks', 'statuses', 'workflows', 'contents', 'actions',
                      'secrets', 'variables', 'pull_requests', 'repository_hooks')
FIELDS = ('schema_version purpose app_id installation_id bot_id owner_id repository_ids '
          'registered_permissions token_permissions denials deployment_digest generation '
          'registry_revision observed expires isolation_established').split()


def normalized(permissions):
    require(isinstance(permissions, dict), 'App permissions unavailable')
    result = dict(permissions)
    require(result.pop('metadata', 'read') == 'read', 'App metadata permission differs')
    return result


def load_identities(d):
    """Only the pinned registry selects public identities; never caller paths."""
    validate_deployment(d)
    raw = d['resources'].get('identity_record')
    require(isinstance(raw, str) and 0 < len(raw.encode('utf-8')) <= 2048,
            'pinned purpose identity record required')
    return identity_record(d, loads(raw))


def identity_record(d, identities):
    validate_deployment(d)
    object_fields(identities, ('schema_version', 'owner_id', 'apps'), 'purpose identities')
    require(type(identities['schema_version']) is int and identities['schema_version'] == 2 and
            positive(identities['owner_id']) and digest(identities) == d['resources'].get('identity_digest'),
            'purpose identity configuration differs')
    object_fields(identities['apps'], PERMISSIONS, 'purpose App identities')
    for purpose, record in identities['apps'].items():
        object_fields(record, ('id', 'slug', 'installation_id', 'actor_id'), 'App identity')
        require(record['id'] == d['apps'][purpose] and positive(record['installation_id']) and
                positive(record['actor_id']) and isinstance(record['slug'], str) and
                re.fullmatch('[A-Za-z0-9_-]{1,100}', record['slug']), 'App identity substitution')
    require(d['policy']['coding_actors'] == [identities['apps']['coding']['actor_id']],
            'strong mode requires the registered coding bot identity')
    require(d['policy']['merge_actors'] == [identities['apps']['merge']['actor_id']] and
            not set(d['policy']['merge_actors']) & set(d['policy']['reviewers']),
            'strong mode requires a separate merge bot and independent human reviewers')
    return identities


def expected_denials(purpose):
    result = ['permission:' + key for key in WRITE_CAPABILITIES if PERMISSIONS[purpose].get(key) != 'write']
    if purpose in ('coding', 'issuer', 'merge'):
        result.append('installation:authority')
    if purpose in ('coding', 'merge'):
        result.append('repository:authority')
    return result


def revoke(result, token_factory):
    token = result.get('token') if isinstance(result, dict) else None
    if isinstance(token, str) and token:
        token_factory(token).fetch('/installation/token', method='DELETE', binary=True)


def denial(api, installation, repos, permissions, category, token_factory):
    try:
        result = api.post('/app/installations/' + str(installation) + '/access_tokens',
                          {'repository_ids': repos, 'permissions': permissions})
    except HostRefusal as error:
        require(error.status == 422 and error.category == category, 'App mint denial has an unexpected cause')
    else:
        revoke(result, token_factory)
        require(False, 'App minted a forbidden capability')


def authenticate(api, authority_reader, d, identities, purpose):
    """Authenticate the own-App domain, also for terminal-only expired recovery."""
    identity_record(d, identities)
    require(purpose in PERMISSIONS, 'fixed own-App purpose required')
    record, p = identities['apps'][purpose], d['policy']
    owner = identities['owner_id']
    info = api.get('/app')
    require(info['id'] == record['id'] and info['slug'] == record['slug'] and info['owner']['id'] == owner and
            normalized(info['permissions']) == PERMISSIONS[purpose], 'registered App domain changed')
    authority = authority_reader.get('/repos/' + p['authority_repository'])
    require(authority['id'] == p['authority_repository_id'] and authority.get('private') is True and
            authority['owner']['id'] == owner, 'authority identity or ownership changed')
    repositories = [p['repository_id']]
    names = [p['repository']]
    if purpose in ('admin', 'reader'):
        repositories.append(p['authority_repository_id'])
        names.append(p['authority_repository'])
    for route in [*('/repos/' + name + '/installation' for name in names),
                  '/app/installations/' + str(record['installation_id'])]:
        installation = api.get(route)
        require(installation['id'] == record['installation_id'] and installation['app_id'] == record['id'] and
                installation['account']['id'] == owner and installation.get('suspended_at') is None and
                installation.get('repository_selection') == 'selected' and
                normalized(installation['permissions']) == PERMISSIONS[purpose], 'App installation domain changed')


def prove(api, authority_reader, d, identities, purpose, registry_revision, now, token_factory=GitHub):
    """API is THIS App's JWT only. Never pass another purpose's root credential."""
    require(sha(registry_revision) and type(now) is int and 0 < now < d['expires'],
            'current App proof coordinates required')
    authenticate(api, authority_reader, d, identities, purpose)
    record, p, owner = identities['apps'][purpose], d['policy'], identities['owner_id']
    repositories = [p['repository_id']] + ([p['authority_repository_id']] if purpose in ('admin','reader') else [])
    permissions = TOKEN_PERMISSIONS[purpose]
    result = api.post('/app/installations/' + str(record['installation_id']) + '/access_tokens',
                      {'repository_ids': repositories, 'permissions': permissions})
    try:
        require(isinstance(result.get('token'), str) and result['token'] and
                normalized(result.get('permissions')) == permissions and
                sorted(r['id'] for r in result.get('repositories', [])) == sorted(repositories),
                'App probe token differs from explicit scope')
        scoped = token_factory(result['token'])
        visible = scoped.pages('/installation/repositories', 'repositories')
        require(sorted(r['id'] for r in visible) == sorted(repositories), 'probe token reaches an unexpected repository')
        bot = scoped.get('/users/' + quote(record['slug'] + '[bot]', safe=''))
        require(bot['id'] == record['actor_id'] and bot.get('type') == 'Bot', 'App bot identity changed')
    finally:
        revoke(result, token_factory)
    for capability in WRITE_CAPABILITIES:
        if PERMISSIONS[purpose].get(capability) != 'write':
            denial(api, record['installation_id'], [p['repository_id']], {capability: 'write'},
                   'permission_scope', token_factory)
    if purpose in ('coding', 'issuer', 'merge'):
        try:
            api.get('/repos/' + p['authority_repository'] + '/installation')
        except HostRefusal as error:
            require(error.status == 404, 'authority installation probe failed for an unexpected cause')
        else:
            require(False, 'non-authority App is installed on the authority')
    if purpose in ('coding', 'merge'):
        denial(api, record['installation_id'], [p['authority_repository_id']], {'contents': 'write'},
               'repository_scope', token_factory)
    return {'schema_version': 2, 'purpose': purpose, 'app_id': record['id'],
        'installation_id': record['installation_id'], 'bot_id': record['actor_id'], 'owner_id': owner,
        'repository_ids': repositories, 'registered_permissions': dict(PERMISSIONS[purpose]),
        'token_permissions': dict(permissions), 'denials': expected_denials(purpose),
        'deployment_digest': digest(d), 'generation': d['generation'], 'registry_revision': registry_revision,
        'observed': now, 'expires': min(now + 300, d['expires']), 'isolation_established': False}


def validate(proof, d, identities, purpose, registry_revision, now):
    """Document validation only; caller must first authenticate the pinned job."""
    identity_record(d, identities)
    require(purpose in PERMISSIONS and sha(registry_revision), 'unknown purpose proof binding')
    object_fields(proof, FIELDS, 'App capability proof')
    record = identities['apps'][purpose]
    repositories = [d['policy']['repository_id']]
    if purpose in ('admin', 'reader'):
        repositories.append(d['policy']['authority_repository_id'])
    require(type(proof['schema_version']) is int and proof['schema_version'] == 2 and proof['purpose'] == purpose and
            proof['app_id'] == record['id'] and proof['installation_id'] == record['installation_id'] and
            proof['bot_id'] == record['actor_id'] and proof['owner_id'] == identities['owner_id'] and
            proof['repository_ids'] == repositories and proof['registered_permissions'] == PERMISSIONS[purpose] and
            proof['token_permissions'] == TOKEN_PERMISSIONS[purpose] and proof['denials'] == expected_denials(purpose),
            'App capability proof domain differs')
    require(proof['deployment_digest'] == digest(d) and proof['generation'] == d['generation'] and
            proof['registry_revision'] == registry_revision and proof['isolation_established'] is False,
            'App proof binding or isolation claim differs')
    require(type(now) is int and positive(proof['observed']) and positive(proof['expires']) and
            proof['observed'] <= now < proof['expires'] <= d['expires'] and
            proof['expires'] - proof['observed'] <= 300, 'App capability proof expired or future')
    return proof
