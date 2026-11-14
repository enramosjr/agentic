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


def _request(request, binding, now):
    object_fields(request, ('schema_version', 'task', 'source_base', 'prompt', 'configuration_revision',
                            'deployment_digest'), 'prepared task controls request')
    task = request['task']
    object_fields(task, TASK_FIELDS, 'prepared task controls coordinates')
    d = validate_deployment(binding['deployment'])
    require(type(request['schema_version']) is int and request['schema_version'] == 2 and
            request['configuration_revision'] == binding['configuration_revision'] and
            sha(request['configuration_revision']) and request['deployment_digest'] == binding['deployment_digest'] == digest(d) and
            d['state'] == 'active' and binding['fence']['pending'] is None and
            sha(request['source_base']) and isinstance(request['prompt'], str) and
            0 < len(request['prompt'].encode('utf-8')) <= 65536 and
            isinstance(task['task_id'], str) and re.fullmatch('[0-9a-f]{32}', task['task_id']) and
            positive(task['run_id']) and positive(task['attempt']) and positive(task['deadline']) and
            task['purpose'] == 'task' and type(now) is int and 0 < now < min(task['deadline'], d['expires']),
            'current bound task controls request required')
    return task


def _location(location, task, job_id=None):
    object_fields(location, ('run_id', 'attempt', 'job_id', 'artifact_id'), 'task readiness locator')
    require(all(positive(v) for v in location.values()) and location['run_id'] == task['run_id'] and
            location['attempt'] == task['attempt'] and (job_id is None or location['job_id'] == job_id),
            'exact task readiness identity required')
    return location


# Production domain remains active-state only; the shared engine owns timing and transport.
import sys
import task_control_protocol as _protocol

READY_KIND, RESPONSE_KIND = 'task-ready', 'task-controls'

def task_name(key): return 'task (' + key + ')'
def admin_name(key): return 'task controls (' + key + ')'
def live_readiness(api, d, location, key, now): return live_task_readiness(api, d, location, key, now)
def closed_response(api, d, location, key, now):
    return authenticated_document(api, d, location, 'task-controls', key, now)

def validate_ready(value, request, binding, now):
    return _protocol.validate_ready(sys.modules[__name__], value, request, binding, now)


def ready(request, binding, job_id, export_digest, nonce, now):
    return _protocol.ready(sys.modules[__name__], request, binding, job_id, export_digest, nonce, now)


def response(request, readiness, location, binding, admin_job_id, facts, started, completed):
    return _protocol.response(sys.modules[__name__], request, readiness, location, binding, admin_job_id, facts, started, completed)


def validate_response(value, request, readiness, location, binding, now):
    return _protocol.validate_response(sys.modules[__name__], value, request, readiness, location, binding, now)


def read_ready(authority, binding, request, location, now):
    return _protocol.read_ready(sys.modules[__name__], authority, binding, request, location, now)


def read_response(authority, binding, request, readiness, ready_location, location, now):
    return _protocol.read_response(sys.modules[__name__], authority, binding, request, readiness, ready_location, location, now)


def collect(admin, authority, read_binding, request, ready_location, admin_job_id, clock):
    return _protocol.collect(sys.modules[__name__], admin, authority, read_binding, request, ready_location, admin_job_id, clock)


def wait_ready(authority, binding, request, clock, guard):
    return _protocol.wait_ready(sys.modules[__name__], authority, binding, request, clock, guard)


def acquire(authority, read_binding, request, job_id, export_digest, uploader, clock, guard):
    return _protocol.acquire(sys.modules[__name__], authority, read_binding, request, job_id, export_digest, uploader, clock, guard)
