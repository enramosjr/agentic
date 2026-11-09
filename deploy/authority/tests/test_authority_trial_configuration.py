"""Disposable native configuration composition over real provisioning/registry."""
import backend_test_support
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import authority_release
import trial_configuration
import test_authority_trial_setup as provisioning
from trusted_ci_policy import Refusal, digest


class TrialConfigurationContracts(unittest.TestCase):
    def test_hold_precedes_pair_readback(self):
        class NoIO:
            def __getattr__(self, name): raise AssertionError(name)
        with self.assertRaises(authority_release.Held):
            trial_configuration.Prepare(NoIO()).run(digest)

    def test_native_selection_is_new_pair_scoped_and_preserves_critical_policy(self):
        fixture = provisioning.TrialProvisionContracts()
        c, api, _, _, _, _, approve, production, _ = fixture.fixture()
        fixture.run_local(c, approve)
        original = production.read()
        original['resources'].update(model_auth='chatgpt-plan', model_id='model', codex_sha='1' * 64,
            codex_version='1.2.3', coding_image='coding@sha256:' + '2' * 64, bundle_sha='3' * 64,
            model_session='production-session', model_account='private-production-account')
        with patch.object(authority_release, 'authorize'):
            pair = c.completed()
            selected = trial_configuration.deployment(c, pair, original)
        self.assertEqual(selected['state'], 'setup')
        self.assertIsNone(selected['qualification'])
        for key in ('target', 'workflow', 'image', 'checks', 'reviewers', 'limits'):
            self.assertEqual(selected['policy'][key], original['policy'][key])
        self.assertEqual(selected['policy']['repository_id'], 701)
        self.assertEqual(selected['policy']['authority_repository_id'], 702)
        self.assertTrue(set(selected['apps'].values()).isdisjoint(original['apps'].values()))
        self.assertNotIn('production-session', str(selected))
        self.assertNotIn('private-production-account', str(selected))
        self.assertEqual(selected['resources']['bundle_sha'], '3' * 64)
        self.assertEqual(selected['resources'].get('coding_slug'), pair['identities']['apps']['coding']['slug'])
        self.assertEqual(selected['resources'].get('coding_bot_id'), str(pair['identities']['apps']['coding']['actor_id']))
        self.assertNotEqual(selected['policy']['epoch'], original['policy']['epoch'])
        self.assertEqual(production.read()['state'], 'qualification')

    def test_cloud_derivation_keeps_approved_account_and_uses_new_authority(self):
        import cloud
        from trusted_ci_policy import loads
        helper = provisioning.TrialProvisionContracts()
        c, _, _, _, _, _, approve, production, _ = helper.fixture()
        helper.run_local(c, approve)
        with patch.object(authority_release, 'authorize'): pair = c.completed()
        for adapter, account in (('aws', '123456789012'), ('azure', '12345678-1234-1234-1234-123456789012')):
            origin = production.read()
            origin.update(adapter=adapter, account=account)
            config = dict(adapter=adapter, account=account, deployment='production-owned', authority='owner/authority',
                branch='main', region='us-east-1' if adapter == 'aws' else 'eastus')
            origin['resources'].update(model_auth='chatgpt-plan', model_id='model', codex_sha='1' * 64,
                codex_version='1.2.3', coding_image='coding@sha256:' + '2' * 64, bundle_sha='3' * 64,
                cloud_configuration=json.dumps(config), bucket='production-bucket', model_session='production-session')
            with self.subTest(adapter=adapter):
                selected = trial_configuration.deployment(c, pair, origin)
                observed = cloud.validate(loads(selected['resources']['cloud_configuration']))
                self.assertEqual(observed['account'], account)
                self.assertEqual(observed['region'], config['region'])
                self.assertEqual(observed['authority'], 'owner/trial-authority')
                self.assertNotEqual(observed['deployment'], config['deployment'])
                self.assertNotIn('production-bucket', str(selected))

    def test_transport_guard_brackets_cli_methods_without_hiding_api(self):
        observations = []
        class CLI:
            def api(self, route):
                observations.append(route)
                return 'observed'
        guarded = trial_configuration._Boundary(CLI(), lambda: observations.append('guard'))
        self.assertEqual(guarded.api('/user'), 'observed')
        self.assertEqual(observations, ['guard', '/user', 'guard'])

    def test_invalid_native_provision_is_not_json_admission(self):
        with patch.object(authority_release, 'authorize'), self.assertRaises(Refusal):
            trial_configuration.Prepare(dict(state='fixture-provisioned')).run(digest)


