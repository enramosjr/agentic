"""Trusted setup composition. Public privileged entrypoints remain release-held.

The first installation has no registry fence yet. Its only capability is an
exact release transition in a newly created private repository. It cannot repair
or adopt an existing resource, configure protections, or activate enforcement.
"""
import copy
import hashlib
import re

import authority_release
from trusted_ci_github import HostRefusal
from trusted_ci_policy import Refusal, digest, object_fields, positive, require, sha
from repository import Repository, valid_path


class InitialAuthority:
    def __init__(self, api, journal, files, clock):
        self.api, self.journal, self.files, self.clock = api, journal, dict(files), clock
        self.document = None

    def _release(self):
        require(self.files and len(self.files) <= 500 and
                all(isinstance(raw, bytes) and len(raw) <= 1024 * 1024 for raw in self.files.values()) and
                sum(map(len, self.files.values())) <= 64 * 1024 * 1024, 'bounded fixed release required')
        for path in self.files: valid_path(path)
        return dict(files={path: hashlib.sha256(raw).hexdigest() for path, raw in self.files.items()})

    def _operator(self, repository):
        user = self.api.get('/user')
        require(positive(user.get('id')) and user.get('type') == 'User' and
                isinstance(user.get('login'), str), 'native human setup identity required')
        owner = repository.split('/')[0]
        if user['login'].lower() == owner.lower():
            return dict(operator_id=user['id'], owner_id=user['id'], organization=None)
        account = self.api.get('/orgs/' + owner)
        membership = self.api.get('/user/memberships/orgs/' + owner)
        require(positive(account.get('id')) and account.get('login', '').lower() == owner.lower() and
                membership.get('state') == 'active' and membership.get('role') == 'admin',
                'current organization owner access required')
        return dict(operator_id=user['id'], owner_id=account['id'], organization=account['login'])

    def _missing(self, route):
        try: self.api.get(route)
        except HostRefusal as error:
            require(error.status == 404, 'resource absence is not authenticated')
            return
        require(False, 'initial installation cannot adopt an existing resource')

    def preview(self, repository):
        require(isinstance(repository, str) and re.fullmatch(
            r'[A-Za-z0-9][A-Za-z0-9-]{0,99}/[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', repository),
            'new authority repository name required')
        identity = self._operator(repository)
        self._missing('/repos/' + repository)
        now = self.clock()
        require(positive(now), 'bounded setup clock required')
        return dict(schema_version=1, kind='initial-authority-preview', repository=repository,
            **identity, private=True, registry_branch='agentic-registry', release=self._release(),
            created=now, expires=now + 3600, cost_owner=repository.split('/')[0],
            billable_types=['GitHub repository storage'], enforcement_active=False)

    def run(self, preview, approval):
        authority_release.authorize('bootstrap')  # Before authentication or journal access.
        return self._run(preview, approval)

    def _approved(self, preview, approval):
        object_fields(preview, ('schema_version kind repository operator_id owner_id organization private '
            'registry_branch release created expires cost_owner billable_types enforcement_active').split(),
            'initial authority preview')
        require(type(preview['schema_version']) is int and preview['schema_version'] == 1 and
                preview['kind'] == 'initial-authority-preview' and preview['private'] is True and
                preview['registry_branch'] == 'agentic-registry' and preview['enforcement_active'] is False and
                isinstance(preview['repository'], str) and re.fullmatch(
                    r'[A-Za-z0-9][A-Za-z0-9-]{0,99}/[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', preview['repository']) and
                positive(preview['created']) and positive(preview['expires']) and
                0 < preview['expires'] - preview['created'] <= 3600 and positive(self.clock()) and
                preview['created'] <= self.clock() < preview['expires'] and
                preview['release'] == self._release() and digest(preview) == approval and
                preview['cost_owner'] == preview['repository'].split('/')[0] and
                preview['billable_types'] == ['GitHub repository storage'], 'fresh complete initial approval required')
        require(self._operator(preview['repository']) == {k: preview[k] for k in
                ('operator_id', 'owner_id', 'organization')}, 'initial setup identity changed')
        now = self.clock()
        require(positive(now) and preview['created'] <= now < preview['expires'], 'initial setup approval expired')

    def _save(self, value):
        self.document = self.journal.write(self.document, value)

    def _created(self, preview, value):
        require(value.get('full_name') == preview['repository'] and positive(value.get('id')) and
                value.get('private') is True and value.get('owner', {}).get('id') == preview['owner_id'] and
                value.get('permissions', {}).get('admin') is True and
                isinstance(value.get('default_branch'), str), 'fresh private authority creation identity differs')
        return dict(repository_id=value['id'], branch=value['default_branch'])

    def _run(self, preview, approval):
        self._approved(preview, approval)
        self.document = self.journal.read()
        if self.document is None:
            self._missing('/repos/' + preview['repository'])
            self._save(dict(schema_version=1, kind='initial-authority-setup', preview=copy.deepcopy(preview),
                phase='approved', creation=None, plan=None, revision=None))
        state = self.document['value']
        object_fields(state, ('schema_version', 'kind', 'preview', 'phase', 'creation', 'plan', 'revision'), 'private initial setup')
        require(type(state['schema_version']) is int and state['schema_version'] == 1 and
                state['kind'] == 'initial-authority-setup' and state['preview'] == preview and
                state['phase'] in ('approved', 'create-started', 'created', 'prepared', 'installed'),
                'retained initial setup differs')
        state = copy.deepcopy(state)
        if state['phase'] == 'approved':
            require(state['creation'] is None and state['plan'] is None and state['revision'] is None,
                    'initial creation phase differs')
            self._missing('/repos/' + preview['repository'])
            state['phase'] = 'create-started'
            self._save(state)  # An unknown POST is never repeated or recovered by name.
            endpoint = '/orgs/' + preview['organization'] + '/repos' if preview['organization'] else '/user/repos'
            self._approved(preview, approval)
            response = self.api.post(endpoint, dict(name=preview['repository'].split('/')[1], private=True,
                auto_init=True, description='AGENTIC authority setup; enforcement inactive'))
            state['creation'] = self._created(preview, response)
            state['phase'] = 'created'
            self._save(state)
        require(state['phase'] != 'create-started', 'creation outcome unknown; no automatic adoption or retry')
        if state['plan'] is not None:
            require(state['plan'].get('desired') == dict(schema_version=2,
                    files=preview['release']['files'], enforcement_active=False),
                    'prepared installation does not match the approved release')
        creation = state['creation']
        object_fields(creation, ('repository_id', 'branch'), 'retained creation receipt')
        require(positive(creation['repository_id']), 'retained creation identity required')
        session = _FreshInstallation(self, preview, approval, creation)
        installer = Repository(self.api, preview['repository'], creation['repository_id'], creation['branch'], session)
        session.installer = installer
        session.require_effect('software', installer.name + ':' + installer.branch)
        if state['phase'] == 'created':
            require(state['revision'] is None, 'unprepared initial revision differs')
            plan = installer.preview(self.files)
            commit = self.api.get(installer.root + '/git/commits/' + plan['base'])
            observed = installer.inspect()
            require(commit['parents'] == [] and set(observed[2]) == {'README.md'} and
                    observed[2]['README.md'][0] == '100644' and not plan['previous']['files'],
                    'fresh auto-initialized authority tree required')
            installer.blob(observed[2]['README.md'][1])  # Bound the sole initial file.
            if state['plan'] is None:
                state['plan'] = plan
                self._save(state)
            require(plan == state['plan'], 'initial repository changed after retained plan')
            result = installer.apply(self.files, digest(plan))
        else:
            require(state['phase'] in ('prepared', 'installed') and sha(state['revision']) and
                    state['plan'] is not None, 'prepared initial installation required')
            result = installer.resume_transition(state['plan'], state['revision'])
        state = copy.deepcopy(self.document['value'])
        require(result['revision'] == state['revision'], 'initial software result differs from retained commit')
        if state['phase'] != 'installed':
            state['phase'] = 'installed'
            self._save(state)
        return dict(repository=installer.name, repository_id=installer.identity,
                    revision=result['revision'], enforcement_active=False)


