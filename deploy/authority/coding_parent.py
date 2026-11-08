"""Trusted task composition; never treat a submission alone as admission.

The caller must authenticate/decrypt the model delivery before passing its lease.
Only the pinned authority job may upload the resulting closed task receipt.
"""
import copy
from contextlib import ExitStack
import json
from pathlib import Path
import secrets
import tempfile
import time

import app_proofs
import authority_release
from coding_transport import _conversation
from coding_worker import CodingSandbox
from codex_harness import profile
from disk import WorkDisk
from model_relay import Relay
from model_vault import validate_lease
from provenance import admit_job
import submission
import task_controls
from trusted_ci_policy import digest, object_fields, positive, require, sha
from worker_facts import measure

TASK_REQUEST_FIELDS = ('schema_version', 'task', 'source_base', 'prompt', 'configuration_revision', 'deployment_digest')


class _FencedSource:
    def __init__(self, api, guard, authorize_write):
        self.api, self.guard, self.authorize_write = api, guard, authorize_write

    def _call(self, method, *args, **kwargs):
        mutation = method == 'post' or (method == 'fetch' and kwargs.get('method', 'GET') != 'GET')
        self.guard(force=mutation)
        if mutation: self.authorize_write()
        value = getattr(self.api, method)(*args, **kwargs)
        self.guard(force=mutation)
        return value

    def get(self, *args, **kwargs): return self._call('get', *args, **kwargs)
    def post(self, *args, **kwargs): return self._call('post', *args, **kwargs)
    def pages(self, *args, **kwargs): return self._call('pages', *args, **kwargs)
    def fetch(self, *args, **kwargs): return self._call('fetch', *args, **kwargs)


