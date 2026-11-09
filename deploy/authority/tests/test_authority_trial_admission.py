"""Admission/source capture over real validators and crypto, fake host transports."""
import backend_test_support
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

try:
    from cryptography.fernet import Fernet
except ImportError:
    Fernet = None

import app_proofs
import authority_release
import model_vault
import provenance
import reconcile
import registry
import submission
import trial_admission
from test_authority_closed_artifacts import HistoricalAPI
from test_authority_registry import RegistryHost
from test_authority_fence import pending
import test_authority_trial_setup as provision_fixture
from trusted_ci_github import HostRefusal
from trusted_ci_policy import Refusal, digest


class TrialHost:
    """Registry Git transport plus independently closed producer artifacts."""
    def __init__(self, pair, result):
        self.pair, self.result, self.git = pair, result, RegistryHost()
        original = pair.hosts[result['authority_repository']]
        self.git.blobs = copy.deepcopy(original.blobs)
        self.git.trees = copy.deepcopy(original.trees)
        self.git.commits = copy.deepcopy(original.commits)
        self.git.refs = {'main': original.ref}
        self.artifacts, self.jobs = [], []
        self.live = dict(id=900, run_id=99, head_sha=original.ref, name='hosted qualification',
                         status='in_progress', conclusion=None)
        self.run = dict(id=99, path='.github/workflows/authority.yml', workflow_id=33,
            repository={'id': 702}, head_sha=original.ref, run_attempt=1, event='workflow_dispatch', head_branch='main')
        self.after_fetch = self.unavailable = None

    def get(self, path):
        if self.unavailable: raise OSError('synthetic authority outage')
        if '/actions/runs/99' in path: return copy.deepcopy(self.run)
        if '/actions/runs/' in path: raise HostRefusal(404)
        if path.endswith('/actions/workflows/33'): return dict(id=33, path=self.run['path'])
        if path == '/repos/owner/trial-authority': return self.pair.get(path)
        return self.git.get(path.replace('/repos/owner/trial-authority', '/repos/owner/authority'))

    def pages(self, path, collection):
        if path.endswith('/attempts/1/jobs'): return copy.deepcopy([self.live, *self.jobs])
        if path.endswith('/artifacts'): return [copy.deepcopy(a.artifact) for a in self.artifacts]
        raise AssertionError(path)

    def fetch(self, path, **kwargs):
        if '/actions/artifacts/' in path:
            item = next(a for a in self.artifacts if path.endswith('/' + str(a.artifact['id']) + '/zip'))
            if self.after_fetch: self.after_fetch()
            return item.raw
        return self.git.fetch(path.replace('/repos/owner/trial-authority', '/repos/owner/authority'), **kwargs)

    def post(self, path, body):
        return self.git.post(path.replace('/repos/owner/trial-authority', '/repos/owner/authority'), body)

    def artifact(self, role, key, document):
        a = HistoricalAPI(role, key)
        number = len(self.artifacts)
        a.run = copy.deepcopy(self.run)
        a.job.update(id=77 + number, head_sha=self.run['head_sha'],
                     started_at='1970-01-01T00:16:41Z', completed_at='1970-01-01T00:16:44Z')
        a.artifact.update(id=555 + number, created_at='1970-01-01T00:16:43Z')
        a.artifact['workflow_run'].update(repository_id=702, head_repository_id=702, head_sha=self.run['head_sha'])
        a.document, a.raw = document, b''
        a.raw = a.archive(a.member)
        a.artifact['digest'] = 'sha256:' + hashlib.sha256(a.raw).hexdigest()
        self.artifacts.append(a)
        self.jobs.append(a.job)
        return dict(run_id=99, attempt=1, job_id=a.job['id'], artifact_id=a.artifact['id'])


class Source:
    def __init__(self, pair, d):
        self.pair, self.d = pair, d
        self.rules = [dict(body, id=i) for i, body in enumerate(reconcile.desired_rules(d).values(), 101)]
        self.after_blob = None

    def get(self, path):
        result = self.pair.get(path)
        if '/git/trees/' in path: result['sha'] = path.split('/git/trees/')[1].split('?')[0]
        return result

    def pages(self, path, collection=None):
        if '/rules/branches/' in path:
            return [dict(rule, ruleset_id=r['id']) for r in self.rules for rule in r['rules']]
        if '/rulesets?' in path: return copy.deepcopy(self.rules)
        raise AssertionError(path)

    def fetch(self, path, **kwargs):
        result = self.get(path)
        if self.after_blob: self.after_blob()
        return result


