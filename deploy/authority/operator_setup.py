"""Trusted native onboarding composition. Public operations remain release-held.

Run only from an authenticated frozen release outside coding-agent access.
The protected operator journal retains choices/consent; each purpose retains its
own journal. A completed native setup is still unqualified and inactive.
"""
import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import re
import secrets
import sys
import tarfile
import time

sys.path[:0] = [str(Path(__file__).resolve().parent),
                str(Path(__file__).resolve().parents[2] / '.ai/scripts')]
import authority_release
import bootstrap
import private_setup
import registration
import repository
import setup
from trusted_ci_github import GitHub
from trusted_ci_policy import Refusal, digest, loads, object_fields, positive, require


class Operator:
    def __init__(self, api, gh, root, files, clock, store_factory=private_setup.Store,
                 registrar=bootstrap.register_app, installer=None):
        self.api, self.gh, self.root = api, gh, Path(root)
        self.files, self.clock, self.store = dict(files), clock, store_factory
        self.registrar, self.installer = registrar, installer
        self.journal = self.document = None

    def _save(self, state):
        self.document = self.journal.write(self.document, state)

    def connect(self, source, authority, approve):
        authority_release.authorize('bootstrap')
        require(all(isinstance(name, str) and re.fullmatch('[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', name) and
                    all(part not in ('.', '..') for part in name.split('/')) for name in (source, authority)),
                'plain source and authority repository selections required')
        # Storage creation is itself privileged, so it follows the hold.
        self.journal = self.store(self.root)
        self.document = self.journal.read()
        initial = setup.InitialAuthority(self.api, self.store(self.root / 'initial'), self.files, self.clock)
        if self.document is None:
            selected = self.gh.api('/repos/' + source)
            require(selected.get('full_name') == source and positive(selected.get('id')) and source != authority and
                    selected.get('permissions', {}).get('admin') is True, 'select an administered source repository')
            preview = initial.preview(authority)
            approval = approve(copy.deepcopy(preview))
            require(approval == digest(preview), 'initial creation consent declined')
            self._save(dict(schema_version=1, kind='native-onboarding', source=source, authority=authority,
                source_id=selected['id'], initial=preview, initial_approval=approval, installation=None,
                registration=None, registration_approval=None, identities=None))
        state = copy.deepcopy(self.document['value'])
        object_fields(state, ('schema_version kind source authority source_id initial initial_approval installation '
                             'registration registration_approval identities').split(), 'native onboarding journal')
        require(type(state['schema_version']) is int and state['schema_version'] == 1 and
                state['kind'] == 'native-onboarding' and state['source'] == source and state['authority'] == authority and
                state['initial']['repository'] == authority and state['initial_approval'] == digest(state['initial']),
                'retained onboarding selection differs')
        if state['installation'] is None:
            state['installation'] = initial.run(state['initial'], state['initial_approval'])
            self._save(state)
        installed = state['installation']
        current = self.api.get('/repos/' + authority)
        require(current.get('id') == installed['repository_id'] and current.get('full_name') == authority and
                current.get('private') is True and current.get('owner', {}).get('id') == state['initial']['owner_id'],
                'retained private authority identity changed')
        software = repository.Repository(self.api, authority, installed['repository_id'], current['default_branch']).inspect()
        require(software[0] == installed['revision'] and software[3]['files'] == state['initial']['release']['files'],
                'retained installed release changed')
        registrar = registration.Registration(self.gh, self.store(self.root / 'registration'), self.clock,
                                            registrar=self.registrar, installer=self.installer)
        if state['registration'] is None:
            preview = registrar.preview(source, authority, installed['revision'])
            require(preview['source_id'] == state['source_id'], 'selected source identity changed')
            approval = approve(copy.deepcopy(preview))
            require(approval == digest(preview), 'App registration consent declined')
            state.update(registration=preview, registration_approval=approval)
            self._save(state)
        result = registrar.run(state['registration'], state['registration_approval'])
        require(state['identities'] in (None, result['identities']), 'retained App identities changed')
        if state['identities'] is None:
            state['identities'] = result['identities']
            self._save(state)
        return dict(state='setup', repository=source, authority_repository=authority,
                    authority_repository_id=installed['repository_id'], software_revision=installed['revision'],
                    identities=result['identities'], enforcement_active=False, hosted_qualified=False)


