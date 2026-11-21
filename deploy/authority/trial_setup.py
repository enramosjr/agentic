"""Provision disposable qualification resources; never admit execution or activate.

The trusted caller supplies frozen fixture/runtime bytes and an already admitted
configuration session. Production Apps are neither reused nor extended. Public
entry remains release-held, including before protected journal creation.
"""
import copy
import secrets
from pathlib import Path

import authority_release
import app_proofs
import bootstrap
import configuration
import operator_setup
import private_setup
import registration
import setup
from trusted_ci_policy import digest, object_fields, positive, require


class Provision:
    def __init__(self, session, api, gh, root, fixture_files, authority_files, clock,
                 store_factory=private_setup.Store, registrar=bootstrap.register_app, installer=None):
        self.session, self.api, self.gh, self.root = session, api, gh, Path(root)
        self.fixture_files, self.authority_files = dict(fixture_files), dict(authority_files)
        self.clock, self.store, self.registrar, self.installer = clock, store_factory, registrar, installer
        self.journal = self.document = self.preview = None

    def _origin(self, fixture, authority):
        require(isinstance(self.session, configuration.ConfigurationSession), 'owned configuration session required')
        require(fixture != authority and isinstance(fixture, str) and isinstance(authority, str),
                'distinct disposable fixture and authority required')
        current = self.session.require_effect('qualification-fixture', fixture)
        require(self.session.require_effect('qualification-fixture', authority) == current,
                'trial configuration changed between scope reads')
        d, p = current['deployment'], current['deployment']['policy']
        require(d['state'] == 'qualification' and d['qualification'] is None and
                type(self.clock()) is int and 0 < self.clock() < d['expires'],
                'unqualified current configuration required for trial provisioning')
        require(set((fixture.lower(), authority.lower())).isdisjoint(
                    {p['repository'].lower(), p['authority_repository'].lower()}) and
                fixture.split('/')[0].lower() == authority.split('/')[0].lower() ==
                p['authority_repository'].split('/')[0].lower(),
                'new same-adopter disposable repositories required')
        return dict(configuration_revision=current['configuration_revision'], deployment_digest=current['deployment_digest'],
            branch_head=current['branch_head'], operation_id=self.session.operation_id, sequence=self.session.sequence,
            workflow_sha=p['workflow_sha'], adapter=d['adapter'], account=d['account'])

    def _guard(self):
        p = self.preview
        require(self._origin(p['fixture']['repository'], p['authority']['repository']) == p['origin'],
                'trial origin configuration or fence changed')
        require(p['created'] <= self.clock() < p['expires'], 'trial provisioning consent expired')
        require(self.journal.read() == self.document, 'trial provisioning journal changed')

    def _save(self, state):
        self.document = self.journal.write(self.document, state)

    def completed(self):
        """Read the exact completed pair without provisioning or installing again.

        A configured trial has its own registry branch, so replaying initial
        installation (which requires that branch absent) is not a readback API.
        """
        authority_release.authorize('bootstrap')
        from repository import Repository
        self.journal = self.store(self.root / 'trial')
        self.document = self.journal.read()
        require(self.document is not None, 'completed trial provisioning required')
        state = self.document['value']
        object_fields(state, ('schema_version', 'kind', 'preview', 'approval', 'fixture', 'connected', 'storage_version', 'storage_id'), 'retained trial provisioning')
        from trial_storage import namespace
        namespace(self)
        require(type(state['schema_version']) is int and state['schema_version'] == 1 and
                state['kind'] == 'private-qualification-fixture' and state['approval'] == digest(state['preview']) and
                isinstance(state['fixture'], dict) and isinstance(state['connected'], dict),
                'completed trial provisioning required')
        self.preview = state['preview']
        self._guard()
        seed, connected = state['fixture'], state['connected']
        for name, identity, revision, files in (
                (self.preview['fixture']['repository'], seed['repository_id'], seed['revision'], self.fixture_files),
                (self.preview['authority']['repository'], connected['authority_repository_id'],
                 connected['software_revision'], self.authority_files)):
            self._guard()
            repo = self.api.get('/repos/' + name)
            require(repo.get('id') == identity and repo.get('full_name') == name and repo.get('private') is True and
                    repo.get('owner', {}).get('id') == self.preview['fixture']['owner_id'], 'trial repository identity changed')
            release = setup.InitialAuthority(self.api, None, files, self.clock)._release()
            preview = self.preview['fixture' if name == self.preview['fixture']['repository'] else 'authority']
            require(preview['release'] == release, 'trial approved release changed')
            installer = Repository(self.api, name, identity, repo['default_branch'])
            observed = installer.inspect()
            require(observed[0] == revision and observed[3]['files'] == release['files'], 'trial frozen software changed')
            # inspect authenticates every owned blob against the release marker.
        production = self.session._check()['deployment']
        require(seed['repository_id'] != connected['authority_repository_id'] and
                {seed['repository_id'], connected['authority_repository_id']}.isdisjoint(
                    {production['policy']['repository_id'], production['policy']['authority_repository_id']}) and
                set(v['id'] for v in connected['identities']['apps'].values()).isdisjoint(production['apps'].values()),
                'trial must not borrow production resources or App identities')
        self._guard()
        return dict(state='fixture-provisioned', origin=copy.deepcopy(self.preview['origin']),
            fixture_repository=self.preview['fixture']['repository'], fixture_repository_id=seed['repository_id'],
            fixture_revision=seed['revision'], authority_repository=self.preview['authority']['repository'],
            authority_repository_id=connected['authority_repository_id'], software_revision=connected['software_revision'],
            identities=copy.deepcopy(connected['identities']), enforcement_active=False,
            hosted_qualified=False, execution_admitted=False)

    def run(self, fixture, authority, approve):
        authority_release.authorize('bootstrap')
        origin = self._origin(fixture, authority)
        # Distinct purpose roots: no production setup/model journal is borrowed.
        self.journal = self.store(self.root / 'trial')
        self.document = self.journal.read()
        fixture_setup = setup.InitialAuthority(self.api, self.store(self.root / 'fixture'), self.fixture_files, self.clock)
        authority_setup = setup.InitialAuthority(self.api, self.store(self.root / 'authority-preview'), self.authority_files, self.clock)
        if self.document is None:
            proposed_fixture = fixture_setup.preview(fixture)
            proposed_authority = authority_setup.preview(authority)
            require(proposed_fixture['owner_id'] == proposed_authority['owner_id'] and
                    proposed_fixture['operator_id'] == proposed_authority['operator_id'], 'trial ownership differs')
            now = self.clock()
            preview = dict(schema_version=1, kind='qualification-fixture-preview', origin=origin,
                fixture=proposed_fixture, authority=proposed_authority, created=now,
                expires=min(proposed_fixture['expires'], proposed_authority['expires']),
                enforcement_active=False, execution_admitted=False)
            approval = approve(copy.deepcopy(preview))
            require(approval == digest(preview), 'exact disposable fixture consent required')
            self.preview = preview
            self._guard()
            self._save(dict(schema_version=1, kind='private-qualification-fixture', preview=preview,
                            storage_version=2,storage_id=secrets.token_hex(16),
                            approval=approval, fixture=None, connected=None))
        state = copy.deepcopy(self.document['value'])
        object_fields(state, ('schema_version', 'kind', 'preview', 'approval', 'fixture', 'connected', 'storage_version', 'storage_id'), 'retained trial provisioning')
        from trial_storage import namespace
        namespace(self)
        require(type(state['schema_version']) is int and state['schema_version'] == 1 and
                state['kind'] == 'private-qualification-fixture' and state['approval'] == digest(state['preview']),
                'retained trial provisioning consent differs')
        self.preview = state['preview']
        object_fields(self.preview, ('schema_version', 'kind', 'origin', 'fixture', 'authority', 'created', 'expires',
                                    'enforcement_active', 'execution_admitted'), 'trial preview')
        require(type(self.preview['schema_version']) is int and self.preview['schema_version'] == 1 and
                self.preview['kind'] == 'qualification-fixture-preview' and self.preview['enforcement_active'] is False and
                self.preview['execution_admitted'] is False and positive(self.preview['created']) and
                positive(self.preview['expires']) and 0 < self.preview['expires'] - self.preview['created'] <= 3600 and
                self.preview['fixture']['repository'] == fixture and self.preview['authority']['repository'] == authority and
                self.preview['origin'] == origin and
                self.preview['fixture']['release'] == fixture_setup._release() and
                self.preview['authority']['release'] == authority_setup._release(), 'retained trial resources or release changed')
        self._guard()
        api, gh = _API(self, self.api), _Gh(self, self.gh)
        fixture_setup.api = api
        seed = fixture_setup.run(self.preview['fixture'], digest(self.preview['fixture']))
        require(state['fixture'] in (None, seed), 'retained fixture identity changed')
        if state['fixture'] is None:
            state['fixture'] = seed
            self._save(state)

        def consent(value):
            self._guard()
            if value['kind'] == 'initial-authority-preview':
                # Pair consent already approved these exact bytes/owner/name.
                # A later generated timestamp must not extend the outer deadline.
                ignore = ('created', 'expires')
                require({k: v for k, v in value.items() if k not in ignore} ==
                        {k: v for k, v in self.preview['authority'].items() if k not in ignore},
                        'trial authority differs from pair consent')
                return digest(value)
            require(value['kind'] == 'registration-setup-preview' and value['source'] == fixture and
                    value['source_id'] == seed['repository_id'] and value['authority'] == authority and
                    value['owner_id'] == self.preview['fixture']['owner_id'], 'trial App consent scope differs')
            result = approve(copy.deepcopy(value))
            self._guard()
            return result

        def registrar(*args):
            self._guard()
            return self.registrar(*args)

        def installer(*args):
            self._guard()
            app, owner, repositories = args
            production = self.session._check()['deployment']
            require(app['id'] not in production['apps'].values(), 'trial cannot install a production App')
            require(repositories == ([seed['repository_id'], operator.document['value']['installation']['repository_id']]
                    if app_proofs.normalized(app['permissions']) in
                    (bootstrap.PERMISSIONS['admin'], bootstrap.PERMISSIONS['reader']) else
                    [seed['repository_id']]), 'trial installation scope changed')
            if self.installer is not None:
                return self.installer(*args)
            retained = self.store(self.root / 'trial-operator' / 'registration').read()['value']['apps']
            entry = next(v for v in retained.values() if v['registration']['id'] == app['id'])
            identity = entry['identity']
            return registration.install(app, owner, repositories, min(600, self.preview['expires'] - self.clock()),
                                        identity['installation_id'] if identity is not None else None, before_call=self._guard)

        operator = operator_setup.Operator(api, gh, self.root / 'trial-operator', self.authority_files,
            self.clock, store_factory=self.store, registrar=registrar,
            installer=installer)
        connected = operator.connect(fixture, authority, consent)
        self._guard()
        require(connected['authority_repository_id'] != seed['repository_id'] and
                connected['identities']['owner_id'] == self.preview['fixture']['owner_id'] and
                state['connected'] in (None, connected), 'trial identity or retained registration changed')
        production = self.session._check()['deployment']
        require(set(v['id'] for v in connected['identities']['apps'].values()).isdisjoint(production['apps'].values()) and
                {seed['repository_id'], connected['authority_repository_id']}.isdisjoint(
                    {production['policy']['repository_id'], production['policy']['authority_repository_id']}),
                'trial must not borrow production resources or App identities')
        if state['connected'] is None:
            state['connected'] = connected
            self._save(state)
        return dict(state='fixture-provisioned', origin=copy.deepcopy(origin), fixture_repository=fixture,
            fixture_repository_id=seed['repository_id'], fixture_revision=seed['revision'],
            authority_repository=authority, authority_repository_id=connected['authority_repository_id'],
            software_revision=connected['software_revision'], identities=connected['identities'],
            enforcement_active=False, hosted_qualified=False, execution_admitted=False)


