"""Trusted native App registration with durable capture before dependent effects.

This never stages secrets or activates enforcement. Public setup remains held.
"""
import copy
import json
import re
from urllib.parse import quote

import app_proofs
import authority_release
import bootstrap
from trusted_ci_github import GitHub
from trusted_ci_policy import digest, object_fields, positive, require, sha

PURPOSES = ('admin', 'reader', 'issuer', 'coding', 'merge')


def install(app, owner, repositories, seconds, installation=None, before_call=None):
    guard = before_call if before_call is not None else lambda: None
    require(callable(guard), 'installation guard must be callable')
    guard()
    if installation is None:
        installation = bootstrap.await_installation(app, owner, seconds=seconds, before_call=before_call)
    guard()
    api = bootstrap.app_api(app['id'], app['pem'])
    guard()
    info = api.get('/app')
    require(info.get('id') == app['id'] and info.get('slug') == app['slug'] and
            info.get('owner', {}).get('id') == owner and
            app_proofs.normalized(info.get('permissions')) == app_proofs.normalized(app['permissions']),
            'registered App identity or domain changed')
    guard()
    observed = api.get('/app/installations/' + str(installation))
    require(observed.get('app_id') == app['id'] and observed.get('account', {}).get('id') == owner and
            observed.get('repository_selection') == 'selected' and observed.get('suspended_at') is None and
            app_proofs.normalized(observed.get('permissions')) == app_proofs.normalized(app['permissions']),
            'registered installation identity or permission domain differs')
    # Omit repository_ids deliberately: enumerating a token already narrowed to
    # the desired IDs would hide extra repositories granted to the installation.
    # Only contents:read is needed; some capabilities (workflows) have no read.
    guard()
    result = api.post('/app/installations/' + str(installation) + '/access_tokens',
                      dict(permissions=dict(contents='read')))
    token = result.get('token')
    try:
        guard()
        require(isinstance(token, str) and token and
                app_proofs.normalized(result.get('permissions')) == dict(contents='read') and
                sorted(item['id'] for item in result.get('repositories', [])) == sorted(repositories),
                'complete registered installation scope differs')
        scoped = GitHub(token)
        guard()
        visible = scoped.pages('/installation/repositories', 'repositories')
        require(sorted(item['id'] for item in visible) == sorted(repositories), 'installation reaches unexpected repositories')
        guard()
        bot = scoped.get('/users/' + quote(app['slug'] + '[bot]', safe=''))
        require(positive(bot.get('id')) and bot.get('type') == 'Bot', 'registered App bot identity unavailable')
        guard()
    finally:
        bootstrap.revoke_token(result)
    return dict(id=app['id'], slug=app['slug'], installation_id=installation, actor_id=bot['id'])


