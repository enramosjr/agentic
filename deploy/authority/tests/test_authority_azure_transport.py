"""Authenticated typed-not-found classification and blocking Azure deletion."""
import backend_test_support  # Establish the explicit source-only test paths.
import io
import json
from pathlib import Path
import sys
import time
import unittest
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'deploy/authority'))
import cloud
from backend_test_support import config
from trusted_ci_policy import Refusal


class AzureTransportContracts(unittest.TestCase):
    def test_get_refuses_unscoped_endpoint_before_loading_credentials(self):
        calls = []
        def runner(argv, **kwargs):
            calls.append(argv)
            return b'{}'
        api = cloud.Azure(config('azure'), runner, opener=lambda *a, **k: None)
        with self.assertRaises(Refusal):
            api.get('https://other.invalid/collect')
        self.assertFalse(calls)

    def test_deletion_waits_and_pins_resource_scope(self):
        calls = []
        def runner(argv, **kwargs):
            calls.append((argv, kwargs))
            return b'{}'
        c = config('azure')
        api = cloud.Azure(c, runner)
        root = '/subscriptions/' + c['account'] + '/resourceGroups/' + c['deployment'] + '/providers/'
        for kind, path in [('vm', 'Microsoft.Compute/virtualMachines/job'),
                           ('nic', 'Microsoft.Network/networkInterfaces/job'), ('disk', 'Microsoft.Compute/disks/job')]:
            api.delete_and_wait(kind, root + path)
        self.assertEqual([a[0][1:3] for a in calls], [['vm', 'delete'], ['network', 'nic'], ['disk', 'delete']])
        self.assertTrue(all('--no-wait' not in a[0] and a[1]['seconds'] == 180 for a in calls))
        before = len(calls)
        with self.assertRaises(Refusal):
            api.delete_and_wait('vm', root.replace(c['account'], 'foreign') + 'Microsoft.Compute/virtualMachines/job')
        self.assertEqual(len(calls), before)

    def test_only_authenticated_specific_resource_not_found_means_absence(self):
        c = config('azure')
        path = '/subscriptions/' + c['account'] + '/resourceGroups/' + c['deployment'] + '/providers/Microsoft.Compute/disks/job'
        def runner(argv, **kwargs):
            self.assertNotIn('synthetic-token', argv)
            return json.dumps({'accessToken': 'synthetic-token', 'subscription': c['account'],
                               'expires_on': int(time.time()) + 3600}).encode()
        for status, code, absent in [(404, 'ResourceNotFound', True), (404, 'Other', False),
                                      (403, 'AuthorizationFailed', False), (500, 'Unknown', False)]:
            def opener(req, timeout):
                self.assertEqual(req.get_header('Authorization'), 'Bearer synthetic-token')
                self.assertTrue(req.full_url.startswith('https://management.azure.com/'))
                raise HTTPError(req.full_url, status, 'remote details must be redacted', {},
                                io.BytesIO(json.dumps({'error': {'code': code}}).encode()))
            api = cloud.Azure(c, runner, opener=opener)
            with self.subTest(status=status, code=code), self.assertRaises(cloud.NotFound if absent else Refusal):
                api.resource('GET', path, '2024-03-02')


if __name__ == '__main__':
    unittest.main()