class _API:
    """Recheck the original configuration fence before each setup API boundary."""
    def __init__(self, controller, api): self.controller, self.api = controller, api
    def get(self, *args, **kwargs):
        self.controller._guard()
        return self.api.get(*args, **kwargs)
    def post(self, *args, **kwargs):
        self.controller._guard()
        result = self.api.post(*args, **kwargs)
        if args[0] == '/user/repos' or args[0].startswith('/orgs/') and args[0].endswith('/repos'):
            c = self.controller
            p = c.session._check()['deployment']['policy']
            seed = c.document['value']['fixture']
            forbidden = {p['repository_id'], p['authority_repository_id']}
            if seed is not None: forbidden.add(seed['repository_id'])
            require(isinstance(result, dict) and positive(result.get('id')) and result['id'] not in forbidden,
                    'created trial repository substituted a retained resource')
        return result
    def fetch(self, *args, **kwargs):
        self.controller._guard()
        return self.api.fetch(*args, **kwargs)


class _Gh:
    def __init__(self, controller, gh): self.controller, self.gh = controller, gh
    def api(self, *args, **kwargs):
        self.controller._guard()
        return self.gh.api(*args, **kwargs)
    def exchange(self, *args, **kwargs):
        self.controller._guard()
        return self.gh.exchange(*args, **kwargs)