class _FreshInstallation:
    """Only initial software writes; never a configuration session substitute."""
    def __init__(self, controller, preview, approval, creation):
        self.controller, self.preview, self.approval, self.creation = controller, preview, approval, creation
        self.installer = None

    def require_effect(self, action, scope):
        c, p, creation = self.controller, self.preview, self.creation
        require(action == 'software' and scope == p['repository'] + ':' + creation['branch'],
                'fresh installation permits only its exact software scope')
        c._approved(p, self.approval)
        require(c.journal.read() == c.document, 'initial setup journal changed')
        current = c.api.get('/repos/' + p['repository'])
        require(c._created(p, current) == creation, 'fresh authority identity changed')
        c._missing('/repos/' + p['repository'] + '/git/ref/heads/' + p['registry_branch'])
        state = c.document['value']
        if state['plan'] is not None:
            require(self.installer.inspect()[0] in (state['plan']['base'], state['revision']),
                    'fresh authority software changed')

    def allow_software_revision(self, repository, branch, revision):
        self.require_effect('software', repository + ':' + branch)
        c = self.controller
        state = copy.deepcopy(c.document['value'])
        require(state['phase'] in ('created', 'prepared') and
                state['revision'] in (None, revision), 'only one prepared initial transition allowed')
        self.installer.authenticate_transition(state['plan'], revision)
        state.update(phase='prepared', revision=revision)
        if state != c.document['value']: c._save(state)  # Durable before pointer publication.


