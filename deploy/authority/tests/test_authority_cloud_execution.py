"""Real adapter code over a local provider fixture; not IAM or hosted evidence."""
import backend_test_support  # Establish the explicit source-only test paths.
import base64
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

from test_authority_jobs import request
from backend_test_support import config
from test_authority_protocol import execution
import authority_jobs as jobs
from trusted_ci_policy import Refusal
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'deploy/authority'))
import cloud_execution as c
from cloud import NotFound
from execution import execute

PROGRAM = b'print("fixture only")\n'


class AwsAPI:
    def __init__(self, lease):
        self.config = config()
        self.lease = lease
        self.calls = []
        self.launch = None
        self.terminated = False
        self.bad_image = False
        self.bad_network = False
        self.retained_disk = False
        self.extra_mapping = False
    def identity(self):
        return {'Account': self.config['account']}
    def call(self, service, operation, body):
        self.calls.append((service, operation, body))
        if operation == 'describe-images':
            mappings = [{'DeviceName': '/dev/sda1', 'Ebs': {'VolumeSize': 8, 'DeleteOnTermination': False}}]
            if self.extra_mapping:
                mappings.append({'DeviceName': '/dev/sdb', 'Ebs': {'VolumeSize': 8}})
            return {'Images': [{'ImageId': body['ImageIds'][0], 'RootDeviceName': '/dev/sda1',
                                'RootDeviceType': 'ebs', 'BlockDeviceMappings': mappings}]}
        if operation == 'describe-volumes':
            return {'Volumes': [{'VolumeId': 'vol-0123456789abcdef0', 'State': 'available',
                                 'Tags': self.launch['TagSpecifications'][0]['Tags']}] if self.retained_disk else []}
        if operation == 'delete-volume':
            self.retained_disk = False
            return {}
        if operation == 'run-instances':
            self.launch = body
            return {'Instances': [{'InstanceId': 'i-0123456789abcdef0'}]}
        if operation == 'describe-instances':
            return {'Reservations': [{'Instances': [{'InstanceId': 'i-0123456789abcdef0',
                'ImageId': 'ami-fffffffffffffffff' if self.bad_image else self.launch['ImageId'],
                'ClientToken': self.lease['id'], 'MetadataOptions': {'HttpTokens': 'required'},
                'SubnetId': 'subnet-fffffffffffffffff' if self.bad_network else self.launch['SubnetId'],
                'SecurityGroups': [{'GroupId': x} for x in self.launch['SecurityGroupIds']],
                'BlockDeviceMappings': self.launch.get('BlockDeviceMappings', []),
                'Tags': self.launch['TagSpecifications'][0]['Tags'],
                'State': {'Name': 'terminated' if self.terminated else 'running'}}]}]}
        if operation == 'describe-instance-attribute':
            return {'UserData': {'Value': self.launch['UserData']}}
        if operation == 'list-objects-v2':
            return {'Contents': [{'Key': 'jobs/' + self.lease['id'] + '/report.json'}]}
        if operation == 'terminate-instances':
            self.terminated = True
            return {}
        raise AssertionError(operation)
    def download_object(self, bucket, key):
        return json.dumps(jobs.result(self.lease, execution(self.lease['deployment'])['outcomes'])).encode()


