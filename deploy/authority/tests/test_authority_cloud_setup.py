"""Native-owned asynchronous cloud provisioning over bounded API fixtures."""
import backend_test_support
import copy
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend_test_support import config
from test_authority_setup_owner import fixture
from trusted_ci_policy import Refusal, digest
import authority_release
import cloud
import cloud_setup
import private_setup


class Provider:
    def __init__(self, adapter):
        self.config = config(adapter)
        self.preview = cloud.preview(self.config)
        self.calls, self.applies, self.polls, self.fail, self.unknown = [], 0, 0, False, False
        self.outputs_defect = False
        self.stale_complete = False
    def identity(self): return dict(Account=self.config['account'], id=self.config['account'])
    def discover(self): return copy.deepcopy(self.preview)
    def prepare_group(self, approval, session, request_id):
        session.require_effect('cloud-apply', digest(self.config))
    def read_group(self, approval, session, request_id):
        session.require_effect('cloud-apply', digest(self.config))
        return dict(id='/subscriptions/' + self.config['account'] + '/resourceGroups/' + self.config['deployment'],
                    request_id=request_id, preexisting=False)
    def submit_deployment(self, approval, session, request_id, group):
        return self.apply(approval, session, request_id)
    def apply(self, approval, session, request_id):
        session.require_effect('cloud-apply', digest(self.config))
        self.applies += 1
        self.request_id = request_id
        if self.unknown: raise OSError('synthetic lost provider acknowledgement')
        return {}
    def call(self, *args):
        self.calls.append(args)
        c = self.config
        if c['adapter'] == 'aws':
            operation, body = args[1], args[2]
            arn = 'arn:aws:cloudformation:' + c['region'] + ':' + c['account'] + ':stack/' + c['deployment'] + '/fixture'
            if operation == 'describe-stack-events':
                return dict(StackEvents=[dict(ClientRequestToken='agentic-' + self.request_id, StackId=arn,
                    ResourceType='AWS::CloudFormation::Stack', PhysicalResourceId=arn, LogicalResourceId=c['deployment'],
                    ResourceStatus='CREATE_IN_PROGRESS' if self.stale_complete else 'CREATE_COMPLETE',
                    Timestamp='1970-01-01T00:16:42Z')])
            if operation == 'get-template': return dict(TemplateBody=cloud.aws_template(c))
            self.polls += 1
            state = 'ROLLBACK_COMPLETE' if self.fail else 'CREATE_COMPLETE' if self.stale_complete else 'CREATE_IN_PROGRESS' if self.polls == 1 else 'CREATE_COMPLETE'
            bucket = 'agentic-' + c['account'] + '-' + c['deployment']
            outputs = dict(Bucket=bucket, Subnet='subnet-12345678', SecurityGroup='sg-12345678',
                LauncherRole='arn:aws:iam::' + c['account'] + ':role/' + c['deployment'] + '-launch',
                JobIoRole='arn:aws:iam::' + c['account'] + ':role/fixture-io')
            if self.outputs_defect: outputs['LauncherRole'] = outputs['LauncherRole'].replace(c['account'], '999999999999')
            return dict(Stacks=[dict(StackId=arn, StackName=c['deployment'], StackStatus=state,
                CreationTime='1970-01-01T00:16:41Z',
                Tags=[dict(Key='AgenticDeployment', Value=c['deployment'])],
                Outputs=[dict(OutputKey=k, OutputValue=v) for k,v in outputs.items()])])
        argv = args[0]
        if argv[:3] == ['deployment', 'group', 'export']: return cloud.azure_template(c)
        self.polls += 1
        name = c['deployment'] + '-' + self.request_id[:24]
        scope = '/subscriptions/' + c['account'] + '/resourceGroups/' + c['deployment']
        storage = 'ag' + hashlib.sha256((c['account'] + c['deployment']).encode()).hexdigest()[:20]
        outputs = dict(storage=storage, clientId='12345678-1234-1234-1234-123456789abc',
            subnet=scope + '/providers/Microsoft.Network/virtualNetworks/' + c['deployment'] + '-network/subnets/jobs')
        if self.outputs_defect: outputs['subnet'] = outputs['subnet'].replace(c['account'], '99999999-9999-9999-9999-999999999999')
        return dict(id=scope + '/providers/Microsoft.Resources/deployments/' + name, name=name,
            properties=dict(provisioningState='Failed' if self.fail else 'Running' if self.polls == 1 else 'Succeeded',
                outputs={k:dict(type='String', value=v) for k,v in outputs.items()}))


