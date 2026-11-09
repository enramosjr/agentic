"""Pinned authority producer roles; candidate execution stays inside the sandbox.

Authority coordinates come from the actual Actions execution, never dispatch
inputs. All public producer roles remain release-held before reads or credentials.
"""
import copy
import json
from contextlib import contextmanager
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
import tempfile
from urllib.parse import quote

sys.path[:0] = [str(Path(__file__).resolve().parent),
                str(Path(__file__).resolve().parents[2] / '.ai/scripts')]
import app_proofs
from artifact_uploader import NodeUploader
import authority_release
from registry import Registry
import setup
from trusted_ci_github import GitHub, HostRefusal
from trusted_ci_policy import Refusal, digest, loads, object_fields, positive, require, sha


def context(environment, api_factory=GitHub):
    name = environment.get('GITHUB_REPOSITORY', '')
    identity = environment.get('GITHUB_REPOSITORY_ID', '')
    token = environment.get('GITHUB_TOKEN', '')
    require(environment.get('GITHUB_SERVER_URL', 'https://github.com') == 'https://github.com' and
            isinstance(name, str) and re.fullmatch('[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', name) and
            all(part not in ('.', '..') for part in name.split('/')) and
            isinstance(identity, str) and re.fullmatch('[1-9][0-9]{0,19}', identity) and
            sha(environment.get('GITHUB_SHA')) and isinstance(token, str) and 0 < len(token) <= 16384,
            'trusted GitHub authority execution identity required')
    api = api_factory(token)
    registry = Registry(api, dict(schema_version=2, repository=name,
        repository_id=int(identity), registry_branch='agentic-registry'))
    binding = registry.binding()
    require(binding['software_revision'] == environment['GITHUB_SHA'], 'execution is not current pinned software')
    return api, registry, binding, app_proofs.load_identities(binding['deployment'])


def credential(environment, challenge, node):
    authority_release.authorize('bootstrap')
    return _credential(environment, challenge, node)


def _credential(environment, challenge, node, clock=None, api_factory=GitHub, uploader_factory=NodeUploader,
                consumer=setup._consume_credential):
    clock = clock or (lambda: int(time.time()))
    api, registry, before, identities = context(environment, api_factory)
    document = consumer(registry, api, environment, identities, challenge, clock)
    require(registry.binding() == before, 'credential configuration moved before upload')
    purpose = document['challenge']['purpose']
    attempt = document['execution']['attempt']
    artifact_id = uploader_factory(node, environment)('credential-proof-' + purpose + '-' + str(attempt),
        json.dumps(document, sort_keys=True, allow_nan=False).encode())
    require(positive(artifact_id), 'credential consumer artifact identity unavailable')
    return dict(run_id=document['execution']['run_id'], attempt=attempt,
                job_id=document['execution']['job_id'], artifact_id=artifact_id)


def model_authorization(environment, task, node):
    authority_release.authorize('protected-run')
    return _authorize_task_request(environment, task, node)


def _model_authorization(environment, task, node, clock=None, api_factory=GitHub, uploader_factory=NodeUploader,
                         provider=None, expected_binding=None):
    from provenance import admit_job
    import model_auth
    import model_auth_store
    clock = clock or (lambda: int(time.time()))
    api, registry, before, _ = context(environment, api_factory)
    require(expected_binding is None or before == expected_binding, 'prepared model authorization configuration changed')
    d, p = before['deployment'], before['deployment']['policy']
    admit_job(api, d, environment, 'model authorization', clock())
    names = {'AGENTIC_MODEL_VAULT_KEY', 'AGENTIC_MODEL_DELIVERY_KEY'}
    forbidden = set(setup.CREDENTIAL_NAMES) - names | {'GH_TOKEN', 'OPENAI_API_KEY', 'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN', 'AZURE_CLIENT_SECRET', 'ARM_CLIENT_SECRET'}
    require(not any(environment.get(key) for key in forbidden), 'model authorization inherited another purpose credential')
    owner = dict(workflow_sha=p['workflow_sha'], run_id=int(environment['GITHUB_RUN_ID']),
                 attempt=int(environment['GITHUB_RUN_ATTEMPT']))
    store = model_auth_store.AuthStore(api, p['authority_repository'], p['authority_repository_id'],
                                     p['workflow_sha'], admitted_owner=owner)
    class PinnedRegistry:
        def binding(self):
            value = registry.binding()
            require(value == before, 'model authorization configuration changed after admission')
            return value
    controller = model_auth.Controller(PinnedRegistry(), api, store, environment,
        environment.get('AGENTIC_MODEL_VAULT_KEY'), environment.get('AGENTIC_MODEL_DELIVERY_KEY'),
        provider=provider, clock=clock)
    return controller._produce(task, uploader_factory(node, environment))


def _authorize_task_request(environment, request, node, clock=None, api_factory=GitHub,
                            uploader_factory=NodeUploader, provider=None):
    from coding_parent import TASK_REQUEST_FIELDS
    import model_vault
    from provenance import admit_job
    clock = clock or (lambda:int(time.time()))
    object_fields(request, TASK_REQUEST_FIELDS, 'prepared model authorization request')
    task = request['task']
    object_fields(task, model_vault.TASK_FIELDS, 'prepared model task')
    api, registry, before, _ = context(environment, api_factory)
    d = before['deployment']
    require(type(request['schema_version']) is int and request['schema_version'] == 2 and
            request['configuration_revision'] == before['configuration_revision'] and
            request['deployment_digest'] == before['deployment_digest'] and before['fence']['pending'] is None and
            task['purpose'] == 'task' and positive(task['deadline']) and clock() < task['deadline'],
            'prepared model authorization intent changed or expired')
    admit_job(api,d,environment,'model authorization',clock())
    require(task['run_id'] == int(environment['GITHUB_RUN_ID']) and task['attempt'] == int(environment['GITHUB_RUN_ATTEMPT']),
            'prepared model authorization execution differs')
    result = _model_authorization(environment,task,node,clock=clock,api_factory=api_factory,
        uploader_factory=uploader_factory,provider=provider,expected_binding=before)
    require(registry.binding() == before and clock() < min(task['deadline'],d['expires']),
            'prepared model authorization changed before completion')
    return result


@contextmanager
def _source_token(purpose, root, authority, deployment, identities, revision, clock, token_factory=GitHub, guard=lambda:None,
                  recovery=False):
    require(purpose in ('coding', 'reader', 'admin', 'issuer', 'merge'), 'fixed source credential purpose required')
    # Preserve mint responses until their cleanup finally: a post-response guard
    # must not discard a newly issued token before it can be revoked.
    class AdmittedRoot:
        def get(self, path):
            guard()
            return root.get(path)
        def post(self, path, body):
            guard()
            return root.post(path, body)
    admitted = AdmittedRoot()
    if recovery:
        require(purpose == 'admin', 'only terminal administrator may borrow expired source access')
        app_proofs.authenticate(admitted, authority, deployment, identities, purpose)
    else:
        app_proofs.prove(admitted, authority, deployment, identities, purpose, revision, clock(), token_factory)
    guard()
    record = identities['apps'][purpose]
    permissions = (dict(administration='write', contents='read', pull_requests='read', repository_hooks='read')
                   if purpose == 'admin' else app_proofs.TOKEN_PERMISSIONS[purpose])
    result = admitted.post('/app/installations/' + str(record['installation_id']) + '/access_tokens',
        dict(repository_ids=[deployment['policy']['repository_id']], permissions=permissions))
    try:
        require(isinstance(result.get('token'), str) and result['token'] and
                app_proofs.normalized(result.get('permissions')) == permissions and
                [r['id'] for r in result.get('repositories', [])] == [deployment['policy']['repository_id']],
                'coding source token expanded its explicit scope')
        guard()
        scoped = token_factory(result['token'])
        require([r['id'] for r in scoped.pages('/installation/repositories', 'repositories')] ==
                [deployment['policy']['repository_id']], 'coding source token reaches another repository')
        guard()
        yield scoped
    finally:
        app_proofs.revoke(result, token_factory)