class Configuration:
    """Compose already admitted native setup without turning it into qualification.

    The session and its protected progress recorder own registry recovery. Each
    component retains its existing journal, authentication and no-replay rules.
    """
    def __init__(self, session, gh, api, journal_root, apps, clock, store_factory=private_setup.Store, app_factory=None):
        self.session, self.gh, self.api = session, gh, api
        self.root, self.apps, self.clock, self.store = Path(journal_root), apps, clock, store_factory
        self.app_factory = app_factory

    def run(self, consent_factory=None):
        authority_release.authorize('provision')
        import credential_workflow
        import dispatch_controls
        import model_auth_store
        import model_consent
        from configuration import SetupConfigurationSession
        require(isinstance(self.session, SetupConfigurationSession), 'owned native onboarding session required')
        current = self.session._check()
        p = current['deployment']['policy']
        require(current['deployment']['state'] == 'setup', 'native credential composition requires setup state')
        auth = model_auth_store.AuthStore(self.session.registry.api, p['authority_repository'],
                                        p['authority_repository_id'], p['workflow_sha'], session=self.session)
        consent_controller = (consent_factory or model_consent.Consent)(auth, self.session, self.root / 'model', clock=self.clock)
        consent_result = consent_controller.run()
        pins = setup.RuntimePins(self.session, self.gh, self.store(self.root / 'runtime-pins')).run()
        lock = dispatch_controls.DispatchLock(self.session, self.api, self.store(self.root / 'dispatch-lock')).run()
        staging = setup.CredentialStaging(self.session, self.gh, self.store(self.root / 'credentials'),
            self.apps, consent_controller, self.clock, app_factory=self.app_factory)
        staging.stage_for_consumers()
        result = credential_workflow.CredentialWorkflow(staging, self.api, self.store(self.root / 'consumers')).run()
        require(result['state'] == 'credentials-verified' and set(result['verified']) == set(setup.CREDENTIAL_NAMES),
                'all independent credential consumers required')
        self.session._check()
        return dict(state='setup', credentials_verified=result['verified'], runtime_pins=pins['pins'],
                    model_resources=consent_result['resources'], dispatch_ruleset_id=lock['ruleset_id'],
                    enforcement_active=False, hosted_qualified=False)


