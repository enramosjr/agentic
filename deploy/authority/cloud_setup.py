"""Native-owned asynchronous provisioning; deployment is never qualification."""
import copy
import hashlib
import re
import secrets
import time

import authority_release
import cloud
from configuration import SetupConfigurationSession
from trusted_ci_deployment import timestamp
from trusted_ci_policy import digest, object_fields, require

UUID = '[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}'


class Provision:
    def __init__(self, session, provider, journal, clock, sleep=time.sleep):
        self.session, self.provider, self.journal = session, provider, journal
        self.clock, self.sleep, self.document = clock, sleep, None
        cloud.validate(provider.config)

    def run(self, approval):
        authority_release.authorize('provision')
        return self._run(approval)

    def _guard(self, approval):
        require(isinstance(self.session, SetupConfigurationSession), 'native configuration owner required')
        c = self.provider.config
        binding = self.session.require_effect('cloud-apply', digest(c))
        d, p = binding['deployment'], binding['deployment']['policy']
        require(d['state'] == 'setup' and d['adapter'] == c['adapter'] and d['account'] == c['account'] and
                c['authority'] == p['authority_repository'] and
                digest(self.session.preview['changes']['cloud']) == approval and self.clock() < d['expires'],
                'approved native cloud configuration differs')
        if self.document is not None:
            require(self.journal.read() == self.document, 'cloud setup journal changed')
        return dict(configuration_revision=binding['configuration_revision'], deployment_digest=binding['deployment_digest'],
            operation_id=self.session.operation_id, sequence=self.session.sequence,
            approval_digest=approval, config=copy.deepcopy(c))

    def _save(self, value):
        self.document = self.journal.write(self.document, value)

    def _observe(self, request_id, existing_stack_id=None, no_change=False):
        p, c = self.provider, self.provider.config
        p.identity()
        if c['adapter'] == 'aws':
            rows = p.call('cloudformation', 'describe-stacks', {'StackName': c['deployment']})['Stacks']
            require(len(rows) == 1, 'single owned AWS deployment required')
            value = rows[0]
            arn = value.get('StackId', '')
            require(re.fullmatch('arn:aws:cloudformation:' + re.escape(c['region']) + ':' + c['account'] +
                ':stack/' + re.escape(c['deployment']) + '/[A-Za-z0-9-]+', arn) and
                value.get('StackName') == c['deployment'] and
                {t['Key']:t['Value'] for t in value.get('Tags', [])}.get('AgenticDeployment') == c['deployment'],
                'AWS deployment ownership differs')
            if existing_stack_id is not None:
                require(arn == existing_stack_id, 'previously approved AWS stack identity changed')
            terminal = []
            if not no_change:
                events = p.call('cloudformation', 'describe-stack-events', {'StackName': arn})['StackEvents']
                roots = [e for e in events if e.get('ClientRequestToken') == 'agentic-' + request_id and
                    e.get('StackId') == arn and e.get('ResourceType') == 'AWS::CloudFormation::Stack' and
                    e.get('PhysicalResourceId') == arn and e.get('LogicalResourceId') == c['deployment']]
                require(not any('ROLLBACK' in e.get('ResourceStatus', '') or e.get('ResourceStatus', '').endswith('_FAILED')
                                for e in roots), 'retained AWS provisioning operation failed')
                terminal = [e for e in roots if e.get('ResourceStatus') in ('CREATE_COMPLETE', 'UPDATE_COMPLETE')]
                if not terminal: return False, value
                require(len(terminal) == 1, 'ambiguous AWS root completion event')
                # A prior COMPLETE status plus this request's IN_PROGRESS event
                # must not authorize completion. Re-read only after its terminal
                # root event, and reject a later operation starting afterward.
                rows = p.call('cloudformation', 'describe-stacks', {'StackName': arn})['Stacks']
                require(len(rows) == 1 and rows[0].get('StackId') == arn and rows[0].get('StackName') == c['deployment'] and
                    {t['Key']:t['Value'] for t in rows[0].get('Tags', [])}.get('AgenticDeployment') == c['deployment'],
                    'terminal AWS stack identity changed')
                value = rows[0]
                modified = value.get('LastUpdatedTime', value.get('CreationTime'))
                require(isinstance(modified, str) and isinstance(terminal[0].get('Timestamp'), str) and
                    timestamp(modified) <= timestamp(terminal[0]['Timestamp']), 'AWS stack advanced after this operation')
            state = value.get('StackStatus')
            require(state in ('CREATE_IN_PROGRESS', 'UPDATE_IN_PROGRESS', 'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS',
                              'CREATE_COMPLETE', 'UPDATE_COMPLETE'), 'AWS deployment failed or has unknown state')
            complete = state in ('CREATE_COMPLETE', 'UPDATE_COMPLETE')
            require(not complete or no_change or state == terminal[0]['ResourceStatus'], 'AWS terminal operation state differs')
            return complete, value
        name = c['deployment'] + '-' + request_id[:24]
        value = p.call(['deployment', 'group', 'show', '--resource-group', c['deployment'], '--name', name])
        expected = '/subscriptions/' + c['account'] + '/resourceGroups/' + c['deployment'] + '/providers/Microsoft.Resources/deployments/' + name
        require(value.get('id') == expected and value.get('name') == name, 'Azure deployment request identity differs')
        state = value.get('properties', {}).get('provisioningState')
        require(state in ('Accepted', 'Running', 'Creating', 'Updating', 'Succeeded'), 'Azure deployment failed or has unknown state')
        return state == 'Succeeded', value

    def _resources(self, request_id, value):
        p, c = self.provider, self.provider.config
        result = dict(region=c['region'], deployment=c['deployment'])
        if c['adapter'] == 'aws':
            template = p.call('cloudformation', 'get-template', {'StackName': value['StackId']})['TemplateBody']
            if isinstance(template, str):
                from trusted_ci_policy import loads
                template = loads(template)
            require(digest(template) == digest(cloud.aws_template(c)), 'deployed AWS template differs')
            entries = value.get('Outputs', [])
            outputs = {item['OutputKey']:item['OutputValue'] for item in entries}
            require(len(outputs) == len(entries), 'duplicate AWS outputs')
            object_fields(outputs, ('Bucket', 'Subnet', 'SecurityGroup', 'LauncherRole', 'JobIoRole'), 'AWS outputs')
            bucket = 'agentic-' + c['account'] + '-' + c['deployment']
            require(outputs['Bucket'] == bucket and re.fullmatch('subnet-[0-9a-f]{8,17}', outputs['Subnet']) and
                    re.fullmatch('sg-[0-9a-f]{8,17}', outputs['SecurityGroup']) and
                    outputs['LauncherRole'] == 'arn:aws:iam::' + c['account'] + ':role/' + c['deployment'] + '-launch' and
                    re.fullmatch('arn:aws:iam::' + c['account'] + ':role/[A-Za-z0-9_+=,.@/-]{1,512}', outputs['JobIoRole']),
                    'AWS outputs escape approved account/resources')
            result.update(bucket=bucket, artifact_host=bucket + '.s3.' + c['region'] + '.amazonaws.com',
                subnet=outputs['Subnet'], security_group=outputs['SecurityGroup'], launcher_role=outputs['LauncherRole'],
                job_io_role=outputs['JobIoRole'], compute_scope=value['StackId'])
        else:
            name = c['deployment'] + '-' + request_id[:24]
            template = p.call(['deployment', 'group', 'export', '--resource-group', c['deployment'], '--name', name])
            require(digest(template) == digest(cloud.azure_template(c)), 'deployed Azure template differs')
            outputs = value['properties'].get('outputs', {})
            object_fields(outputs, ('storage', 'clientId', 'subnet'), 'Azure outputs')
            require(all(isinstance(v, dict) and v.get('type', '').lower() == 'string' and
                        isinstance(v.get('value'), str) for v in outputs.values()), 'string Azure outputs required')
            outputs = {k:v['value'] for k,v in outputs.items()}
            scope = '/subscriptions/' + c['account'] + '/resourceGroups/' + c['deployment']
            storage = 'ag' + hashlib.sha256((c['account'] + c['deployment']).encode()).hexdigest()[:20]
            subnet = scope + '/providers/Microsoft.Network/virtualNetworks/' + c['deployment'] + '-network/subnets/jobs'
            require(outputs['storage'] == storage and outputs['subnet'] == subnet and
                    re.fullmatch(UUID, outputs['clientId']), 'Azure outputs escape approved subscription/resources')
            result.update(storage_account=storage, artifact_host=storage + '.blob.core.windows.net',
                launcher_client_id=outputs['clientId'], resource_group=c['deployment'], compute_scope=scope, subnet=subnet)
        return result

    def _run(self, approval):
        end = time.monotonic() + 600
        binding = self._guard(approval)
        self.document = self.journal.read()
        if self.document is None:
            preview = self.provider.discover()
            require(digest(preview) == approval, 'fresh authenticated cloud preview required')
            existing = preview.get('existing_stack_id') if self.provider.config['adapter'] == 'aws' else None
            if self.provider.config['adapter'] == 'aws' and preview.get('existing_template_digest') is not None:
                require(isinstance(existing, str) and existing, 'approved existing stack identity required')
            self._guard(approval)
            self._save(dict(schema_version=1, kind='native-cloud-setup', binding=binding,
                request_id=secrets.token_hex(16), existing_stack_id=existing, group=None, phase='prepared', result=None))
        state = copy.deepcopy(self.document['value'])
        object_fields(state, ('schema_version', 'kind', 'binding', 'request_id', 'existing_stack_id', 'group', 'phase', 'result'), 'private cloud setup')
        require(type(state['schema_version']) is int and state['schema_version'] == 1 and state['kind'] == 'native-cloud-setup' and
                state['binding'] == binding and re.fullmatch('[0-9a-f]{32}', state['request_id']) and
                state['phase'] in ('prepared', 'group-started', 'group-ready', 'apply-started', 'observed'), 'retained cloud operation differs')
        preview = self.session.preview['changes']['cloud']
        aws = self.provider.config['adapter'] == 'aws'
        expected_existing = preview.get('existing_stack_id') if aws else None
        no_change = aws and preview.get('existing_template_digest') == preview.get('template_digest')
        require(state['existing_stack_id'] == expected_existing, 'retained cloud recovery mode differs from approval')
        if not aws:
            if state['phase'] == 'prepared':
                state['phase'] = 'group-started'
                self._save(state)
                self._guard(approval)
                self.provider.prepare_group(approval, self.session, state['request_id'])
            if state['phase'] == 'group-started':
                for _ in range(60):
                    self._guard(approval)
                    require(time.monotonic() < end, 'Azure group observation deadline reached')
                    group = self.provider.read_group(approval, self.session, state['request_id'])
                    self._guard(approval)
                    if group is not None:
                        state.update(group=group, phase='group-ready')
                        self._save(state)
                        break
                    self.sleep(5)
                require(state['phase'] == 'group-ready', 'Azure group is not ready; resume without repeating creation')
            if state['phase'] == 'group-ready':
                state['phase'] = 'apply-started'
                self._save(state)
                self._guard(approval)
                self.provider.submit_deployment(approval, self.session, state['request_id'], state['group'])
        if state['phase'] == 'prepared':
            state['phase'] = 'apply-started'
            self._save(state)
            self._guard(approval)
            if not no_change:
                self.provider.apply(approval, session=self.session, request_id=state['request_id'])
        # A lost acknowledgement is recovered only by the unpredictable retained
        # provider request identity. Never replay a create/update by name.
        for _ in range(60):
            self._guard(approval)
            require(time.monotonic() < end, 'cloud provisioning observation deadline reached')
            complete, value = self._observe(state['request_id'], state['existing_stack_id'], no_change)
            self._guard(approval)
            if complete:
                resources = self._resources(state['request_id'], value)
                self._guard(approval)
                result = dict(state='provisioned-unqualified', resources=resources,
                    request_id=state['request_id'], enforcement_active=False)
                require(state['result'] in (None, result), 'previously observed cloud resources changed')
                if state['phase'] != 'observed':
                    state.update(phase='observed', result=result)
                    self._save(state)
                return result
            self.sleep(5)
        require(False, 'cloud provisioning incomplete; resume the retained operation without reapplying')
