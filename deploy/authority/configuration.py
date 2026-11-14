"""Mandatory configuration fence checks; no finally/expiry unlock is permitted.

The trusted caller must admit the owner job and approve the scope before acquiring
the operation. This module does not turn caller-supplied JSON into provenance.
"""
import copy

from authority_protocol import fingerprint
from trusted_ci_policy import digest, object_fields, positive, require, sha

ACTIONS = ('rules', 'software', 'cloud-apply', 'cloud-destroy', 'registry', 'credentials', 'qualification-fixture')


def require_session(session, action, scope):
    require(session is not None, 'owned configuration session required before mutation')
    return session.require_effect(action, scope)


class ConfigurationSession:
    def __init__(self, registry, operation_id, sequence, admitted_owner, approved_scope, clock):
        object_fields(admitted_owner, ('workflow_sha', 'run_id', 'attempt'), 'configuration owner execution')
        require(sha(admitted_owner['workflow_sha']) and positive(admitted_owner['run_id']) and
                positive(admitted_owner['attempt']) and positive(sequence), 'invalid configuration owner')
        self._initialize(registry, operation_id, sequence, admitted_owner, approved_scope, clock)

    def _initialize(self, registry, operation_id, sequence, admitted_owner, approved_scope, clock, allowed_software=None):
        require(isinstance(approved_scope, dict) and approved_scope and set(approved_scope) <= set(ACTIONS) and
                all(isinstance(values, list) and values and len(values) == len(set(values)) and
                    all(isinstance(v, str) and 0 < len(v) <= 2048 for v in values)
                    for values in approved_scope.values()), 'exact approved resource scope required')
        self.registry, self.operation_id, self.sequence = registry, operation_id, sequence
        self.owner, self.scope, self.clock = copy.deepcopy(admitted_owner), copy.deepcopy(approved_scope), clock
        before = registry.binding(check_software=False)
        self.expected = (before['configuration_revision'], before['deployment_digest'], before['branch_head'])
        self.software = set(allowed_software) if allowed_software is not None else {before['deployment']['policy']['workflow_sha']}
        self._check()

    def _owned(self, current):
        op = self.registry.require_configuration_operation(current, self.operation_id)
        require(current['fence']['sequence'] == self.sequence and op['scope_digest'] == digest(self.scope) and
                all(op[key] == value for key, value in self.owner.items()), 'configuration session owner or scope differs')
        p = current['deployment']['policy']
        require(op['repository_id'] == p['repository_id'] and op['target'] == p['target'] and
                type(self.clock()) is int and op['created'] <= self.clock() < op['execution_deadline'],
                'configuration session expired or target differs')
        require(current['software_revision'] in self.software, 'unexpected configuration or software progress')
        return current

    def _check(self):
        current = self._owned(self.registry.binding(check_software=False))
        require((current['configuration_revision'], current['deployment_digest'], current['branch_head']) == self.expected,
                'unexpected configuration or software progress')
        return current

    def require_effect(self, action, scope):
        require(action in self.scope and scope in self.scope[action], 'configuration effect outside approved scope')
        return self._check()

    def write_configuration(self, expected_digest, value):
        c = self.registry.coordinates
        self.require_effect('registry', c['repository'] + ':' + c['registry_branch'])
        self.registry.write(expected_digest, value, operation_id=self.operation_id, before_effect=self._check)
        after = self.registry.binding(check_software=False)
        require(after['deployment'] == value, 'owned configuration write did not read back')
        self.expected = (after['configuration_revision'], after['deployment_digest'], after['branch_head'])

    def allow_software_revision(self, repository, branch, revision):
        """Called only for the commit built from Repository.apply's approved plan."""
        self.require_effect('software', repository + ':' + branch)
        require(sha(revision) and len(self.software) == 1, 'only one approved software transition per session')
        self.software.add(revision)

    def recover_transition(self, before_head, configuration_revision, old_digest, value, before_fence, expected_fence):
        """Only exact authenticated completion resynchronizes; no writes/unlock."""
        c = self.registry.coordinates
        require('registry' in self.scope and c['repository'] + ':' + c['registry_branch'] in self.scope['registry'],
                'registry recovery outside approved scope')
        current = self.registry.authenticate_transition_write(before_head, configuration_revision, old_digest,
                                                              value, before_fence, expected_fence)
        self._owned(current)
        pending = current['fence']['pending']
        require(pending['configuration_revision'] == configuration_revision and pending['deployment_digest'] == old_digest,
                'transition recovery does not match the acquired operation')
        self.expected = (current['configuration_revision'], current['deployment_digest'], current['branch_head'])


