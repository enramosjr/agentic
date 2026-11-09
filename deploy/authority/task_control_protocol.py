"""Task/admin rendezvous after cleanup. Readiness is never task admission.

The task retains the nonce and exact upload acknowledgement. Only the separate
closed administrative producer can authorize writes, for thirty seconds from the
original observation start. Reading that artifact again cannot extend the window.
"""
import copy
import json
import re
import secrets
import time

from authority_protocol import fingerprint, validate_deployment
from control_rendezvous import validate_source_facts
from model_vault import TASK_FIELDS
from provenance import authenticated_document, live_task_readiness
from trusted_ci_policy import digest, object_fields, positive, require, sha

READY_FIELDS = ('schema_version kind configuration_revision deployment_digest request_digest source_base '
                'task_id run_id attempt task_job_id export_digest nonce issued expires').split()
RESPONSE_FIELDS = ('schema_version kind configuration_revision deployment_digest request_digest source_base '
                   'task_id run_id attempt task_job_id export_digest nonce ready_digest ready_location '
                   'admin_job_id readback_started readback_completed expires result').split()


def validate_ready(domain, value, request, binding, now):
    task = domain._request(request, binding, now)
    object_fields(value, READY_FIELDS, 'task readiness document')
    require(type(value['schema_version']) is int and value['schema_version'] == 2 and value['kind'] == domain.READY_KIND and
            all(value[k] == request[k] for k in ('configuration_revision', 'deployment_digest', 'source_base')) and
            all(value[k] == task[k] for k in ('task_id', 'run_id', 'attempt')) and
            value['request_digest'] == digest(request) and positive(value['task_job_id']) and
            fingerprint(value['export_digest']) and isinstance(value['nonce'], str) and
            re.fullmatch('[0-9a-f]{32}', value['nonce']) and positive(value['issued']) and positive(value['expires']) and
            value['issued'] <= now < value['expires'] <= min(value['issued'] + 120, task['deadline'],
                                                            binding['deployment']['expires']),
            'task readiness binding or lifetime differs')
    return value


def ready(domain, request, binding, job_id, export_digest, nonce, now):
    task = domain._request(request, binding, now)
    value = {k: request[k] for k in ('configuration_revision', 'deployment_digest', 'source_base')}
    value.update({k: task[k] for k in ('task_id', 'run_id', 'attempt')})
    value.update(schema_version=2, kind=domain.READY_KIND, request_digest=digest(request), task_job_id=job_id,
                 export_digest=export_digest, nonce=nonce, issued=now,
                 expires=min(now + 120, task['deadline'], binding['deployment']['expires']))
    return domain.validate_ready(value, request, binding, now)


def response(domain, request, readiness, location, binding, admin_job_id, facts, started, completed):
    domain.validate_ready(readiness, request, binding, completed)
    domain._location(location, request['task'], readiness['task_job_id'])
    value = {k: readiness[k] for k in ('configuration_revision', 'deployment_digest', 'source_base', 'request_digest',
                                     'task_id', 'run_id', 'attempt', 'task_job_id', 'export_digest', 'nonce', 'expires')}
    value.update(schema_version=2, kind=domain.RESPONSE_KIND, ready_digest=digest(readiness), ready_location=dict(location),
                 admin_job_id=admin_job_id, readback_started=started, readback_completed=completed, result=copy.deepcopy(facts))
    return domain.validate_response(value, request, readiness, location, binding, completed)


def validate_response(domain, value, request, readiness, location, binding, now):
    domain.validate_ready(readiness, request, binding, now)
    domain._location(location, request['task'], readiness['task_job_id'])
    object_fields(value, RESPONSE_FIELDS, 'task administrative response')
    require(type(value['schema_version']) is int and value['schema_version'] == 2 and value['kind'] == domain.RESPONSE_KIND and
            all(value[k] == readiness[k] for k in ('configuration_revision', 'deployment_digest', 'source_base',
                'request_digest', 'task_id', 'run_id', 'attempt', 'task_job_id', 'export_digest', 'nonce', 'expires')) and
            value['ready_digest'] == digest(readiness) and value['ready_location'] == location and
            positive(value['admin_job_id']) and value['admin_job_id'] != readiness['task_job_id'] and
            positive(value['readback_started']) and positive(value['readback_completed']) and
            readiness['issued'] <= value['readback_started'] <= value['readback_completed'] <= now and
            now - value['readback_started'] <= 30, 'task controls binding or original observation expired')
    validate_source_facts(value['result'], binding['deployment'], binding['deployment_digest'], request['source_base'])
    return value


def read_ready(domain, authority, binding, request, location, now):
    domain._location(location, request['task'])
    proof = domain.live_readiness(authority, binding['deployment'], location, request['task']['task_id'], now)
    value = domain.validate_ready(proof['document'], request, binding, now)
    require(value['task_job_id'] == location['job_id'] and
            proof['job_started'] <= value['issued'] <= proof['artifact_created'] <= now,
            'readiness artifact predates cleanup readiness')
    return value


