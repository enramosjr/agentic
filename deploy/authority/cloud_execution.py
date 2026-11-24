"""Concrete disposable-host adapters; invoked only by a trusted execution service."""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
from pathlib import Path
import re
import secrets
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.ai/scripts'))
from authority_jobs import validate_lease
from trusted_ci_policy import digest, loads, require
from cloud import NotFound, aws_launch_readback, azure_command_complete


def bootstrap(lease, program):
    validate_lease(lease, lease['issued'])
    require(isinstance(program, bytes) and 0 < len(program) <= 65536 and
            hashlib.sha256(program).hexdigest() == lease['deployment']['resources'].get('worker_program_sha'),
            'approved worker program digest required')
    source = base64.b64encode(program).decode('ascii')
    data = base64.b64encode(json.dumps(lease, sort_keys=True).encode()).decode('ascii')
    # All interpolated content is base64 data. Candidate text never becomes shell.
    return ('#!/bin/bash\nset -euo pipefail\n'
        'shutdown -h +15\n'
        'if ! command -v docker >/dev/null; then\n'
        ' if command -v dnf >/dev/null; then dnf -y install docker git python3 util-linux e2fsprogs; '
        'else apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io git python3 util-linux e2fsprogs; fi\n'
        'fi\nsystemctl start docker\n'
        'python3 -I -c "import base64; exec(compile(base64.b64decode(\'' + source +
        '\'),\'approved-worker\',\'exec\'))" \'' + data + '\'\n').encode()