class AzureAPI(cloud.Azure):
    """Exercise actual Azure adapter methods across its intermediate effect."""
    def __init__(self):
        super().__init__(config('azure'))
        self.group, self.deployment = None, None
        self.group_writes = self.deployment_writes = 0
        self.group_reads = self.pending_group_reads = 0
        self.lose_group_ack = True

    def call(self, argv, **kwargs):
        c = self.config
        scope = '/subscriptions/' + c['account'] + '/resourceGroups/' + c['deployment']
        if argv[:2] == ['account', 'show']: return dict(id=c['account'])
        if argv[:2] == ['group', 'list']: return [] if self.group is None else [copy.deepcopy(self.group)]
        if argv[:2] == ['resource', 'list']: return []
        if argv[:2] == ['group', 'create']:
            tags = argv[argv.index('--tags') + 1:]
            self.group = dict(id=scope, name=c['deployment'], location=c['region'],
                              tags=dict(item.split('=', 1) for item in tags), properties=dict(provisioningState='Succeeded'))
            self.group_writes += 1
            if self.lose_group_ack: raise OSError('synthetic lost group-create acknowledgement')
            return copy.deepcopy(self.group)
        if argv[:2] == ['group', 'show']:
            if self.group is None: raise Refusal('synthetic group not found')
            self.group_reads += 1
            result = copy.deepcopy(self.group)
            if self.group_reads <= self.pending_group_reads: result['properties']['provisioningState'] = 'Creating'
            return result
        if argv[:3] == ['deployment', 'group', 'create']:
            name = argv[argv.index('--name') + 1]
            self.deployment_writes += 1
            self.deployment = dict(id=scope + '/providers/Microsoft.Resources/deployments/' + name, name=name,
                properties=dict(provisioningState='Succeeded', outputs=dict(
                    storage=dict(type='String', value='ag' + hashlib.sha256((c['account'] + c['deployment']).encode()).hexdigest()[:20]),
                    clientId=dict(type='String', value='12345678-1234-1234-1234-123456789abc'),
                    subnet=dict(type='String', value=scope + '/providers/Microsoft.Network/virtualNetworks/' + c['deployment'] + '-network/subnets/jobs'))))
            return {}
        if argv[:3] == ['deployment', 'group', 'show']:
            if self.deployment is None: raise Refusal('synthetic deployment not found')
            return copy.deepcopy(self.deployment)
        if argv[:3] == ['deployment', 'group', 'export']: return cloud.azure_template(c)
        raise AssertionError(argv)