def _coding_source(root, authority, deployment, identities, revision, clock, token_factory=GitHub, guard=lambda:None):
    return _source_token('coding', root, authority, deployment, identities, revision, clock, token_factory, guard)


def prepare_task(environment, request):
    authority_release.authorize('protected-run')
    return _prepare_task(environment, request)


def _prepare_task(environment, request, clock=None, api_factory=GitHub, app_factory=None, token_factory=GitHub):
    import bootstrap
    from codex_harness import profile
    from provenance import admit_job
    clock = clock or (lambda:int(time.time()))
    object_fields(request, ('prompt',), 'task preparation request')
    require(isinstance(request['prompt'],str) and 0 < len(request['prompt'].encode('utf-8')) <= 65536,
            'bounded task prompt required')
    require(len(json.dumps(request,allow_nan=False).encode()) <= 48 * 1024,
            'task prompt exceeds the serialized preparation bound')
    forbidden = set(setup.CREDENTIAL_NAMES) - {'AGENTIC_READER_PRIVATE_KEY'} | {'GH_TOKEN','OPENAI_API_KEY',
        'AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY','AWS_SESSION_TOKEN','AZURE_CLIENT_SECRET','ARM_CLIENT_SECRET'}
    require(not any(environment.get(key) for key in forbidden), 'task preparation inherited another purpose credential')
    api, registry, before, identities = context(environment, api_factory)
    d, p = before['deployment'], before['deployment']['policy']
    profile(d)
    require(before['fence']['pending'] is None, 'task preparation requires a settled configuration fence')
    admit_job(api,d,environment,'prepare task',clock())
    def guard():
        require(registry.binding() == before and clock() < d['expires'], 'task preparation configuration changed or expired')
    guard()
    root = (app_factory or bootstrap.app_api)(d['apps']['reader'],environment.get('AGENTIC_READER_PRIVATE_KEY'))
    with _source_token('reader',root,api,d,identities,before['branch_head'],clock,token_factory,guard) as source:
        repository = source.get('/repos/' + p['repository'])
        require(repository.get('id') == p['repository_id'], 'task preparation source repository changed')
        base = source.get('/repos/' + p['repository'] + '/git/ref/heads/' + quote(p['target'],safe=''))['object']['sha']
        require(sha(base), 'task preparation source base unavailable')
    guard()
    now = clock()
    deadline = min(now + 900,d['expires'])
    require(deadline - now >= d['policy']['limits']['seconds'] + 60, 'configuration expires before a complete bounded task')
    return dict(schema_version=2,task=dict(task_id=secrets.token_hex(16),run_id=int(environment['GITHUB_RUN_ID']),
        attempt=int(environment['GITHUB_RUN_ATTEMPT']),deadline=deadline,purpose='task'), source_base=base,
        prompt=request['prompt'],configuration_revision=before['configuration_revision'],deployment_digest=before['deployment_digest'])


def task(environment, request, node):
    authority_release.authorize('protected-run')
    return _task(environment, request, node)


def task_controls(environment, request, node):
    authority_release.authorize('protected-run')
    return _task_controls(environment, request, node)


def _task_controls(environment, request, node, clock=None, api_factory=GitHub, app_factory=None,
                   token_factory=GitHub, uploader_factory=NodeUploader):
    import bootstrap
    import task_controls as rendezvous
    from provenance import admit_job
    clock = clock or (lambda:int(time.time()))
    forbidden = set(setup.CREDENTIAL_NAMES) - {'AGENTIC_ADMIN_PRIVATE_KEY'} | {'GH_TOKEN', 'OPENAI_API_KEY',
        'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN', 'AZURE_CLIENT_SECRET', 'ARM_CLIENT_SECRET'}
    require(not any(environment.get(key) for key in forbidden), 'task controls inherited another purpose credential')
    api, registry, before, identities = context(environment, api_factory)
    task = rendezvous._request(request, before, clock())
    require(task['run_id'] == int(environment['GITHUB_RUN_ID']) and task['attempt'] == int(environment['GITHUB_RUN_ATTEMPT']),
            'task controls belong to another execution')
    name = 'task controls (' + task['task_id'] + ')'
    job = admit_job(api, before['deployment'], environment, name, clock())
    def guard():
        require(registry.binding() == before and clock() < min(task['deadline'], before['deployment']['expires']),
                'task controls configuration changed or expired')
    location = rendezvous.wait_ready(api, before, request, clock, guard)
    guard()
    # This candidate-free job alone borrows source administration-write visibility.
    # No key/token is passed to the task job or to the artifact uploader.
    root = (app_factory or bootstrap.app_api)(before['deployment']['apps']['admin'], environment.get('AGENTIC_ADMIN_PRIVATE_KEY'))
    with _source_token('admin', root, api, before['deployment'], identities, before['branch_head'],
                       clock, token_factory, guard) as source:
        class Observation:
            def get(self, path):
                guard()
                if path == '/repos/' + before['deployment']['policy']['authority_repository']: return api.get(path)
                return source.get(path)
            def pages(self, path):
                guard()
                return source.pages(path)
        admit_job(api, before['deployment'], environment, name, clock())
        document = rendezvous.collect(Observation(), api, registry.binding, request, location, job['id'], clock)
    guard()
    rendezvous.validate_response(document, request,
        rendezvous.read_ready(api, before, request, location, clock()), location, before, clock())
    artifact = uploader_factory(node, environment)('task-controls-' + task['task_id'] + '-' + str(task['attempt']),
        json.dumps(document, sort_keys=True, allow_nan=False).encode())
    require(positive(artifact), 'task controls upload acknowledgement unavailable')
    return dict(run_id=task['run_id'], attempt=task['attempt'], job_id=job['id'], artifact_id=artifact)


def _prepare_task_images(deployment, guard, runner=subprocess.run):
    from codex_harness import profile
    from coding_transport import ENGINE_ENVIRONMENT
    resources = profile(deployment)
    runtime = resources.get('container_runtime', 'docker')
    require(runtime in ('docker', 'podman'), 'approved task image engine required')
    # Only authenticated registry pins are pulled, before candidate execution or
    # source credential construction. The engine never inherits authority keys.
    for image in dict.fromkeys((deployment['policy']['image'], resources['coding_image'])):
        guard()
        result = runner([runtime, 'pull', '--', image], env=ENGINE_ENVIRONMENT,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=120, check=False)
        require(result.returncode == 0, 'approved task image unavailable')
        guard()