class AWS:
    def __init__(self, api, program, sleep=time.sleep):
        self.api, self.program, self.sleep = api, program, sleep

    def launch(self, lease):
        script = gzip.compress(bootstrap(lease, self.program), mtime=0)
        require(len(script) <= 16384, 'compressed EC2 user data exceeds limit')
        d, r = lease['deployment'], lease['deployment']['resources']
        require(self.api.config['account'] == d['account'] and
                self.api.config['region'] == r['region'] and
                self.api.config['deployment'] == r['deployment'], 'AWS execution scope differs from deployment')
        self.api.identity()
        for key, pattern in [('worker_image', 'ami-[0-9a-f]{8,17}'),
                             ('subnet', 'subnet-[0-9a-f]{8,17}'), ('security_group', 'sg-[0-9a-f]{8,17}')]:
            require(re.fullmatch(pattern, r.get(key, '')), 'registered AWS ' + key + ' required')
        images = self.api.call('ec2', 'describe-images', {'ImageIds': [r['worker_image']]})['Images']
        require(len(images) == 1 and images[0]['ImageId'] == r['worker_image'], 'approved AMI readback unavailable')
        image = images[0]
        mappings = image.get('BlockDeviceMappings', [])
        require(image.get('RootDeviceType') == 'ebs' and len(mappings) == 1 and
                mappings[0].get('DeviceName') == image.get('RootDeviceName') and
                re.fullmatch('/dev/[a-z0-9]+', image.get('RootDeviceName', '')) and
                isinstance(mappings[0].get('Ebs'), dict), 'only a single approved EBS root mapping is supported')
        size = r.get('worker_disk_gb', '32')
        require(re.fullmatch('[0-9]{2,3}', size) and 16 <= int(size) <= 128 and
                type(mappings[0]['Ebs'].get('VolumeSize')) is int and
                0 < mappings[0]['Ebs']['VolumeSize'] <= int(size), 'approved root disk capacity is invalid')
        tags = [{'Key': 'AgenticDeployment', 'Value': r['deployment']},
                {'Key': 'AgenticJob', 'Value': lease['id']}]
        body = {'ImageId': r['worker_image'], 'InstanceType': r.get('worker_size', 't3.small'),
            'MinCount': 1, 'MaxCount': 1, 'ClientToken': lease['id'], 'SubnetId': r['subnet'],
            'SecurityGroupIds': [r['security_group']],
            'MetadataOptions': {'HttpTokens': 'required', 'HttpPutResponseHopLimit': 1},
            'InstanceInitiatedShutdownBehavior': 'terminate',
            'BlockDeviceMappings': [{'DeviceName': image['RootDeviceName'], 'Ebs': {
                'DeleteOnTermination': True, 'Encrypted': True, 'VolumeSize': int(size), 'VolumeType': 'gp3'}}],
            'UserData': base64.b64encode(script).decode(),
            'TagSpecifications': [{'ResourceType': kind, 'Tags': tags} for kind in ('instance', 'volume')]}
        try:
            value = self.api.call('ec2', 'run-instances', body)['Instances']
            require(len(value) == 1 and re.fullmatch('i-[0-9a-f]{8,17}', value[0]['InstanceId']),
                    'unexpected EC2 launch response')
            return {'id': value[0]['InstanceId'], 'userdata_sha': hashlib.sha256(script).hexdigest()}
        except Exception:
            self.recover(lease)
            raise

    def recover(self, lease):
        # A lost RunInstances reply is not proof that allocation failed. Discover
        # by the idempotency token AND ownership tags, never by an untrusted ID.
        filters = [{'Name': 'client-token', 'Values': [lease['id']]},
            {'Name': 'tag:AgenticJob', 'Values': [lease['id']]},
            {'Name': 'tag:AgenticDeployment', 'Values': [lease['deployment']['resources']['deployment']]}]
        found = {}
        for _ in range(31):
            body = {'Filters': filters}
            for _page in range(100):
                value = self.api.call('ec2', 'describe-instances', body)
                for reservation in value['Reservations']:
                    for instance in reservation['Instances']:
                        self.owned(instance, lease)
                        found[instance['InstanceId']] = instance
                token = value.get('NextToken')
                if not token:
                    break
                require(isinstance(token, str) and len(token) <= 4096, 'invalid EC2 recovery pagination')
                body['NextToken'] = token
            else:
                require(False, 'EC2 recovery pagination exceeded limit')
            if found:
                for identity in found:
                    self.cleanup({'id': identity}, lease)
                return
            self.sleep(2)
        require(False, 'EC2 allocation outcome could not be established; trusted recovery required')

    def instance(self, handle):
        values = self.api.call('ec2', 'describe-instances', {'InstanceIds': [handle['id']]})
        instances = [i for r in values['Reservations'] for i in r['Instances']]
        require(len(instances) == 1 and instances[0]['InstanceId'] == handle['id'], 'EC2 readback identity changed')
        return instances[0]

    def owned(self, value, lease):
        tags = {t['Key']: t['Value'] for t in value.get('Tags', [])}
        require(tags.get('AgenticDeployment') == lease['deployment']['resources']['deployment'] and
                tags.get('AgenticJob') == lease['id'] and value.get('ClientToken') == lease['id'],
                'EC2 ownership is not established')

    def observe(self, handle, lease):
        value = self.instance(handle)
        self.owned(value, lease)
        aws_launch_readback(value, {'instance_id': handle['id'],
            'image': lease['deployment']['resources']['worker_image'],
            'deployment': lease['deployment']['resources']['deployment'], 'job': lease['id']})
        resources = lease['deployment']['resources']
        require(value.get('SubnetId') == resources['subnet'] and
                {g['GroupId'] for g in value.get('SecurityGroups', [])} == {resources['security_group']} and
                not value.get('IamInstanceProfile'), 'EC2 network or credential profile differs from approval')
        mappings = value.get('BlockDeviceMappings', [])
        require(len(mappings) == 1 and mappings[0].get('Ebs', {}).get('DeleteOnTermination') is True,
                'EC2 root disk deletion differs from approval')
        raw = self.api.call('ec2', 'describe-instance-attribute',
                            {'InstanceId': handle['id'], 'Attribute': 'userData'})['UserData']['Value']
        require(hashlib.sha256(base64.b64decode(raw, validate=True)).hexdigest() == handle['userdata_sha'],
                'EC2 approved worker launch data changed')

    def report(self, lease):
        bucket = lease['deployment']['resources']['bucket']
        key = 'jobs/' + lease['id'] + '/report.json'
        found = self.api.call('s3api', 'list-objects-v2', {'Bucket': bucket, 'Prefix': key, 'MaxKeys': 2})
        entries = found.get('Contents', [])
        require(all(e['Key'] == key for e in entries) and len(entries) <= 1, 'ambiguous job report')
        return loads(self.api.download_object(bucket, key)) if entries else None

    def cleanup(self, handle, lease):
        value = self.instance(handle)
        self.owned(value, lease)
        if value['State']['Name'] != 'terminated':
            self.api.call('ec2', 'terminate-instances', {'InstanceIds': [handle['id']]})
        for _ in range(31):
            if self.instance(handle)['State']['Name'] == 'terminated':
                self.clean_volumes(lease)
                return
            self.sleep(2)
        require(False, 'owned EC2 host termination was not confirmed')

    def clean_volumes(self, lease):
        filters = [{'Name': 'tag:AgenticJob', 'Values': [lease['id']]},
                   {'Name': 'tag:AgenticDeployment', 'Values': [lease['deployment']['resources']['deployment']]}]
        for _ in range(31):
            value = self.api.call('ec2', 'describe-volumes', {'Filters': filters})
            require(not value.get('NextToken'), 'incomplete EBS cleanup inventory')
            volumes = value['Volumes']
            if not volumes:
                return
            for volume in volumes:
                tags = {t['Key']: t['Value'] for t in volume.get('Tags', [])}
                require(tags.get('AgenticJob') == lease['id'] and
                        tags.get('AgenticDeployment') == lease['deployment']['resources']['deployment'],
                        'EBS cleanup ownership mismatch')
                require(re.fullmatch('vol-[0-9a-f]{8,17}', volume['VolumeId']), 'invalid EBS identity')
                if volume['State'] == 'available':
                    self.api.call('ec2', 'delete-volume', {'VolumeId': volume['VolumeId']})
            self.sleep(2)
        require(False, 'owned EBS deletion was not confirmed')