try:
    import jwt
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
except ImportError:
    jwt = None


@unittest.skipIf(jwt is None, 'optional model-auth cryptography environment required')
class NativePreparation(unittest.TestCase):
    def fixture(self, native_window=False):
        import bootstrap
        import model_consent
        import model_vault
        import private_setup
        import registry
        import setup
        from test_model_vault import fixture as model_fixture
        from test_authority_model_auth_store import AuthHost
        from test_authority_app_proofs import AppAPI
        from test_authority_reconcile import Host as SourceControls
        from test_authority_closed_artifacts import HistoricalAPI
        record, binding, _ = model_fixture()
        origin = provisioning.intent()
        origin['resources'].update({k: binding['deployment']['resources'][k] for k in
            ('model_auth', 'model_id', 'codex_sha', 'codex_version', 'coding_image')})
        origin['resources'].update(bundle_sha='f' * 64, model_session='production-model-session')
        helper = provisioning.TrialProvisionContracts()
        pending = provisioning.pending
        def native_pending(binding, kind):
            value = pending(binding, kind)
            if native_window:
                # The original consent/fence is born with the native setup
                # budget, never extended while preparation is running.
                value['execution_deadline'] = min(value['created'] + 3600, binding['deployment']['expires'])
            return value
        with patch.object(provisioning, 'intent', return_value=origin), patch.object(provisioning, 'pending', side_effect=native_pending):
            f = helper.fixture()
        c, pair, _, journals, _, _, approve, production, clock = f
        c.fixture_files['.github/CODEOWNERS'] = b'* @maintainer\n'
        connected = helper.run_local(c, approve)
        software = connected['software_revision']
        records = connected['identities']
        git = AuthHost()
        installed = pair.hosts['owner/trial-authority']
        git.blobs, git.trees, git.commits = copy.deepcopy(installed.blobs), copy.deepcopy(installed.trees), copy.deepcopy(installed.commits)
        git.refs = {'main': installed.ref}
        source = SourceControls()
        outer = self
        class API:
            def __init__(self):
                self.secrets, self.variables, self.proofs = {}, {}, []
                self.dispatches, self.secret_writes, self.authority_rules = 0, [], []
                self.lost_secret = self.lost_dispatch = self.expire_write = self.expire_token = False
                self.after_secret = None
            def get(self, route):
                if route == '/user': return pair.get(route)
                if route in ('/repos/owner/trial', '/repos/owner/trial-authority'):
                    return dict(pair.get(route), allow_merge_commit=True)
                if route.startswith('/repos/owner/trial-authority/git/'):
                    return git.get(route.replace('owner/trial-authority', 'owner/authority'))
                if route.startswith('/repos/owner/trial/git/'): return pair.get(route)
                if '/actions/runs/99' in route: return copy.deepcopy(self.proofs[0].run)
                if route.endswith('/actions/workflows/33'): return dict(id=33, path=origin['policy']['workflow'])
                if '/rulesets/81' in route: return copy.deepcopy(self.authority_rules[0])
                if route.endswith('/rules/branches/main') and 'trial-authority/' in route:
                    return [dict(rule, ruleset_id=r['id'], ruleset_source_type='Repository',
                        ruleset_source='owner/trial-authority') for r in self.authority_rules for rule in r['rules']]
                if '/branches/' in route: return dict(commit=dict(sha=pair.hosts['owner/trial'].ref))
                return source.get(route.replace('owner/trial', 'owner/project'))
            def fetch(self, route, **kwargs):
                if '/actions/artifacts/' in route:
                    return next(p.raw for p in self.proofs if route.endswith('/' + str(p.artifact['id']) + '/zip'))
                if route.startswith('/repos/owner/trial-authority/'):
                    return git.fetch(route.replace('owner/trial-authority', 'owner/authority'), **kwargs)
                return pair.fetch(route, **kwargs)
            def pages(self, route, collection=None):
                if route == '/installation/repositories': return [dict(id=702)]
                if collection == 'variables': return [dict(name=n, value=v) for n, v in self.variables.items()]
                if collection == 'secrets': return [dict(name=n) for n in self.secrets]
                if collection == 'workflow_runs': return [self.proofs[0].run] if self.proofs else []
                if collection == 'jobs': return [p.job for p in self.proofs]
                if collection == 'artifacts': return [p.artifact for p in self.proofs]
                if route.endswith('/rulesets') and 'trial-authority/' in route: return copy.deepcopy(self.authority_rules)
                return source.pages(route.replace('owner/trial', 'owner/project'), collection)
            def post(self, route, body):
                if route.endswith('/rulesets'):
                    if 'trial-authority/' in route:
                        rule = dict(copy.deepcopy(body), id=81, source='owner/trial-authority', source_type='Repository')
                        self.authority_rules.append(rule)
                        return rule
                    return source.post(route.replace('owner/trial', 'owner/project'), body)
                if route.endswith('/dispatches'):
                    self.dispatches += 1
                    for name, challenge in json.loads(body['inputs']['challenges']).items(): self.consume(challenge)
                    if self.lost_dispatch:
                        self.lost_dispatch = False
                        raise OSError('synthetic dispatch acknowledgement lost')
                    return None
                return git.post(route.replace('owner/trial-authority', 'owner/authority'), body)
            def consume(self, challenge):
                purpose, name = challenge['purpose'], challenge['name']
                proof = HistoricalAPI('credential-proof', purpose)
                offset = len(self.proofs)
                proof.run.update(path=origin['policy']['workflow'], repository=dict(id=702), head_sha=software,
                    event='workflow_dispatch', status='completed', conclusion='success')
                timestamp = lambda: datetime.fromtimestamp(clock[0], timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                proof.job.update(id=77 + offset, head_sha=software, status='in_progress', conclusion=None,
                    started_at=timestamp())
                proof.artifact.update(id=555 + offset)
                proof.artifact['workflow_run'].update(repository_id=702, head_repository_id=702, head_sha=software)
                location = dict(run_id=99, attempt=1, job_id=proof.job['id'], artifact_id=proof.artifact['id'])
                class ConsumerAPI:
                    def get(_, route):
                        if route.endswith('/actions/runs/99'): return proof.run
                        if '/actions/' in route: return proof.get(route)
                        return api.get(route)
                    def pages(_, route, collection):
                        if '/actions/' in route: return proof.pages(route, collection)
                        return api.pages(route, collection)
                    def fetch(_, *args, **kwargs): return api.fetch(*args, **kwargs)
                # HistoricalAPI's workflow endpoint is fixed, so expose the selected path.
                original_get = proof.get
                proof.get = lambda route: dict(id=33, path=origin['policy']['workflow']) if route.endswith('/actions/workflows/33') else original_get(route)
                env = dict(GITHUB_REPOSITORY_ID='702', GITHUB_SHA=software, GITHUB_JOB=purpose + '_credential_proof',
                    GITHUB_RUN_ID='99', GITHUB_RUN_ATTEMPT='1', **{name: self.secrets[name]})
                proof.document = setup._consume_credential(reg, ConsumerAPI(), env, records, challenge, lambda: clock[0], app_factory=app_factory)
                proof.job.update(status='completed', conclusion='success', completed_at=timestamp())
                proof.artifact['created_at'] = timestamp()
                proof.raw = proof.archive(proof.member)
                proof.artifact['digest'] = 'sha256:' + hashlib.sha256(proof.raw).hexdigest()
                self.proofs.append(proof)
        api = API()
        c.api = api
        reg = registry.Registry(api, dict(schema_version=2, repository='owner/trial-authority', repository_id=702, registry_branch='agentic-registry'))
        class Gh:
            def api(self, route, method='GET', body=None):
                if method == 'GET': return api.get(route)
                outer.assertEqual(route, '/repos/owner/trial-authority/actions/variables')
                api.variables[body['name']] = body['value']
            def secret(self, repository, name, value):
                outer.assertEqual(repository, 'owner/trial-authority')
                api.secret_writes.append(name)
                api.secrets[name] = value
                if api.after_secret: api.after_secret()
                if api.expire_write: clock[0] = 1300
                if api.lost_secret:
                    api.lost_secret = False
                    raise OSError('synthetic secret acknowledgement lost')
        c.gh = Gh()
        def store(path):
            value = journals.setdefault(str(path), provisioning.Journal())
            value.root = Path(path)
            return value
        c.store = store
        keys = {}
        registration = store(c.root / 'trial-operator' / 'registration')
        value = copy.deepcopy(registration.read()['value'])
        for purpose, identity in records['apps'].items():
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
            value['apps'][purpose]['registration']['pem'] = pem
            keys[identity['id']] = key.public_key()
        registration.write(registration.read(), value)
        original_app_api = bootstrap.app_api
        def app_factory(app_id, pem):
            jwt.decode(original_app_api(app_id, pem).token, keys[app_id], algorithms=['RS256'], issuer=str(app_id))
            purpose = next(k for k, v in records['apps'].items() if v['id'] == app_id)
            app = AppAPI(None, records, purpose)
            post = app.post
            def mint(*args, **kwargs):
                result = post(*args, **kwargs)
                if api.expire_token: clock[0] = 1300
                return result
            app.post = mint
            return app
        class Consent(model_consent.Consent):
            def run(self):
                self._load()
                if self.document['value']['attempt'] is None: self._begin('http://127.0.0.1:1455/auth/callback')
                body = copy.deepcopy(self.document['value'])
                if body['sealed_vault'] is None:
                    authenticated = copy.deepcopy(record)
                    authenticated.update(authority_repository_id=702, session_id=body['session_id'])
                    duration = authenticated['credentials']['access_expires'] - authenticated['credentials']['issued']
                    authenticated['credentials'].update(issued=clock[0], access_expires=clock[0] + duration)
                    body['sealed_vault'] = model_vault.seal_record(authenticated, body['keys']['vault'])
                    body['attempt']['received_issued_client_id'] = record['identity']['client_id']
                    self._save(body)
                return self._install(body)
        # Keep the native Consent type for CredentialStaging's type check.
        patches = [patch.object(authority_release, 'authorize'), patch.object(bootstrap, 'app_api', side_effect=app_factory),
            patch.object(bootstrap, 'installation_token', return_value='synthetic-trial-admin'),
            patch.object(bootstrap, 'revoke_token'), patch.object(trial_configuration.operator_setup, 'GitHub', return_value=api),
            patch.object(private_setup, 'Store', side_effect=store), patch.object(model_consent.Consent, 'run', Consent.run)]
        return c, api, reg, production, clock, patches

    def test_full_native_preparation_recovers_secret_and_dispatch_without_replay(self):
        from contextlib import ExitStack
        import setup
        c, api, reg, production, clock, patches = self.fixture()
        original = production.binding()
        with ExitStack() as stack:
            for p in patches: stack.enter_context(p)
            controller = trial_configuration.Prepare(c)
            api.lost_secret = True
            with self.assertRaisesRegex(Refusal, 'unknown'): controller.run(digest)
            self.assertEqual(len(api.secret_writes), 1)
            api.lost_dispatch = True
            with self.assertRaises(OSError): controller.run(digest)
            self.assertEqual(api.dispatches, 1)
            clock[0] = 1003
            result = controller.run(digest)
            self.assertEqual(result['state'], 'qualification')
            self.assertEqual(set(result['credentials_verified']), set(setup.CREDENTIAL_NAMES))
            self.assertEqual(controller.run(digest), result)
            self.assertEqual(len(api.secret_writes), 7)
            self.assertEqual(api.dispatches, 1)
            self.assertIsNone(reg.binding()['fence']['pending'])
            self.assertEqual(reg.read()['state'], 'qualification')
            self.assertIsNone(reg.read()['qualification'])
            coding = c.document['value']['connected']['identities']['apps']['coding']
            self.assertEqual(reg.read()['resources']['coding_slug'], coding['slug'])
            self.assertEqual(reg.read()['resources']['coding_bot_id'], str(coding['actor_id']))
            import trial_admission
            admission = trial_admission.Admission(c, reg, api, api, c.root / 'prepared-admission', c.clock, store_factory=c.store)
            pair, admitted, identities = admission._binding()
            self.assertEqual(admitted, reg.binding())
            self.assertEqual(identities['apps']['coding'], coding)
            self.assertEqual(production.binding(), original)
            for secret in api.secrets.values(): self.assertNotIn(secret, json.dumps(result))

    def test_origin_expiry_during_secret_write_stops_all_later_effects_and_resume(self):
        from contextlib import ExitStack
        c, api, reg, production, clock, patches = self.fixture()
        before = production.binding()
        with ExitStack() as stack:
            for p in patches: stack.enter_context(p)
            controller = trial_configuration.Prepare(c)
            api.expire_write = True
            with self.assertRaises(Refusal): controller.run(digest)
            self.assertEqual(len(api.secret_writes), 1)
            self.assertEqual(api.dispatches, 0)
            with self.assertRaises(Refusal): controller.run(digest)
            self.assertEqual(len(api.secret_writes), 1)
            self.assertEqual(production.binding(), before)

    def test_declined_configuration_consent_does_not_stage_or_dispatch(self):
        from contextlib import ExitStack
        c, api, reg, production, clock, patches = self.fixture()
        with ExitStack() as stack:
            for p in patches: stack.enter_context(p)
            def decline(value):
                return '0' * 64 if value['kind'] == 'adopter-setup-preview' else digest(value)
            with self.assertRaisesRegex(Refusal, 'consent'): trial_configuration.Prepare(c).run(decline)
            self.assertEqual(api.secret_writes, [])
            self.assertEqual(api.dispatches, 0)
            self.assertIsNone(reg.binding()['fence']['pending'])

    def test_minted_token_is_revoked_when_origin_expires_during_mint(self):
        from contextlib import ExitStack
        import bootstrap
        mint = bootstrap.installation_token
        c, api, reg, production, clock, patches = self.fixture()
        with ExitStack() as stack:
            for p in patches: stack.enter_context(p)
            revoke = stack.enter_context(patch.object(bootstrap, 'revoke_token'))
            stack.enter_context(patch.object(bootstrap, 'installation_token', side_effect=mint))
            api.expire_token = True
            with self.assertRaises(Refusal): trial_configuration.Prepare(c).run(digest)
            self.assertEqual(revoke.call_count, 1)
            self.assertTrue(revoke.call_args.args[0]['token'].startswith('SYNTHETIC-TOKEN-'))
            self.assertEqual(api.secret_writes, [])

    def test_preparation_fits_original_fence_with_100ms_transport_latency(self):
        from contextlib import ExitStack
        c, api, reg, production, clock, patches = self.fixture(native_window=True)
        original_deadline = production.binding()['fence']['pending']['execution_deadline']
        ticks = [clock[0] * 10]
        def delayed(call):
            def invoke(*args, **kwargs):
                ticks[0] += 1
                clock[0] = ticks[0] // 10
                return call(*args, **kwargs)
            return invoke
        for transport in (api, production.api):
            for name in ('get', 'post', 'fetch', 'pages'):
                if hasattr(transport, name): setattr(transport, name, delayed(getattr(transport, name)))
        with ExitStack() as stack:
            for p in patches: stack.enter_context(p)
            result = trial_configuration.Prepare(c).run(digest)
            self.assertEqual(result['state'], 'qualification')
            self.assertEqual(len(api.secret_writes), 7)
            self.assertEqual(api.dispatches, 1)
            self.assertLess(clock[0], original_deadline)

    def test_origin_trial_or_consent_movement_after_secret_stops_next_effect(self):
        from contextlib import ExitStack
        for fault in ('origin', 'trial', 'consent', 'session-owner', 'session-scope'):
            c, api, reg, production, clock, patches = self.fixture()
            def move():
                if fault == 'origin': production.api.refs['main'] = 'e' * 40
                elif fault == 'session-owner': c.session.owner = {}
                elif fault == 'session-scope': c.session.scope = {}
                else:
                    journal = c.store(c.root / 'trial')
                    value = copy.deepcopy(journal.read()['value'])
                    value['approval'] = '0' * 64
                    journal.write(journal.read(), value)
            # Trial pointer substitution is a simulated out-of-band host event.
            if fault == 'trial':
                original = api.get
                changed = [False]
                def get(route):
                    value = original(route)
                    if changed[0] and route.endswith('/git/ref/heads/main') and 'trial-authority/' in route:
                        return dict(object=dict(sha='e' * 40))
                    return value
                api.get = get
                api.after_secret = lambda: changed.__setitem__(0, True)
            else: api.after_secret = move
            with self.subTest(fault=fault), ExitStack() as stack:
                for p in patches: stack.enter_context(p)
                with self.assertRaises(Refusal): trial_configuration.Prepare(c).run(digest)
                self.assertEqual(len(api.secret_writes), 1)
                self.assertEqual(api.dispatches, 0)

    def test_trial_move_during_original_pre_effect_readback_blocks_first_secret(self):
        from contextlib import ExitStack
        c, api, reg, production, clock, patches = self.fixture()
        flags = [False, False]
        boundary_attr = trial_configuration._Boundary.__getattr__
        origin_get, trial_get = production.api.get, api.get
        def attr(boundary, name):
            if name == 'secret': flags[0] = True
            return boundary_attr(boundary, name)
        def origin(route):
            result = origin_get(route)
            if flags[0]: flags[1] = True
            return result
        def trial(route):
            result = trial_get(route)
            if flags[1] and 'trial-authority/' in route and route.endswith('/git/ref/heads/main'):
                return dict(object=dict(sha='e' * 40))
            return result
        production.api.get, api.get = origin, trial
        with ExitStack() as stack:
            for p in patches: stack.enter_context(p)
            stack.enter_context(patch.object(trial_configuration._Boundary, '__getattr__', attr))
            with self.assertRaises(Refusal): trial_configuration.Prepare(c).run(digest)
            self.assertTrue(flags[1])
            self.assertEqual(api.secret_writes, [])