PURPOSES = ('admin', 'reader', 'issuer', 'coding', 'merge')
CREDENTIAL_NAMES = tuple('AGENTIC_' + p.upper() + '_PRIVATE_KEY' for p in PURPOSES) + (
    'AGENTIC_MODEL_VAULT_KEY', 'AGENTIC_MODEL_DELIVERY_KEY')


class TrialReadStaging:
    """Stage one expiring original-authority reader token, never its root key.

    A secret acknowledgement is not consumption proof. The dispatch coordinator
    must authenticate its exact closed consumer before binding execution.
    """
    NAME = 'AGENTIC_TRIAL_ORIGIN_TOKEN'
    JOURNAL = 'trial-read-staging'

    def __init__(self, provision, registry, revision, reader, token_factory):
        self.provision, self.registry, self.revision = provision, registry, revision
        self.reader, self.token_factory = reader, token_factory

    def run(self):
        authority_release.authorize('bootstrap')
        import trial_handoff
        from trial_setup import Provision
        c = self.provision
        require(isinstance(c, Provision), 'actual completed native trial provision required')
        publication = c.store(c.root / 'handoff').read()
        require(publication is not None and publication['value']['phase'] == 'published' and
                publication['value']['revision'] == self.revision, 'retained native handoff publication required')
        record, origin = trial_handoff.read(c.session.registry, self.revision, c.clock())
        require(publication['value']['record'] == record and publication['value']['approval'] == digest(record) and
                c.completed() == record['pair'], 'native handoff consent or completed pair differs')
        session, original = c.session, c.session.registry
        ownership = copy.deepcopy((session.operation_id, session.sequence, session.owner, session.scope, session.software))
        expected = tuple(origin[k] for k in ('configuration_revision', 'deployment_digest', 'branch_head'))
        provision_document = copy.deepcopy(c.document)
        journal = c.store(c.root / self.JOURNAL)
        branch = 'agentic-trial-' + record['task_id']
        def guard(document):
            require(c.session is session and session.registry is original and session.expected == expected and
                    (session.operation_id, session.sequence, session.owner, session.scope, session.software) == ownership and
                    c.journal.read() == provision_document and c.document == provision_document and
                    c.store(c.root / 'handoff').read() == publication and journal.read() == document and
                    record['created'] <= c.clock() < record['expires'], 'native trial delegation changed or expired')
            session._owned(origin)
            original_branch = original.unchanged(origin)
            self.registry.unchanged(record['trial'])
            require(original.ref(original.coordinates['registry_branch']) == origin['branch_head'] and
                    original.ref(original_branch) == origin['software_revision'] and
                    original.ref(branch) == self.revision, 'original pointers moved during final trial observation')
            require(c.journal.read() == provision_document and journal.read() == document and
                    c.store(c.root / 'handoff').read() == publication and c.clock() < record['expires'],
                    'native delegation authorization changed during readback')
        return self._stage(c, record, origin, journal, guard)

    def _stage(self, c, record, origin, journal, check, previous=None):
        """Shared own-App mint/write journal; phases never replay unknown effects."""
        import app_proofs
        from trusted_ci_deployment import timestamp
        original = c.session.registry
        document = journal.read()
        def guard(): check(document)
        self._guard = guard
        guard()
        if document is None:
            prior=c.store(c.root/previous).read() if previous is not None else None
            require(previous is None or prior is not None and prior['value']['phase']=='revoked' and
                    prior['value']['credential'] is not None and prior['value']['revision']!=self.revision,
                    'owned old delegation must be revoked before replacement')
            inventory = c.api.pages(self.registry.root + '/actions/secrets', 'secrets')
            require(isinstance(inventory, list) and len(inventory) <= 10000 and
                    all(isinstance(v, dict) and isinstance(v.get('name'), str) for v in inventory) and
                    (prior is not None or not any(v['name'].upper() == self.NAME for v in inventory)), 'unowned origin-read secret already exists')
            guard()
            document = journal.write(None, dict(revision=self.revision, phase='prepared', credential=None))
        state = copy.deepcopy(document['value'])
        object_fields(state, ('revision', 'phase', 'credential'), 'native trial read staging')
        require(state['revision'] == self.revision and state['phase'] in
                ('prepared', 'mint-started', 'minted', 'secret-started', 'staged'), 'retained trial delegation differs')
        if state['phase'] == 'prepared':
            identities = app_proofs.load_identities(origin['deployment'])
            app_proofs.authenticate(self.reader, original.api, origin['deployment'], identities, 'reader')
            guard()
            state['phase'] = 'mint-started'
            document = journal.write(document, state)
            guard()
            response = self.reader.post('/app/installations/' + str(identities['apps']['reader']['installation_id']) +
                '/access_tokens', dict(repository_ids=[original.coordinates['repository_id']], permissions=dict(contents='read')))
            try:
                require(isinstance(response.get('token'), str) and response['token'] and
                        (previous is None or response['token']!=c.store(c.root/previous).read()['value']['credential']['token']) and
                        app_proofs.normalized(response.get('permissions')) == dict(contents='read') and
                        [v['id'] for v in response.get('repositories', [])] == [original.coordinates['repository_id']],
                        'delegated token scope differs from original authority contents-read')
                expires = int(timestamp(response['expires_at']).timestamp())
                require(c.clock() < expires <= c.clock() + 3600, 'delegated token must be short-lived')
                guard()
                scoped = self.token_factory(response['token'])
                require([v['id'] for v in scoped.pages('/installation/repositories', 'repositories')] ==
                        [original.coordinates['repository_id']], 'delegated read token reaches another repository')
                guard()
                state.update(phase='minted', credential=dict(token=response['token'], expires=expires))
                document = journal.write(document, state)
            except BaseException:
                app_proofs.revoke(response, self.token_factory)
                raise
        require(state['credential'] is not None, 'delegated token mint remains unknown; never mint another')
        credential = state['credential']
        require(c.clock() < min(record['expires'], credential['expires']), 'retained origin-read token expired')
        if state['phase'] == 'minted':
            guard()
            actor = c.gh.api('/user')
            require(actor.get('type') == 'User' and actor.get('id') == c.preview['fixture']['operator_id'],
                    'delegated secret writer differs from native operator')
            guard()
            state['phase'] = 'secret-started'
            document = journal.write(document, state)
            try:
                guard()
                c.gh.secret(record['pair']['authority_repository'], self.NAME, credential['token'])
                guard()
            except Refusal:
                app_proofs.revoke(credential, self.token_factory)
                raise
            state['phase'] = 'staged'
            document = journal.write(document, state)
        guard()
        return dict(revision=self.revision, repository_id=original.coordinates['repository_id'],
            permissions=dict(contents='read'), token_digest=digest(credential['token']),
            expires=min(record['expires'], credential['expires']))

    def revoke(self):
        """Cleanup stays available after expiry; it never mints or stages another token."""
        authority_release.authorize('bootstrap')
        import app_proofs
        from trial_setup import Provision
        require(isinstance(self.provision, Provision), 'actual native trial purpose required for cleanup')
        journal = self.provision.store(self.provision.root / self.JOURNAL)
        document = journal.read()
        require(document is not None and document['value']['revision'] == self.revision and
                document['value']['credential'] is not None, 'retained exact delegated token required')
        state = copy.deepcopy(document['value'])
        if state['phase'] == 'revoked': return
        state['phase'] = 'revoke-started'
        document = journal.write(document,state)
        try:
            app_proofs.revoke(state['credential'],self.token_factory)
        except HostRefusal as error:
            require(error.status == 401, 'delegated token revocation remains unknown')
        state['phase'] = 'revoked'
        journal.write(document,state)