class CloudSetupContracts(unittest.TestCase):
    def test_real_adapter_requests_bind_retained_nonce_and_reject_substitution(self):
        from backend_test_support import LocalSession
        nonce = 'e' * 32
        for adapter in ('aws', 'azure'):
            c = config(adapter)
            p = cloud.preview(c)
            p.update(existing_template_digest=None, oidc_provider='', existing_resources=[])
            api = cloud.Aws(c) if adapter == 'aws' else cloud.Azure(c)
            calls = []
            api.discover = lambda: copy.deepcopy(p)
            api.call = lambda *args, **kwargs: calls.append(args) or {}
            def contract(request_id):
                calls.clear()
                api.apply(digest(p), LocalSession(), request_id=request_id)
                if adapter == 'aws': self.assertEqual(calls[-1][2]['ClientRequestToken'], 'agentic-' + nonce)
                else: self.assertEqual(calls[-1][0][calls[-1][0].index('--name') + 1], c['deployment'] + '-' + nonce[:24])
            contract(nonce)
            with self.assertRaises(AssertionError): contract(None)  # Deliberately broken request binding.
            with self.assertRaises(Refusal): api.apply(digest(p), LocalSession(), request_id='../arbitrary')

    def controller(self, adapter, existing=False):
        provider = Provider(adapter)
        if existing:
            c = provider.config
            provider.preview.update(existing_template_digest=provider.preview['template_digest'],
                existing_stack_id='arn:aws:cloudformation:' + c['region'] + ':' + c['account'] + ':stack/' + c['deployment'] + '/fixture')
        return self.for_provider(provider)

    def for_provider(self, provider):
        preview = provider.discover()
        host, registry, make, *rest = fixture(embedded_identities=True, cloud_setup=(provider.config, preview))
        temporary = tempfile.TemporaryDirectory(prefix='agentic-cloud-setup-fixture-',
            dir=str(Path.home()) if os.name == 'nt' else '/tmp')
        self.addCleanup(temporary.cleanup)
        journal = private_setup.Store(Path(temporary.name) / 'cloud')
        clock = rest[-1]
        return provider, journal, cloud_setup.Provision(make(), provider, journal, lambda: clock[0], sleep=lambda n: None)

    def test_azure_group_ack_loss_recovers_request_bound_group_then_submits_once(self):
        p, store, controller = self.for_provider(AzureAPI())
        approval = digest(controller.session.preview['changes']['cloud'])
        with self.assertRaises(OSError): controller._run(approval)
        self.assertEqual(p.group_writes, 1)
        self.assertEqual(p.deployment_writes, 0)
        self.assertEqual(p.group['tags'].get('AgenticSetupRequest'), store.read()['value']['request_id'])
        result = controller._run(approval)
        self.assertEqual(result['state'], 'provisioned-unqualified')
        self.assertEqual(p.group_writes, 1)
        self.assertEqual(p.deployment_writes, 1)

    def test_azure_unknown_group_never_adopts_a_name_without_its_request_marker(self):
        p, store, controller = self.for_provider(AzureAPI())
        approval = digest(controller.session.preview['changes']['cloud'])
        with self.assertRaises(OSError): controller._run(approval)
        p.group['tags']['AgenticSetupRequest'] = 'f' * 32
        with self.assertRaises(Refusal): controller._run(approval)
        self.assertEqual(p.deployment_writes, 0)

    def test_azure_group_ready_is_not_persisted_while_provider_is_still_creating(self):
        p, store, controller = self.for_provider(AzureAPI())
        p.lose_group_ack = False
        p.pending_group_reads = 1
        original = store.write
        def write(expected, value):
            if value['phase'] == 'group-ready': self.assertGreater(p.group_reads, p.pending_group_reads)
            return original(expected, value)
        store.write = write
        result = controller._run(digest(controller.session.preview['changes']['cloud']))
        self.assertEqual(result['state'], 'provisioned-unqualified')
        self.assertEqual(p.deployment_writes, 1)

    def test_existing_identical_approved_stack_is_observed_without_update(self):
        p, store, controller = self.controller('aws', existing=True)
        result = controller._run(digest(p.preview))
        self.assertEqual(p.applies, 0)
        self.assertEqual(result['state'], 'provisioned-unqualified')

    def test_stale_stack_complete_with_current_in_progress_event_never_completes(self):
        p, store, controller = self.controller('aws')
        p.stale_complete = True
        with self.assertRaises(Refusal): controller._run(digest(p.preview))
        self.assertNotEqual(store.read()['value']['phase'], 'observed')

    def test_existing_aws_update_pins_approved_arn_in_request(self):
        from backend_test_support import LocalSession
        c = config('aws')
        p = cloud.preview(c)
        arn = 'arn:aws:cloudformation:' + c['region'] + ':' + c['account'] + ':stack/' + c['deployment'] + '/original'
        p.update(existing_template_digest='0' * 64, existing_stack_id=arn, oidc_provider='')
        api = cloud.Aws(c)
        api.discover = lambda: copy.deepcopy(p)
        calls = []
        api.call = lambda *args: calls.append(args) or {}
        api.apply(digest(p), LocalSession(), request_id='e' * 32)
        self.assertEqual(calls[-1][2]['StackName'], arn)

    def test_public_hold_precedes_cloud_and_private_storage(self):
        p, store, controller = self.controller('aws')
        with self.assertRaises(authority_release.Held): controller.run(digest(p.preview))
        self.assertIsNone(store.read())
        self.assertEqual(p.applies, 0)

    def test_both_adapters_poll_actual_completion_bind_outputs_and_never_qualify(self):
        for adapter in ('aws', 'azure'):
            p, store, controller = self.controller(adapter)
            result = controller._run(digest(p.preview))
            self.assertEqual(p.applies, 1)
            self.assertGreaterEqual(p.polls, 2)
            self.assertEqual(result['state'], 'provisioned-unqualified')
            self.assertFalse(result['enforcement_active'])
            self.assertEqual(result['resources']['region'], p.config['region'])
            self.assertEqual(store.read()['value']['phase'], 'observed')
            self.assertEqual(controller._run(digest(p.preview)), result)
            self.assertEqual(p.applies, 1)

    def test_provider_failure_or_substituted_outputs_cannot_claim_completion(self):
        for adapter in ('aws', 'azure'):
            for defect in ('fail', 'outputs_defect'):
                p, store, controller = self.controller(adapter)
                setattr(p, defect, True)
                with self.subTest(adapter=adapter, defect=defect), self.assertRaises(Refusal):
                    controller._run(digest(p.preview))
                self.assertNotEqual(store.read()['value']['phase'], 'observed')

    def test_unknown_apply_uses_retained_operation_readback_without_second_effect(self):
        for adapter in ('aws', 'azure'):
            p, store, controller = self.controller(adapter)
            p.unknown = True
            with self.assertRaises(OSError): controller._run(digest(p.preview))
            result = controller._run(digest(p.preview))
            self.assertEqual(p.applies, 1)
            self.assertEqual(result['state'], 'provisioned-unqualified')


if __name__ == '__main__': unittest.main()