class Parent:
    def __init__(self, registry, authority, source, environment, identities, clock=None):
        self.registry, self.authority, self.source = registry, authority, source
        self.environment, self.identities = dict(environment), copy.deepcopy(identities)
        self.clock = clock or (lambda: int(time.time()))

    def run(self, request, lease, uploader):
        authority_release.authorize('protected-run')
        return self._run(request, lease, uploader)

    def _run(self, request, lease, uploader, disk_factory=WorkDisk, relay_factory=Relay,
             sandbox_factory=CodingSandbox, cancelled=lambda: False):
        object_fields(request, TASK_REQUEST_FIELDS, 'managed task request')
        require(type(request['schema_version']) is int and request['schema_version'] == 2 and
                sha(request['source_base']) and isinstance(request['prompt'], str) and
                0 < len(request['prompt'].encode('utf-8')) <= 65536, 'bounded exact managed task request required')
        before = self.registry.binding()
        require(request['configuration_revision'] == before['configuration_revision'] and
                request['deployment_digest'] == before['deployment_digest'], 'prepared task configuration changed')
        require(isinstance(before.get('fence'), dict) and 'pending' in before['fence'] and
                before['fence']['pending'] is None, 'managed tasks require a settled configuration fence')
        d, task = before['deployment'], request['task']
        resources = profile(d)
        app_proofs.identity_record(d, self.identities)
        issued = self.clock()
        validate_lease(lease, before, task, issued)
        job = admit_job(self.authority, d, self.environment, 'task (' + task['task_id'] + ')', issued)
        require(task['purpose'] == 'task' and task['run_id'] == int(self.environment['GITHUB_RUN_ID']) and
                task['attempt'] == int(self.environment['GITHUB_RUN_ATTEMPT']), 'model task execution differs from coding job')
        next_observation = [0.0]
        def guard(force=False):
            now = self.clock()
            require(issued <= now < min(task['deadline'], lease['expires'], d['expires']) and not cancelled(),
                    'managed task lease ended or was cancelled')
            if force or time.monotonic() >= next_observation[0]:
                require(self.registry.binding() == before, 'managed task configuration moved')
                # Remote readback may block; transport watchdogs independently
                # stop the owned candidate/exporter while this call is pending.
                require(self.clock() < min(task['deadline'], lease['expires'], d['expires']) and not cancelled(),
                        'managed task authorization observation expired')
                next_observation[0] = time.monotonic() + 2
        authorization = []
        authorization_deadline = []
        def authorize_write():
            require(len(authorization) == len(authorization_deadline) == 1 and time.monotonic() <= authorization_deadline[0],
                    'fresh administrative task controls required before source writes')
            readiness, location, response = authorization[0]
            task_controls.validate_response(response, request, readiness, location, before, self.clock())
        source = _FencedSource(self.source, guard, authorize_write)
        archive = submission.capture_source(source, d, request['source_base'], guard)
        runtime = d['resources'].get('container_runtime', 'docker')
        require(runtime in ('docker', 'podman'), 'approved coding engine required')
        capability = 'agentic-task.' + secrets.token_hex(32)
        expires = min(issued + d['policy']['limits']['seconds'], task['deadline'], lease['expires'], d['expires'])
        name = 'agentic-task-' + task['task_id']
        with tempfile.TemporaryDirectory(prefix='agentic-coding-parent-') as temporary, ExitStack() as owned:
            guard(force=True)
            disk = owned.enter_context(disk_factory(name, d['policy']['limits']['disk_mb'], runtime=runtime,
                                                     formatter_image=d['policy']['image']))
            relay = relay_factory(lease, before, task, capability, clock=self.clock)
            owned.callback(relay.close)
            relay._start(Path(temporary))
            box = sandbox_factory(d, disk.name, relay.directory, runtime=runtime)
            box._enter()
            owned.callback(box.close)
            facts = measure(box)  # Before source materialization or candidate execution.
            protocol = _conversation(box, d, archive, capability, request['prompt'], expires, guard,
                                     cancelled=lambda: cancelled() or relay.failed)
            inference = relay.result()
            require(inference['completed_inference'] is True and inference['model_execution_qualified'] is False and
                    positive(inference['requests']) and positive(inference['completed']), 'completed task inference required')
            relay.close()  # Revoke the capability before the stopped-volume exporter.
            exported = box._export(guard)
        # ExitStack has confirmed box, relay and hard disk cleanup. No source write
        # or receipt upload occurs while candidate resources are still owned.
        guard(force=True)
        files = submission.read_export(exported)
        authorization.append(task_controls.acquire(self.authority, self.registry.binding, request, job['id'],
            digest(submission.export_manifest(files)), uploader, self.clock, lambda: guard(force=True)))
        authorization_deadline.append(time.monotonic() + 30 - (self.clock() - authorization[0][2]['readback_started']))
        authorize_write()
        submitted = submission.submit(source, d, dict(schema_version=2, task_id=task['task_id'],
            configuration_revision=before['configuration_revision'], deployment_digest=before['deployment_digest'],
            base=request['source_base'], issued=issued, run_id=task['run_id'], attempt=task['attempt']),
            files, self.clock())
        completed = self.clock()
        document = dict(schema_version=2, kind='protected-task', task_id=task['task_id'],
            configuration_revision=before['configuration_revision'], deployment_digest=before['deployment_digest'],
            source_base=request['source_base'], coding_installation_id=self.identities['apps']['coding']['installation_id'],
            submitted=submitted, execution=dict(run_id=task['run_id'], attempt=task['attempt'], job_id=job['id']),
            harness=dict(image=resources['coding_image'], sha256=resources['codex_sha'],
                         version=resources['codex_version'], auth_profile=resources['model_auth']),
            protocol=protocol, isolation=facts,
            relay={key: inference[key] for key in ('requests', 'completed', 'response_digests')},
            cleanup_complete=True, issued=issued, completed=completed, expires=min(completed + 300, d['expires']))
        guard(force=True)
        admit_job(self.authority, d, self.environment, 'task (' + task['task_id'] + ')', self.clock())
        guard(force=True)
        artifact = uploader('task-' + task['task_id'] + '-' + str(task['attempt']),
                            json.dumps(document, sort_keys=True, allow_nan=False).encode())
        guard(force=True)
        require(positive(artifact), 'managed task artifact identity unavailable')
        return dict(run_id=task['run_id'], attempt=task['attempt'], job_id=job['id'], artifact_id=artifact)
