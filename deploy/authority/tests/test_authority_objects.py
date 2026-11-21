"""Job object capabilities never grant list, delete, or another job's access."""
import backend_test_support  # Establish the explicit source-only test paths.
import json
import hashlib
from pathlib import Path
import sys
import unittest

from test_authority_jobs import request
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'deploy/authority'))
import cloud_objects as objects
from trusted_ci_policy import Refusal


class ObjectContracts(unittest.TestCase):
    def test_aws_uploads_and_presigns_only_exact_objects(self):
        lease = request()
        d = lease['deployment']
        d['resources']['bundle_sha'] = hashlib.sha256(b'bundle').hexdigest()
        d['resources']['deployment'] = 'test'
        d['resources']['job_io_role'] = 'arn:aws:iam::' + d['account'] + ':role/fixture-io'
        calls = []
        class STS:
            def assume_role(self, **kwargs):
                calls.append(('assume', kwargs))
                return {'Credentials': {'AccessKeyId': 'id', 'SecretAccessKey': 'secret', 'SessionToken': 'session'}}
        class S3:
            def put_object(self, **kwargs):
                calls.append(('upload', kwargs))
            def generate_presigned_url(self, operation, **kwargs):
                calls.append((operation, kwargs))
                return 'https://' + d['resources']['artifact_host'] + '/' + kwargs['Params']['Key'] + '?signature=fixture'
        prepared = objects.prepare(objects.AWS(STS(), S3(), lambda credentials, region: S3()),
            d, lease['snapshot'], lease['job_id'], lease['id'], lease['issued'], b'bundle', b'candidate')
        self.assertEqual(prepared['id'], lease['id'])
        policy = json.loads(calls[2][1]['Policy'])
        self.assertEqual([s['Action'] for s in policy['Statement']], ['s3:GetObject', 's3:PutObject'])
        self.assertEqual(len(policy['Statement'][0]['Resource']), 2)
        self.assertEqual(policy['Statement'][1]['Resource'],
                         'arn:aws:s3:::' + d['resources']['bucket'] + '/jobs/' + lease['id'] + '/report.json')
        self.assertEqual([c[0] for c in calls], ['upload', 'upload', 'assume', 'get_object', 'get_object', 'put_object'])
        self.assertTrue(all(c[1]['ExpiresIn'] <= 600 for c in calls[3:]))

    def test_scope_and_lease_are_checked_before_side_effects(self):
        lease = request()
        class Never:
            adapter = 'azure'
            def scope(self, deployment):
                raise AssertionError('must not access provider')
        with self.assertRaises(Refusal):
            objects.prepare(Never(), lease['deployment'], lease['snapshot'], 1, lease['id'], lease['issued'], b'a', b'b')

    def test_azure_capabilities_are_blob_specific_and_use_user_delegation(self):
        lease = request()
        d = lease['deployment']
        d.update(adapter='azure', account='11111111-2222-3333-4444-555555555555')
        d['resources']['bundle_sha'] = hashlib.sha256(b'bundle').hexdigest()
        r = d['resources']
        r.update(storage_account='fixtureaccount', artifact_host='fixtureaccount.blob.core.windows.net',
                 resource_group='fixture', compute_scope='/subscriptions/' + d['account'] + '/resourceGroups/fixture')
        calls = []
        class Api:
            config = {'account': d['account'], 'deployment': 'fixture'}
            def identity(self):
                return {}
            def call(self, argv):
                calls.append(argv)
                if 'generate-sas' in argv:
                    return 'sp=' + argv[argv.index('--permissions') + 1] + '&sig=fixture'
                return {}
        # Derive the same deterministic storage name as provisioning.
        r['storage_account'] = 'ag' + hashlib.sha256((d['account'] + 'fixture').encode()).hexdigest()[:20]
        r['artifact_host'] = r['storage_account'] + '.blob.core.windows.net'
        prepared = objects.prepare(objects.Azure(Api()), d, lease['snapshot'], lease['job_id'], lease['id'],
                                   lease['issued'], b'bundle', b'candidate')
        self.assertTrue(prepared['objects']['report']['url'].endswith('?sp=cw&sig=fixture'))
        self.assertEqual(len(calls), 5)
        for argv in calls[2:]:
            self.assertIn('--as-user', argv)
            self.assertEqual(argv[argv.index('--auth-mode') + 1], 'login')
            self.assertEqual(argv[argv.index('--https-only')], '--https-only')
        self.assertEqual([a[a.index('--permissions') + 1] for a in calls[2:]], ['r', 'r', 'cw'])


if __name__ == '__main__':
    unittest.main()
