"""Offline real-SDK URL compatibility; uses synthetic credentials, no network."""
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import boto3
from botocore.config import Config

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.ai/scripts/tests'))
from test_authority_jobs import request
import cloud_objects
from trusted_ci_policy import Refusal


class SigningContracts(unittest.TestCase):
    def prepare(self, broken=False):
        lease = request()
        d = lease['deployment']
        d['resources'].update(deployment='test', bundle_sha=hashlib.sha256(b'bundle').hexdigest(),
                              job_io_role='arn:aws:iam::123456789012:role/test-io')
        session = boto3.Session(aws_access_key_id='SYNTHETICACCESSKEY', aws_secret_access_key='synthetic-secret',
                                aws_session_token='synthetic-session', region_name='us-east-2')
        class STS:
            def get_caller_identity(self):
                return {'Account': d['account']}
            def assume_role(self, **kwargs):
                return {'Credentials': {'AccessKeyId': 'SYNTHETICACCESSKEY',
                    'SecretAccessKey': 'synthetic-secret', 'SessionToken': 'synthetic-session'}}
        class Uploader:
            def put_object(self, **kwargs):
                return {}
        class Session:
            def client(self, name, **kwargs):
                return STS() if name == 'sts' else Uploader()
        def config(**kwargs):
            if broken:
                kwargs['s3'] = {'addressing_style': 'path'}
            return Config(**kwargs)
        with patch.object(boto3, 'Session', return_value=Session()), \
             patch.object(boto3, 'client', side_effect=session.client), \
             patch('botocore.config.Config', side_effect=config):
            provider = cloud_objects.AWS.authenticated(d)
            return cloud_objects.prepare(provider, d, lease['snapshot'], lease['job_id'],
                lease['id'], lease['issued'], b'bundle', b'candidate')

    def test_real_sdk_urls_match_worker_contract_and_negative_control(self):
        lease = self.prepare()
        for value in lease['objects'].values():
            url = urlsplit(value['url'])
            query = parse_qs(url.query)
            self.assertEqual(url.hostname, lease['deployment']['resources']['artifact_host'])
            self.assertTrue(url.path.startswith('/jobs/' + lease['id'] + '/'))
            self.assertEqual(query['X-Amz-Expires'], ['600'])
            self.assertEqual(len(query['X-Amz-Signature'][0]), 64)
            self.assertEqual(query['X-Amz-SignedHeaders'], ['host'])
            self.assertIn('/us-east-2/s3/aws4_request', query['X-Amz-Credential'][0])
        with self.assertRaises(Refusal):
            self.prepare(broken=True)


if __name__ == '__main__':
    unittest.main()
