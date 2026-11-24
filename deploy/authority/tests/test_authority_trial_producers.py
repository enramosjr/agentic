"""Original fencing contains the real model producer and own-App effect paths."""
import backend_test_support
import json
import unittest
import service
import test_authority_trial_hosted as hosted
from test_authority_app_proofs import AppAPI
from trusted_ci_policy import Refusal


@unittest.skipIf(hosted.workflow.staging.handoff.preparation.jwt is None, 'optional cryptography required')
class Producers(unittest.TestCase):
    fixture = hosted.Hosted.fixture
    prepared = hosted.Hosted.prepared
    connected = hosted.Hosted.connected
    configured = hosted.Hosted.configured

    def test_real_model_and_proof_producers_obey_original_fence(self):
        for role, revoked in ((role,revoked) for role in ('trial-model','trial-proof') for revoked in (False,True)):
            f = self.configured()
            c, reg, origin, clock, env, hint, model, proofs, delivery, jobs, artifacts = f
            api, uploads = reg.api, []
            task_id = c.store(c.root / 'handoff').read()['value']['record']['task_id']
            binding = reg.binding()
            request = dict(schema_version=2,handoff=json.loads(hint),prompt='prompt',source_base=c.completed()['fixture_revision'],
                configuration_revision=binding['configuration_revision'],deployment_digest=binding['deployment_digest'],
                task=dict(task_id=task_id,run_id=100,attempt=1,deadline=2000,purpose='qualification'))
            environment = dict(env,AGENTIC_TRIAL_ORIGIN_TOKEN=api.secrets['AGENTIC_TRIAL_ORIGIN_TOKEN'])
            root = None
            if role == 'trial-model':
                environment.update(GITHUB_JOB='trial_model_auth', **{k:api.secrets[k] for k in ('AGENTIC_MODEL_VAULT_KEY','AGENTIC_MODEL_DELIVERY_KEY')})
                producer = next(j for j in jobs if j['name'] == 'model authorization')
                get = api.get
                def race(path):
                    value = get(path)
                    if revoked and '/git/ref/heads/agentic-model-auth' in path: origin.api.refs['main'] = '9' * 40
                    return value
                api.get = race
            else:
                d = reg.read()
                ids = __import__('app_proofs').load_identities(d)
                root = AppAPI(d,ids,'reader')
                get = root.get
                def race(path):
                    value = get(path)
                    if revoked and path == '/app': origin.api.refs['main'] = '9' * 40
                    return value
                root.get = race
                environment.update(GITHUB_JOB='trial_reader_proof',AGENTIC_READER_PRIVATE_KEY=api.secrets['AGENTIC_READER_PRIVATE_KEY'])
                producer = next(j for j in jobs if j['name'] == 'proof (reader)')
            producer.update(status='in_progress',conclusion=None)
            factory = lambda token:api if token == env['GITHUB_TOKEN'] else origin.reader
            def produce():
                return service._trial(environment,request,'fixture-node',role,clock=c.clock,api_factory=factory,
                    app_factory=lambda *args:root,token_factory=root.token_api if root else None,
                    uploader_factory=lambda *args:lambda name,raw:uploads.append((name,raw)) or 3000)
            with self.subTest(role=role,revoked=revoked):
                if revoked:
                    with self.assertRaises(Refusal): produce()
                    self.assertEqual(uploads,[])
                    if root: self.assertEqual(root.visible,{})
                else:
                    result = produce()
                    self.assertEqual(result['artifact_id'],3000)
                    self.assertEqual(len(uploads),1)
                    document = json.loads(uploads[0][1])
                    if role == 'trial-model':
                        lease = __import__('model_vault').open_lease(document['ciphertext'],delivery,binding,request['task'],clock[0])
                        self.assertEqual(lease['task_id'],task_id)
                    else:
                        self.assertEqual(__import__('app_proofs').validate(document,binding['deployment'],ids,'reader',
                            binding['branch_head'],clock[0])['purpose'],'reader')