def _task(environment, request, node, clock=None, api_factory=GitHub, app_factory=None, token_factory=GitHub,
          uploader_factory=NodeUploader, parent_factory=None, image_loader=None):
    import bootstrap
    from coding_parent import Parent, TASK_REQUEST_FIELDS
    import model_vault
    from provenance import admit_job
    clock = clock or (lambda:int(time.time()))
    object_fields(request, TASK_REQUEST_FIELDS, 'task service request')
    model_task = request['task']
    object_fields(model_task, model_vault.TASK_FIELDS, 'task model request')
    require(type(request['schema_version']) is int and request['schema_version'] == 2 and
            sha(request['source_base']) and isinstance(request['prompt'], str) and
            0 < len(request['prompt'].encode('utf-8')) <= 65536 and
            isinstance(model_task['task_id'], str) and re.fullmatch('[0-9a-f]{32}', model_task['task_id']),
            'bounded exact task request required')
    names = {'AGENTIC_CODING_PRIVATE_KEY', 'AGENTIC_MODEL_DELIVERY_KEY'}
    forbidden = set(setup.CREDENTIAL_NAMES) - names | {'GH_TOKEN', 'OPENAI_API_KEY', 'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN', 'AZURE_CLIENT_SECRET', 'ARM_CLIENT_SECRET'}
    require(not any(environment.get(key) for key in forbidden), 'task inherited another purpose credential')
    api, registry, before, identities = context(environment, api_factory)
    require(request['configuration_revision'] == before['configuration_revision'] and
            request['deployment_digest'] == before['deployment_digest'], 'prepared task service configuration changed')
    d = before['deployment']
    require(before['fence']['pending'] is None, 'task service requires a settled configuration fence')
    admit_job(api, d, environment, 'task (' + model_task['task_id'] + ')', clock())
    require(model_task['purpose'] == 'task' and model_task['run_id'] == int(environment['GITHUB_RUN_ID']) and
            model_task['attempt'] == int(environment['GITHUB_RUN_ATTEMPT']), 'task delivery belongs to another execution')
    path = '/repos/' + d['policy']['authority_repository'] + '/actions/runs/' + str(model_task['run_id'])
    jobs = api.pages(path + '/attempts/' + str(model_task['attempt']) + '/jobs', 'jobs')
    artifacts = api.pages(path + '/artifacts', 'artifacts')
    require(isinstance(jobs, list) and isinstance(artifacts, list) and len(jobs) <= 10000 and len(artifacts) <= 10000,
            'bounded model producer inventory required')
    matching_jobs = [j for j in jobs if j.get('name') == 'model authorization']
    matching_artifacts = [a for a in artifacts if a.get('name') ==
        'model-lease-' + model_task['task_id'] + '-' + str(model_task['attempt'])]
    require(len(matching_jobs) == len(matching_artifacts) == 1, 'missing or ambiguous task model delivery')
    location = dict(run_id=model_task['run_id'], attempt=model_task['attempt'],
                    job_id=matching_jobs[0]['id'], artifact_id=matching_artifacts[0]['id'])
    # Authenticate the exact closed producer before decrypting or loading an App
    # key. Never accept a plaintext lease selected by a dispatch input.
    lease = model_vault.read_delivery(api, before, model_task, location,
                                     environment.get('AGENTIC_MODEL_DELIVERY_KEY'), clock())
    def guard():
        require(registry.binding() == before and clock() < min(model_task['deadline'], lease['expires'], d['expires']),
                'task service configuration or lease ended')
    guard()
    (image_loader or _prepare_task_images)(d, guard)
    guard()
    root = (app_factory or bootstrap.app_api)(d['apps']['coding'], environment.get('AGENTIC_CODING_PRIVATE_KEY'))
    with _coding_source(root, api, d, identities, before['branch_head'], clock, token_factory, guard) as source:
        guard()
        metadata = {key:environment[key] for key in ('GITHUB_REPOSITORY_ID', 'GITHUB_SHA', 'GITHUB_RUN_ID',
                                                    'GITHUB_RUN_ATTEMPT', 'GITHUB_JOB')}
        parent = (parent_factory or Parent)(registry, api, source, metadata, identities, clock=clock)
        result = parent._run(request, lease, uploader_factory(node, environment))
    guard()
    return result


PRODUCER_ROLES = ('discover', 'prepare', 'verify', 'publication-controls', 'publish',
                  'proof', 'broker', 'controls', 'final-proof', 'finalize')
TRIAL_ROLES = ('trial-handoff', 'trial-prepare', 'trial-model', 'trial-proof', 'trial-worker', 'trial-controls')


def _trial_evidence(api, context):
    """Locate exact closed producers; their domain validators authenticate contents."""
    import provenance
    task, d = context.task, context.record['trial']['deployment']
    root = '/repos/' + d['policy']['authority_repository'] + '/actions/runs/' + str(task['run_id'])
    jobs = api.pages(root + '/attempts/' + str(task['attempt']) + '/jobs', 'jobs')
    artifacts = api.pages(root + '/artifacts', 'artifacts')
    require(isinstance(jobs, list) and isinstance(artifacts, list) and len(jobs) <= 10000 and len(artifacts) <= 10000,
            'bounded exact trial producer inventory required')
    def locator(role, key, job_name):
        producer = provenance.execution_job(api, d, task['run_id'], task['attempt'], job_name, completed=True)
        matches = [a for a in artifacts if a.get('name') == role + '-' + key + '-' + str(task['attempt'])]
        require(len(matches) == 1 and positive(matches[0].get('id')), 'missing or ambiguous closed trial producer')
        return dict(run_id=task['run_id'], attempt=task['attempt'], job_id=producer['id'], artifact_id=matches[0]['id'])
    return locator('model-lease', task['task_id'], 'model authorization'), {
        p:locator('proof', p, 'proof (' + p + ')') for p in setup.PURPOSES}


