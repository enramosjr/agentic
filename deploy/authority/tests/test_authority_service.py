"""Fixed service dispatch and pinned registry discovery, no hosted effects."""
import backend_test_support
import copy
import json
import unittest
from unittest.mock import patch

from test_authority_setup_owner import fixture
from trusted_ci_policy import Refusal, digest
import authority_release
import service
from test_authority_app_proofs import identities as public_identities, AppAPI, AuthorityReader
from test_authority_protocol import deployment
from test_authority_codex_harness import configured
from test_authority_closed_artifacts import HistoricalAPI


class ServiceContracts(unittest.TestCase):
    def test_all_fixed_public_cli_roles_hold_before_stdin_or_api(self):
        class Unreadable:
            @property
            def buffer(self): raise AssertionError('must hold before reading input')
        for role in ('credential','prepare-task','model-authorization','task','task-controls'):
            with self.subTest(role=role), patch.object(service.sys,'argv',['service.py',role,'synthetic-node']), \
                 patch.object(service.sys,'stdin',Unreadable()), patch.object(service,'GitHub',side_effect=AssertionError('must not authenticate')):
                with self.assertRaises(authority_release.Held): service.main()

    def test_task_preparation_chooses_source_and_execution_without_coding_or_model_roots(self):
        d = configured()
        d.update(state='active',qualification='f'*64)
        d['policy']['merge_actors'] = [19]
        identities = public_identities(d)
        d['resources']['identity_digest'] = digest(identities)
        before = dict(deployment=d,deployment_digest=digest(d),configuration_revision='b'*40,
            branch_head='c'*40,fence={'pending':None})
        class Registry:
            def binding(self): return copy.deepcopy(before)
        class API(HistoricalAPI):
            def get(self,path):
                if path.endswith('/actions/runs/99'): return self.run
                if path == '/repos/owner/authority': return AuthorityReader().get(path)
                return super().get(path)
        api = API()
        api.job.update(name='prepare task',status='in_progress',conclusion=None)
        root = AppAPI(d,identities,'reader')
        def token_factory(token):
            scoped = root.token_api(token)
            original = scoped.get
            def get(path):
                if path == '/repos/owner/project': return dict(id=123,default_branch='main')
                if '/git/ref/heads/' in path: return dict(object=dict(sha='a'*40))
                return original(path)
            scoped.get = get
            return scoped
        env = dict(GITHUB_REPOSITORY_ID='456',GITHUB_SHA=d['policy']['workflow_sha'],
            GITHUB_RUN_ID='99',GITHUB_RUN_ATTEMPT='1',GITHUB_JOB='prepare_task',
            AGENTIC_READER_PRIVATE_KEY='SYNTHETIC-READER-ROOT')
        with patch.object(service,'context',return_value=(api,Registry(),before,identities)):
            result = service._prepare_task(env,{'prompt':'Reviewed task'},clock=lambda:1000,
                app_factory=lambda identity,pem:root,token_factory=token_factory)
        self.assertEqual(set(result),{'schema_version','task','source_base','prompt','configuration_revision','deployment_digest'})
        self.assertEqual(result['configuration_revision'],before['configuration_revision'])
        self.assertEqual(result['deployment_digest'],before['deployment_digest'])
        self.assertEqual(result['source_base'],'a'*40)
        self.assertEqual(result['task']['run_id'],99)
        self.assertEqual(result['task']['attempt'],1)
        self.assertEqual(result['task']['deadline'],1900)
        self.assertEqual(len(result['task']['task_id']),32)
        self.assertNotIn('SYNTHETIC-',json.dumps(result))
        self.assertEqual(set(root.revoked),set(root.visible))

    def test_coding_source_borrows_only_its_source_token_and_always_revokes(self):
        for raises in (False, True):
            d = deployment()
            d['policy']['merge_actors'] = [19]
            identities = public_identities(d)
            d['resources']['identity_digest'] = digest(identities)
            root = AppAPI(d, identities, 'coding')
            entered = []
            def exercise():
                with service._coding_source(root, AuthorityReader(), d, identities, 'b' * 40, lambda:1000,
                                            token_factory=root.token_api) as scoped:
                    entered.append(scoped)
                    self.assertEqual(scoped.pages('/installation/repositories','repositories'),[{'id':123}])
                    if raises: raise RuntimeError('synthetic parent failure')
            if raises:
                with self.assertRaises(RuntimeError): exercise()
            else: exercise()
            self.assertEqual(len(entered),1)
            self.assertEqual(len(root.revoked),2)  # Separate probe and actual borrowed token.
            self.assertEqual(set(root.revoked),set(root.visible))

    def test_public_hold_precedes_api_upload_and_challenge_reads(self):
        with patch.object(service, 'GitHub', side_effect=AssertionError('must not construct API')):
            with self.assertRaises(authority_release.Held): service.credential({}, {}, None)

    def test_authority_is_discovered_only_from_execution_identity(self):
        host, store, make, *_ = fixture(embedded_identities=True)
        env = dict(GITHUB_REPOSITORY='owner/authority', GITHUB_REPOSITORY_ID='456',
                   GITHUB_SHA='a' * 40, GITHUB_TOKEN='SYNTHETIC-READ-TOKEN')
        api, registry, binding, records = service.context(env, api_factory=lambda token: host)
        self.assertIs(api, host)
        self.assertEqual(registry.coordinates['registry_branch'], 'agentic-registry')
        self.assertEqual(records, make().identities)
        for key, value in [('GITHUB_REPOSITORY_ID', '123'), ('GITHUB_SHA', 'b' * 40),
                           ('GITHUB_REPOSITORY', 'owner/project'), ('GITHUB_SERVER_URL', 'https://hostile.invalid')]:
            wrong = dict(env, **{key: value})
            with self.subTest(key=key), self.assertRaises((Refusal, AssertionError, KeyError)):
                service.context(wrong, api_factory=lambda token: host)


if __name__ == '__main__': unittest.main()
