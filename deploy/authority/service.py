"""Pinned candidate-free credential and encrypted model-delivery entrypoints.

Authority coordinates come from the actual Actions execution, never dispatch
inputs. Other authority operations are not exposed until their producers exist.
"""
import json
from contextlib import contextmanager
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
from urllib.parse import quote

sys.path[:0] = [str(Path(__file__).resolve().parent),
                str(Path(__file__).resolve().parents[2] / '.ai/scripts')]
import app_proofs
from artifact_uploader import NodeUploader
import authority_release
from registry import Registry
import setup
from trusted_ci_github import GitHub
from trusted_ci_policy import Refusal, loads, object_fields, positive, require, sha


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
def _source_token(purpose, root, authority, deployment, identities, revision, clock, token_factory=GitHub, guard=lambda:None):
    require(purpose in ('coding', 'reader', 'admin'), 'fixed task source credential purpose required')
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
    app_proofs.prove(admitted, authority, deployment, identities, purpose, revision, clock(), token_factory)
    guard()
    record = identities['apps'][purpose]
    permissions = (dict(administration='write', contents='read', repository_hooks='read') if purpose == 'admin' else
                   app_proofs.TOKEN_PERMISSIONS['coding'] if purpose == 'coding' else {'contents':'read'})
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


def main():
    # Hold before stdin reads, API construction, root-key loading or SDK import.
    require(len(sys.argv) == 3 and sys.argv[1] in ('credential', 'prepare-task', 'model-authorization', 'task', 'task-controls'),
            'fixed authority role required')
    role = sys.argv[1]
    authority_release.authorize('bootstrap' if role == 'credential' else 'protected-run')
    raw = sys.stdin.buffer.read(65537)
    require(0 < len(raw) <= 65536, 'bounded credential challenge required')
    request = loads(raw)
    if role == 'prepare-task':
        print(json.dumps(_prepare_task(os.environ,request),sort_keys=True,allow_nan=False))
    else:
        handler = {'credential':_credential,'model-authorization':_authorize_task_request,'task':_task,'task-controls':_task_controls}[role]
        handler(os.environ,request,sys.argv[2])


if __name__ == '__main__':
    try: main()
    except Exception:
        print('authority credential consumer refused; no verified progress claimed', file=sys.stderr)
        sys.exit(1)