def _trial(environment, request, node, role, clock=None, api_factory=GitHub, app_factory=None,
           token_factory=GitHub, uploader_factory=NodeUploader, root=None, store_factory=None,
           image_loader=None, execution=None, sleep=time.sleep):
    """Fixed native qualification graph; never production task or review admission."""
    authority_release.authorize('protected-run')
    import bootstrap
    import private_setup
    import provenance
    import trial_handoff
    from trial_admission import Admission
    from trial_controls import Controls
    from trial_worker import Worker
    clock = clock or (lambda:int(time.time()))
    require(role in TRIAL_ROLES, 'fixed trial role required')
    trial_purpose = next((p for p in setup.PURPOSES if environment.get('GITHUB_JOB') == 'trial_' + p + '_proof'), None)
    allowed = ({'AGENTIC_MODEL_VAULT_KEY', 'AGENTIC_MODEL_DELIVERY_KEY'} if role == 'trial-model' else
        {'AGENTIC_CODING_PRIVATE_KEY', 'AGENTIC_MODEL_DELIVERY_KEY'} if role == 'trial-worker' else
        {'AGENTIC_ADMIN_PRIVATE_KEY'} if role == 'trial-controls' else
        {'AGENTIC_' + trial_purpose.upper() + '_PRIVATE_KEY'} if role == 'trial-proof' and trial_purpose else set())
    forbidden = set(setup.CREDENTIAL_NAMES) - allowed | {'GH_TOKEN', 'OPENAI_API_KEY', 'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN', 'AZURE_CLIENT_SECRET', 'ARM_CLIENT_SECRET'}
    require(not any(environment.get(k) for k in forbidden), 'trial producer inherited another purpose credential')
    token = environment.get(setup.TrialReadStaging.NAME)
    require(isinstance(token, str) and 0 < len(token) <= 16384, 'native staged origin-read capability required')
    origin_reader = api_factory(token)
    api, registry, before, identities = context(environment, api_factory)
    if role == 'trial-handoff':
        document = trial_handoff.consume(registry, api, environment, request, origin_reader, clock)
        artifact = uploader_factory(node, environment)('trial-handoff-' + document['task_id'] + '-' + str(document['attempt']),
            json.dumps(document, sort_keys=True, allow_nan=False).encode())
        require(positive(artifact), 'trial handshake upload acknowledgement unknown; never replay')
        return dict(run_id=document['run_id'], attempt=document['attempt'], job_id=document['job_id'], artifact_id=artifact)
    if role == 'trial-prepare':
        object_fields(request, ('handoff', 'prompt'), 'native trial preparation hints')
        hint = request['handoff']
        object_fields(hint, ('origin', 'revision'), 'native handoff lookup')
        original = Registry(origin_reader, hint['origin'])
        initial, origin = trial_handoff.read(original, hint['revision'], clock())
        require(initial['execution'] is None and before == initial['trial'] and
                digest(request['prompt']) == initial['prompt_digest'], 'native trial preparation intent differs')
        provenance.admit_job(api, before['deployment'], environment, 'trial preparation', clock())
        deadline = time.monotonic() + min(300, initial['expires'] - clock())
        while True:
            original.unchanged(origin)
            registry.unchanged(before)
            require(time.monotonic() < deadline and clock() < initial['expires'], 'native run binding remains pending')
            try:
                original.ref('agentic-trial-' + initial['task_id'] + '-execution')
                break
            except HostRefusal as error:
                require(error.status == 404, 'native run binding observation unavailable')
            sleep(0.25)
        admitted = trial_handoff.Hosted(registry, origin_reader, api, environment, hint, request['prompt'], clock)
        return dict(schema_version=2, handoff=hint, task=admitted.task, prompt=request['prompt'],
            source_base=admitted.record['pair']['fixture_revision'], configuration_revision=before['configuration_revision'],
            deployment_digest=before['deployment_digest'])
    object_fields(request, ('schema_version', 'handoff', 'task', 'prompt', 'source_base', 'configuration_revision',
                            'deployment_digest'), 'native prepared trial request')
    admitted = trial_handoff.Hosted(registry, origin_reader, api, environment, request['handoff'], request['prompt'], clock)
    expected = dict(schema_version=2, handoff=request['handoff'], task=admitted.task, prompt=request['prompt'],
        source_base=admitted.record['pair']['fixture_revision'], configuration_revision=before['configuration_revision'],
        deployment_digest=before['deployment_digest'])
    require(request == expected, 'prepared trial request differs from authenticated native binding')
    if role == 'trial-model':
        require(environment.get('GITHUB_JOB') == 'trial_model_auth', 'separate trial model authorization required')
        admitted.guard()
        from trial_configuration import _Boundary
        from oauth_transport import OpenAI
        guarded = _Boundary(api, admitted.guard, admitted.local_guard)
        def uploader(node, environment):
            target = uploader_factory(node, environment)
            def send(*args):
                admitted.guard()
                value = target(*args)
                admitted.guard()
                return value
            return send
        result = _model_authorization(environment, admitted.task, node, clock, lambda token:guarded, uploader,
            provider=_Boundary(OpenAI(), admitted.guard, admitted.local_guard), expected_binding=before)
        admitted.guard()
        return result
    if role == 'trial-proof':
        require(trial_purpose is not None, 'fixed trial own-App proof purpose required')
        app = (app_factory or bootstrap.app_api)(before['deployment']['apps'][trial_purpose],
            environment.get('AGENTIC_' + trial_purpose.upper() + '_PRIVATE_KEY'))
        class GuardedApp:
            def get(self, path):
                admitted.local_guard()
                return app.get(path)
            def post(self, path, body):
                admitted.guard()
                value = app.post(path, body)
                try: admitted.guard()
                except BaseException:
                    app_proofs.revoke(value, token_factory)
                    raise
                return value
        admitted.guard()
        document = app_proofs.prove(GuardedApp(), api, before['deployment'], identities, trial_purpose, before['branch_head'], clock(), token_factory)
        admitted.guard()
        artifact = uploader_factory(node, environment)('proof-' + trial_purpose + '-' + str(admitted.task['attempt']),
            json.dumps(document, sort_keys=True, allow_nan=False).encode())
        admitted.guard()
        require(positive(artifact), 'trial own-App proof upload acknowledgement unknown; never replay')
        return dict(run_id=admitted.task['run_id'], attempt=admitted.task['attempt'], job_id=admitted.job['id'], artifact_id=artifact)
    model, proofs = _trial_evidence(api, admitted)
    purpose = 'coding' if role == 'trial-worker' else 'admin'
    require((role, environment.get('GITHUB_JOB')) in (('trial-worker', 'qualification'),
            ('trial-controls', 'trial_task_controls')), 'fixed trial worker or independent controls required')
    if role == 'trial-worker':
        # Authenticate/decrypt before coding-root construction; model refresh keys
        # belong only to the separate auth job. The container gets only the relay.
        import model_vault
        model_vault.read_delivery(api, before, admitted.task, model, environment.get('AGENTIC_MODEL_DELIVERY_KEY'), clock())
    root = Path(root) if root is not None else Path.home() / ('.agentic-trial-' + str(before['deployment']['policy']['authority_repository_id']) +
        '-' + str(admitted.task['run_id']) + '-' + str(admitted.task['attempt']) + '-' + str(admitted.job['id']))
    store_factory = store_factory or private_setup.Store
    store_factory(root)  # Establish the private parent before purpose children.
    upload = uploader_factory(node, environment)
    controls = None
    if role == 'trial-controls':
        controls = Controls.hosted(registry, origin_reader, api, root, clock, environment, request['handoff'], request['prompt'],
                                  model, proofs, store_factory)
        import task_control_protocol
        task_control_protocol.wait_ready(controls, api, before, controls.request, clock, admitted.guard)
    app = (app_factory or bootstrap.app_api)(before['deployment']['apps'][purpose],
        environment.get('AGENTIC_' + purpose.upper() + '_PRIVATE_KEY'))
    with _source_token(purpose, app, api, before['deployment'], identities, before['branch_head'], clock,
                       token_factory, admitted.guard) as source:
        class Readback:
            def get(self, path):
                admitted.local_guard()
                if path == '/repos/' + before['deployment']['policy']['authority_repository']: return api.get(path)
                return source.get(path)
            def pages(self, path, *args):
                admitted.local_guard()
                return source.pages(path, *args)
            def fetch(self, path, **kwargs):
                admitted.local_guard()
                return source.fetch(path, **kwargs)
        if controls is not None:
            return controls.collect(Readback(), environment, upload)
        admission = Admission.hosted(registry, origin_reader, api, Readback(), root, clock, environment, request['handoff'],
            request['prompt'], model, proofs, environment.get('AGENTIC_MODEL_DELIVERY_KEY'), store_factory)
        (image_loader or _prepare_task_images)(before['deployment'], admission._guard)
        admission._guard()
        return Worker(admission, source)._run(request['prompt'], environment.get('AGENTIC_MODEL_DELIVERY_KEY'),
            upload, None, **(execution or {}))
PRODUCER_FIELDS = ('schema_version configuration_revision deployment_digest operation_id sequence snapshot task qualification').split()


def _guard_binding(registry, before, clock):
    current = registry.binding()
    require(all(current[k] == before[k] for k in ('deployment', 'configuration_revision', 'deployment_digest', 'fence')),
            'producer configuration or operation changed')
    op = before['fence']['pending']
    require(clock() < min(before['deployment']['expires'], op['execution_deadline'] if op else before['deployment']['expires']),
            'producer configuration or operation expired')


def _producer_request(request, binding, environment, clock):
    return _bound_producer_request(request, binding, environment, clock)


def _bound_producer_request(request, binding, environment, clock, admission=None):
    import broker_proofs
    object_fields(request, PRODUCER_FIELDS, 'prepared producer request')
    require(type(request['schema_version']) is int and request['schema_version'] == 2 and
            request['configuration_revision'] == binding['configuration_revision'] and
            request['deployment_digest'] == binding['deployment_digest'] and
            type(request['sequence']) is int and request['sequence'] == binding['fence']['sequence'],
            'prepared producer configuration differs')
    op = broker_proofs._operation(binding, request['snapshot'], admission)
    if admission is not None: require(request == admission.request, 'exact retained trial producer request required')
    require(request['operation_id'] == op['operation_id'] and str(op['run_id']) == environment.get('GITHUB_RUN_ID') and
            str(op['attempt']) == environment.get('GITHUB_RUN_ATTEMPT') and clock() < min(op['execution_deadline'], binding['deployment']['expires']),
            'prepared producer execution differs')
    object_fields(request['task'], ('task_id', 'locator'), 'prepared task locator')
    return op


def _producer_environment(environment, purpose, broker=False):
    names = {'AGENTIC_' + purpose.upper() + '_PRIVATE_KEY'}
    if broker: names.add('AGENTIC_READER_PRIVATE_KEY')
    forbidden = set(setup.CREDENTIAL_NAMES) - names | {'GH_TOKEN', 'OPENAI_API_KEY', 'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN', 'AZURE_CLIENT_SECRET', 'ARM_CLIENT_SECRET'}
    require(not any(environment.get(k) for k in forbidden), 'producer inherited another purpose credential')