def select_deployment(operator, connected, bundle_sha, ask=input):
    """Only human policy/account values; App IDs, workflows and wiring are automatic."""
    from authority_protocol import validate_deployment
    p = connected
    source = operator.api.get('/repos/' + p['repository'])
    require(source.get('id') == operator.document['value']['source_id'] and source.get('permissions', {}).get('admin') is True,
            'selected source identity changed')
    reviewers = []
    for name in ask('Independent human reviewer logins (comma separated): ').split(','):
        name = name.strip()
        require(re.fullmatch('[A-Za-z0-9-]{1,39}', name), 'plain independent reviewer login required')
        user = operator.api.get('/users/' + name)
        require(user.get('type') == 'User' and positive(user.get('id')), 'independent human reviewer required')
        reviewers.append(user['id'])
    from trusted_ci_policy import CHECKS
    print('Available independent critical checks: ' + ', '.join(CHECKS))
    checks = [value.strip() for value in ask('Human-approved critical check IDs (comma separated): ').split(',')]
    require(checks and set(checks) <= set(CHECKS), 'select implemented independent critical checks')
    image = ask('Approved verifier image (registry name@sha256:digest): ').strip()
    limits = {name: int(ask('Approved maximum ' + name + ': ')) for name in ('seconds', 'memory_mb', 'processes', 'disk_mb')}
    valid_seconds = int(ask('Deployment validity in seconds: '))
    require(0 < valid_seconds <= 31536000, 'bounded deployment validity required')
    ids = p['identities']
    epoch = secrets.token_hex(16)
    policy = dict(schema_version=1, repository=p['repository'], repository_id=source['id'], target=source['default_branch'],
        app_id=ids['apps']['issuer']['id'], authority_repository=p['authority_repository'],
        authority_repository_id=p['authority_repository_id'], workflow='.github/workflows/authority-v2.yml',
        workflow_sha=p['software_revision'], verifier_sha=p['software_revision'], image=image, checks=checks,
        reviewers=reviewers, coding_actors=[ids['apps']['coding']['actor_id']], merge_actors=[ids['apps']['merge']['actor_id']],
        epoch=epoch, check_name='AGENTIC acceptance ' + epoch, transitions=[], limits=limits)
    resources = dict(authority=p['authority_repository'], operation_id=secrets.token_hex(16), bundle_sha=bundle_sha,
        identity_digest=digest(ids), identity_record=json.dumps(ids, sort_keys=True, separators=(',', ':')),
        actions_resource=p['authority_repository'], container_runtime='docker')
    for name, question in [('coding_image', 'Approved coding image (registry name@sha256:digest): '),
            ('codex_sha', 'Approved Codex executable SHA256: '), ('codex_version', 'Approved Codex version: '),
            ('model_id', 'Selected model ID: '), ('model_auth', 'Approved model authorization profile: ')]:
        resources[name] = ask(question).strip()
    adapter = ask('Execution adapter (github-actions, aws, azure): ').strip()
    require(adapter in ('github-actions', 'aws', 'azure'), 'select an existing execution adapter')
    account = p['authority_repository'].split('/')[0]
    if adapter != 'github-actions':
        import cloud
        account = ask('Adopter AWS account ID or Azure subscription ID: ').strip()
        config = dict(adapter=adapter, authority=p['authority_repository'], account=account,
            region=ask('Selected cloud region: ').strip(),
            branch=operator.api.get('/repos/' + p['authority_repository'])['default_branch'])
        config['deployment'] = 'agentic-' + digest(config)[:16]
        cloud.validate(config)
        resources['cloud_configuration'] = json.dumps(config, sort_keys=True, separators=(',', ':'))
    deployment = validate_deployment(dict(schema_version=2, policy=policy, adapter=adapter,
        account=account, resources=resources, generation=1,
        apps={purpose: value['id'] for purpose, value in ids['apps'].items()}, state='setup',
        expires=operator.clock() + valid_seconds, qualification=None))
    from codex_harness import profile
    profile(deployment)
    return deployment