class SetupConfigurationSession(ConfigurationSession):
    """Native administrator admission for trusted setup, never a coding worker.

    Approval is retained by the trusted setup controller, not authenticated by
    caller JSON. Every effect reauthenticates native API identities and grants.
    This class cannot establish absence of a same-user modifying process.
    """

    @classmethod
    def broker_context(cls, native, operator_api, admin_api, document):
        from trial_broker_context import configuration_preview
        preview, before = configuration_preview(native,document)
        result = cls.__new__(cls)
        result.native_broker_context = (native,document)
        cls.__init__(result,native.registry,before['fence']['pending']['operation_id'],before['fence']['sequence'],
            operator_api,admin_api,document['value']['record']['pair']['identities'],preview,preview['effects'],
            {k:before[k] for k in ('configuration_revision','deployment_digest','branch_head')},native.provision.clock)
        return result

    @classmethod
    def trial_transition(cls, native, name, operator_api, admin_api, document):
        """Finite protected native context admission, never a setup-preview waiver."""
        from trial_transition import configuration_preview
        preview, before = configuration_preview(native, name, document)
        result = cls.__new__(cls)
        result.native_transition = (native, name, document)
        cls.__init__(result, native.registry, before['fence']['pending']['operation_id'], before['fence']['sequence'],
            operator_api, admin_api, document['value']['record']['pair']['identities'], preview, preview['effects'],
            {k:before[k] for k in ('configuration_revision', 'deployment_digest', 'branch_head')}, native.provision.clock)
        return result

    def __init__(self, registry, operation_id, sequence, operator_api, admin_api, identities,
                 approved_preview, approved_scope, known_binding, clock, software_progress=None, persist_software_progress=None):
        self.operator_api, self.admin_api = operator_api, admin_api
        self.identities, self.preview = copy.deepcopy(identities), copy.deepcopy(approved_preview)
        self.software_progress = copy.deepcopy(software_progress)
        self.persist_software_progress = persist_software_progress
        before = registry.binding(check_software=False)
        setup = self._authenticate(before)
        op = before['fence']['pending']
        require(op is not None and op['kind'] == 'configuration' and op.get('setup') == setup and
                op['run_id'] is None and op['attempt'] is None, 'native setup operation admission differs')
        require(self.preview['effects'] == approved_scope and
                self.preview['configuration_revision'] == op['configuration_revision'] and
                self.preview['deployment_digest'] == op['deployment_digest'] and
                self.preview['workflow_sha'] == op['workflow_sha'], 'approved setup acquisition differs')
        object_fields(known_binding, ('configuration_revision', 'deployment_digest', 'branch_head'), 'known setup progress')
        require(sha(known_binding['configuration_revision']) and sha(known_binding['branch_head']) and
                fingerprint(known_binding['deployment_digest']) and positive(sequence), 'known setup progress required')
        owner = dict(workflow_sha=op['workflow_sha'], run_id=None, attempt=None, setup=setup)
        software = {op['workflow_sha']}
        if self.software_progress is not None:
            self._validate_software_progress(registry, before, self.software_progress)
            software.add(self.software_progress['revision'])
        self._initialize(registry, operation_id, sequence, owner, approved_scope, clock, allowed_software=software)
        require(self.expected == tuple(known_binding[k] for k in ('configuration_revision', 'deployment_digest', 'branch_head')),
                'setup progress is not the retained authenticated binding')

    def _authenticate(self, current):
        import app_proofs
        preview, d = self.preview, current['deployment']
        if hasattr(self, 'native_broker_context'):
            from trial_broker_context import configuration_preview
            native,document = self.native_broker_context
            expected,_ = configuration_preview(native,document)
            require(preview == expected, 'native broker context preview changed')
            return self._native_identity(d)
        if hasattr(self, 'native_transition'):
            from trial_transition import configuration_preview
            native, name, document = self.native_transition
            expected, _ = configuration_preview(native, name, document)
            require(digest(preview) == digest(expected), 'native transition preview changed')
            return self._native_identity(d)
        object_fields(preview, ('schema_version kind operator_id repository repository_id target authority_repository '
            'authority_repository_id adapter account configuration_revision deployment_digest workflow_sha effects changes').split(),
            'approved setup preview')
        require(type(preview['schema_version']) is int and preview['schema_version'] == 1 and
                preview['kind'] == 'adopter-setup-preview' and positive(preview['operator_id']) and
                sha(preview['configuration_revision']) and fingerprint(preview['deployment_digest']) and
                sha(preview['workflow_sha']), 'complete approved setup preview required')
        object_fields(preview['changes'], ('software', 'cloud', 'protections', 'credentials'), 'exact setup changes')
        changes = preview['changes']
        require(isinstance(changes['software'], dict) and changes['software'] and
                isinstance(changes['protections'], dict) and changes['protections'] and
                isinstance(changes['credentials'], list) and changes['credentials'] and
                all(isinstance(v, str) and 0 < len(v) <= 512 for v in changes['credentials']) and
                len(set(changes['credentials'])) == len(changes['credentials']) and
                (changes['cloud'] is None if d['adapter'] == 'github-actions' else
                 isinstance(changes['cloud'], dict) and bool(changes['cloud'])), 'exact setup inventory required')
        return self._native_identity(d)

    def _native_identity(self, d):
        import app_proofs
        preview, p = self.preview, d['policy']
        require(all(preview[k] == p[k] for k in ('repository', 'repository_id', 'target', 'authority_repository',
                    'authority_repository_id')) and preview['adapter'] == d['adapter'] and preview['account'] == d['account'],
                'approved setup account or target differs')
        app_proofs.identity_record(d, self.identities)
        user = self.operator_api.get('/user')
        require(positive(user.get('id')) and user['id'] == preview['operator_id'] and user.get('type') == 'User' and
                user['id'] not in [v['actor_id'] for v in self.identities['apps'].values()], 'native human setup identity differs')
        for name, identity in ((p['repository'], p['repository_id']), (p['authority_repository'], p['authority_repository_id'])):
            repo = self.operator_api.get('/repos/' + name)
            require(positive(repo.get('id')) and positive(repo.get('owner',{}).get('id')) and
                    repo.get('id') == identity and repo.get('owner', {}).get('id') == self.identities['owner_id'] and
                    repo.get('permissions', {}).get('admin') is True and
                    (name != p['authority_repository'] or repo.get('private') is True),
                    'current native administrative repository access required')
        record = self.identities['apps']['admin']
        app = self.admin_api.get('/app')
        require(positive(app.get('id')) and app['id'] == record['id'] and app['slug'] == record['slug'] and
                positive(app.get('owner',{}).get('id')) and app['owner']['id'] == self.identities['owner_id'] and
                app_proofs.normalized(app['permissions']) == app_proofs.PERMISSIONS['admin'], 'setup administrative App changed')
        for route in ('/app/installations/' + str(record['installation_id']),
                      '/repos/' + p['repository'] + '/installation', '/repos/' + p['authority_repository'] + '/installation'):
            installation = self.admin_api.get(route)
            require(positive(installation.get('id')) and positive(installation.get('app_id')) and
                    positive(installation.get('account',{}).get('id')) and
                    installation['id'] == record['installation_id'] and installation['app_id'] == record['id'] and
                    installation['account']['id'] == self.identities['owner_id'] and installation.get('suspended_at') is None and
                    installation.get('repository_selection') == 'selected' and
                    app_proofs.normalized(installation['permissions']) == app_proofs.PERMISSIONS['admin'],
                    'setup administrative installation changed')
        return dict(operator_id=user['id'], installation_id=record['installation_id'], approval_digest=digest(preview))

    def _owned(self, current):
        require(self._authenticate(current) == self.owner['setup'], 'setup admission changed')
        policy_sha, actual = current['deployment']['policy']['workflow_sha'], current['software_revision']
        prepared = self.software_progress['revision'] if self.software_progress else None
        require(policy_sha in (self.owner['workflow_sha'], prepared) and
                (actual == policy_sha or policy_sha == self.owner['workflow_sha'] and actual == prepared),
                'setup software does not match its approved transition phase')
        return super()._owned(current)

    def _check(self):
        current = super()._check()
        if hasattr(self, 'native_transition'):
            from submission import existing_ref
            native, name, document = self.native_transition
            v = document['value']; p = current['deployment']['policy']
            expected = v['source']['base'] if v['source'] is not None else v['preview']['base']
            require(existing_ref(self.operator_api, '/repos/'+p['repository'], p['target']) == expected,
                    'native configuration source moved during admission')
        return current

    def _validate_software_progress(self, registry, binding, progress):
        from repository import Repository
        object_fields(progress, ('operation_id', 'sequence', 'approval_digest', 'plan_digest', 'revision'), 'retained software preparation')
        op = binding['fence']['pending']
        require(op is not None and progress['operation_id'] == op['operation_id'] and
                positive(progress['sequence']) and progress['sequence'] == binding['fence']['sequence'] and
                progress['approval_digest'] == digest(self.preview) and
                progress['plan_digest'] == digest(self.preview['changes']['software']) and sha(progress['revision']) and
                binding['software_revision'] in (op['workflow_sha'], progress['revision']),
                'retained approved software preparation differs')
        plan = self.preview['changes']['software']
        require('software' in self.preview['effects'] and
                self.preview['authority_repository'] + ':' + plan.get('branch', '') in self.preview['effects']['software'] and
                plan.get('base') == op['workflow_sha'], 'software preparation was not approved')
        Repository(registry.api, self.preview['authority_repository'], self.preview['authority_repository_id'],
                   plan['branch']).authenticate_transition(plan, progress['revision'])

    def allow_software_revision(self, repository, branch, revision):
        from repository import Repository
        current = self.require_effect('software', repository + ':' + branch)
        require(repository == self.preview['authority_repository'] and sha(revision), 'approved setup software scope differs')
        plan = self.preview['changes']['software']
        Repository(self.registry.api, repository, self.preview['authority_repository_id'], branch).authenticate_transition(plan, revision)
        if self.software_progress is not None:
            require(self.software_progress['revision'] == revision, 'resume the original prepared software commit')
            return
        require(len(self.software) == 1 and callable(self.persist_software_progress),
                'durable software preparation recorder required before ref update')
        progress = dict(operation_id=self.operation_id, sequence=self.sequence, approval_digest=digest(self.preview),
                        plan_digest=digest(plan), revision=revision)
        require(self.persist_software_progress(copy.deepcopy(progress)) == digest(progress),
                'software preparation persistence not confirmed')
        self.require_effect('software', repository + ':' + branch)
        self.software_progress = progress
        self.software.add(revision)