@contextmanager
def _admin_authority(root, authority, registry, binding, identities, token_factory):
    """Only source-free administrative jobs borrow authority CAS rights."""
    record = identities['apps']['admin']
    result = root.post('/app/installations/' + str(record['installation_id']) + '/access_tokens',
        dict(repository_ids=[binding['deployment']['policy']['authority_repository_id']],
             permissions={'contents':'write', 'actions':'read'}))
    try:
        expected = binding['deployment']['policy']['authority_repository_id']
        require(result.get('token') and app_proofs.normalized(result.get('permissions')) == {'contents':'write','actions':'read'} and
                [r['id'] for r in result.get('repositories', [])] == [expected], 'administrative authority token scope differs')
        scoped = token_factory(result['token'])
        require([r['id'] for r in scoped.pages('/installation/repositories', 'repositories')] == [expected],
                'administrative authority token reaches another repository')
        yield Registry(scoped, registry.coordinates)
    finally:
        app_proofs.revoke(result, token_factory)


def _locator(authority, d, run_id, attempt, role, key):
    from provenance import execution_job
    prefix = role if key is None else role + '-' + str(key)
    name = ('verify' if role == 'evidence' else 'publication controls' if role == 'publication-controls' else
            'hosted qualification' if role == 'qualification' else role)
    if key is not None: name += ' (' + str(key) + ')'
    job = execution_job(authority, d, run_id, attempt, name, completed=True)
    items = authority.pages('/repos/' + d['policy']['authority_repository'] + '/actions/runs/' + str(run_id) + '/artifacts', 'artifacts')
    matches = [a for a in items if a['name'] == prefix + '-' + str(attempt)]
    require(len(matches) == 1 and positive(matches[0]['id']), 'missing or ambiguous producer artifact')
    return dict(run_id=run_id, attempt=attempt, job_id=job['id'], artifact_id=matches[0]['id'])


def _retained(authority, source, binding, identities, snapshot, clock):
    """Inventory supplies hints only; closed producer/domain validators decide."""
    from provenance import authenticated_document
    import task_admission
    import qualification_record
    d = binding['deployment']
    pr = source.get('/repos/' + d['policy']['repository'] + '/pulls/' + str(snapshot['pr']))
    match = re.fullmatch(r'agentic/task-([0-9a-f]{32})', pr['head']['ref'])
    require(match is not None, 'candidate is not a protected task branch')
    task_id = match.group(1)
    inventory = authority.pages('/repos/' + d['policy']['authority_repository'] + '/actions/artifacts', 'artifacts')
    require(isinstance(inventory, list) and len(inventory) <= 10000, 'bounded retained producer inventory required')
    found = {'task':[], 'qualification':[]}
    for artifact in inventory:
        name = artifact.get('name', '')
        role = 'task' if re.fullmatch('task-' + task_id + r'-[1-9][0-9]{0,19}', name) else (
            'qualification' if re.fullmatch(r'qualification-[1-9][0-9]{0,19}', name) else None)
        if role is None or artifact.get('expired') is not False: continue
        execution = artifact.get('workflow_run', {})
        if any(execution.get(k) != expected for k, expected in (
            ('head_sha',d['policy']['workflow_sha']),('repository_id',d['policy']['authority_repository_id']),
            ('head_repository_id',d['policy']['authority_repository_id']))): continue
        run_id, attempt = artifact['workflow_run']['id'], int(name.rsplit('-',1)[1])
        location = _locator(authority, d, run_id, attempt, role, task_id if role == 'task' else None)
        proof = authenticated_document(authority, d, location, role, task_id if role == 'task' else None, clock())
        value = proof['document']
        if role == 'qualification':
            if digest(value) != d['qualification']: continue
            qualification_record.validate(value, binding, identities, proof, value.get('controls_digest'), clock())
        else:
            if value.get('submitted',{}).get('head') != snapshot['head']: continue
            task_admission.read(source, authority, binding, identities, snapshot, location, task_id, clock())
        found[role].append(location)
    require(all(len(v) == 1 for v in found.values()), 'exact retained task and qualification required')
    return dict(task_id=task_id, locator=found['task'][0]), found['qualification'][0]


def _publication_observation(binding, snapshot, started, completed, facts):
    return _bound_publication_observation(binding, snapshot, started, completed, facts)


def _bound_publication_observation(binding, snapshot, started, completed, facts, admission=None):
    import broker_proofs
    import control_rendezvous
    op = broker_proofs._operation(binding, snapshot, admission)
    control_rendezvous.validate_facts(facts, binding)
    require(positive(started) and positive(completed) and op['created'] <= started <= completed <= started + 30,
            'fresh publication observation required')
    return dict(schema_version=2, kind='publication-observation', operation_id=op['operation_id'],
        sequence=binding['fence']['sequence'], configuration_revision=binding['configuration_revision'],
        deployment_digest=binding['deployment_digest'], snapshot=snapshot,
        readback_started=started, readback_completed=completed, result=facts)


def _validate_publication_observation(value, binding, snapshot, proof, now):
    return _bound_validate_publication_observation(value, binding, snapshot, proof, now)


def _bound_validate_publication_observation(value, binding, snapshot, proof, now, admission=None):
    object_fields(value, ('schema_version kind operation_id sequence configuration_revision deployment_digest snapshot '
                          'readback_started readback_completed result').split(), 'closed publication observation')
    expected = _bound_publication_observation(binding, snapshot, value['readback_started'], value['readback_completed'], value['result'], admission)
    require(value == expected and type(value['schema_version']) is int and type(value['sequence']) is int and
            proof['role'] == 'publication-controls' and proof['key'] == snapshot['pr'] and
            proof['run_id'] == snapshot['run_id'] and proof['attempt'] == snapshot['run_attempt'] and
            proof['job_started'] <= value['readback_started'] <= value['readback_completed'] <=
            proof['artifact_created'] <= proof['job_completed'] <= now and now - value['readback_started'] <= 300,
            'publication observation is stale or from another closed producer')
    return value['result']


def _discover(environment, request, node=None, clock=None, api_factory=GitHub, app_factory=None, token_factory=GitHub):
    import bootstrap
    from provenance import admit_job
    object_fields(request, (), 'discovery request')
    _producer_environment(environment, 'reader')
    clock = clock or (lambda:int(time.time()))
    api, registry, before, identities = context(environment, api_factory)
    d, p = before['deployment'], before['deployment']['policy']
    require(d['state'] == 'active' and before['fence']['pending'] is None, 'discovery requires active settled authority')
    admit_job(api, d, environment, 'discover', clock())
    guard = lambda:_guard_binding(registry, before, clock)
    root = (app_factory or bootstrap.app_api)(d['apps']['reader'], environment.get('AGENTIC_READER_PRIVATE_KEY'))
    with _source_token('reader', root, api, d, identities, before['configuration_revision'], clock, token_factory, guard) as source:
        prs = source.pages('/repos/' + p['repository'] + '/pulls?state=open&base=' + quote(p['target'],safe=''))
        require(isinstance(prs, list) and len(prs) <= 1000, 'bounded candidate inventory required')
        eligible = [v['number'] for v in prs if v.get('draft') is False and v['base']['ref'] == p['target'] and
            v['head']['repo']['id'] == p['repository_id'] and v['user']['id'] == identities['apps']['coding']['actor_id'] and
            re.fullmatch(r'agentic/task-[0-9a-f]{32}', v['head']['ref']) and positive(v['number'])]
    guard()
    return dict(pr=min(eligible) if eligible else None)


def _prepare(environment, request, node=None, clock=None, api_factory=GitHub, app_factory=None, token_factory=GitHub):
    import bootstrap
    from authority_github import Readers, current_snapshot
    from provenance import admit_job
    from trusted_ci_github import independent_approval
    object_fields(request, ('pr',), 'discovered candidate')
    require(positive(request['pr']), 'one discovered candidate required')
    _producer_environment(environment, 'admin')
    clock = clock or (lambda:int(time.time()))
    api, registry, before, identities = context(environment, api_factory)
    d, p = before['deployment'], before['deployment']['policy']
    require(d['state'] == 'active' and before['fence']['pending'] is None, 'preparation requires active settled authority')
    job = admit_job(api, d, environment, 'prepare', clock())
    guard = lambda:_guard_binding(registry, before, clock)
    root = (app_factory or bootstrap.app_api)(d['apps']['admin'], environment.get('AGENTIC_ADMIN_PRIVATE_KEY'))
    return _prepare_candidate(api, registry, before, identities, request, environment, job, root, clock, token_factory, guard)