def configure_operator(operator, bundle_sha, approve, select=select_deployment):
    """Select/approve initial registry, own its fence and drive the native consumers.

    Effective protections complete native configuration; hosted qualification and
    activation remain separate and cannot be manufactured by this coordinator.
    """
    authority_release.authorize('provision')
    import app_proofs
    import configuration
    import dispatch_controls
    from registry import Registry, DOCUMENT, OPERATION
    from reconcile import Reconciler
    from authority_protocol import validate_deployment
    operator.journal = operator.store(operator.root)
    operator.document = operator.journal.read()
    require(operator.document is not None, 'connect the native operator before setup')
    connected_state = operator.document['value']
    connected = operator.connect(connected_state['source'], connected_state['authority'], approve)
    records = connected['identities']
    registrations = operator.store(operator.root / 'registration').read()['value']['apps']
    apps = {purpose: copy.deepcopy(value['registration']) for purpose, value in registrations.items()}
    app = bootstrap.app_api(records['apps']['admin']['id'], apps['admin']['pem'])
    installation = records['apps']['admin']['installation_id']
    token = bootstrap.installation_token(app, installation, [connected['authority_repository_id']], dict(contents='write'))
    try:
        registry = Registry(GitHub(token), dict(schema_version=2, repository=connected['authority_repository'],
            repository_id=connected['authority_repository_id'], registry_branch='agentic-registry'))
        journal = operator.store(operator.root / 'configuration')
        document = journal.read()
        if document is None:
            d = select(operator, connected, bundle_sha)
            app_proofs.identity_record(d, records)
            approval = approve(dict(kind='initial-policy-preview', deployment=d, enforcement_active=False,
                credential_domains=list(setup.CREDENTIAL_NAMES), candidate_review_approved=False))
            preview = dict(kind='initial-policy-preview', deployment=d, enforcement_active=False,
                credential_domains=list(setup.CREDENTIAL_NAMES), candidate_review_approved=False)
            require(approval == digest(preview), 'initial policy consent declined')
            require(registry.binding(missing=True)['deployment'] is None, 'existing registry requires owned recovery')
            document = journal.write(None, dict(schema_version=1, kind='native-configuration', deployment=d,
                progress=d, preview=None, approval=None, operation=None, known=None, acquisition=None,
                write=None, phase='provision', cloud_result=None, result=None, terminal=None, terminal_before=None))
        state = copy.deepcopy(document['value'])
        object_fields(state, ('schema_version kind deployment progress preview approval operation known acquisition '
            'write phase cloud_result result terminal terminal_before').split(), 'native configuration')
        require(type(state['schema_version']) is int and state['schema_version'] == 1 and
                state['kind'] == 'native-configuration', 'retained native configuration differs')
        d = validate_deployment(state['deployment'])
        app_proofs.identity_record(d, records)
        require(d['state'] == 'setup' and d['policy']['workflow_sha'] == connected['software_revision'] and
                d['resources']['bundle_sha'] == bundle_sha, 'retained policy or native release changed')
        before = registry.binding(missing=True)
        if before['deployment'] is None: registry.write(None, d)
        before = registry.binding()
        def persist():
            nonlocal document
            document = journal.write(document, state)
        def known(binding):
            return {k: binding[k] for k in ('configuration_revision', 'deployment_digest', 'branch_head')}
        if state['write'] is not None:
            intent = state['write']
            if before != intent['before']:
                before = registry.authenticate_setup_progress(intent['before'], intent['documents'])
                state.update(known=known(before), progress=before['deployment'])
            state['write'] = None
            persist()
        require(before['deployment'] == state['progress'], 'native setup configuration drift')
        provider = None
        if d['adapter'] != 'github-actions':
            import cloud
            config = cloud.validate(loads(d['resources']['cloud_configuration']))
            require(config['adapter'] == d['adapter'] and config['account'] == d['account'] and
                    config['authority'] == d['policy']['authority_repository'], 'native provider selection differs')
            provider = (cloud.Aws if d['adapter'] == 'aws' else cloud.Azure)(config)
        if state['preview'] is None:
            protections = dict(source=Reconciler(operator.api, registry, operator.clock).preview(),
                authority_dispatch=dispatch_controls.preview(operator.api, d['policy']['authority_repository'],
                    d['policy']['authority_repository_id'], d['policy']['workflow_sha']),
                runtime_pins={name: dict(authority_repository=d['policy']['authority_repository'],
                    authority_repository_id=d['policy']['authority_repository_id'], workflow=workflow,
                    workflow_sha=d['policy']['workflow_sha']) for name, workflow in setup.RuntimePins.NAMES.items()})
            authority = d['policy']['authority_repository']
            effects = dict(credentials=[authority + ':model-vault'] +
                [authority + ':secret:' + n for n in setup.CREDENTIAL_NAMES] +
                [authority + ':variable:' + n for n in setup.RuntimePins.NAMES],
                rules=[authority + ':dispatch-lock', d['policy']['repository']], registry=[authority + ':agentic-registry'])
            if provider is not None: effects['cloud-apply'] = [digest(provider.config)]
            state['preview'] = dict(schema_version=1, kind='adopter-setup-preview', operator_id=operator.api.get('/user')['id'],
                **{key: d['policy'][key] for key in ('repository', 'repository_id', 'target', 'authority_repository', 'authority_repository_id')},
                adapter=d['adapter'], account=d['account'], configuration_revision=before['configuration_revision'],
                deployment_digest=before['deployment_digest'], workflow_sha=d['policy']['workflow_sha'], effects=effects,
                changes=dict(software=repository.Repository(operator.api, authority, connected['authority_repository_id'],
                    operator.api.get('/repos/' + authority)['default_branch']).preview(operator.files),
                    cloud=provider.discover() if provider is not None else None,
                    protections=protections, credentials=['model-vault', *setup.CREDENTIAL_NAMES, *setup.RuntimePins.NAMES]))
            state['approval'] = approve(copy.deepcopy(state['preview']))
            require(state['approval'] == digest(state['preview']), 'native configuration consent declined')
            now = operator.clock()
            state['operation'] = dict(kind='configuration', operation_id=secrets.token_hex(16), scope_digest=digest(effects),
                repository_id=d['policy']['repository_id'], target=d['policy']['target'],
                configuration_revision=before['configuration_revision'], deployment_digest=before['deployment_digest'],
                workflow_sha=d['policy']['workflow_sha'], run_id=None, attempt=None, created=now,
                execution_deadline=min(now + 3600, d['expires']), pr=None, head=None, base=None, merge=None,
                setup=dict(operator_id=state['preview']['operator_id'], installation_id=installation, approval_digest=state['approval']))
            state['known'] = {k: before[k] for k in ('configuration_revision', 'deployment_digest', 'branch_head')}
            state['acquisition'] = copy.deepcopy(before)
            persist()
        require(state['approval'] == digest(state['preview']), 'retained native approval differs')
        if state['acquisition'] is not None:
            acquired_from = state['acquisition']
            if before == acquired_from:
                registry.acquire_operation(before['branch_head'], before['configuration_revision'], state['operation'])
            fence = copy.deepcopy(acquired_from['fence'])
            fence.update(sequence=fence['sequence'] + 1, pending=state['operation'])
            before = registry.authenticate_setup_progress(acquired_from, {OPERATION: fence})
            state.update(known=known(before), acquisition=None)
            persist()
        if state['phase'] in ('finalize', 'complete'):
            terminal_before = state['terminal_before']
            fence = copy.deepcopy(terminal_before['fence'])
            fence['pending'] = None
            fence['completed'].append(state['terminal'])
            if before == terminal_before:
                registry.finalize_operation(before['branch_head'], state['terminal'])
            before = registry.authenticate_setup_progress(terminal_before, {OPERATION: fence})
            state.update(phase='complete', known=known(before))
            persist()
            require(Reconciler(operator.api, registry, operator.clock).readback() == state['result']['controls_digest'],
                    'completed native source controls drifted')
            return copy.deepcopy(state['result'])
        require(known(before) == state['known'] and before['fence']['pending'] == state['operation'],
                'native setup progress is not its retained authenticated binding')
        class TrackedSession(configuration.SetupConfigurationSession):
            def write_configuration(self, expected_digest, value):
                prior = self._check()
                state['write'] = dict(before=prior, documents={DOCUMENT: copy.deepcopy(value)})
                persist()
                super().write_configuration(expected_digest, value)
                after = registry.authenticate_setup_progress(prior, state['write']['documents'])
                state.update(known=known(after), progress=after['deployment'], write=None)
                persist()
        session = TrackedSession(registry, state['operation']['operation_id'], before['fence']['sequence'],
            operator.api, app, records, state['preview'], state['preview']['effects'], state['known'], operator.clock)
        if state['phase'] == 'provision':
            if provider is not None:
                import cloud_setup
                if state['cloud_result'] is None:
                    state['cloud_result'] = cloud_setup.Provision(session, provider,
                        operator.store(operator.root / 'cloud'), operator.clock).run(digest(state['preview']['changes']['cloud']))
                    persist()
                desired = copy.deepcopy(d)
                desired['resources'].update(state['cloud_result']['resources'])
                desired['generation'] += 1
                if state['progress'] != desired:
                    require(state['progress'] == d, 'unexpected native cloud configuration progress')
                    session.write_configuration(digest(d), desired)
            state['phase'] = 'consumers'
            persist()
        if state['phase'] == 'consumers':
            state['result'] = Configuration(session, operator.gh, operator.api, operator.root / 'configuration', apps,
                                           operator.clock, operator.store).run()
            state['phase'] = 'model-binding'
            persist()
        if state['phase'] == 'model-binding':
            resources = state['result']['model_resources']
            object_fields(resources, ('model_auth', 'model_host_id', 'model_session', 'model_account', 'model_client'),
                          'authenticated initial model resources')
            require(resources['model_auth'] == 'chatgpt-plan' and all(isinstance(v, str) and 0 < len(v) <= 2048
                    for v in resources.values()), 'complete authenticated model resources required')
            desired = copy.deepcopy(state['progress'])
            require(all(k not in desired['resources'] or desired['resources'][k] == v for k, v in resources.items()),
                    'initial model configuration conflicts with approved identity')
            if any(desired['resources'].get(k) != v for k, v in resources.items()):
                # Consumers authenticate the original configuration first. Changing
                # it before their proofs would invalidate native consent recovery.
                desired['resources'].update(resources)
                desired['generation'] += 1
                session.write_configuration(digest(state['progress']), desired)
            state['phase'] = 'controls'
            persist()
        require(state['phase'] == 'controls', 'unknown native setup phase')
        reconciler = Reconciler(operator.api, registry, operator.clock, session=session)
        original = state['preview']['changes']['protections']['source']
        fresh = reconciler.preview()
        require(fresh['base'] == original['base'] and fresh['owners_digest'] == original['owners_digest'] and
                all(new['kind'] == old['kind'] and new['body'] == old['body'] and
                    (new == old or old['action'] == 'create' and new['action'] == 'observe')
                    for new, old in zip(fresh['operations'], original['operations'])),
                'source protection changes differ from approved onboarding')
        # Reconciler owns only the nonce-named controls. Foreign controls remain
        # untouched; their current digest is checked again before its mutations.
        controls = reconciler.apply(digest(fresh))
        state['result'].update(state='qualification', deployment_digest=controls['deployment_digest'],
                               controls_digest=controls['controls_digest'])
        terminal_before = session._check()
        state.update(phase='finalize', terminal_before=terminal_before,
            terminal=dict(operation_id=session.operation_id, sequence=session.sequence,
                kind='configuration-complete', receipt_digest=digest(state['result'])))
        persist()
        registry.finalize_operation(terminal_before['branch_head'], state['terminal'])
        fence = copy.deepcopy(terminal_before['fence'])
        fence['pending'] = None
        fence['completed'].append(state['terminal'])
        after = registry.authenticate_setup_progress(terminal_before, {OPERATION: fence})
        state.update(phase='complete', known=known(after))
        persist()
        return copy.deepcopy(state['result'])
    finally:
        bootstrap.revoke_token(dict(token=token))


