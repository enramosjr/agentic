"""Adapter contract tests; live qualification remains a separate required check."""
import backend_test_support  # Establish the explicit source-only test paths.
import copy
import json
import os
from pathlib import Path
import sys
import unittest

from trusted_ci_fixtures import policy
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'deploy' / 'authority'))
import cloud
from trusted_ci_policy import Refusal, digest
from backend_test_support import config


class CloudOwnershipContracts(unittest.TestCase):
    def test_azure_provisions_private_job_container(self):
        template = cloud.azure_template(config('azure'))
        containers = [r for r in template['resources'] if r['type'] ==
                      'Microsoft.Storage/storageAccounts/blobServices/containers']
        self.assertEqual(len(containers), 1)
        self.assertTrue(containers[0]['name'].endswith('/default/jobs'))
        self.assertEqual(containers[0]['properties']['publicAccess'], 'None')
        self.assertNotIn('tags', containers[0])

    def test_shared_federation_provider_retained_during_replacement(self):
        provider = cloud.aws_template(config())['Resources']['GithubProvider']
        self.assertEqual(provider.get('DeletionPolicy'), 'Retain')
        self.assertEqual(provider.get('UpdateReplacePolicy'), 'Retain',
                         'shared federation must survive replacement as well as deletion')

    def test_cloud_previews_are_adopter_owned_and_require_approval(self):
        for adapter in ('aws', 'azure'):
            p = cloud.preview(config(adapter))
            self.assertEqual(p['account'], config(adapter)['account'])
            self.assertTrue(p['billable'])
            self.assertEqual(p['authority'], 'owner/authority')
            self.assertNotIn('AGENTIC-funded', json.dumps(p))
            with self.assertRaises(Refusal):
                cloud.approved(config(adapter), '0' * 64)
            self.assertEqual(cloud.approved(config(adapter), digest(p)), p)

    def test_federation_never_grants_owner_wide_workflow_trust(self):
        template = cloud.aws_template(config())
        trust = template['Resources']['LauncherRole']['Properties']['AssumeRolePolicyDocument']
        statement = trust['Statement'][0]
        self.assertEqual(statement['Condition']['StringEquals']['token.actions.githubusercontent.com:sub'],
                         'repo:owner/authority:ref:refs/heads/main')
        self.assertEqual(statement['Condition']['StringEquals']['token.actions.githubusercontent.com:aud'],
                         'sts.amazonaws.com')
        azure = cloud.azure_template(config('azure'))
        identity = next(r for r in azure['resources'] if r['type'] == 'Microsoft.ManagedIdentity/userAssignedIdentities')
        subject = identity['resources'][0]['properties']['subject']
        self.assertEqual(subject, 'repo:owner/authority:ref:refs/heads/main')


class CloudAuthorizationContracts(unittest.TestCase):
    def test_azure_transport_rejects_another_subscription_before_tool_call(self):
        calls = []
        api = cloud.Azure(config('azure'), lambda *args, **kwargs: calls.append(args))
        with self.assertRaises(Refusal):
            api.resource('GET', '/subscriptions/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/resourceGroups/x/providers/Microsoft.Compute/virtualMachines/x', '2024-11-01')
        self.assertFalse(calls)

    def test_storage_transport_ignores_ambient_connection_string(self):
        from unittest.mock import patch
        seen = []
        def runner(argv, data=None, **kwargs):
            seen.append((argv, set(kwargs['env'])))
            return b'{"exists":false}'
        c = config('azure')
        account = 'ag' + __import__('hashlib').sha256((c['account'] + c['deployment']).encode()).hexdigest()[:20]
        with patch.dict(os.environ, {'AZURE_STORAGE_CONNECTION_STRING': 'untrusted-override'}):
            self.assertFalse(cloud.Azure(c, runner).blob_exists(account, 'jobs', 'a' * 32 + '/report.json'))
        self.assertNotIn('AZURE_STORAGE_CONNECTION_STRING', seen[0][1])
        self.assertIn('login', seen[0][0])

    def test_azure_account_and_resource_group_are_pinned(self):
        calls = []
        def runner(argv, data=None, **kwargs):
            calls.append(argv)
            return json.dumps({'id': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'}).encode()
        with self.assertRaises(Refusal):
            cloud.Azure(config('azure'), runner).identity()
        self.assertEqual(len(calls), 1)

    def test_destructive_operations_require_exact_owned_inventory(self):
        with self.assertRaises(Refusal):
            cloud.owned_inventory(['a', 'b'], ['a'])
        with self.assertRaises(Refusal):
            cloud.owned_inventory(['a'], ['a', 'a'])
        self.assertEqual(cloud.owned_inventory(['a', 'b'], ['b', 'a']), ['a', 'b'])

    def test_template_changes_include_modified_and_removed_resources(self):
        old = {'Resources': {'One': {'Type': 'A'}, 'Two': {'Type': 'B'}}}
        new = {'Resources': {'One': {'Type': 'C'}, 'Three': {'Type': 'D'}}}
        self.assertEqual(cloud.template_changes(old, new), [
            {'resource': 'One', 'change': 'modify'}, {'resource': 'Three', 'change': 'create'},
            {'resource': 'Two', 'change': 'remove'}])

    def test_bad_provider_resource_values_refused_before_any_tool_execution(self):
        for key, value in [('account', 'not-an-account'), ('authority', '../evil'),
                           ('branch', '*'), ('deployment', '../../etc'), ('region', 'us-east-2;evil')]:
            c = config()
            c[key] = value
            with self.subTest(key=key), self.assertRaises(Refusal):
                cloud.preview(c)

    def test_wrong_authenticated_account_is_refused(self):
        calls = []
        def runner(argv, data=None, **kwargs):
            calls.append(argv)
            return json.dumps({'Account': '999999999999'}).encode()
        with self.assertRaises(Refusal):
            cloud.Aws(config(), runner).identity()
        self.assertEqual(len(calls), 1)

    def test_azure_provisioning_success_is_not_execution_success(self):
        good = {'properties': {'provisioningState': 'Succeeded',
                'instanceView': {'executionState': 'Succeeded', 'exitCode': 0}}}
        cloud.azure_command_complete(good)
        for bad in [dict(properties={'provisioningState': 'Succeeded'}),
                    dict(properties={'provisioningState': 'Succeeded',
                         'instanceView': {'executionState': 'Failed', 'exitCode': 1}})]:
            with self.assertRaises(Refusal):
                cloud.azure_command_complete(bad)

    def test_aws_launch_readback_rejects_substituted_image_or_namespace(self):
        expected = dict(instance_id='i-0123456789abcdef0', image='ami-0123456789abcdef0',
                        deployment='agentic-123', job='a' * 32)
        observed = dict(InstanceId=expected['instance_id'], ImageId=expected['image'],
                        MetadataOptions={'HttpTokens': 'required'},
                        Tags=[{'Key': 'AgenticDeployment', 'Value': expected['deployment']},
                              {'Key': 'AgenticJob', 'Value': expected['job']}])
        cloud.aws_launch_readback(observed, expected)
        for field, value in [('ImageId', 'ami-fffffffffffffffff'), ('Tags', [])]:
            bad = copy.deepcopy(observed)
            bad[field] = value
            with self.assertRaises(Refusal):
                cloud.aws_launch_readback(bad, expected)


if __name__ == '__main__':
    unittest.main()