def _prepare_trial(admission, environment, root, token_factory=GitHub):
    from trial_controller import authenticated
    from provenance import admit_job
    authenticated(admission)
    admission.guard()
    require(admission.value['phase'] == 'ready', 'trial fence already attempted; never replay preparation')
    before, registry = admission.binding, admission.registry
    api, d = registry.api, before['deployment']
    job = admit_job(api,d,environment,'prepare',admission.clock())
    return _prepare_candidate(api,registry,before,admission.record['pair']['identities'],
        dict(pr=admission.candidate['submitted']['pr']),environment,job,root,admission.clock,token_factory,admission.guard,admission)


def _prepare_candidate(api, registry, before, identities, request, environment, job, root, clock, token_factory, guard, admission=None):
    from authority_github import Readers, current_snapshot
    from trusted_ci_github import independent_approval
    d, p = before['deployment'], before['deployment']['policy']
    with _source_token('admin', root, api, d, identities, before['configuration_revision'], clock, token_factory, guard) as source:
        readers = Readers(source, api, d)
        s = current_snapshot(readers, d, request['pr'], job['run_id'], int(environment['GITHUB_RUN_ATTEMPT']))
        def reviewed():
            guard()
            pr = source.get('/repos/' + p['repository'] + '/pulls/' + str(s['pr']))
            require(pr['head']['sha'] == s['head'] and pr['base']['sha'] == s['base'], 'reviewed candidate moved')
            independent_approval(source, p, pr, human=True)
            require(current_snapshot(readers, d, s['pr'], s['run_id'], s['run_attempt']) == s,
                    'candidate moved during human review readback')
            guard()
        # Setup consent and cached check success cannot substitute for review.
        # Observe only; the coordinator never submits or requests a human review.
        reviewed()
        if admission is None:
            task, qualification = _retained(api, source, before, identities, s, clock)
        else:
            task = dict(task_id=admission.candidate['submitted']['task_id'],locator=admission.value['worker']['locator'])
            admission.task(before,s,task['locator'],task['task_id'])
            qualification = None
        guard()
        require(current_snapshot(readers, d, s['pr'], s['run_id'], s['run_attempt']) == s, 'candidate moved before fencing')
        now = clock()
        require(d['expires'] - now >= p['limits']['seconds'] + 300, 'insufficient configuration lifetime for verification')
        op = dict(kind='merge', operation_id=secrets.token_hex(16), scope_digest=None,
            repository_id=p['repository_id'], target=p['target'], configuration_revision=before['configuration_revision'],
            deployment_digest=before['deployment_digest'], workflow_sha=p['workflow_sha'], run_id=s['run_id'], attempt=s['run_attempt'],
            created=now, execution_deadline=min(now+3600,d['expires']), **{k:s[k] for k in ('pr','head','base','merge')})
        with _admin_authority(root, api, registry, before, identities, token_factory) as writer:
            reviewed()
            if admission is None:
                after = writer.acquire_operation(before['branch_head'], before['configuration_revision'], op)
            else:
                from controls import observe
                facts = observe(source,d)
                reviewed()
                after = admission.acquire(writer,before,op,s,task,facts)
    require(after['fence']['pending'] == op, 'prepared fence readback differs')
    if admission is not None: return copy.deepcopy(admission.request)
    return dict(schema_version=2, configuration_revision=after['configuration_revision'], deployment_digest=after['deployment_digest'],
        operation_id=op['operation_id'], sequence=after['fence']['sequence'], snapshot=s, task=task, qualification=qualification)


def _upload_document(uploader, name, document):
    artifact = uploader(name, json.dumps(document, sort_keys=True, allow_nan=False).encode())
    require(positive(artifact), 'producer upload acknowledgement unavailable')
    return artifact


def _verify_actions(source, d, snapshot, job_id, guard, clock, disk_factory=None, box_factory=None,
                    controller=None, image_loader=None):
    from cloud_worker import unpack
    from disk import WorkDisk
    from trusted_ci_sandbox import Sandbox
    from trusted_ci_controller import verify
    from coding_transport import ENGINE_ENVIRONMENT
    require(d['adapter'] == 'github-actions', 'cloud producer promotion remains held')
    guard()
    if image_loader is None:
        result = subprocess.run(['docker','pull','--',d['policy']['image']], env=ENGINE_ENVIRONMENT,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120, check=False)
        require(result.returncode == 0, 'approved verification image unavailable')
    else: image_loader(d, guard)
    guard()
    raw = source.fetch('/repos/' + d['policy']['repository'] + '/tarball/' + snapshot['merge'], binary=True, limit=64*1024*1024)
    with tempfile.TemporaryDirectory(prefix='agentic-verify-') as folder:
        candidate = unpack(raw, Path(folder)/'candidate')
        candidate.chmod(0o755)
        for path in candidate.rglob('*'):
            if path.is_dir(): path.chmod(0o755)
        guard()
        with (disk_factory or WorkDisk)('agentic-'+secrets.token_hex(12), d['policy']['limits']['disk_mb'], formatter_image=d['policy']['image']) as disk:
            with (box_factory or Sandbox)(candidate, d['policy'], runtime='docker', work_volume=disk.name) as box:
                report = (controller or verify)(box, d['policy'], snapshot, capture_failure=True)
    guard()
    return dict(schema_version=2, report=dict(schema_version=2, deployment_digest=digest(d), generation=d['generation'],
        snapshot=snapshot, adapter=d['adapter'], execution=dict(run_id=snapshot['run_id'], attempt=snapshot['run_attempt'],
        job_id=job_id, account=d['account'], resource=d['resources'].get('actions_resource')), outcomes=report['outcomes']),
        cleanup_complete=True, enforcement_active=False)


def _producer(environment, request, node, role, clock=None, api_factory=GitHub, app_factory=None,
              token_factory=GitHub, uploader_factory=NodeUploader, verifier=None, sleeper=time.sleep):
    return _produce(environment,request,node,role,clock,api_factory,app_factory,token_factory,uploader_factory,verifier,sleeper)


def _trial_producer(admission, environment, request, node, role, clock=None, api_factory=GitHub, app_factory=None,
                    token_factory=GitHub, uploader_factory=NodeUploader, verifier=None, sleeper=time.sleep):
    from trial_controller import authenticated
    authenticated(admission)
    admission.guard()
    require(role in ('verify','proof','publication-controls','publish','broker','controls','final-proof'), 'fixed trial controller role required')
    return _produce(environment,request,node,role,admission.clock,api_factory,app_factory,token_factory,uploader_factory,verifier,sleeper,admission)


def case_producer(environment, hint, node, role):
    authority_release.authorize('qualify-live')
    return _case_producer(environment,hint,node,role)