class RuntimePins:
    """Initial, exactly approved finalization/recovery variables, never activation.

    An uncertain POST is observed on resume, never repeated. Existing variables
    cannot be adopted, even if their bytes happen to match the proposed values.
    """
    NAMES = {'AGENTIC_FINALIZE_PIN': '.github/workflows/authority-v2.yml',
             'AGENTIC_RECOVERY_PIN': '.github/workflows/authority-v2-recovery.yml'}

    def __init__(self, session, gh, journal):
        self.session, self.gh, self.journal = session, gh, journal
        self.document = None

    def run(self):
        authority_release.authorize('bootstrap')
        return self._run()

    def _guard(self):
        from configuration import SetupConfigurationSession
        require(isinstance(self.session, SetupConfigurationSession), 'native runtime-pin setup session required')
        repository = self.session.preview['authority_repository']
        current = None
        for name in self.NAMES:
            observed = self.session.require_effect('credentials', repository + ':variable:' + name)
            require(current is None or current == observed, 'runtime-pin configuration changed')
            current = observed
        require(current['deployment']['state'] == 'setup', 'initial runtime-pin setup required')
        actor = self.gh.api('/user')
        require(actor.get('type') == 'User' and actor.get('id') == self.session.owner['setup']['operator_id'],
                'runtime-pin writer differs from approved native operator')
        require(self.session._check() == current and self.journal.read() == self.document,
                'runtime-pin authorization or private journal changed')
        return current

    def _pins(self, current):
        pins = self.session.preview['changes']['protections'].get('runtime_pins')
        object_fields(pins, tuple(self.NAMES), 'approved runtime pins')
        policy = current['deployment']['policy']
        for name, value in pins.items():
            object_fields(value, ('authority_repository', 'authority_repository_id', 'workflow', 'workflow_sha'),
                          'approved immutable runtime pin')
            require(value['authority_repository'] == policy['authority_repository'] and
                    positive(value['authority_repository_id']) and
                    value['authority_repository_id'] == policy['authority_repository_id'] and
                    value['workflow'] == self.NAMES[name] and sha(value['workflow_sha']),
                    'runtime pin differs from approved authority or workflow')
        require(pins['AGENTIC_FINALIZE_PIN']['workflow_sha'] == policy['workflow_sha'],
                'finalization pin must match the approved main runtime')
        return copy.deepcopy(pins)

    def _inventory(self):
        self._guard()
        repository = self.session.preview['authority_repository']
        rows = self.session.operator_api.pages('/repos/' + repository + '/actions/variables', 'variables')
        require(isinstance(rows, list) and len(rows) <= 10000 and all(isinstance(v, dict) and
                isinstance(v.get('name'), str) and isinstance(v.get('value'), str) for v in rows),
                'bounded authenticated runtime variable inventory required')
        values = {v['name'].upper(): v['value'] for v in rows}
        require(len(values) == len(rows), 'ambiguous runtime variable inventory')
        self._guard()
        return values

    def _save(self, state):
        self._guard()
        self.document = self.journal.write(self.document, state)

    def _run(self):
        import json
        self.document = self.journal.read()
        current = self._guard()
        pins = self._pins(current)
        binding = _credential_binding(current)
        values = {name: json.dumps(value, sort_keys=True, separators=(',', ':')) for name, value in pins.items()}
        if self.document is None:
            require(not set(self._inventory()) & set(self.NAMES), 'existing runtime pin requires explicit owned repair')
            self._save(dict(schema_version=1, kind='runtime-pin-setup', binding=binding, pins=pins,
                            phase='writing', started=[]))
        state = copy.deepcopy(self.document['value'])
        object_fields(state, ('schema_version', 'kind', 'binding', 'pins', 'phase', 'started'), 'private runtime-pin setup')
        require(type(state['schema_version']) is int and state['schema_version'] == 1 and
                state['kind'] == 'runtime-pin-setup' and state['binding'] == binding and state['pins'] == pins and
                state['phase'] in ('writing', 'verified') and isinstance(state['started'], list) and
                len(state['started']) == len(set(state['started'])) and set(state['started']) <= set(self.NAMES),
                'retained runtime-pin approval differs')
        for name, value in values.items():
            inventory = self._inventory()
            if name not in state['started']:
                require(name not in inventory and state['phase'] == 'writing', 'unowned runtime variable appeared')
                state['started'].append(name)
                self._save(state)  # Durable before the one possible POST.
                self._guard()
                self.gh.api('/repos/' + pins[name]['authority_repository'] + '/actions/variables', 'POST',
                            dict(name=name, value=value))
                inventory = self._inventory()
            require(inventory.get(name) == value, 'runtime-pin write unknown or drifted; no automatic retry')
        require(all(self._inventory().get(n) == v for n, v in values.items()), 'runtime-pin final readback differs')
        if state['phase'] != 'verified':
            state['phase'] = 'verified'
            self._save(state)
        return dict(state='runtime-pins-configured', pins=pins, enforcement_active=False)