class Registration:
    def __init__(self, gh, journal, clock, registrar=bootstrap.register_app, installer=None):
        self.gh, self.journal, self.clock = gh, journal, clock
        self.registrar, self.installer = registrar, installer
        self.document = None

    def _facts(self, source, authority, software):
        require(source != authority and sha(software) and all(isinstance(name, str) and
            re.fullmatch('[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', name) and
            all(p not in ('.', '..') for p in name.split('/')) for name in (source, authority)),
            'distinct source and authority coordinates required')
        user = self.gh.api('/user')
        require(positive(user.get('id')) and user.get('type') == 'User' and isinstance(user.get('login'), str),
                'native human registration actor required')
        repositories = [self.gh.api('/repos/' + name) for name in (source, authority)]
        for name, repo in zip((source, authority), repositories):
            require(repo.get('full_name') == name and positive(repo.get('id')) and
                    repo.get('permissions', {}).get('admin') is True and positive(repo.get('owner', {}).get('id')),
                    'native administrator access to exact repository required')
        require(repositories[0]['id'] != repositories[1]['id'] and repositories[1].get('private') is True and
                repositories[0]['owner']['id'] == repositories[1]['owner']['id'], 'private same-owner independent authority required')
        owner, organization = repositories[1]['owner']['id'], None
        if user['id'] != owner:
            organization = authority.split('/')[0]
            membership = self.gh.api('/user/memberships/orgs/' + organization)
            account = self.gh.api('/orgs/' + organization)
            require(account.get('id') == owner and membership.get('state') == 'active' and
                    membership.get('role') == 'admin', 'current organization owner required')
        branch = repositories[1].get('default_branch')
        require(isinstance(branch, str) and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_/-]{0,99}', branch) and
                '..' not in branch and '//' not in branch, 'plain authority software branch required')
        require(self.gh.api('/repos/' + authority + '/git/ref/heads/' + quote(branch, safe=''))['object']['sha'] == software,
                'registration software pin changed')
        return dict(source=source, source_id=repositories[0]['id'], authority=authority, authority_id=repositories[1]['id'],
            software_revision=software, operator_id=user['id'], owner_id=owner, organization=organization,
            purposes={purpose: dict(bootstrap.PERMISSIONS[purpose]) for purpose in PURPOSES}, enforcement_active=False)

    def preview(self, source, authority, software):
        facts = self._facts(source, authority, software)
        now = self.clock()
        require(positive(now), 'positive registration clock required')
        return dict(schema_version=1, kind='registration-setup-preview', **facts, created=now, expires=now + 3600)

    def run(self, preview, approval):
        authority_release.authorize('bootstrap')
        return self._run(preview, approval)

    def _guard(self, preview, approval):
        object_fields(preview, ('schema_version kind source source_id authority authority_id software_revision operator_id '
            'owner_id organization purposes enforcement_active created expires').split(), 'registration setup preview')
        require(type(preview['schema_version']) is int and preview['schema_version'] == 1 and
                preview['kind'] == 'registration-setup-preview' and digest(preview) == approval and
                positive(preview['created']) and positive(preview['expires']) and
                0 < preview['expires'] - preview['created'] <= 3600, 'complete approved registration preview required')
        facts = self._facts(preview['source'], preview['authority'], preview['software_revision'])
        require(facts == {key: preview[key] for key in facts} and
                preview['created'] <= self.clock() < preview['expires'], 'registration approval or identity expired/changed')
        if self.document is not None:
            require(self.journal.read() == self.document, 'registration journal changed')

    def _save(self, value):
        self.document = self.journal.write(self.document, value)

    def _validate_app(self, app, purpose, preview):
        require(isinstance(app, dict) and positive(app.get('id')) and isinstance(app.get('pem'), str) and
                0 < len(app['pem']) <= 16384 and isinstance(app.get('slug'), str) and
                re.fullmatch('[A-Za-z0-9_-]{1,100}', app['slug']) and app.get('owner', {}).get('id') == preview['owner_id'] and
                app_proofs.normalized(app.get('permissions')) == bootstrap.PERMISSIONS[purpose], 'captured App identity/domain differs')

    def _run(self, preview, approval):
        self._guard(preview, approval)
        self.document = self.journal.read()
        if self.document is None:
            self._save(dict(schema_version=1, kind='private-registration', preview=copy.deepcopy(preview), apps={}))
        state = self.document['value']
        object_fields(state, ('schema_version', 'kind', 'preview', 'apps'), 'retained registration')
        require(type(state['schema_version']) is int and state['schema_version'] == 1 and
                state['kind'] == 'private-registration' and state['preview'] == preview and
                isinstance(state['apps'], dict) and set(state['apps']) <= set(PURPOSES), 'retained registration differs')
        controller = self
        for purpose in PURPOSES:
            self._guard(preview, approval)
            state = copy.deepcopy(self.document['value'])
            if purpose not in state['apps']:
                state['apps'][purpose] = dict(phase='registration-started', registration=None, identity=None)
                self._save(state)
                class Capture:
                    def exchange(self, code):
                        controller._guard(preview, approval)
                        response = controller.gh.exchange(code)
                        # Retain key bytes before validation, browser acknowledgement
                        # or installation can fail. Unknown exchanges are not repeated.
                        retained = {key: response.get(key) for key in ('id', 'slug', 'pem', 'owner', 'permissions')}
                        require(len(json.dumps(retained).encode()) <= 32768, 'registration response exceeds protected limit')
                        next_state = copy.deepcopy(controller.document['value'])
                        require(next_state['apps'][purpose]['phase'] == 'registration-started', 'duplicate registration callback')
                        next_state['apps'][purpose].update(phase='captured', registration=retained)
                        controller._save(next_state)
                        return response
                self.registrar(purpose, Capture(), preview['organization'])
                state = copy.deepcopy(self.document['value'])
            entry = state['apps'][purpose]
            object_fields(entry, ('phase', 'registration', 'identity'), 'retained App registration')
            require(entry['phase'] in ('captured', 'installed'), 'registration outcome unknown; automatic retry/adoption refused')
            self._validate_app(entry['registration'], purpose, preview)
            require(entry['registration']['id'] not in [item['registration']['id'] for key, item in state['apps'].items()
                    if key != purpose and item['registration'] is not None], 'purpose Apps must be distinct')
            self._guard(preview, approval)
            repositories = [preview['source_id']] + ([preview['authority_id']] if purpose in ('admin', 'reader') else [])
            if self.installer is None:
                identity = install(entry['registration'], preview['owner_id'], repositories,
                    min(600, preview['expires'] - self.clock()),
                    entry['identity']['installation_id'] if entry['phase'] == 'installed' else None)
            else: identity = self.installer(entry['registration'], preview['owner_id'], repositories)
            self._guard(preview, approval)
            object_fields(identity, ('id', 'slug', 'installation_id', 'actor_id'), 'registered identity')
            require(identity['id'] == entry['registration']['id'] and identity['slug'] == entry['registration']['slug'] and
                    positive(identity['installation_id']) and positive(identity['actor_id']), 'installation/bot identity differs')
            if entry['phase'] == 'installed':
                require(identity == entry['identity'], 'retained installation changed')
            else:
                state['apps'][purpose].update(phase='installed', identity=identity)
                self._save(state)
        identities = dict(schema_version=2, owner_id=preview['owner_id'], apps={
            purpose: copy.deepcopy(self.document['value']['apps'][purpose]['identity']) for purpose in PURPOSES})
        require(len({v['actor_id'] for v in identities['apps'].values()}) == 5 and
                len({v['installation_id'] for v in identities['apps'].values()}) == 5, 'separate registered bots/installations required')
        return dict(identities=identities, enforcement_active=False)