def _case_producer(environment, hint, node, role, clock=None, api_factory=GitHub, app_factory=None,
                   token_factory=GitHub, uploader_factory=NodeUploader, verifier=None, sleeper=time.sleep):
    """Reconstruct each job from authenticated data; never accept native objects."""
    import bootstrap
    import trial_case
    clock = clock or (lambda:int(time.time()))
    object_fields(hint, ('origin','revision'), 'case lookup hint')
    require(role in ('handoff','finalize','verify','proof','publication-controls','publish','broker','controls','final-proof'),
            'fixed case producer required')
    require(not environment.get('AGENTIC_TRIAL_ORIGIN_TOKEN'), 'original worker capability is not a case delegation')
    purpose = 'admin' if role == 'finalize' else _producer_purpose(environment,role)
    require(purpose in ('admin','reader','issuer','coding','merge'), 'fixed case credential purpose required')
    if role == 'handoff':
        _producer_environment(environment,purpose)
        require(not any(environment.get(k) for k in setup.CREDENTIAL_NAMES), 'case consumer inherited another purpose credential')
    else:
        _producer_environment(environment,purpose,broker=role == 'broker')
    token = environment.get(trial_case.CaseReadStaging.NAME)
    require(isinstance(token,str) and 0 < len(token) <= 16384, 'fresh staged case read capability required')
    origin_reader = api_factory(token)
    api, registry, before, identities = context(environment,api_factory)
    if role == 'finalize':
        from broker_finalize import Finalizer
        Finalizer(None,api,None,loads(environment.get('AGENTIC_RECOVERY_PIN','')),environment,clock)._admit()
    if role == 'handoff':
        value = trial_case.consume(registry,origin_reader,environment,hint,clock)
        artifact = _upload_document(uploader_factory(node,environment),'trial-case-handoff-'+value['task_id']+'-1',value)
        return dict(run_id=value['run_id'],attempt=1,job_id=value['job_id'],artifact_id=artifact)
    # Authenticate scope, CLOSED consumption, exact pending fence and pinned job
    # before constructing a role root or minting its source credentials.
    admitted = trial_case.Hosted(registry,origin_reader,None,environment,hint,role,clock)
    read_purpose = 'reader' if role == 'broker' else purpose
    root = (app_factory or bootstrap.app_api)(before['deployment']['apps'][read_purpose],environment.get('AGENTIC_'+read_purpose.upper()+'_PRIVATE_KEY'))
    with _source_token(read_purpose,root,api,before['deployment'],identities,before['configuration_revision'],clock,token_factory,admitted.guard) as source:
        admitted.bind_source(source)
        if role == 'finalize':
            from broker_finalize import Finalizer
            pin = loads(environment.get('AGENTIC_RECOVERY_PIN',''))
            # Administrative write authority is borrowed only by this separately
            # pinned terminal role, using the existing finalizer and fence engine.
            with _admin_authority(root,api,registry,before,identities,token_factory) as writer:
                admitted.guard()
                return Finalizer(writer,api,source,pin,environment,clock)._finalize(
                    admitted.request['operation_id'],admitted.request['sequence'],
                    _case_broker_job(api,admitted),_admission=admitted)
        return _trial_producer(admitted,environment,admitted.request,node,role,clock,api_factory,app_factory,
                               token_factory,uploader_factory,verifier,sleeper)


def _case_broker_job(api, admission):
    s = admission.request['snapshot']
    p = admission.binding['deployment']['policy']
    jobs = api.pages('/repos/'+p['authority_repository']+'/actions/runs/'+str(s['run_id'])+
                     '/attempts/'+str(s['run_attempt'])+'/jobs','jobs')
    require(isinstance(jobs,list) and len(jobs) <= 10000, 'bounded terminal job inventory required')
    matches = [j for j in jobs if j.get('name') == 'broker ('+str(s['pr'])+')']
    require(len(matches) == 1 and positive(matches[0].get('id')), 'exact terminal broker hint required')
    # A denial normally fails its job. Finalizer's existing terminal_job reader
    # authenticates the hint and admissible terminal conclusion, not success-only.
    return matches[0]['id']


def _producer_purpose(environment, role):
    return ('admin' if role in ('publication-controls','controls') else 'issuer' if role == 'publish' else
            'merge' if role == 'broker' else environment.get('GITHUB_JOB','').split('_',1)[0]
            if role in ('proof','final-proof') else 'reader')


def _produce(environment, request, node, role, clock=None, api_factory=GitHub, app_factory=None,
             token_factory=GitHub, uploader_factory=NodeUploader, verifier=None, sleeper=time.sleep, admission=None):
    """Fixed candidate-free service roles; public dispatch remains release-held."""
    import bootstrap
    import broker_proofs
    from authority_github import Readers, current_snapshot
    from provenance import admit_job, authenticated_document, validate_evidence
    purpose = _producer_purpose(environment,role)
    require(purpose in ('admin','reader','issuer','coding','merge'), 'fixed producer purpose required')
    _producer_environment(environment, purpose, broker=role == 'broker')
    clock = clock or (lambda:int(time.time()))
    if admission is None:
        api, registry, before, identities = context(environment, api_factory)
    else:
        api, registry, before, identities = admission.registry.api, admission.registry, admission.binding, admission.record['pair']['identities']
    op = _bound_producer_request(request, before, environment, clock, admission)
    d, s = before['deployment'], request['snapshot']
    name = ('publication controls' if role == 'publication-controls' else 'final proof' if role == 'final-proof' else role)
    name += ' (' + (purpose if role in ('proof','final-proof') else str(op['pr'])) + ')'
    job = admit_job(api, d, environment, name, clock())
    guard = (lambda:_guard_binding(registry, before, clock)) if admission is None else admission.guard
    guard()
    root = (app_factory or bootstrap.app_api)(d['apps'][purpose], environment.get('AGENTIC_'+purpose.upper()+'_PRIVATE_KEY'))
    uploader = uploader_factory(node, environment)
    if role in ('proof','final-proof'):
        if role == 'final-proof':
            broker, ready = _wait_broker_ready(api, registry, before, clock, guard, sleeper, admission)
            value = broker_proofs._refresh(root, api, registry, identities, purpose, environment, broker, ready, clock, token_factory, admission)
        else:
            started = clock()
            result = app_proofs.prove(root, api, d, identities, purpose, before['configuration_revision'], started, token_factory)
            value = dict(schema_version=2, kind='broker-purpose-proof', operation_id=op['operation_id'],
                sequence=before['fence']['sequence'], configuration_revision=before['configuration_revision'],
                deployment_digest=before['deployment_digest'], snapshot=s, issued=started, completed=clock(),
                expires=min(result['expires'], op['execution_deadline']), result=result)
        guard()
        return _upload_document(uploader, role+'-'+purpose+'-'+str(op['attempt']), value)
    # Borrowed source credentials never reach the artifact child or candidate.
    with _source_token(purpose, root, api, d, identities, before['configuration_revision'], clock, token_factory, guard) as source:
        readers = Readers(source, api, d)
        if role != 'broker':
            require(current_snapshot(readers, d, op['pr'], op['run_id'], op['attempt']) == s, 'prepared candidate changed')
        if role == 'verify':
            import task_admission
            if admission is None:
                task_admission.read(source, api, before, identities, s, request['task']['locator'], request['task']['task_id'], clock())
            else:
                admission.task(before,s,request['task']['locator'],request['task']['task_id'])
            result = (verifier or _verify_actions)(source, d, s, job['id'], guard, clock)
            document = dict(schema_version=2, kind='actions', registry_revision=before['configuration_revision'], result=result)
            validate_evidence(document, d, s, before['configuration_revision'], job['id'], clock())
        elif role == 'publication-controls':
            from controls import observe
            started = clock()
            facts = observe(readers, d)
            require(current_snapshot(readers, d, op['pr'], op['run_id'], op['attempt']) == s, 'candidate moved during publication readback')
            document = _bound_publication_observation(before, s, started, clock(), facts, admission)
        elif role == 'controls':
            import control_rendezvous
            broker, ready = _wait_broker_ready(api, registry, before, clock, guard, sleeper, admission)
            document = control_rendezvous._collect(readers, api, registry.binding, broker, ready, clock, admission)
        elif role == 'publish':
            document = _publish_bound(source, api, registry, before, identities, request, clock, guard, admission)
        elif role == 'broker':
            from broker_session import Session
            from merge_window import MergeSource
            # Resolve closed inputs inside Session's positive no-dispatch path.
            locators = lambda:_publication_locators(api, before, request)
            merger = MergeSource(source.token, d['policy']['repository'], d['policy']['repository_id'])
            reader_root = (app_factory or bootstrap.app_api)(d['apps']['reader'], environment.get('AGENTIC_READER_PRIVATE_KEY'))
            with _source_token('reader', reader_root, api, d, identities, before['configuration_revision'], clock,
                               token_factory, guard) as reader:
                return Session(registry, reader, api, identities, job['id'], locators, merger, uploader, clock, sleeper)._run(_admission=admission)
        else: raise Refusal('unsupported producer role')
    guard()
    if role == 'publish': return document
    return _upload_document(uploader, role.replace('verify','evidence')+'-'+str(op['pr'])+'-'+str(op['attempt']), document)