def consent(preview):
    print(json.dumps({'preview': preview, 'approval_digest': digest(preview)}, indent=2, sort_keys=True))
    return digest(preview) if input('Approve these exact changes? Type approve: ').strip() == 'approve' else None


def release_files(root):
    import build_runtime
    raw = build_runtime.archive(root)
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        files = {member.name.removeprefix('authority/'): archive.extractfile(member).read()
                 for member in archive.getmembers() if member.isfile()}
    return files, hashlib.sha256(raw).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('connect', 'setup'))
    args = parser.parse_args(argv)
    try:
        authority_release.authorize('bootstrap' if args.command == 'connect' else 'provision')
        # The trusted operator uses normal gh account authentication. Its token
        # stays in memory, never argv, return values, journals or diagnostics.
        token = bootstrap.run(['gh', 'auth', 'token', '--hostname', 'github.com']).decode().strip()
        api, gh = GitHub(token), bootstrap.Gh()
        root = Path.home() / '.agentic-native-authority'
        files, bundle_sha = release_files(Path(__file__).resolve().parents[2])
        operator = Operator(api, gh, root, files, lambda: int(time.time()))
        if args.command == 'connect':
            retained = private_setup.Store(root).read()
            source = retained['value']['source'] if retained else input('Source repository (owner/name): ').strip()
            authority = retained['value']['authority'] if retained else input('New private authority (same owner/name): ').strip()
            result = operator.connect(source, authority, consent)
        else:
            result = configure_operator(operator, bundle_sha, consent)
        print(json.dumps(result, sort_keys=True))
        return 0
    except authority_release.Held:
        print(json.dumps(authority_release.status(), sort_keys=True), file=sys.stderr)
        return 1
    except (Refusal, OSError, ValueError, KeyError, TypeError, EOFError, KeyboardInterrupt):
        print(json.dumps(dict(state='blocked', enforcement_active=False, hosted_qualified=False,
            error='Native setup incomplete; retain protected journals and resources for trusted recovery.')),
            file=sys.stderr)
        return 1


if __name__ == '__main__': sys.exit(main())
