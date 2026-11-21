"""Adopter-owned cloud deployment plans and authenticated provider readback.

No cloud call is made by template rendering. Apply requires a fresh authenticated
preview and its exact digest; publication credentials never enter this module.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib import request
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.ai' / 'scripts'))
from trusted_ci_policy import Refusal, digest, object_fields, require
from bootstrap import run
from trusted_ci_github import NoRedirect


class NotFound(Refusal):
    """Authenticated ARM ResourceNotFound; never a generic CLI/authentication error."""


def validate(c):
    object_fields(c, ('adapter', 'deployment', 'authority', 'branch', 'account', 'region'), 'cloud configuration')
    require(c['adapter'] in ('aws', 'azure'), 'cloud adapter required')
    for key, pattern in [('deployment', '[a-z][a-z0-9-]{2,31}'),
                         ('authority', r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+'),
                         ('branch', '[A-Za-z0-9][A-Za-z0-9_/-]{0,99}'),
                         ('region', '[a-z][a-z0-9-]{1,29}')]:
        require(isinstance(c[key], str) and re.fullmatch(pattern, c[key]), 'invalid ' + key)
    require(all(part not in ('.', '..') for part in c['authority'].split('/')),
            'invalid authority repository segment')
    pattern = ('[0-9]{12}' if c['adapter'] == 'aws' else
               '[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}')
    require(isinstance(c['account'], str) and re.fullmatch(pattern, c['account']), 'invalid account')
    return c


def preview(c):
    validate(c)
    template = aws_template(c) if c['adapter'] == 'aws' else azure_template(c)
    return dict(schema_version=2, adapter=c['adapter'], account=c['account'],
                region=c['region'], deployment=c['deployment'], authority=c['authority'],
                template_digest=digest(template),
                billable=['job compute', 'work disks', 'object storage', 'network transfer',
                          'public IPv4' if c['adapter'] == 'aws' else 'NAT gateway and public IPv4'],
                controls={'max_job_seconds': 600, 'concurrent_jobs': 1,
                          'object_retention_days': 7, 'hard_billing_cap': False})


def approved(c, approval):
    p = preview(c)
    require(approval == digest(p), 'fresh cloud resource/cost preview approval required')
    return p


def aws_template(c):
    validate(c)
    require(c['adapter'] == 'aws', 'AWS configuration required')
    account, region, name = c['account'], c['region'], c['deployment']
    bucket = 'agentic-' + account + '-' + name
    subject = 'repo:' + c['authority'] + ':ref:refs/heads/' + c['branch']
    ref = lambda value: {'Ref': value}
    attr = lambda value, key: {'Fn::GetAtt': [value, key]}
    tags = [{'Key': 'AgenticDeployment', 'Value': name}]
    policy = lambda statements: {'Version': '2012-10-17', 'Statement': statements}
    resources = {
        'GithubProvider': {'Type': 'AWS::IAM::OIDCProvider', 'Condition': 'CreateProvider',
                           'DeletionPolicy': 'Retain', 'UpdateReplacePolicy': 'Retain',
                           'Properties': {'Url': 'https://token.actions.githubusercontent.com',
                                          'ClientIdList': ['sts.amazonaws.com']}},
        'Artifacts': {'Type': 'AWS::S3::Bucket', 'Properties': {
            'BucketName': bucket, 'Tags': tags,
            'PublicAccessBlockConfiguration': {k: True for k in
                ('BlockPublicAcls', 'BlockPublicPolicy', 'IgnorePublicAcls', 'RestrictPublicBuckets')},
            'BucketEncryption': {'ServerSideEncryptionConfiguration': [
                {'ServerSideEncryptionByDefault': {'SSEAlgorithm': 'AES256'}}]},
            'VersioningConfiguration': {'Status': 'Enabled'},
            'LifecycleConfiguration': {'Rules': [{'Id': 'JobRetention', 'Status': 'Enabled',
                'Prefix': 'jobs/', 'ExpirationInDays': 7,
                'NoncurrentVersionExpiration': {'NoncurrentDays': 7},
                'AbortIncompleteMultipartUpload': {'DaysAfterInitiation': 1}}]}}},
        'ArtifactsPolicy': {'Type': 'AWS::S3::BucketPolicy', 'Properties': {
            'Bucket': ref('Artifacts'), 'PolicyDocument': policy([{
                'Effect': 'Deny', 'Principal': '*', 'Action': 's3:*',
                'Resource': ['arn:aws:s3:::' + bucket, 'arn:aws:s3:::' + bucket + '/*'],
                'Condition': {'Bool': {'aws:SecureTransport': 'false'}}}])}},
        'Vpc': {'Type': 'AWS::EC2::VPC', 'Properties': {'CidrBlock': '10.80.0.0/24',
                'EnableDnsSupport': True, 'EnableDnsHostnames': True, 'Tags': tags}},
        'Subnet': {'Type': 'AWS::EC2::Subnet', 'Properties': {'VpcId': ref('Vpc'),
                   'CidrBlock': '10.80.0.0/25', 'MapPublicIpOnLaunch': True, 'Tags': tags}},
        'Gateway': {'Type': 'AWS::EC2::InternetGateway', 'Properties': {'Tags': tags}},
        'GatewayAttachment': {'Type': 'AWS::EC2::VPCGatewayAttachment', 'Properties': {
                              'VpcId': ref('Vpc'), 'InternetGatewayId': ref('Gateway')}},
        'Routes': {'Type': 'AWS::EC2::RouteTable', 'Properties': {'VpcId': ref('Vpc'), 'Tags': tags}},
        'Outbound': {'Type': 'AWS::EC2::Route', 'DependsOn': 'GatewayAttachment', 'Properties': {
                     'RouteTableId': ref('Routes'), 'DestinationCidrBlock': '0.0.0.0/0',
                     'GatewayId': ref('Gateway')}},
        'SubnetRoutes': {'Type': 'AWS::EC2::SubnetRouteTableAssociation', 'Properties': {
                         'SubnetId': ref('Subnet'), 'RouteTableId': ref('Routes')}},
        'WorkerSecurity': {'Type': 'AWS::EC2::SecurityGroup', 'Properties': {
            'VpcId': ref('Vpc'), 'GroupDescription': 'AGENTIC job hosts: no inbound access',
            'SecurityGroupIngress': [], 'SecurityGroupEgress': [
                {'IpProtocol': 'tcp', 'FromPort': 443, 'ToPort': 443, 'CidrIp': '0.0.0.0/0'}], 'Tags': tags}},
        'LauncherRole': {'Type': 'AWS::IAM::Role', 'Properties': {
            'Tags': tags, 'MaxSessionDuration': 3600,
            'AssumeRolePolicyDocument': policy([{'Effect': 'Allow',
                'Principal': {'Federated': {'Fn::If': ['CreateProvider', ref('GithubProvider'), ref('OidcProviderArn')]}},
                'Action': 'sts:AssumeRoleWithWebIdentity', 'Condition': {'StringEquals': {
                    'token.actions.githubusercontent.com:aud': 'sts.amazonaws.com',
                    'token.actions.githubusercontent.com:sub': subject}}}]),
            'Policies': [{'PolicyName': 'Dispatch', 'PolicyDocument': policy([
                {'Effect': 'Allow', 'Action': 'ec2:RunInstances',
                 'Resource': 'arn:aws:ec2:' + region + ':' + account + ':instance/*',
                 'Condition': {'StringEquals': {'aws:RequestTag/AgenticDeployment': name}}},
                {'Effect': 'Allow', 'Action': 'ec2:RunInstances', 'Resource': [
                    'arn:aws:ec2:' + region + '::image/*',
                    'arn:aws:ec2:' + region + ':' + account + ':volume/*',
                    'arn:aws:ec2:' + region + ':' + account + ':network-interface/*',
                    {'Fn::Sub': 'arn:aws:ec2:' + region + ':' + account + ':subnet/${Subnet}'},
                    {'Fn::Sub': 'arn:aws:ec2:' + region + ':' + account + ':security-group/${WorkerSecurity}'}]},
                {'Effect': 'Allow', 'Action': 'ec2:CreateTags', 'Resource': '*',
                 'Condition': {'StringEquals': {'ec2:CreateAction': 'RunInstances',
                                               'aws:RequestTag/AgenticDeployment': name}}},
                {'Effect': 'Allow', 'Action': ['ec2:DescribeInstances', 'ec2:DescribeImages',
                  'ec2:DescribeInstanceAttribute', 'ec2:DescribeInstanceStatus', 'ec2:DescribeVolumes'], 'Resource': '*'},
                {'Effect': 'Allow', 'Action': 'ec2:DeleteVolume',
                 'Resource': 'arn:aws:ec2:' + region + ':' + account + ':volume/*',
                 'Condition': {'StringEquals': {'ec2:ResourceTag/AgenticDeployment': name}}},
                {'Effect': 'Allow', 'Action': 'ec2:TerminateInstances',
                 'Resource': 'arn:aws:ec2:' + region + ':' + account + ':instance/*',
                 'Condition': {'StringEquals': {'ec2:ResourceTag/AgenticDeployment': name}}},
                {'Effect': 'Allow', 'Action': ['s3:GetObject', 's3:PutObject', 's3:DeleteObject'],
                 'Resource': 'arn:aws:s3:::' + bucket + '/jobs/*'},
                {'Effect': 'Allow', 'Action': 's3:ListBucket', 'Resource': 'arn:aws:s3:::' + bucket,
                 'Condition': {'StringLike': {'s3:prefix': 'jobs/*'}}},
                {'Effect': 'Allow', 'Action': 'sts:AssumeRole', 'Resource': attr('JobIoRole', 'Arn')},
                {'Effect': 'Allow', 'Action': ['cloudformation:DescribeStacks'],
                 'Resource': 'arn:aws:cloudformation:' + region + ':' + account + ':stack/' + name + '/*'}])}]}},
        'JobIoRole': {'Type': 'AWS::IAM::Role', 'Properties': {
            'Tags': tags, 'MaxSessionDuration': 3600,
            'AssumeRolePolicyDocument': policy([{'Effect': 'Allow',
                'Principal': {'Federated': {'Fn::If': ['CreateProvider', ref('GithubProvider'), ref('OidcProviderArn')]}},
                'Action': 'sts:AssumeRoleWithWebIdentity', 'Condition': {'StringEquals': {
                    'token.actions.githubusercontent.com:aud': 'sts.amazonaws.com',
                    'token.actions.githubusercontent.com:sub': subject}}}]),
            'Policies': [{'PolicyName': 'JobObjectsOnly', 'PolicyDocument': policy([{
                'Effect': 'Allow', 'Action': ['s3:GetObject', 's3:PutObject'],
                'Resource': 'arn:aws:s3:::' + bucket + '/jobs/*'}])}]}},
    }
    # The job role trusts the exact launcher role, not arbitrary account identities.
    # Substitute a deterministic role ARN to avoid a CloudFormation dependency cycle.
    resources['LauncherRole']['Properties']['RoleName'] = name + '-launch'
    resources['JobIoRole']['Properties']['AssumeRolePolicyDocument'] = policy([{
        'Effect': 'Allow', 'Principal': {'AWS': 'arn:aws:iam::' + account + ':root'},
        'Action': 'sts:AssumeRole', 'Condition': {'ArnEquals': {
            'aws:PrincipalArn': 'arn:aws:iam::' + account + ':role/' + name + '-launch'}}}])
    return {'AWSTemplateFormatVersion': '2010-09-09', 'Description': 'Adopter-owned AGENTIC verification resources',
            'Parameters': {'OidcProviderArn': {'Type': 'String', 'Default': ''}},
            'Conditions': {'CreateProvider': {'Fn::Equals': [ref('OidcProviderArn'), '']}},
            'Resources': resources, 'Outputs': {
                'Bucket': {'Value': ref('Artifacts')}, 'Subnet': {'Value': ref('Subnet')},
                'SecurityGroup': {'Value': ref('WorkerSecurity')},
                'LauncherRole': {'Value': attr('LauncherRole', 'Arn')},
                'JobIoRole': {'Value': attr('JobIoRole', 'Arn')}}}


def azure_template(c):
    validate(c)
    require(c['adapter'] == 'azure', 'Azure configuration required')
    name, region = c['deployment'], c['region']
    storage = 'ag' + hashlib.sha256((c['account'] + name).encode()).hexdigest()[:20]
    subject = 'repo:' + c['authority'] + ':ref:refs/heads/' + c['branch']
    resources = [
        {'type': 'Microsoft.ManagedIdentity/userAssignedIdentities', 'apiVersion': '2023-01-31',
         'name': name + '-launch', 'location': region,
         'resources': [{'type': 'federatedIdentityCredentials', 'apiVersion': '2023-01-31',
             'name': 'github-authority', 'properties': {'issuer': 'https://token.actions.githubusercontent.com',
             'subject': subject, 'audiences': ['api://AzureADTokenExchange']}}]},
        {'type': 'Microsoft.Storage/storageAccounts', 'apiVersion': '2023-05-01',
         'name': storage, 'location': region, 'sku': {'name': 'Standard_LRS'}, 'kind': 'StorageV2',
         'properties': {'supportsHttpsTrafficOnly': True, 'minimumTlsVersion': 'TLS1_2',
                        'allowBlobPublicAccess': False, 'allowSharedKeyAccess': False}},
        {'type': 'Microsoft.Storage/storageAccounts/blobServices/containers', 'apiVersion': '2023-05-01',
         'name': storage + '/default/jobs',
         'dependsOn': ["[resourceId('Microsoft.Storage/storageAccounts', '" + storage + "')]"],
         'properties': {'publicAccess': 'None'}},
        {'type': 'Microsoft.Network/publicIPAddresses', 'apiVersion': '2023-09-01',
         'name': name + '-outbound', 'location': region, 'sku': {'name': 'Standard'},
         'properties': {'publicIPAllocationMethod': 'Static'}},
        {'type': 'Microsoft.Network/natGateways', 'apiVersion': '2023-09-01',
         'name': name + '-nat', 'location': region, 'sku': {'name': 'Standard'},
         'dependsOn': ["[resourceId('Microsoft.Network/publicIPAddresses', '" + name + "-outbound')]"],
         'properties': {'publicIpAddresses': [{'id': "[resourceId('Microsoft.Network/publicIPAddresses', '" + name + "-outbound')]"}]}},
        {'type': 'Microsoft.Network/networkSecurityGroups', 'apiVersion': '2023-09-01',
         'name': name + '-jobs', 'location': region, 'properties': {'securityRules': [{
             'name': 'DenyInbound', 'properties': {'priority': 100, 'direction': 'Inbound', 'access': 'Deny',
              'protocol': '*', 'sourcePortRange': '*', 'destinationPortRange': '*',
              'sourceAddressPrefix': '*', 'destinationAddressPrefix': '*'}}]}},
        {'type': 'Microsoft.Network/virtualNetworks', 'apiVersion': '2023-09-01',
         'name': name + '-network', 'location': region,
         'dependsOn': ["[resourceId('Microsoft.Network/natGateways', '" + name + "-nat')]",
                       "[resourceId('Microsoft.Network/networkSecurityGroups', '" + name + "-jobs')]"],
         'properties': {'addressSpace': {'addressPrefixes': ['10.81.0.0/24']}, 'subnets': [{
             'name': 'jobs', 'properties': {'addressPrefix': '10.81.0.0/25', 'defaultOutboundAccess': False,
                 'natGateway': {'id': "[resourceId('Microsoft.Network/natGateways', '" + name + "-nat')]"},
                 'networkSecurityGroup': {'id': "[resourceId('Microsoft.Network/networkSecurityGroups', '" + name + "-jobs')]"}}}]}}
    ]
    # Assign only owned-resource-group compute/network readback and storage data
    # permissions. The runtime identity cannot assign roles or administer GitHub.
    for label, role in [('compute', '9980e02c-c2be-4d73-94e8-173b1dc7cf3c'),
                        ('network', '4d97b98b-1d4f-4787-a291-c67834d212e7'),
                        ('read', 'acdd72a7-3385-48ef-bd42-f606fba81ae7')]:
        resources.append({'type': 'Microsoft.Authorization/roleAssignments', 'apiVersion': '2022-04-01',
            'name': "[guid(resourceGroup().id, '" + name + "', '" + label + "')]",
            'dependsOn': ["[resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', '" + name + "-launch')]"],
            'properties': {'roleDefinitionId': "[subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '" + role + "')]",
                'principalId': "[reference(resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', '" + name + "-launch'), '2023-01-31').principalId]",
                'principalType': 'ServicePrincipal'}})
    resources.append({'type': 'Microsoft.Storage/storageAccounts/providers/roleAssignments',
        'apiVersion': '2022-04-01', 'name': "[concat('" + storage + "/Microsoft.Authorization/', guid(resourceGroup().id, '" + name + "', 'objects'))]",
        'dependsOn': ["[resourceId('Microsoft.Storage/storageAccounts', '" + storage + "')]",
                      "[resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', '" + name + "-launch')]"],
        'properties': {'roleDefinitionId': "[subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')]",
            'principalId': "[reference(resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', '" + name + "-launch'), '2023-01-31').principalId]",
            'principalType': 'ServicePrincipal'}})
    for resource in resources:
        if (resource['type'] != 'Microsoft.Authorization/roleAssignments' and
                not resource['type'].endswith(('/roleAssignments', '/containers'))):
            resource['tags'] = {'AgenticDeployment': name}
    return {'$schema': 'https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#',
            'contentVersion': '1.0.0.0', 'resources': resources, 'outputs': {
                'storage': {'type': 'string', 'value': storage},
                'clientId': {'type': 'string', 'value': "[reference(resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', '" + name + "-launch'), '2023-01-31').clientId]"},
                'subnet': {'type': 'string', 'value': "[resourceId('Microsoft.Network/virtualNetworks/subnets', '" + name + "-network', 'jobs')]"}}}


class Aws:
    def __init__(self, config, runner=run):
        self.config = validate(config)
        require(config['adapter'] == 'aws', 'AWS adapter configuration required')
        self.run = runner

    def call(self, service, operation, body=None, outfile=None):
        require(service in ('sts', 'iam', 'ec2', 's3api', 'cloudformation'), 'unsupported AWS service')
        endpoint = ('https://iam.amazonaws.com' if service == 'iam' else
                    'https://' + ('s3' if service == 's3api' else service) + '.' + self.config['region'] + '.amazonaws.com')
        argv = ['aws', service, operation, '--region', self.config['region'], '--output', 'json',
                '--no-cli-pager', '--endpoint-url', endpoint]
        if body is None:
            return json.loads(self.run(argv))
        with tempfile.TemporaryDirectory(prefix='agentic-aws-') as directory:
            path = Path(directory) / 'request.json'
            path.write_text(json.dumps(body), encoding='utf-8')
            args = argv + ['--cli-input-json', 'file://' + str(path)]
            if outfile is not None:
                args.append(str(outfile))
            raw = self.run(args)
            return json.loads(raw) if raw.strip() else {}

    def download_object(self, bucket, key):
        expected = 'agentic-' + self.config['account'] + '-' + self.config['deployment']
        require(bucket == expected and re.fullmatch('jobs/[0-9a-f]{32}/report\\.json', key),
                'AWS report object is outside deployment scope')
        with tempfile.TemporaryDirectory(prefix='agentic-report-') as folder:
            output = Path(folder) / 'report.json'
            self.call('s3api', 'get-object', {'Bucket': bucket, 'Key': key,
                      'Range': 'bytes=0-1048576'}, outfile=output)
            with output.open('rb') as stream:
                raw = stream.read(1024 * 1024 + 1)
            require(len(raw) <= 1024 * 1024, 'AWS report exceeds limit')
            return raw

    def identity(self):
        result = self.call('sts', 'get-caller-identity')
        require(result['Account'] == self.config['account'], 'authenticated AWS account differs from selection')
        return result

    def discover(self):
        self.identity()
        providers = self.call('iam', 'list-open-id-connect-providers')['OpenIDConnectProviderList']
        matches = [p['Arn'] for p in providers if p['Arn'].endswith('/token.actions.githubusercontent.com')]
        require(len(matches) <= 1, 'ambiguous GitHub federation provider')
        p = preview(self.config)
        existing = self.call('cloudformation', 'list-stacks')['StackSummaries']
        existing = [s for s in existing if s['StackName'] == self.config['deployment'] and
                    s['StackStatus'] != 'DELETE_COMPLETE']
        require(len(existing) <= 1, 'ambiguous deployment stack')
        old = None
        provider = matches[0] if matches else ''
        if existing:
            stack = self.call('cloudformation', 'describe-stacks',
                              {'StackName': self.config['deployment']})['Stacks'][0]
            require({t['Key']: t['Value'] for t in stack.get('Tags', [])}.get('AgenticDeployment') ==
                    self.config['deployment'], 'existing stack is not owned by this deployment')
            old = self.call('cloudformation', 'get-template',
                            {'StackName': self.config['deployment']})['TemplateBody']
            if isinstance(old, str):
                old = json.loads(old)
            provider = {x['ParameterKey']: x['ParameterValue'] for x in stack.get('Parameters', [])}.get('OidcProviderArn', '')
        p['oidc_provider'] = provider
        p['existing_stack_id'] = stack['StackId'] if existing else None
        p['existing_template_digest'] = digest(old) if old else None
        p['changes'] = template_changes(old or {}, aws_template(self.config))
        return p

    def apply(self, approval, session=None, request_id=None):
        from configuration import require_session
        require(request_id is None or isinstance(request_id, str) and re.fullmatch('[0-9a-f]{32}', request_id),
                'fixed AWS provisioning request identity required')
        require_session(session, 'cloud-apply', digest(self.config))
        p = self.discover()
        require(digest(p) == approval, 'authenticated AWS deployment preview approval required')
        if p['existing_template_digest'] == p['template_digest']:
            return self.readback()
        operation = 'update-stack' if p['existing_template_digest'] else 'create-stack'
        target = self.config['deployment']
        if operation == 'update-stack':
            target = p.get('existing_stack_id')
            require(isinstance(target, str) and re.fullmatch('arn:aws:cloudformation:' +
                re.escape(self.config['region']) + ':' + self.config['account'] + ':stack/' +
                re.escape(self.config['deployment']) + '/[A-Za-z0-9-]+', target), 'approved immutable AWS stack ID required')
        require_session(session, 'cloud-apply', digest(self.config))
        return self.call('cloudformation', operation, {
            'StackName': target, 'TemplateBody': json.dumps(aws_template(self.config)),
            'Capabilities': ['CAPABILITY_NAMED_IAM'], 'Parameters': [
                {'ParameterKey': 'OidcProviderArn', 'ParameterValue': p['oidc_provider']}],
            'Tags': [{'Key': 'AgenticDeployment', 'Value': self.config['deployment']}],
            'ClientRequestToken': 'agentic-' + (request_id or approval)})

    def readback(self):
        self.identity()
        result = self.call('cloudformation', 'describe-stacks', {'StackName': self.config['deployment']})
        stacks = result['Stacks']
        require(len(stacks) == 1 and stacks[0]['StackStatus'] in ('CREATE_COMPLETE', 'UPDATE_COMPLETE'),
                'AWS deployment is not complete')
        require({t['Key']: t['Value'] for t in stacks[0].get('Tags', [])}.get('AgenticDeployment') ==
                self.config['deployment'], 'AWS stack ownership mismatch')
        return stacks[0]

    def destroy(self, inventory, approval, session=None):
        from configuration import require_session
        require_session(session, 'cloud-destroy', digest(self.config))
        self.identity()
        observed = self.call('cloudformation', 'list-stack-resources',
                             {'StackName': self.config['deployment']})['StackResourceSummaries']
        resources = [x['PhysicalResourceId'] for x in observed if 'PhysicalResourceId' in x]
        owned_inventory(resources, inventory)
        p = {'operation': 'destroy', 'account': self.config['account'],
             'deployment': self.config['deployment'], 'resources': sorted(resources)}
        require(digest(p) == approval, 'exact AWS teardown preview approval required')
        self.readback()
        require_session(session, 'cloud-destroy', digest(self.config))
        return self.call('cloudformation', 'delete-stack', {'StackName': self.config['deployment'],
                                                          'ClientRequestToken': 'agentic-' + approval})


class Azure:
    def __init__(self, config, runner=run, opener=None):
        self.config = validate(config)
        require(config['adapter'] == 'azure', 'Azure adapter configuration required')
        self.run = runner
        self.open = opener or request.build_opener(NoRedirect()).open
        self.token = None

    def call(self, argv, seconds=60):
        env = {k: v for k, v in os.environ.items() if not k.startswith('AZURE_STORAGE_')}
        raw = self.run(['az', *argv, '--subscription', self.config['account'],
                        '--only-show-errors', '--output', 'json'], env=env, seconds=seconds)
        return json.loads(raw) if raw.strip() else {}

    def get(self, url):
        require(isinstance(url, str), 'invalid Azure readback URL')
        parsed = urlsplit(url)
        prefix = '/subscriptions/' + self.config['account'] + '/resourceGroups/' + self.config['deployment'] + '/providers/'
        require(parsed.scheme == 'https' and parsed.netloc == 'management.azure.com' and not parsed.fragment and
                parsed.path.startswith(prefix) and re.fullmatch('[A-Za-z0-9_./-]+', parsed.path) and
                not any(p in ('.', '..') for p in parsed.path.split('/')) and
                re.fullmatch(r'api-version=[0-9]{4}-[0-9]{2}-[0-9]{2}(&\$expand=instanceView)?', parsed.query),
                'Azure readback escapes approved endpoint or resource scope')
        if self.token is None or self.token[1] <= int(time.time()) + 60:
            value = self.call(['account', 'get-access-token', '--resource', 'https://management.azure.com/'])
            token, expiry = value.get('accessToken'), str(value.get('expires_on', ''))
            require(value.get('subscription', '').lower() == self.config['account'] and
                    isinstance(token, str) and 0 < len(token) <= 32768 and
                    not any(ord(c) < 32 or ord(c) == 127 for c in token) and
                    re.fullmatch('[0-9]{10}', expiry) and int(expiry) > int(time.time()) + 60,
                    'current subscription-scoped Azure token unavailable')
            self.token = token, int(expiry)
        req = request.Request(url, headers={'Authorization': 'Bearer ' + self.token[0]})
        try:
            with self.open(req, timeout=30) as response:
                raw = response.read(1024 * 1024 + 1)
                require(len(raw) <= 1024 * 1024, 'Azure resource response exceeds limit')
                value = json.loads(raw)
                require(isinstance(value, dict), 'invalid Azure resource response')
                return value
        except HTTPError as error:
            with error:
                raw = error.read(8193)
            try:
                code = json.loads(raw).get('error', {}).get('code') if len(raw) <= 8192 else None
            except (ValueError, AttributeError):
                code = None
            if error.code == 404 and code == 'ResourceNotFound':
                raise NotFound('authenticated Azure resource not found') from None
            raise Refusal('Azure resource readback failed') from None
        except (URLError, OSError, ValueError):
            raise Refusal('Azure resource readback unavailable') from None

    def delete_and_wait(self, kind, identity):
        provider, commands = {'vm': ('Microsoft.Compute/virtualMachines', ['vm', 'delete']),
            'nic': ('Microsoft.Network/networkInterfaces', ['network', 'nic', 'delete']),
            'disk': ('Microsoft.Compute/disks', ['disk', 'delete'])}.get(kind, (None, None))
        require(provider is not None, 'unsupported Azure deletion kind')
        prefix = '/subscriptions/' + self.config['account'] + '/resourceGroups/' + self.config['deployment'] + '/providers/' + provider + '/'
        require(identity.startswith(prefix) and re.fullmatch('[A-Za-z0-9_.-]+', identity[len(prefix):]) and
                identity[len(prefix):] not in ('.', '..'), 'Azure deletion escapes owned scope')
        # Typed commands wait for the provider LRO. A request acknowledgement or
        # an empty eventually-consistent inventory is not a completion witness.
        return self.call(commands + ['--ids', identity] + ([] if kind == 'nic' else ['--yes']), seconds=180)

    def resource(self, method, path, version, body=None, expand=False):
        prefix = '/subscriptions/' + self.config['account'] + '/resourceGroups/' + self.config['deployment'] + '/providers/'
        require(method in ('GET', 'PUT', 'DELETE') and path.startswith(prefix) and
                not any(p in ('.', '..') for p in path.split('/')) and
                re.fullmatch(r'[A-Za-z0-9_./-]+', path) and re.fullmatch('[0-9]{4}-[0-9]{2}-[0-9]{2}', version),
                'Azure request escapes deployment scope')
        argv = ['rest', '--method', method, '--url', 'https://management.azure.com' + path +
                '?api-version=' + version + ('&$expand=instanceView' if expand else '')]
        if method == 'GET':
            return self.get(argv[-1])
        if body is None:
            return self.call(argv)
        with tempfile.TemporaryDirectory(prefix='agentic-azure-body-') as folder:
            request = Path(folder) / 'body.json'
            request.write_text(json.dumps(body), encoding='utf-8')
            return self.call(argv + ['--body', '@' + str(request)])

    def list_resources(self, kind):
        require(kind in ('Microsoft.Compute/virtualMachines', 'Microsoft.Network/networkInterfaces', 'Microsoft.Compute/disks'),
                'unsupported job resource type')
        return self.call(['resource', 'list', '--resource-group', self.config['deployment'], '--resource-type', kind])

    def storage_arguments(self, account, container, key):
        expected = 'ag' + hashlib.sha256((self.config['account'] + self.config['deployment']).encode()).hexdigest()[:20]
        require(account == expected and container == 'jobs' and re.fullmatch('[0-9a-f]{32}/report\\.json', key),
                'Azure report object is outside deployment scope')
        return ['--auth-mode', 'login', '--account-name', account, '--blob-endpoint',
                'https://' + account + '.blob.core.windows.net', '--container-name', container, '--name', key]

    def blob_exists(self, account, container, key):
        result = self.call(['storage', 'blob', 'exists', *self.storage_arguments(account, container, key)])
        require(type(result.get('exists')) is bool, 'invalid Azure object existence response')
        return result['exists']

    def download_object(self, account, container, key):
        args = self.storage_arguments(account, container, key)
        with tempfile.TemporaryDirectory(prefix='agentic-report-') as folder:
            output = Path(folder) / 'report.json'
            self.call(['storage', 'blob', 'download', *args, '--file', str(output),
                       '--start-range', '0', '--end-range', '1048576', '--no-progress'])
            with output.open('rb') as stream:
                raw = stream.read(1024 * 1024 + 1)
            require(len(raw) <= 1024 * 1024, 'Azure report exceeds limit')
            return raw

    def identity(self):
        result = self.call(['account', 'show'])
        require(result['id'].lower() == self.config['account'],
                'authenticated Azure subscription differs from selection')
        require(result.get('environmentName', 'AzureCloud') == 'AzureCloud',
                'only Azure public cloud is supported')
        return result

    def discover(self):
        self.identity()
        p = preview(self.config)
        groups = self.call(['group', 'list'])
        matches = [g for g in groups if g['name'] == self.config['deployment']]
        require(len(matches) <= 1, 'ambiguous resource group')
        if matches:
            require(matches[0].get('tags', {}).get('AgenticDeployment') == self.config['deployment'],
                    'existing resource group is not owned by this deployment')
            current = self.call(['resource', 'list', '--resource-group', self.config['deployment']])
            require(all(r.get('tags', {}).get('AgenticDeployment') == self.config['deployment'] for r in current),
                    'resource group contains unrelated resources; automatic mutation refused')
            p['existing_resources'] = sorted(r['id'] for r in current)
        else:
            p['existing_resources'] = None
        return p

    def _setup_preview(self, approval, session, request_id):
        from configuration import SetupConfigurationSession, require_session
        require(isinstance(session, SetupConfigurationSession) and isinstance(request_id, str) and
                re.fullmatch('[0-9a-f]{32}', request_id), 'native request-bound Azure setup required')
        require_session(session, 'cloud-apply', digest(self.config))
        p = session.preview['changes']['cloud']
        require(isinstance(p, dict) and digest(p) == approval and
                all(p.get(k) == v for k,v in preview(self.config).items()) and
                'existing_resources' in p, 'approved Azure template/account preview differs')
        return p

    def prepare_group(self, approval, session, request_id):
        from configuration import require_session
        p = self._setup_preview(approval, session, request_id)
        require(self.discover() == p, 'Azure group changed before creation intent')
        if p['existing_resources'] is None:
            require_session(session, 'cloud-apply', digest(self.config))
            self.call(['group', 'create', '--name', self.config['deployment'], '--location', self.config['region'],
                       '--tags', 'AgenticDeployment=' + self.config['deployment'], 'AgenticSetupRequest=' + request_id])

    def read_group(self, approval, session, request_id):
        p = self._setup_preview(approval, session, request_id)
        self.identity()
        c = self.config
        value = self.call(['group', 'show', '--name', c['deployment']])
        expected = '/subscriptions/' + c['account'] + '/resourceGroups/' + c['deployment']
        require(value.get('id') == expected and value.get('name') == c['deployment'] and
                value.get('location') == c['region'] and
                value.get('tags', {}).get('AgenticDeployment') == c['deployment'], 'Azure group identity/ownership differs')
        created = p['existing_resources'] is None
        require(not created or value.get('tags', {}).get('AgenticSetupRequest') == request_id,
                'unknown Azure group does not belong to the retained request')
        state = value.get('properties', {}).get('provisioningState')
        require(state in ('Accepted', 'Creating', 'Updating', 'Succeeded'), 'Azure group failed or has unknown provisioning state')
        if state != 'Succeeded': return None
        return dict(id=expected, preexisting=not created, request_id=None if not created else request_id)

    def submit_deployment(self, approval, session, request_id, group):
        from configuration import require_session
        object_fields(group, ('id', 'preexisting', 'request_id'), 'retained Azure group')
        p = self._setup_preview(approval, session, request_id)
        require(self.read_group(approval, session, request_id) == group, 'retained Azure group changed')
        expected = dict(p, existing_resources=p['existing_resources'] if p['existing_resources'] is not None else [])
        require(self.discover() == expected, 'Azure resources changed between group creation and deployment')
        with tempfile.TemporaryDirectory(prefix='agentic-arm-') as folder:
            path = Path(folder) / 'authority.json'
            path.write_text(json.dumps(azure_template(self.config)), encoding='utf-8')
            require_session(session, 'cloud-apply', digest(self.config))
            return self.call(['deployment', 'group', 'create', '--resource-group', self.config['deployment'],
                '--name', self.config['deployment'] + '-' + request_id[:24], '--template-file', str(path), '--no-wait'])

    def apply(self, approval, session=None, request_id=None):
        from configuration import require_session
        require(request_id is None or isinstance(request_id, str) and re.fullmatch('[0-9a-f]{32}', request_id),
                'fixed Azure provisioning request identity required')
        require_session(session, 'cloud-apply', digest(self.config))
        p = self.discover()
        require(digest(p) == approval, 'authenticated Azure resource/cost preview approval required')
        name = self.config['deployment']
        deployment_name = name + '-' + request_id[:24] if request_id is not None else name
        if p['existing_resources'] is None:
            require_session(session, 'cloud-apply', digest(self.config))
            self.call(['group', 'create', '--name', name, '--location', self.config['region'],
                       '--tags', 'AgenticDeployment=' + name])
        with tempfile.TemporaryDirectory(prefix='agentic-arm-') as folder:
            path = Path(folder) / 'authority.json'
            path.write_text(json.dumps(azure_template(self.config)), encoding='utf-8')
            require_session(session, 'cloud-apply', digest(self.config))
            return self.call(['deployment', 'group', 'create', '--resource-group', name,
                              '--name', deployment_name, '--template-file', str(path), '--no-wait'])

    def readback(self):
        self.identity()
        result = self.call(['deployment', 'group', 'show', '--resource-group', self.config['deployment'],
                            '--name', self.config['deployment']])
        require(result['properties']['provisioningState'] == 'Succeeded', 'Azure deployment is incomplete')
        return result

    def destroy(self, inventory, approval, session=None):
        from configuration import require_session
        require_session(session, 'cloud-destroy', digest(self.config))
        p = self.discover()
        require(p['existing_resources'] is not None, 'Azure deployment does not exist')
        resources = owned_inventory(p['existing_resources'], inventory)
        destruction = {'operation': 'destroy', 'account': self.config['account'],
                       'deployment': self.config['deployment'], 'resources': resources}
        require(digest(destruction) == approval, 'exact Azure teardown preview approval required')
        require_session(session, 'cloud-destroy', digest(self.config))
        return self.call(['group', 'delete', '--name', self.config['deployment'], '--yes', '--no-wait'])


def owned_inventory(observed, expected):
    require(isinstance(observed, list) and isinstance(expected, list) and observed and
            all(isinstance(x, str) and x for x in observed + expected) and
            len(expected) == len(set(expected)) and len(observed) == len(set(observed)) and
            set(observed) == set(expected), 'owned resource inventory changed; teardown refused')
    return sorted(observed)


def template_changes(old, new):
    left, right = old.get('Resources', {}), new.get('Resources', {})
    return [{'resource': key, 'change': ('create' if key not in left else
            'remove' if key not in right else 'modify')} for key in sorted(set(left) | set(right))
            if left.get(key) != right.get(key)]


def aws_launch_readback(observed, expected):
    require(observed.get('InstanceId') == expected['instance_id'] and
            observed.get('ImageId') == expected['image'] and
            observed.get('MetadataOptions', {}).get('HttpTokens') == 'required', 'AWS launch identity mismatch')
    tags = {t['Key']: t['Value'] for t in observed.get('Tags', [])}
    require(tags.get('AgenticDeployment') == expected['deployment'] and
            tags.get('AgenticJob') == expected['job'], 'AWS job namespace mismatch')
    return observed


def azure_command_complete(result):
    view = result.get('properties', {}).get('instanceView', {})
    require(view.get('executionState') == 'Succeeded' and type(view.get('exitCode')) is int and
            view['exitCode'] == 0, 'Azure command has not completed successfully')
    return result