def _publication_locators(api, binding, request):
    d, s = binding['deployment'], request['snapshot']
    return dict(evidence=_locator(api,d,s['run_id'],s['run_attempt'],'evidence',s['pr']),
        proofs={p:_locator(api,d,s['run_id'],s['run_attempt'],'proof',p) for p in ('admin','reader','issuer','coding','merge')},
        task=request['task'], qualification=request['qualification'])


def _publish(source, api, registry, binding, identities, request, clock, guard):
    return _publish_bound(source, api, registry, binding, identities, request, clock, guard)


def _publish_bound(source, api, registry, binding, identities, request, clock, guard, admission=None):
    import broker_proofs
    import checks
    import task_admission
    import qualification_record
    from authority_github import Readers, current_snapshot
    from provenance import authenticated_document, validate_evidence
    d, s = binding['deployment'], request['snapshot']
    locators = _publication_locators(api, binding, request)
    evidence = authenticated_document(api,d,locators['evidence'],'evidence',s['pr'],clock())
    validate_evidence(evidence['document'],d,s,binding['configuration_revision'],evidence['job_id'],clock())
    broker_proofs._read(api,binding,identities,s,locators['proofs'],clock(),admission=admission)
    task = (task_admission.read(source,api,binding,identities,s,locators['task']['locator'],locators['task']['task_id'],clock())
            if admission is None else admission.task(binding,s,locators['task']['locator'],locators['task']['task_id']))
    location = _locator(api,d,s['run_id'],s['run_attempt'],'publication-controls',s['pr'])
    controls = authenticated_document(api,d,location,'publication-controls',s['pr'],clock())
    facts = _bound_validate_publication_observation(controls['document'],binding,s,controls,clock(),admission)
    if admission is None:
        qualification_record.read(api,binding,identities,locators['qualification'],facts['controls_digest'],clock())
    else:
        require(locators['qualification'] == admission.request['qualification'], 'exact trial certificate required')
        admission.qualification(binding,facts['controls_digest'])
    require(current_snapshot(Readers(source,api,d),d,s['pr'],s['run_id'],s['run_attempt']) == s, 'candidate changed before publication')
    coordinates = dict(configuration_revision=binding['configuration_revision'],operation=binding['fence']['pending'],
        sequence=binding['fence']['sequence'], issuer_installation_id=identities['apps']['issuer']['installation_id'],
        evidence_job_id=evidence['job_id'], evidence_digest=digest(evidence['document']), task_digest=task['task_digest'])
    guard()
    _bound_validate_publication_observation(controls['document'],binding,s,controls,clock(),admission)
    body = checks.publication_body(d,s,evidence['document'],coordinates,clock())
    source.post('/repos/'+d['policy']['repository']+'/check-runs',body)
    guard()
    return checks.current(source,d,s,coordinates,clock())


def _wait_broker_ready(api, registry, binding, clock, guard, sleeper, admission=None):
    from merge_receipts import ActionsReceipts
    op, p = binding['fence']['pending'], binding['deployment']['policy']
    deadline = min(clock()+120,op['execution_deadline']-60,binding['deployment']['expires']-60)
    while clock() < deadline:
        guard()
        jobs = api.pages('/repos/'+p['authority_repository']+'/actions/runs/'+str(op['run_id'])+'/attempts/'+str(op['attempt'])+'/jobs','jobs')
        matches = [j for j in jobs if j['name'] == 'broker ('+str(op['pr'])+')']
        require(len(matches) <= 1, 'ambiguous warm broker')
        if matches:
            store = ActionsReceipts._create(api, registry.binding, matches[0]['id'], clock, admission=admission)
            store.current_job()
            artifacts = store._matches('control-ready')
            require(len(artifacts) <= 1, 'ambiguous broker readiness')
            if artifacts:
                location = store._locator('control-ready',artifacts[0])
                store.authenticate(location)
                return matches[0]['id'], location
        sleeper(1)
    raise Refusal('broker readiness unavailable; fence remains pending')


def _finalize(environment, request, node=None, clock=None, api_factory=GitHub, app_factory=None, token_factory=GitHub):
    import bootstrap
    from broker_finalize import Finalizer
    object_fields(request, (), 'terminal recovery request')
    _producer_environment(environment, 'admin')
    clock = clock or (lambda:int(time.time()))
    # This pin is trusted recovery workflow configuration, never dispatch data or
    # inferred from the current default branch/deployment being recovered.
    pin = loads(environment.get('AGENTIC_RECOVERY_PIN', ''))
    api = api_factory(environment.get('GITHUB_TOKEN', ''))
    Finalizer(None, api, None, pin, environment, clock)._admit()
    registry = Registry(api, dict(schema_version=2,repository=pin['authority_repository'],
        repository_id=pin['authority_repository_id'],registry_branch='agentic-registry'))
    before = registry.binding(check_software=False)
    d, op = before['deployment'], before['fence']['pending']
    require(op is not None and op['kind'] == 'merge', 'pending terminal merge operation required')
    identities = app_proofs.load_identities(d)
    root = (app_factory or bootstrap.app_api)(d['apps']['admin'], environment.get('AGENTIC_ADMIN_PRIVATE_KEY'))
    def guard():
        require(registry.binding(check_software=False) == before, 'terminal recovery binding changed')
    jobs = api.pages('/repos/'+d['policy']['authority_repository']+'/actions/runs/'+str(op['run_id'])+
        '/attempts/'+str(op['attempt'])+'/jobs','jobs')
    brokers = [j for j in jobs if j['name'] == 'broker ('+str(op['pr'])+')']
    require(len(brokers) == 1 and positive(brokers[0]['id']), 'exact terminal broker required; preserve fence')
    with _source_token('admin',root,api,d,identities,before['configuration_revision'],clock,token_factory,guard,recovery=True) as source:
        with _admin_authority(root,api,registry,before,identities,token_factory) as writer:
            guard()
            return Finalizer(writer,api,source,pin,environment,clock)._finalize(op['operation_id'],before['fence']['sequence'],brokers[0]['id'])


def main():
    # Hold before stdin reads, API construction, root-key loading or SDK import.
    require(len(sys.argv) == 3 and sys.argv[1] in ('credential', 'prepare-task', 'model-authorization', 'task', 'task-controls') + PRODUCER_ROLES + TRIAL_ROLES,
            'fixed authority role required')
    role = sys.argv[1]
    authority_release.authorize('bootstrap' if role == 'credential' else
        'broker-merge' if role in PRODUCER_ROLES else 'protected-run')
    raw = sys.stdin.buffer.read(65537)
    require(0 < len(raw) <= 65536, 'bounded credential challenge required')
    request = loads(raw)
    if role in TRIAL_ROLES:
        result = _trial(os.environ, request, sys.argv[2], role)
        if role == 'trial-prepare': print(json.dumps(result, sort_keys=True, allow_nan=False))
    elif role in ('prepare-task','discover','prepare'):
        handler = {'prepare-task':_prepare_task,'discover':_discover,'prepare':_prepare}[role]
        print(json.dumps(handler(os.environ,request),sort_keys=True,allow_nan=False))
    elif role == 'finalize':
        _finalize(os.environ,request,sys.argv[2])
    elif role in PRODUCER_ROLES:
        _producer(os.environ,request,sys.argv[2],role)
    else:
        handler = {'credential':_credential,'model-authorization':_authorize_task_request,'task':_task,'task-controls':_task_controls}[role]
        handler(os.environ,request,sys.argv[2])


if __name__ == '__main__':
    try: main()
    except Exception:
        print('authority credential consumer refused; no verified progress claimed', file=sys.stderr)
        sys.exit(1)