class CredentialStaging:
    """Retain exact values before writes; acknowledgements never prove consumption.

    Supply a separate protected journal directory, not the initial-installation or
    model-consent directory. This capability cannot provision cloud credentials.
    """
    def __init__(self, session, gh, journal, registered_apps, consent, clock, app_factory=None):
        self.session, self.gh, self.journal = session, gh, journal
        self.apps, self.consent, self.clock = registered_apps, consent, clock
        self.app_factory = app_factory
        self.document = None

    def run(self):
        authority_release.authorize('bootstrap')
        return self._stage()

    def _guard(self, name=None):
        from configuration import SetupConfigurationSession
        require(isinstance(self.session, SetupConfigurationSession), 'native owned setup session required for secret staging')
        repository = self.session.preview['authority_repository']
        name = name or CREDENTIAL_NAMES[0]
        require(name in CREDENTIAL_NAMES, 'unknown authority credential family')
        current = self.session.require_effect('credentials', repository + ':secret:' + name)
        d, op = current['deployment'], current['fence']['pending']
        require(d['state'] == 'setup' and positive(self.clock()) and self.clock() < d['expires'] and
                op is not None and op['kind'] == 'configuration' and
                set(CREDENTIAL_NAMES) <= set(self.session.preview['changes']['credentials']) and
                all(repository + ':secret:' + key in self.session.scope['credentials'] for key in CREDENTIAL_NAMES),
                'complete approved setup credential scope required')
        actor = self.gh.api('/user')
        require(actor.get('type') == 'User' and actor.get('id') == self.session.owner['setup']['operator_id'],
                'secret writer CLI identity differs from native setup operator')
        if self.document is not None:
            require(self.journal.read() == self.document, 'private credential setup changed')
        after = self.session.require_effect('credentials', repository + ':secret:' + name)
        require(after == current and positive(self.clock()) and self.clock() < d['expires'],
                'credential authorization changed or expired during writer readback')
        return after

    def _values(self, current):
        import app_proofs
        import bootstrap
        import model_consent
        import model_vault
        d, records = current['deployment'], self.session.identities
        object_fields(self.apps, PURPOSES, 'retained private App registrations')
        app_proofs.identity_record(d, records)
        values = {}
        for purpose in PURPOSES:
            registration, identity = self.apps[purpose], records['apps'][purpose]
            require(isinstance(registration, dict) and registration.get('id') == identity['id'] and
                    isinstance(registration.get('pem'), str), 'retained private App registration differs')
            api = (self.app_factory or bootstrap.app_api)(identity['id'], registration['pem'])
            info = api.get('/app')
            require(info.get('id') == identity['id'] and info.get('slug') == identity['slug'] and
                    info.get('owner', {}).get('id') == records['owner_id'] and
                    app_proofs.normalized(info.get('permissions')) == bootstrap.PERMISSIONS[purpose],
                    'retained App key or registered permission domain differs')
            installation = api.get('/app/installations/' + str(identity['installation_id']))
            require(installation.get('id') == identity['installation_id'] and
                    installation.get('app_id') == identity['id'] and
                    installation.get('account', {}).get('id') == records['owner_id'] and
                    installation.get('suspended_at') is None and installation.get('repository_selection') == 'selected' and
                    app_proofs.normalized(installation.get('permissions')) == bootstrap.PERMISSIONS[purpose],
                    'staging App installation differs')
            values['AGENTIC_' + purpose.upper() + '_PRIVATE_KEY'] = registration['pem']
        require(isinstance(self.consent, model_consent.Consent) and self.consent.session is self.session,
                'same owned model consent required')
        model_current, body = self.consent._load()
        require(model_current == current and body['attempt'] is not None and body['attempt']['phase'] == 'installed' and
                body['sealed_vault'] is not None, 'verified installed initial model consent required')
        sealed = body['sealed_vault']
        expected = {key: sealed[key] for key in model_vault.BINDING_FIELDS}
        record = model_vault.open_record(sealed, body['keys']['vault'], expected)
        stored = self.consent.auth_store.read()
        require(expected['generation'] == 1 and expected['session_id'] == body['session_id'] and
                expected['authority_repository_id'] == d['policy']['authority_repository_id'] and
                record['identity']['client_id'] == body['attempt']['received_issued_client_id'] and
                stored['state']['vault'] == sealed and stored['state']['pending'] is None,
                'initial model envelope or authenticated identity differs')
        model_vault.validate_keys(body['keys']['vault'], body['keys']['delivery'])
        values.update(AGENTIC_MODEL_VAULT_KEY=body['keys']['vault'], AGENTIC_MODEL_DELIVERY_KEY=body['keys']['delivery'])
        require(len(set(values.values())) == len(CREDENTIAL_NAMES), 'purpose credentials must be distinct')
        return values, sealed

    def _inventory(self):
        p = self.session.preview
        entries = self.session.operator_api.pages('/repos/' + p['authority_repository'] + '/actions/secrets', 'secrets')
        require(isinstance(entries, list) and len(entries) <= 10000 and
                all(isinstance(v, dict) and isinstance(v.get('name'), str) and
                    re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,99}', v['name']) for v in entries),
                'authenticated bounded secret inventory required')
        names = [v['name'].upper() for v in entries]
        require(len(set(names)) == len(names), 'secret inventory changed during pagination')
        return set(names)

    def _save(self, state):
        self._guard()
        self.document = self.journal.write(self.document, state)

    def _prepare(self):
        import secrets
        current = self._guard()
        values, sealed = self._values(current)
        op, policy = current['fence']['pending'], current['deployment']['policy']
        binding = _credential_binding(current)
        self.document = self.journal.read()
        if self.document is None:
            inventory = self._inventory()
            require(not inventory & set(CREDENTIAL_NAMES), 'existing credential requires an explicit owned repair preview')
            self._save(dict(schema_version=1, kind='authority-credential-staging', binding=binding,
                initial_names=sorted(inventory), model_vault=sealed, entries={name: dict(value=value,
                    phase='unstarted', intent_id=secrets.token_hex(16), nonce=secrets.token_hex(32),
                    started=None, proof=None) for name, value in values.items()}))
        state = copy.deepcopy(self.document['value'])
        object_fields(state, ('schema_version', 'kind', 'binding', 'initial_names', 'model_vault', 'entries'),
                      'private credential staging')
        require(type(state['schema_version']) is int and state['schema_version'] == 1 and
                state['kind'] == 'authority-credential-staging' and state['binding'] == binding and
                state['model_vault'] == sealed and isinstance(state['initial_names'], list),
                'retained credential setup binding differs')
        object_fields(state['entries'], CREDENTIAL_NAMES, 'fixed staged credentials')
        for name, entry in state['entries'].items():
            object_fields(entry, ('value', 'phase', 'intent_id', 'nonce', 'started', 'proof'), 'private staged credential')
            require(entry['value'] == values[name] and entry['phase'] in ('unstarted', 'write-started', 'acknowledged', 'unknown', 'verified') and
                    isinstance(entry['intent_id'], str) and re.fullmatch('[0-9a-f]{32}', entry['intent_id']) and
                    isinstance(entry['nonce'], str) and re.fullmatch('[0-9a-f]{64}', entry['nonce']) and
                    (entry['started'] is None if entry['phase'] == 'unstarted' else positive(entry['started'])) and
                    (isinstance(entry['proof'], dict) if entry['phase'] == 'verified' else entry['proof'] is None),
                    'retained credential value or phase differs')
        return current, state

    def stage_for_consumers(self):
        authority_release.authorize('bootstrap')
        return self._stage(allow_unknown=True)

    def _stage(self, allow_unknown=False):
        current, state = self._prepare()
        policy = current['deployment']['policy']
        for name in CREDENTIAL_NAMES:
            entry = state['entries'][name]
            if entry['phase'] in ('acknowledged', 'verified'): continue
            self._guard(name)
            present = name in self._inventory()
            if allow_unknown and entry['phase'] in ('write-started', 'unknown'):
                require(present, 'unknown credential write is absent; no automatic retry')
                continue  # A consumer must still prove the retained exact value.
            require(not present, 'present unverified secret requires authenticated consumer evidence; do not overwrite')
            entry.update(phase='write-started', started=self.clock())
            self._save(state)  # Exact value and intent are durable before native writer invocation.
            self._guard(name)
            try: self.gh.secret(policy['authority_repository'], name, entry['value'])
            except Exception:
                entry['phase'] = 'unknown'
                self._save(state)
                require(False, 'credential write outcome unknown; preserve private staging state')
            entry['phase'] = 'acknowledged'
            self._save(state)
        verified = [name for name in CREDENTIAL_NAMES if state['entries'][name]['phase'] == 'verified']
        return dict(state='credentials-verified' if len(verified) == len(CREDENTIAL_NAMES) else 'awaiting-consumer-verification',
            acknowledged=[name for name in CREDENTIAL_NAMES if state['entries'][name]['phase'] in ('acknowledged', 'verified')],
            verified=verified, enforcement_active=False)

    def challenge(self, name):
        authority_release.authorize('bootstrap')
        return self._challenge(name)

    def _challenge(self, name):
        current, state = self._prepare()
        require(name in CREDENTIAL_NAMES and state['entries'][name]['phase'] != 'unstarted',
                'credential must have a retained write intent before consumer verification')
        entry = state['entries'][name]
        return dict(schema_version=1, kind='credential-challenge', binding=state['binding'], name=name,
            purpose=_credential_purpose(name), intent_id=entry['intent_id'], nonce=entry['nonce'],
            issued=entry['started'], expires=min(current['deployment']['expires'], current['fence']['pending']['execution_deadline']),
            model_vault_digest=digest(state['model_vault']))

    def accept(self, name, authority, locator):
        authority_release.authorize('bootstrap')
        return self._accept(name, authority, locator)

    def _accept(self, name, authority, locator):
        import hmac
        from provenance import authenticated_document
        challenge = self._challenge(name)
        current, state = self._prepare()
        now = self.clock()
        proof = authenticated_document(authority, current['deployment'], locator, 'credential-proof', challenge['purpose'], now)
        value = proof['document']
        object_fields(value, ('schema_version', 'kind', 'challenge', 'execution', 'issued', 'completed', 'mac'),
                      'credential consumption proof')
        require(type(value['schema_version']) is int and value['schema_version'] == 1 and
                value['kind'] == 'credential-consumption' and value['challenge'] == challenge and
                value['execution'] == {key: proof[key] for key in ('run_id', 'attempt', 'job_id')} and
                positive(value['issued']) and positive(value['completed']) and
                max(challenge['issued'], proof['job_started']) <= value['issued'] <= value['completed'] <=
                proof['artifact_created'] <= proof['job_completed'] <= now < challenge['expires'] and
                now - value['completed'] <= 300 and isinstance(value['mac'], str) and
                re.fullmatch('[0-9a-f]{64}', value['mac']), 'fresh exact credential consumer proof required')
        body = {key: item for key, item in value.items() if key != 'mac'}
        require(hmac.compare_digest(value['mac'], _credential_mac(state['entries'][name]['value'], body)),
                'consumer did not load the retained credential value')
        require(name in self._inventory(), 'consumed credential is no longer present')
        state['entries'][name].update(phase='verified', proof=dict(locator=copy.deepcopy(locator),
            digest=digest(value), artifact_digest=proof['artifact_digest']))
        self._save(state)
        return dict(name=name, state='verified', enforcement_active=False)