def read_response(domain, authority, binding, request, readiness, ready_location, location, now):
    domain._location(location, request['task'])
    proof = domain.closed_response(authority, binding['deployment'], location, request['task']['task_id'], now)
    value = domain.validate_response(proof['document'], request, readiness, ready_location, binding, now)
    require(proof['job_id'] == value['admin_job_id'] and
            proof['job_started'] <= value['readback_started'] <= value['readback_completed'] <= proof['artifact_created'],
            'task controls response lies outside administrative producer interval')
    return value


def collect(domain, admin, authority, read_binding, request, ready_location, admin_job_id, clock):
    from controls import observe
    binding = copy.deepcopy(read_binding())
    readiness = domain.read_ready(authority, binding, request, ready_location, clock())
    started = clock()
    observed_at = time.monotonic()
    facts = observe(admin, binding['deployment'])
    require(read_binding() == binding, 'task configuration changed during administrative observation')
    require(time.monotonic() - observed_at <= 30, 'administrative task observation exceeded its original budget')
    return domain.response(request, readiness, ready_location, binding, admin_job_id, facts, started, clock())


def wait_ready(domain, authority, binding, request, clock, guard):
    """Wait for a single readiness producer; never accept a successful task receipt."""
    task = domain._request(request, binding, clock())
    root = '/repos/' + binding['deployment']['policy']['authority_repository'] + '/actions/runs/' + str(task['run_id'])
    deadline = time.monotonic() + min(900, task['deadline'] - clock())
    while True:
        guard()
        require(time.monotonic() < deadline and clock() < task['deadline'], 'task readiness wait expired')
        jobs = [j for j in authority.pages(root + '/attempts/' + str(task['attempt']) + '/jobs', 'jobs')
                if j.get('name') == domain.task_name(task['task_id'])]
        artifacts = [a for a in authority.pages(root + '/artifacts', 'artifacts')
                     if a.get('name') == domain.READY_KIND + '-' + task['task_id'] + '-' + str(task['attempt'])]
        require(len(jobs) <= 1 and len(artifacts) <= 1, 'ambiguous task readiness producer')
        if jobs:
            require(jobs[0]['status'] in ('queued', 'in_progress') and jobs[0]['conclusion'] is None,
                    'task ended without live cleanup readiness')
        if artifacts:
            require(len(jobs) == 1, 'task readiness has no exact live producer')
            location = dict(run_id=task['run_id'], attempt=task['attempt'], job_id=jobs[0]['id'], artifact_id=artifacts[0]['id'])
            domain.read_ready(authority, binding, request, location, clock())
            guard()
            return location
        time.sleep(0.25)


def acquire(domain, authority, read_binding, request, job_id, export_digest, uploader, clock, guard):
    """One readiness upload, then bounded polling of the exact parallel admin job."""
    binding = copy.deepcopy(read_binding())
    began = time.monotonic()
    readiness = domain.ready(request, binding, job_id, export_digest, secrets.token_hex(16), clock())
    deadline = began + readiness['expires'] - readiness['issued']
    task = request['task']
    name = domain.READY_KIND + '-' + task['task_id'] + '-' + str(task['attempt'])
    guard()
    artifact_id = uploader(name, json.dumps(readiness, sort_keys=True, allow_nan=False).encode())
    location = dict(run_id=task['run_id'], attempt=task['attempt'], job_id=job_id, artifact_id=artifact_id)
    require(domain.read_ready(authority, binding, request, location, clock()) == readiness, 'uploaded task readiness differs')
    root = '/repos/' + binding['deployment']['policy']['authority_repository'] + '/actions/runs/' + str(task['run_id'])
    while True:
        guard()
        require(read_binding() == binding and time.monotonic() < deadline and clock() < readiness['expires'],
                'task controls rendezvous expired or configuration changed')
        jobs = authority.pages(root + '/attempts/' + str(task['attempt']) + '/jobs', 'jobs')
        matches = [j for j in jobs if j.get('name') == domain.admin_name(task['task_id'])]
        require(len(matches) == 1 and matches[0]['id'] != job_id, 'parallel administrative task producer unavailable')
        job = matches[0]
        if job['status'] == 'completed':
            require(job['conclusion'] == 'success', 'administrative task producer failed')
            artifacts = [a for a in authority.pages(root + '/artifacts', 'artifacts') if a.get('name') ==
                         domain.RESPONSE_KIND + '-' + task['task_id'] + '-' + str(task['attempt'])]
            require(len(artifacts) == 1, 'exact administrative task response unavailable')
            result = domain.read_response(authority, binding, request, readiness, location,
                dict(run_id=task['run_id'], attempt=task['attempt'], job_id=job['id'], artifact_id=artifacts[0]['id']), clock())
            guard()
            require(read_binding() == binding and time.monotonic() < deadline, 'task controls changed in transit')
            return readiness, location, result
        require(job['status'] in ('queued', 'in_progress') and job['conclusion'] is None,
                'administrative task producer state unsupported')
        time.sleep(0.25)