@unittest.skipIf(Fernet is None, 'optional model-auth cryptography environment required')
class TrialAdmissionContracts(unittest.TestCase):
    def fixture(self):
        from test_model_vault import fixture as model_fixture
        fixture = provision_fixture.TrialProvisionContracts()
        record, b, task = model_fixture()
        b['deployment']['resources']['bundle_sha'] = 'f' * 64
        origin = provision_fixture.intent()
        origin['resources'].update(b['deployment']['resources'])
        with patch.object(provision_fixture, 'intent', return_value=origin):
            c, pair, _, journals, _, _, approve, production, clock = fixture.fixture()
        result = fixture.run_local(c, approve)
        d = copy.deepcopy(b['deployment'])
        d.update(state='qualification', qualification=None, generation=1)
        p = d['policy']
        p.update(repository='owner/trial', repository_id=701, authority_repository='owner/trial-authority',
                 authority_repository_id=702, workflow_sha=result['software_revision'],
                 coding_actors=[result['identities']['apps']['coding']['actor_id']],
                 merge_actors=[result['identities']['apps']['merge']['actor_id']],
                 app_id=result['identities']['apps']['issuer']['id'])
        d['apps'] = {k: v['id'] for k, v in result['identities']['apps'].items()}
        d['resources'].update(authority=p['authority_repository'], identity_digest=digest(result['identities']),
            identity_record=json.dumps(result['identities']), operation_id='e' * 32,
            acceptance_rule='101', updates_rule='102', model_session='d' * 32)
        record.update(authority_repository_id=702, session_id='d' * 32)
        host = TrialHost(pair, result)
        reg = registry.Registry(host, dict(schema_version=2, repository=p['authority_repository'],
            repository_id=702, registry_branch='agentic-registry'))
        reg.write(None, d)
        binding = reg.binding()
        source = Source(pair, d)
        task.update(purpose='qualification', deadline=1800)
        key = Fernet.generate_key()
        cipher = model_vault.issue_lease(record, key, binding, task, 1002)
        model = host.artifact('model-lease', task['task_id'], dict(ciphertext=cipher, model_execution_qualified=False))
        proofs = {}
        for purpose, identity in result['identities']['apps'].items():
            proof = dict(schema_version=2, purpose=purpose, app_id=identity['id'],
                installation_id=identity['installation_id'], bot_id=identity['actor_id'], owner_id=7,
                repository_ids=[701, 702] if purpose in ('admin', 'reader') else [701],
                registered_permissions=app_proofs.PERMISSIONS[purpose], token_permissions=app_proofs.TOKEN_PERMISSIONS[purpose],
                denials=app_proofs.expected_denials(purpose), deployment_digest=digest(d), generation=d['generation'],
                registry_revision=binding['branch_head'], observed=1002, expires=1302, isolation_established=False)
            proofs[purpose] = host.artifact('proof', purpose, proof)
        clock[0] = 1005
        controller = trial_admission.Admission(c, reg, host, source, Path('/synthetic-admission-purpose'),
            lambda: clock[0], store_factory=c.store)
        env = dict(GITHUB_REPOSITORY_ID='702', GITHUB_SHA=p['workflow_sha'], GITHUB_JOB='qualification',
                   GITHUB_RUN_ID='99', GITHUB_RUN_ATTEMPT='1')
        return controller, env, task, model, proofs, key, source, host, c, production, clock, journals

    def run_local(self, f):
        c, env, task, model, proofs, key, *_ = f
        with patch.object(authority_release, 'authorize'):
            return c.run(env, task, model, proofs, key, digest)

    def test_exact_admission_captures_real_frozen_source_without_active_or_production_writes(self):
        f = self.fixture()
        c, _, task, _, _, key, source, host, provision, production, _, journals = f
        before = production.binding()
        writes = copy.deepcopy(host.git.writes)
        admission = self.run_local(f)
        self.assertEqual(admission['task'], task)
        self.assertTrue(admission['execution_admitted'])
        self.assertFalse(admission['hosted_qualified'])
        self.assertFalse(admission['enforcement_active'])
        with patch.object(authority_release, 'authorize'):
            raw = c.capture_source()
        files = submission.read_export(raw)
        self.assertEqual(files['.ai/scripts/qualification_fixture.py']['content'], b'approved fixture seed')
        self.assertEqual(production.binding(), before)
        self.assertEqual(host.git.writes, writes)
        self.assertEqual(c.registry.binding()['deployment']['state'], 'qualification')
        f[10][0] += 1  # Resume reauthenticates at a later instant, preserving identity.
        self.assertEqual(self.run_local(f), admission)
        text = json.dumps([admission, [j.read() for p, j in journals.items() if 'admission' in p]])
        for secret in ('SYNTHETIC-ACCESS', 'SYNTHETIC-REFRESH', key.decode()): self.assertNotIn(secret, text)

    def test_admission_and_capture_fit_original_window_with_transport_latency(self):
        f = self.fixture()
        c, _, _, _, _, _, source, host, provision, production, clock, _ = f
        elapsed, calls, downloads = [10050], [0], [0]
        def delayed(call, method):
            def invoke(*args, **kwargs):
                elapsed[0] += 1  # 100 ms/request, no wall-clock sleep.
                clock[0] = elapsed[0] // 10
                calls[0] += 1
                if method == 'fetch' and '/actions/artifacts/' in args[0]: downloads[0] += 1
                return call(*args, **kwargs)
            return invoke
        for api, methods in ((source, ('get', 'pages', 'fetch')), (host, ('get', 'pages', 'fetch')),
                             (provision.api, ('get',)), (production.api, ('get',))):
            for method in methods: setattr(api, method, delayed(getattr(api, method), method))
        self.run_local(f)
        with patch.object(authority_release, 'authorize'):
            raw = c.capture_source()
        self.assertIn('.ai/scripts/qualification_fixture.py', submission.read_export(raw))
        self.assertLess(clock[0], 1300)
        self.assertEqual(downloads[0], 6)  # Model + five Apps, once; never per source blob.

    def test_scope_fence_state_runtime_or_pair_substitution_fails(self):
        for fault in ('fence', 'origin', 'state', 'runtime', 'pair', 'software', 'model-pin', 'model-session'):
            f = self.fixture()
            c, _, _, _, _, _, source, host, provision, production, clock, _ = f
            if fault == 'fence':
                before = c.registry.binding()
                c.registry.acquire_operation(before['branch_head'], before['configuration_revision'], pending(before, 'configuration'))
            elif fault == 'origin': clock[0] = 1300
            elif fault == 'pair': provision.api.ids['owner/trial'] = 123
            elif fault == 'software': provision.authority_files['.ai/scripts/authority_release.py'] = b'changed'
            else:
                before = c.registry.binding()
                changed = copy.deepcopy(before['deployment'])
                if fault == 'state': changed.update(state='active', qualification='f' * 64)
                elif fault == 'model-pin': changed['resources']['coding_image'] = 'other@sha256:' + '0' * 64
                elif fault == 'model-session': changed['resources']['model_session'] = 'a' * 32
                else: changed['policy']['checks'] = ['OTHER']
                # Change the underlying authenticated blob, then update its tree hash.
                tree = host.git.trees[host.git.commits[before['branch_head']]['tree']['sha']]
                tree[registry.DOCUMENT] = ('100644', host.git.blob(json.dumps(changed).encode()))
            with self.subTest(fault=fault), self.assertRaises(Refusal):
                self.run_local(f)

    def test_wrong_job_run_model_purpose_key_or_closed_artifact_refuses(self):
        for fault in ('job', 'run', 'purpose', 'key', 'duplicate', 'failed', 'model'):
            f = self.fixture()
            c, env, task, model, proofs, key, source, host, *_ = f
            if fault == 'job': host.live['name'] = 'task (' + task['task_id'] + ')'
            elif fault == 'run': env['GITHUB_RUN_ID'] = '100'
            elif fault == 'purpose': task['purpose'] = 'task'
            elif fault == 'key': f = (*f[:5], Fernet.generate_key(), *f[6:])
            elif fault == 'duplicate': host.artifacts.append(host.artifacts[0])
            elif fault == 'failed': host.jobs[0]['conclusion'] = 'failure'
            else: host.artifacts[0].artifact['digest'] = 'sha256:' + '0' * 64
            with self.subTest(fault=fault), self.assertRaises(Refusal): self.run_local(f)

    def test_effective_control_and_own_app_proof_semantics_are_mandatory(self):
        for fault in ('controls', 'missing', 'scope', 'expired', 'identity'):
            f = self.fixture()
            c, _, _, _, proofs, _, source, host, *_ = f
            if fault == 'controls': source.rules[0]['bypass_actors'] = [{'actor_type': 'Integration', 'actor_id': 999, 'bypass_mode': 'always'}]
            elif fault == 'missing': del proofs['merge']
            else:
                a = host.artifacts[-1]
                if fault == 'scope': a.document['repository_ids'].append(123)
                elif fault == 'expired': a.document['expires'] = 1005
                else: a.document['installation_id'] = 999
                a.raw = a.archive(a.member)
                a.artifact['digest'] = 'sha256:' + hashlib.sha256(a.raw).hexdigest()
            with self.subTest(fault=fault), self.assertRaises(Refusal): self.run_local(f)

    def test_consent_is_exact_and_cannot_reuse_setup_approval(self):
        f = self.fixture()
        c, env, task, model, proofs, key, *_ = f
        def substitute(preview):
            preview['task']['task_id'] = 'b' * 32
            return digest(preview)
        for approve in (lambda p: c.provision.document['value']['approval'], substitute):
            with patch.object(authority_release, 'authorize'), self.assertRaises(Refusal):
                c.run(env, task, model, proofs, key, approve)
        self.assertIsNone(c.store(c.root / 'execution').read())

    def test_other_purpose_credentials_and_expiry_during_consent_are_rejected(self):
        for fault in ('admin', 'vault', 'expiry'):
            f = self.fixture()
            c, env, task, model, proofs, key, _, _, _, _, clock, _ = f
            if fault != 'expiry':
                env['AGENTIC_ADMIN_PRIVATE_KEY' if fault == 'admin' else 'AGENTIC_MODEL_VAULT_KEY'] = 'SYNTHETIC-OTHER-PURPOSE'
            def approve(value):
                if fault == 'expiry': clock[0] = 1300
                return digest(value)
            with self.subTest(fault=fault), patch.object(authority_release, 'authorize'), self.assertRaises(Refusal):
                c.run(env, task, model, proofs, key, approve)
            self.assertIsNone(c.store(c.root / 'execution').read())

    def test_resume_rereads_and_refuses_replay_or_drift_during_capture(self):
        for fault in ('replay', 'job', 'target', 'expiry', 'outage', 'controls', 'origin', 'late-origin', 'late-journal'):
            f = self.fixture()
            c, _, task, _, _, _, source, host, _, _, clock, _ = f
            self.run_local(f)
            if fault == 'replay':
                task['task_id'] = 'b' * 32
                with self.subTest(fault=fault), self.assertRaises(Refusal): self.run_local(f)
                continue
            if fault == 'job': host.live['status'] = 'completed'
            elif fault == 'target':
                git = source.pair.hosts['owner/trial']
                git.commits['f' * 40] = copy.deepcopy(git.commits[git.ref])
                git.ref = 'f' * 40
            elif fault == 'expiry': source.after_blob = lambda: clock.__setitem__(0, 1300)
            elif fault == 'controls':
                source.after_blob = lambda: source.rules[0]['rules'].clear()
            elif fault in ('origin', 'late-origin', 'late-journal'):
                def end_origin():
                    source.after_blob = None
                    reg = c.provision.session.registry
                    current = reg.binding()
                    reg.finalize_operation(current['branch_head'], dict(operation_id='1' * 32, sequence=1,
                        kind='configuration-complete', receipt_digest='a' * 64))
                if fault == 'origin': source.after_blob = end_origin
                else:
                    pages, count = source.pages, [0]
                    def late_change(*args, **kwargs):
                        count[0] += 1
                        if count[0] == 3:  # First controls read in the final live guard.
                            if fault == 'late-origin': end_origin()
                            else: c.journal.write(c.document, dict(admission=c.intent, approval='0' * 64))
                        return pages(*args, **kwargs)
                    source.pages = late_change
            else: host.unavailable = True
            with self.subTest(fault=fault), patch.object(authority_release, 'authorize'), self.assertRaises((Refusal, OSError)):
                c.capture_source()

    def test_production_task_admission_stays_closed_in_qualification(self):
        f = self.fixture()
        c, env, task, *_ = f
        self.run_local(f)
        with self.assertRaises(Refusal):
            provenance.admit_job(c.authority, c.registry.binding()['deployment'], dict(env, GITHUB_JOB='task'),
                                 'task (' + task['task_id'] + ')', c.clock())


class PublicHold(unittest.TestCase):
    def test_hold_before_journal_auth_or_source_read(self):
        class NoIO:
            def __getattr__(self, name): raise AssertionError(name)
        c = trial_admission.Admission(NoIO(), NoIO(), NoIO(), NoIO(), '/unused', lambda: 1005,
                                      store_factory=NoIO())
        with self.assertRaises(authority_release.Held): c.run({}, {}, {}, {}, b'', digest)
        with self.assertRaises(authority_release.Held): c.capture_source()


if __name__ == '__main__': unittest.main()