def _credential_binding(current):
    op = current['fence']['pending']
    require(current['deployment']['state'] == 'setup' and op is not None and op['kind'] == 'configuration' and
            isinstance(op.get('setup'), dict), 'native setup operation required for credential verification')
    return dict(authority_repository_id=current['deployment']['policy']['authority_repository_id'],
        operation_id=op['operation_id'], sequence=current['fence']['sequence'],
        approval_digest=op['setup']['approval_digest'], workflow_sha=op['workflow_sha'],
        configuration_revision=current['configuration_revision'], deployment_digest=current['deployment_digest'])


def _credential_purpose(name):
    require(name in CREDENTIAL_NAMES, 'unknown authority credential family')
    return name.removeprefix('AGENTIC_').removesuffix('_PRIVATE_KEY').removesuffix('_KEY').lower()


def _credential_mac(secret, document):
    import hmac
    return hmac.new(secret.encode('utf-8'), ('AGENTIC credential consumption v1\0' + digest(document)).encode('ascii'),
                    hashlib.sha256).hexdigest()


def consume_credential(registry, authority, environment, identities, challenge, clock):
    authority_release.authorize('bootstrap')
    return _consume_credential(registry, authority, environment, identities, challenge, clock)


def _consume_credential(registry, authority, environment, identities, challenge, clock, app_factory=None):
    """Fixed pinned job consumer; no candidate or native setup credential is run."""
    import app_proofs
    import bootstrap
    import model_auth_store
    import model_vault
    from provenance import admit_job
    object_fields(challenge, ('schema_version', 'kind', 'binding', 'name', 'purpose', 'intent_id', 'nonce',
                             'issued', 'expires', 'model_vault_digest'), 'credential challenge')
    name, purpose = challenge['name'], challenge['purpose']
    require(type(challenge['schema_version']) is int and challenge['schema_version'] == 1 and
            challenge['kind'] == 'credential-challenge' and purpose == _credential_purpose(name) and
            isinstance(challenge['intent_id'], str) and re.fullmatch('[0-9a-f]{32}', challenge['intent_id']) and
            isinstance(challenge['nonce'], str) and re.fullmatch('[0-9a-f]{64}', challenge['nonce']) and
            positive(challenge['issued']) and positive(challenge['expires']) and
            positive(clock()) and challenge['issued'] <= clock() < challenge['expires'] and
            isinstance(challenge['model_vault_digest'], str) and re.fullmatch('[0-9a-f]{64}', challenge['model_vault_digest']),
            'bounded exact credential challenge required')
    current = registry.binding()
    d = current['deployment']
    require(_credential_binding(current) == challenge['binding'] and
            challenge['expires'] == min(d['expires'], current['fence']['pending']['execution_deadline']),
            'credential challenge configuration differs')
    job = admit_job(authority, d, environment, 'credential proof (' + purpose + ')', clock())
    app_proofs.identity_record(d, identities)
    forbidden = set(CREDENTIAL_NAMES) - {name} | {'GH_TOKEN', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY',
        'AWS_SESSION_TOKEN', 'AZURE_CLIENT_SECRET', 'ARM_CLIENT_SECRET', 'OPENAI_API_KEY'}
    require(not any(environment.get(key) for key in forbidden), 'credential consumer inherited another purpose capability')
    secret = environment.get(name)
    require(isinstance(secret, str) and 0 < len(secret) <= 16 * 1024, 'exact loaded consumer credential required')
    started = clock()
    if purpose in PURPOSES:
        identity = identities['apps'][purpose]
        api = (app_factory or bootstrap.app_api)(identity['id'], secret)
        info = api.get('/app')
        require(info.get('id') == identity['id'] and info.get('slug') == identity['slug'] and
                info.get('owner', {}).get('id') == identities['owner_id'] and
                app_proofs.normalized(info.get('permissions')) == bootstrap.PERMISSIONS[purpose],
                'consumer App credential domain differs')
    else:
        model_vault._fernet(secret)
        if purpose == 'model_vault':
            p = d['policy']
            stored = model_auth_store.AuthStore(authority, p['authority_repository'], p['authority_repository_id'],
                                               p['workflow_sha']).read()['state']
            require(stored is not None and stored['pending'] is None and
                    digest(stored['vault']) == challenge['model_vault_digest'], 'consumer model envelope differs')
            sealed = stored['vault']
            require(sealed['generation'] == 1, 'initial encrypted model generation required')
            model_vault.open_record(sealed, secret, {key: sealed[key] for key in model_vault.BINDING_FIELDS})
    require(registry.binding() == current and started <= clock() < challenge['expires'], 'credential setup changed during consumption')
    result = dict(schema_version=1, kind='credential-consumption', challenge=copy.deepcopy(challenge),
        execution=dict(run_id=int(environment['GITHUB_RUN_ID']), attempt=int(environment['GITHUB_RUN_ATTEMPT']), job_id=job['id']),
        issued=started, completed=clock())
    return dict(result, mac=_credential_mac(secret, result))