class AzureAPI:
    def __init__(self, lease):
        self.config, self.lease = config('azure'), lease
        self.resources = {}
        self.bad_exit = False
        self.bad_image = False
        self.lose_nic_ack = False
        self.retain_disk = False
        self.bad_delete = False
        self.foreign_attachment = False
        self.bad_mapping = False
        self.delayed_delete = False
        self.pending_delete = None
        self.delete_polls = 0
        self.stale = {}
        self.delete_ops = []
        self.slow_disk_inventory = False
    def identity(self):
        return {'id': self.config['account']}
    def resource(self, method, path, version, body=None, expand=False):
        if method == 'PUT':
            self.resources[path] = dict(copy.deepcopy(body), id=path)
            if '/virtualMachines/' in path and '/runCommands/' not in path:
                disk = body['properties']['storageProfile']['osDisk']
                identity = path.split('/providers/')[0] + '/providers/Microsoft.Compute/disks/' + disk.get('name', 'legacy-os')
                self.resources[path]['properties']['storageProfile']['osDisk']['managedDisk']['id'] = identity
                self.resources[identity] = {'id': identity, 'managedBy': path,
                    'properties': {'uniqueId': '11111111-aaaa-bbbb-cccc-222222222222', 'diskState': 'Attached'}}
            if self.lose_nic_ack and '/networkInterfaces/' in path:
                raise OSError('lost NIC creation acknowledgement')
        if method == 'DELETE':
            if '/virtualMachines/' in path and '/runCommands/' not in path:
                disk = self.resources[path]['properties']['storageProfile']['osDisk']['managedDisk']['id']
                if self.retain_disk:
                    self.resources[disk]['managedBy'] = 'foreign-vm' if self.foreign_attachment else None
                    self.resources[disk]['properties']['diskState'] = 'Unattached'
                else:
                    self.resources.pop(disk, None)
                if self.delayed_delete:
                    self.pending_delete = path
                    return {}
            self.resources = {k: v for k, v in self.resources.items() if k != path and not k.startswith(path + '/')}
            return {}
        if path not in self.resources:
            raise NotFound('authenticated fixture resource not found')
        value = copy.deepcopy(self.resources[path])
        value['properties']['provisioningState'] = 'Succeeded'
        if '/runCommands/' in path:
            value['properties']['instanceView'] = {'executionState': 'Succeeded', 'exitCode': 1 if self.bad_exit else 0}
        elif self.bad_image and '/virtualMachines/' in path:
            value['properties']['storageProfile']['imageReference']['version'] = '0.0.0'
        if self.bad_delete and '/virtualMachines/' in path and '/runCommands/' not in path:
            value['properties']['storageProfile']['osDisk']['deleteOption'] = 'Detach'
        if self.bad_mapping and '/virtualMachines/' in path and '/runCommands/' not in path:
            value['properties']['storageProfile']['osDisk']['managedDisk']['id'] = '/foreign/disk'
        return value
    def list_resources(self, kind):
        if kind == 'Microsoft.Compute/virtualMachines' and self.pending_delete:
            self.delete_polls += 1
            if self.delete_polls >= 3:
                path = self.pending_delete
                self.resources = {k: v for k, v in self.resources.items() if k != path and not k.startswith(path + '/')}
                self.pending_delete = None
        values = copy.deepcopy([v for k, v in self.resources.items()
                                if '/providers/' + kind + '/' in k and '/runCommands/' not in k])
        if kind in self.stale:
            row, remaining = self.stale[kind]
            if remaining:
                values.append(row)
                self.stale[kind] = row, remaining - 1
        # az resource list is a generic ARM inventory, not a typed Compute GET.
        return [{'id': v['id'], 'tags': v.get('tags', {}), 'properties': None} for v in values]
    def delete_and_wait(self, kind, identity):
        self.delete_ops.append((kind, identity))
        previous = copy.deepcopy(self.resources[identity])
        self.resource('DELETE', identity, '2024-11-01')
        if kind == 'vm' and self.pending_delete:
            # Blocking typed delete finished; generic ARM inventory still lags.
            self.resources = {k: v for k, v in self.resources.items()
                              if k != identity and not k.startswith(identity + '/')}
            self.pending_delete = None
            self.stale['Microsoft.Compute/virtualMachines'] = previous, 3
        if kind == 'disk' and self.slow_disk_inventory:
            self.stale['Microsoft.Compute/disks'] = previous, 3
    def blob_exists(self, account, container, key):
        return True
    def download_object(self, account, container, key):
        return json.dumps(jobs.result(self.lease, execution(self.lease['deployment'])['outcomes'])).encode()