class Azure:
    def __init__(self, api, program, sleep=time.sleep):
        self.api, self.program, self.sleep = api, program, sleep

    def root(self, lease):
        d, r = lease['deployment'], lease['deployment']['resources']
        require(d['account'] == self.api.config['account'] and
                r.get('resource_group') == self.api.config['deployment'] and
                r.get('region') == self.api.config['region'], 'Azure execution scope differs')
        return '/subscriptions/' + d['account'] + '/resourceGroups/' + r['resource_group'] + '/providers/'

    def launch(self, lease):
        script = bootstrap(lease, self.program).decode()
        self.api.identity()
        root = self.root(lease)
        r = lease['deployment']['resources']
        require(re.fullmatch(r'[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+:[0-9][A-Za-z0-9_.-]*',
                             r.get('worker_image', '')), 'version-pinned Azure image URN required')
        require(r.get('subnet', '').lower().startswith(root.split('/providers/')[0].lower() + '/providers/microsoft.network/'),
                'registered subnet is outside owned Azure resource group')
        name = 'job-' + lease['id']
        nic = root + 'Microsoft.Network/networkInterfaces/' + name
        vm = root + 'Microsoft.Compute/virtualMachines/' + name
        tags = {'AgenticDeployment': r['resource_group'], 'AgenticJob': lease['id']}
        handle = {'id': vm, 'nic': nic, 'disk': root + 'Microsoft.Compute/disks/' + name + '-os',
                  'script_sha': hashlib.sha256(script.encode()).hexdigest()}
        try:
            self.api.resource('PUT', nic, '2023-09-01', {'location': self.api.config['region'], 'tags': tags,
                'properties': {'ipConfigurations': [{'name': 'job', 'properties': {
                    'subnet': {'id': r['subnet']}, 'privateIPAllocationMethod': 'Dynamic'}}]}})
            publisher, offer, sku, version = r['worker_image'].split(':')
            self.api.resource('PUT', vm, '2024-11-01', {'location': self.api.config['region'], 'tags': tags,
                'properties': {'hardwareProfile': {'vmSize': r.get('worker_size', 'Standard_B2s')},
                    'storageProfile': {'imageReference': {'publisher': publisher, 'offer': offer, 'sku': sku, 'version': version},
                                      'osDisk': {'name': name + '-os', 'createOption': 'FromImage', 'deleteOption': 'Delete',
                                                 'managedDisk': {'storageAccountType': 'StandardSSD_LRS'}}},
                    'osProfile': {'computerName': name[:32], 'adminUsername': 'agentichost',
                                  'adminPassword': 'Ag!' + secrets.token_urlsafe(32) + '7z',
                                  'linuxConfiguration': {'disablePasswordAuthentication': False}},
                    'networkProfile': {'networkInterfaces': [{'id': nic, 'properties': {'deleteOption': 'Delete'}}]}}})
            for _ in range(151):
                current = self.api.resource('GET', vm, '2024-11-01')
                state = current['properties']['provisioningState']
                require(state not in ('Failed', 'Canceled'), 'Azure VM provisioning failed')
                if state == 'Succeeded':
                    break
                self.sleep(2)
            else:
                require(False, 'Azure VM provisioning deadline exceeded')
            self.api.resource('PUT', vm + '/runCommands/verify', '2024-11-01', {
                'location': self.api.config['region'], 'properties': {'source': {'script': script},
                'timeoutInSeconds': 600, 'asyncExecution': False, 'treatFailureAsDeploymentFailure': True}})
            return handle
        except BaseException:
            self.cleanup(handle, lease)
            raise

    def observe(self, handle, lease):
        value = self.api.resource('GET', handle['id'], '2024-11-01')
        self.owned(value, lease)
        r = lease['deployment']['resources']
        image = value['properties']['storageProfile']['imageReference']
        require(':'.join(image[k] for k in ('publisher', 'offer', 'sku', 'version')) == r['worker_image'],
                'Azure runtime image differs from approval')
        self.capture_disk(value, handle, lease, require_delete=True)
        interfaces = value['properties']['networkProfile']['networkInterfaces']
        require(len(interfaces) == 1 and interfaces[0]['id'].lower() == handle['nic'].lower() and
                (value.get('identity') or {}).get('type', 'None') == 'None',
                'Azure network or managed identity differs from approval')
        nic = self.api.resource('GET', handle['nic'], '2023-09-01')
        self.owned(nic, lease)
        configs = nic['properties']['ipConfigurations']
        require(configs and all(v['properties']['subnet']['id'].lower() == r['subnet'].lower() and
                not v['properties'].get('publicIPAddress') for v in configs), 'Azure subnet or public endpoint drift')
        command = self.api.resource('GET', handle['id'] + '/runCommands/verify', '2024-11-01', expand=True)
        require(hashlib.sha256(command['properties']['source']['script'].encode()).hexdigest() == handle['script_sha'],
                'Azure worker program changed')
        view = command['properties'].get('instanceView', {})
        require(view.get('executionState') not in ('Failed', 'Canceled'), 'Azure worker command failed')

    def report(self, lease):
        account = lease['deployment']['resources']['storage_account']
        key = lease['id'] + '/report.json'
        if not self.api.blob_exists(account, 'jobs', key):
            return None
        root = self.root(lease) + 'Microsoft.Compute/virtualMachines/job-' + lease['id']
        command = self.api.resource('GET', root + '/runCommands/verify', '2024-11-01', expand=True)
        if command['properties'].get('instanceView', {}).get('executionState') != 'Succeeded':
            return None
        azure_command_complete(command)
        return loads(self.api.download_object(account, 'jobs', key))

    def owned(self, value, lease):
        tags = value.get('tags', {})
        require(tags.get('AgenticJob') == lease['id'] and
                tags.get('AgenticDeployment') == lease['deployment']['resources']['resource_group'],
                'Azure job ownership is not established')

    def capture_disk(self, vm, handle, lease, require_delete=False):
        self.owned(vm, lease)
        require(vm['id'].lower() == handle['id'].lower(), 'Azure VM identity changed during disk readback')
        profile = vm['properties']['storageProfile']
        disk = profile['osDisk']
        expected = self.root(lease) + 'Microsoft.Compute/disks/job-' + lease['id'] + '-os'
        require(handle['disk'].lower() == expected.lower() and
                disk['managedDisk']['id'].lower() == expected.lower() and
                disk['name'] == 'job-' + lease['id'] + '-os' and not profile.get('dataDisks'),
                'Azure OS disk mapping differs from approved job')
        interfaces = vm['properties']['networkProfile']['networkInterfaces']
        require(len(interfaces) == 1 and interfaces[0]['id'].lower() == handle['nic'].lower(),
                'Azure NIC mapping changed before cleanup')
        observed = self.api.resource('GET', expected, '2024-03-02')
        uid = observed['properties'].get('uniqueId')
        require(observed['id'].lower() == expected.lower() and
                str(observed.get('managedBy', '')).lower() == handle['id'].lower() and
                isinstance(uid, str) and re.fullmatch('[0-9a-fA-F-]{36}', uid) and
                handle.get('disk_uid', uid) == uid, 'Azure OS disk ownership changed')
        handle['disk_uid'] = uid
        require(not require_delete or disk.get('deleteOption') == 'Delete', 'Azure OS disk retention drift')

    def cleanup(self, handle, lease):
        # Monotonic phases: fresh typed ownership -> one blocking delete ->
        # identity-only absence polling. Never acquire ownership after DELETE.
        state = handle.setdefault('cleanup', {})
        resources = [('vm', 'id', 'Microsoft.Compute/virtualMachines', '2024-11-01'),
                     ('nic', 'nic', 'Microsoft.Network/networkInterfaces', '2023-09-01'),
                     ('disk', 'disk', 'Microsoft.Compute/disks', '2024-03-02')]
        root = self.root(lease)
        for kind, key, provider, version in resources:
            expected = root + provider + '/job-' + lease['id'] + ('-os' if kind == 'disk' else '')
            require(handle[key].lower() == expected.lower(), 'Azure cleanup handle escapes job scope')
            require(state.get(kind) != 'pending', 'Azure deletion outcome unresolved; trusted recovery required')
            if kind not in state:
                try:
                    observed = self.api.resource('GET', expected, version)
                except NotFound:
                    # Only a specifically authenticated provider not-found is an
                    # absence witness. Generic CLI/auth/network failures block.
                    state[kind] = 'absent'
                else:
                    require(observed['id'].lower() == expected.lower(), 'Azure cleanup readback identity changed')
                    if kind == 'vm':
                        self.capture_disk(observed, handle, lease)
                    elif kind == 'nic':
                        self.owned(observed, lease)
                        require(not observed['properties'].get('virtualMachine'), 'Azure NIC remains attached')
                    else:
                        self.detached_disk(observed, handle)
                    state[kind] = 'pending'
                    self.api.delete_and_wait(kind, expected)
                    state[kind] = 'confirmed'
            require(state[kind] in ('absent', 'confirmed'), 'invalid Azure cleanup phase')
            self.wait_absent(provider, expected)
        # A reappearing identity is drift, never a reason to delete a replacement.
        for _, key, provider, _ in resources:
            require(not self.inventory(provider, handle[key]), 'Azure resource reappeared during cleanup')

    def inventory(self, kind, identity):
        matches = [v for v in self.api.list_resources(kind) if v['id'].lower() == identity.lower()]
        require(len(matches) <= 1, 'ambiguous Azure cleanup inventory')
        return matches

    def wait_absent(self, kind, identity):
        for _ in range(31):
            if not self.inventory(kind, identity):
                return
            self.sleep(2)
        require(False, 'Azure owned-resource absence not confirmed')

    def detached_disk(self, disk, handle):
        for _ in range(31):
            require(disk['id'].lower() == handle['disk'].lower() and handle.get('disk_uid') and
                    disk['properties'].get('uniqueId') == handle['disk_uid'] and
                    not disk.get('managedByExtended'), 'Azure OS disk ownership changed; trusted recovery required')
            owner = disk.get('managedBy')
            if not owner and disk['properties'].get('diskState') == 'Unattached':
                return disk
            require(isinstance(owner, str) and owner.lower() == handle['id'].lower(),
                    'Azure OS disk has a foreign owner or unsupported state')
            self.sleep(2)
            disk = self.api.resource('GET', handle['disk'], '2024-03-02')
        require(False, 'Azure owned OS disk detachment not confirmed')
