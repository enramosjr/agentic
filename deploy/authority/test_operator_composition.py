"""Native credential setup composition, real crypto/journals, fake external APIs."""
import copy
import json
import unittest
from unittest.mock import patch

from test_setup_credentials import SetupCredentialContracts, NAMES
import authority_release
import configuration
import dispatch_controls
import operator_setup
import private_setup
import registry as registry_module
import setup
from trusted_ci_policy import Refusal, digest


class NativeComposition(unittest.TestCase):
    def test_seven_independent_consumers_recover_lost_secret_ack_without_replay(self):
        fixture = SetupCredentialContracts()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        outer = self
        class Actions:
            def __init__(self):
                self.proofs, self.variables, self.rules = [], {}, None
                self.dispatches = self.rule_creates = 0
            def pages(self, route, collection=None):
                if collection == 'variables': return [dict(name=n, value=v) for n, v in self.variables.items()]
                if collection == 'secrets': return [dict(name=n) for n in fixture.reader_names]
                if collection == 'workflow_runs': return [dict(self.proofs[0].run, event='workflow_dispatch')] if self.proofs else []
                if collection == 'jobs': return [p.job for p in self.proofs]
                if collection == 'artifacts': return [p.artifact for p in self.proofs]
                if route.endswith('/rulesets'): return [] if self.rules is None else [self.rules]
                raise AssertionError(route)
            def get(self, route):
                if route == '/user': return dict(id=71, type='User')
                if route.endswith('/rulesets/81'): return copy.deepcopy(self.rules)
                if route.endswith('/rules/branches/main'):
                    return [dict(type=t, ruleset_id=81, ruleset_source_type='Repository', ruleset_source='owner/authority')
                            for t in ('update', 'deletion')] if self.rules else []
                if route == '/repos/owner/authority' or '/git/ref/heads/' in route: return fixture.host.get(route)
                return self.proofs[0].get(route)
            def post(self, route, body):
                if route.endswith('/rulesets'):
                    self.rule_creates += 1
                    self.rules = dict(copy.deepcopy(body), id=81, source='owner/authority', source_type='Repository')
                    return self.rules
                self.dispatches += 1
                outer.assertTrue(route.endswith('/dispatches'))
                outer.assertEqual(set(json.loads(body['inputs']['challenges'])), {setup._credential_purpose(n) for n in NAMES})
                for name in NAMES:
                    fixture.clock[0] = 1001
                    proof = fixture.consumer(name)
                    proof.run.update(event='workflow_dispatch', status='completed', conclusion='success')
                    self.proofs.append(proof)
            def fetch(self, route, **kwargs):
                return next(p.raw for p in self.proofs if route.endswith('/' + str(p.artifact['id']) + '/zip'))
        api = Actions()
        preview = copy.deepcopy(fixture.session.preview)
        preview['effects']['rules'] = ['owner/authority:dispatch-lock']
        preview['effects']['credentials'].extend('owner/authority:variable:' + n for n in setup.RuntimePins.NAMES)
        preview['changes']['protections'] = dict(authority_dispatch=dispatch_controls.preview(api, 'owner/authority', 456, 'a' * 40),
            runtime_pins={n: dict(authority_repository='owner/authority', authority_repository_id=456,
                workflow=w, workflow_sha='a' * 40) for n, w in setup.RuntimePins.NAMES.items()})
        before = fixture.registry.binding()
        fence = copy.deepcopy(before['fence'])
        fence['pending']['scope_digest'] = digest(preview['effects'])
        fence['pending']['setup']['approval_digest'] = digest(preview)
        after = fixture.registry._replace(before, {registry_module.OPERATION: fence})
        old = fixture.session
        session = configuration.SetupConfigurationSession(fixture.registry, old.operation_id, old.sequence,
            old.operator_api, old.admin_api, old.identities, preview, preview['effects'],
            {k: after[k] for k in ('configuration_revision', 'deployment_digest', 'branch_head')}, lambda: fixture.clock[0])
        fixture.session = fixture.controller.session = fixture.consent.session = fixture.consent.auth_store.session = session
        old.operator_api.pages = api.pages
        original_gh = fixture.gh
        class Gh:
            def api(self, route, method='GET', body=None):
                if route == '/user': return original_gh.api(route)
                outer.assertEqual(method, 'POST')
                outer.assertEqual(route, '/repos/owner/authority/actions/variables')
                api.variables[body['name']] = body['value']
            def secret(self, *args): return original_gh.secret(*args)
        def store(path):
            return fixture.journal if path.name == 'credentials' else private_setup.Store(path)
        controller = operator_setup.Configuration(session, Gh(), api, fixture.root, fixture.apps,
            lambda: fixture.clock[0], store_factory=store, app_factory=fixture.controller.app_factory)
        with patch.object(authority_release, 'authorize'):
            original_gh.lose_ack = True
            with self.assertRaises(Refusal): controller.run(consent_factory=lambda *a, **k: fixture.consent)
            self.assertEqual(len(fixture.writes), 1)
            original_gh.lose_ack = False
            result = controller.run(consent_factory=lambda *a, **k: fixture.consent)
            self.assertEqual(result['state'], 'setup')
            self.assertEqual(set(result['credentials_verified']), set(NAMES))
            self.assertEqual(result['model_resources']['model_session'], fixture.consent.document['value']['session_id'])
            self.assertEqual(result['model_resources']['model_host_id'], fixture.consent.document['value']['host_id'])
            self.assertFalse(result['enforcement_active'])
            self.assertEqual(controller.run(consent_factory=lambda *a, **k: fixture.consent), result)
        self.assertEqual(len(fixture.writes), 7)
        self.assertEqual(api.dispatches, 1)
        self.assertEqual(api.rule_creates, 1)
        self.assertEqual(set(api.variables), set(setup.RuntimePins.NAMES))
        self.assertTrue(all(v['phase'] == 'verified' for v in fixture.journal.read()['value']['entries'].values()))
        rendered = json.dumps(result)
        for app in fixture.apps.values(): self.assertNotIn(app['pem'], rendered)


if __name__ == '__main__': unittest.main()