def aws_lease():
    lease = request()
    lease['deployment']['resources'].update(deployment='agentic-123', worker_image='ami-0123456789abcdef0',
        subnet='subnet-0123456789abcdef0', security_group='sg-0123456789abcdef0',
        worker_program_sha=hashlib.sha256(PROGRAM).hexdigest())
    return lease


def azure_lease():
    lease = aws_lease()
    d = lease['deployment']
    d.update(adapter='azure', account=config('azure')['account'])
    r = d['resources']
    r.update(resource_group='agentic-123', storage_account='agfixture123',
             region='eastus', compute_scope='/subscriptions/' + d['account'] + '/resourceGroups/agentic-123',
             artifact_host='agfixture123.blob.core.windows.net',
             worker_image='Canonical:ubuntu-24_04-lts:server:24.04.202610010',
             subnet='/subscriptions/' + d['account'] + '/resourceGroups/agentic-123/providers/Microsoft.Network/virtualNetworks/network/subnets/jobs')
    for value in lease['objects'].values():
        value['url'] = value['url'].replace('agentic-123456789012-test.s3.us-east-2.amazonaws.com', r['artifact_host'])
    return lease


class CloudExecutionContracts(unittest.TestCase):
    def test_azure_missing_child_disk_cannot_label_existing_vm_absent(self):
        lease = azure_lease()
        api = AzureAPI(lease)
        provider = c.Azure(api, PROGRAM, sleep=lambda _: None)
        handle = provider.launch(lease)
        provider.observe(handle, lease)
        api.resources.pop(handle['disk'])
        with self.assertRaises(Refusal):
            provider.cleanup(handle, lease)
        self.assertNotEqual(handle.get('cleanup', {}).get('vm'), 'absent')
        self.assertEqual(api.delete_ops, [])

    def test_azure_ambiguous_delete_stays_pending_and_retry_never_reissues(self):
        lease = azure_lease()
        api = AzureAPI(lease)
        provider = c.Azure(api, PROGRAM, sleep=lambda _: None)
        handle = provider.launch(lease)
        original = api.delete_and_wait
        def lost_ack(kind, identity):
            original(kind, identity)
            raise OSError('lost completion acknowledgement')
        api.delete_and_wait = lost_ack
        with self.assertRaises(OSError):
            provider.cleanup(handle, lease)
        self.assertEqual(handle['cleanup']['vm'], 'pending')
        with self.assertRaises(Refusal):
            provider.cleanup(handle, lease)
        self.assertEqual(len(api.delete_ops), 1)

    def test_azure_final_reappearance_blocks_without_deleting_replacement(self):
        lease = azure_lease()
        api = AzureAPI(lease)
        original = api.list_resources
        reads = [0]
        def inventory(kind):
            values = original(kind)
            if kind == 'Microsoft.Compute/disks':
                reads[0] += 1
                if reads[0] == 2:
                    return [{'id': c.Azure(api, PROGRAM).root(lease) + 'Microsoft.Compute/disks/job-' + lease['id'] + '-os'}]
            return values
        api.list_resources = inventory
        with self.assertRaises(Refusal):
            execute(c.Azure(api, PROGRAM, sleep=lambda _: None), lease,
                    now=lambda: 1001, sleep=lambda _: None)
        self.assertFalse(any(kind == 'disk' for kind, _ in api.delete_ops))

    def test_azure_cleanup_refreshes_mapping_despite_cached_uid(self):
        lease = azure_lease()
        api = AzureAPI(lease)
        provider = c.Azure(api, PROGRAM, sleep=lambda _: None)
        handle = provider.launch(lease)
        provider.observe(handle, lease)
        self.assertIn('disk_uid', handle)
        api.bad_mapping = True
        with self.assertRaises(Refusal):
            provider.cleanup(handle, lease)
        self.assertEqual(api.delete_ops, [])

    def test_azure_disk_delete_is_issued_once_despite_stale_inventory(self):
        lease = azure_lease()
        api = AzureAPI(lease)
        api.retain_disk, api.slow_disk_inventory = True, True
        result = execute(c.Azure(api, PROGRAM, sleep=lambda _: None), lease,
                         now=lambda: 1001, sleep=lambda _: None)
        self.assertTrue(result['cleanup_complete'])
        self.assertEqual(sum(kind == 'disk' for kind, _ in api.delete_ops), 1)

    def test_azure_asynchronous_vm_deletion_does_not_recapture_deleted_disk(self):
        lease = azure_lease()
        api = AzureAPI(lease)
        api.delayed_delete = True
        result = execute(c.Azure(api, PROGRAM, sleep=lambda _: None), lease,
                         now=lambda: 1001, sleep=lambda _: None)
        self.assertTrue(result['cleanup_complete'])
        self.assertEqual(list(api.resources), [])

    def test_azure_foreign_mapping_or_attachment_never_authorizes_disk_deletion(self):
        for mode in ('bad_mapping', 'foreign_attachment'):
            lease = azure_lease()
            api = AzureAPI(lease)
            api.retain_disk = True
            setattr(api, mode, True)
            with self.subTest(mode=mode), self.assertRaises(Refusal):
                execute(c.Azure(api, PROGRAM, sleep=lambda _: None), lease,
                        now=lambda: 1001, sleep=lambda _: None)
            self.assertTrue(any('/disks/' in p for p in api.resources))

    def test_azure_same_named_orphan_without_ownership_proof_blocks_cleanup(self):
        lease = azure_lease()
        api = AzureAPI(lease)
        provider = c.Azure(api, PROGRAM, sleep=lambda _: None)
        root = provider.root(lease)
        name = 'job-' + lease['id']
        disk = root + 'Microsoft.Compute/disks/' + name + '-os'
        api.resources[disk] = {'id': disk, 'managedBy': None,
            'properties': {'uniqueId': '11111111-aaaa-bbbb-cccc-222222222222', 'diskState': 'Unattached'}}
        with self.assertRaises(Refusal):
            provider.cleanup({'id': root + 'Microsoft.Compute/virtualMachines/' + name,
                'nic': root + 'Microsoft.Network/networkInterfaces/' + name, 'disk': disk}, lease)
        self.assertIn(disk, api.resources)

    def test_azure_detach_drift_is_denied_and_its_confirmed_leftover_disk_is_removed(self):
        lease = azure_lease()
        api = AzureAPI(lease)
        api.bad_delete, api.retain_disk = True, True
        with self.assertRaises(Refusal):
            execute(c.Azure(api, PROGRAM, sleep=lambda _: None), lease,
                    now=lambda: 1001, sleep=lambda _: None)
        self.assertFalse(api.resources)

    def test_azure_success_confirms_owned_disk_deletion(self):
        lease = azure_lease()
        api = AzureAPI(lease)
        api.retain_disk = True
        result = execute(c.Azure(api, PROGRAM, sleep=lambda _: None), lease,
                         now=lambda: 1001, sleep=lambda _: None)
        self.assertTrue(result['cleanup_complete'])
        self.assertFalse(api.resources)

    def test_aws_root_disk_is_forced_to_delete_and_leftovers_are_confirmed_removed(self):
        lease = aws_lease()
        api = AwsAPI(lease)
        api.retained_disk = True
        result = execute(c.AWS(api, PROGRAM, sleep=lambda _: None), lease,
                         now=lambda: 1001, sleep=lambda _: None)
        self.assertEqual(api.launch.get('BlockDeviceMappings'), [
            {'DeviceName': '/dev/sda1', 'Ebs': {'DeleteOnTermination': True, 'Encrypted': True,
                                              'VolumeSize': 32, 'VolumeType': 'gp3'}}])
        self.assertFalse(api.retained_disk)
        self.assertTrue(result['cleanup_complete'])

    def test_aws_ami_with_unapproved_extra_disk_is_refused_before_launch(self):
        lease = aws_lease()
        api = AwsAPI(lease)
        api.extra_mapping = True
        with self.assertRaises(Refusal):
            c.AWS(api, PROGRAM).launch(lease)
        self.assertIsNone(api.launch)

    def test_aws_lost_launch_ack_discovers_and_terminates_owned_host(self):
        lease = aws_lease()
        api = AwsAPI(lease)
        original = api.call
        def call(service, operation, body):
            value = original(service, operation, body)
            if operation == 'run-instances':
                raise OSError('lost EC2 launch acknowledgement')
            return value
        api.call = call
        with self.assertRaises(OSError):
            execute(c.AWS(api, PROGRAM, sleep=lambda _: None), lease,
                    now=lambda: 1001, sleep=lambda _: None)
        self.assertTrue(api.terminated)

    def test_aws_network_substitution_is_rejected(self):
        lease = aws_lease()
        api = AwsAPI(lease)
        api.bad_network = True
        with self.assertRaises(Refusal):
            execute(c.AWS(api, PROGRAM, sleep=lambda _: None), lease,
                    now=lambda: 1001, sleep=lambda _: None)
        self.assertTrue(api.terminated)

    def test_azure_lost_nic_ack_is_cleaned(self):
        lease = azure_lease()
        api = AzureAPI(lease)
        api.lose_nic_ack = True
        with self.assertRaises(OSError):
            execute(c.Azure(api, PROGRAM, sleep=lambda _: None), lease,
                    now=lambda: 1001, sleep=lambda _: None)
        self.assertFalse(api.resources)

    def test_azure_launch_result_and_cleanup_use_real_adapter_code(self):
        lease = azure_lease()
        api = AzureAPI(lease)
        result = execute(c.Azure(api, PROGRAM, sleep=lambda _: None), lease,
                         now=lambda: 1001, sleep=lambda _: None)
        self.assertTrue(result['cleanup_complete'])
        self.assertFalse(api.resources)

    def test_azure_wrong_image_and_nonzero_exit_cannot_succeed(self):
        for field in ('bad_image', 'bad_exit'):
            lease = azure_lease()
            api = AzureAPI(lease)
            setattr(api, field, True)
            with self.subTest(field=field), self.assertRaises(Refusal):
                execute(c.Azure(api, PROGRAM, sleep=lambda _: None), lease,
                        now=lambda: 1001, sleep=lambda _: None)
            self.assertFalse(api.resources)

    def test_aws_launch_is_scoped_read_back_and_terminated_before_return(self):
        lease = aws_lease()
        api = AwsAPI(lease)
        provider = c.AWS(api, PROGRAM, sleep=lambda _: None)
        result = execute(provider, lease, now=lambda: 1001, sleep=lambda _: None)
        self.assertTrue(result['cleanup_complete'])
        self.assertTrue(api.terminated)
        self.assertEqual(api.launch['ClientToken'], lease['id'])
        self.assertNotIn('IamInstanceProfile', api.launch)
        self.assertEqual(api.launch['MetadataOptions']['HttpTokens'], 'required')

    def test_aws_substituted_image_is_denied_and_own_host_cleaned(self):
        lease = aws_lease()
        api = AwsAPI(lease)
        api.bad_image = True
        with self.assertRaises(Refusal):
            execute(c.AWS(api, PROGRAM, sleep=lambda _: None), lease,
                    now=lambda: 1001, sleep=lambda _: None)
        self.assertTrue(api.terminated)

    def test_worker_code_is_pinned_and_cannot_be_selected_by_candidate(self):
        lease = aws_lease()
        api = AwsAPI(lease)
        with self.assertRaises(Refusal):
            c.AWS(api, b'other code').launch(lease)
        self.assertFalse(api.calls)


if __name__ == '__main__':
    unittest.main()
