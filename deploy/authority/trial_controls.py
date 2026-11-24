"""Separate administrative rendezvous for a retained disposable-trial admission.

The shared protocol preserves production nonce, artifact and original time budgets.
No JSON flag can select this domain: a live native Admission is required.
"""
import copy
import json

import authority_release
import provenance
import task_control_protocol as protocol
import task_controls
from trial_admission import Admission, ControlAdmission
from trusted_ci_policy import digest, object_fields, require


class Controls:
    READY_KIND, RESPONSE_KIND = 'trial-task-ready', 'trial-task-controls'
    _location = staticmethod(task_controls._location)
    live_readiness = staticmethod(provenance.live_trial_readiness)

    def __init__(self, admission, request):
        require(isinstance(admission, (Admission, ControlAdmission)), 'authenticated trial admission required')
        self.admission, self.request = admission, copy.deepcopy(request)
        self._request(request, admission.binding, admission.clock())

    @classmethod
    def hosted(cls, registry, origin_reader, authority, root, clock, environment, hint, prompt, model, proofs,
               store_factory):
        authority_release.authorize('protected-run')
        admission = ControlAdmission(registry, origin_reader, authority, root, clock, environment, hint, prompt,
                                     model, proofs, store_factory)
        request = dict(schema_version=2, task=admission.intent['task'], prompt=prompt,
            **{k:admission.intent[k] for k in ('source_base', 'configuration_revision', 'deployment_digest')})
        return cls(admission, request)

    def _request(self, request, binding, now):
        c = self.admission
        c._clock()
        object_fields(request, ('schema_version', 'task', 'source_base', 'prompt', 'configuration_revision',
                                'deployment_digest'), 'trial worker request')
        require(request == self.request and binding == c.binding and
                binding['deployment']['state'] == 'qualification' and binding['deployment']['qualification'] is None and
                binding['fence']['pending'] is None and type(request['schema_version']) is int and
                request['schema_version'] == 2 and request['task'] == c.intent['task'] and
                request['task']['purpose'] == 'qualification' and
                all(request[k] == c.intent[k] for k in ('source_base', 'configuration_revision', 'deployment_digest')) and
                isinstance(request['prompt'], str) and 0 < len(request['prompt'].encode('utf-8')) <= 65536 and
                type(now) is int and c.started <= now < c.intent['expires'], 'exact admitted trial request required')
        require(c.document is not None and c.journal.read() == c.document,
                'retained trial admission required for controls')
        return request['task']

    def task_name(self, key): return 'hosted qualification'
    def admin_name(self, key): return 'trial task controls (' + key + ')'
    def closed_response(self, api, d, location, key, now):
        return provenance.authenticated_document(api, d, location, self.RESPONSE_KIND, key, now)

    def collect(self, admin, environment, uploader):
        """Only the separate pinned admin job observes controls and uploads a response."""
        authority_release.authorize('protected-run')
        c, task = self.admission, self.request['task']
        c._guard()
        remote = isinstance(c, ControlAdmission)
        worker = None if remote else c.store(c.root / 'worker').read()
        intent = dict(kind='trial-worker', admission_digest=digest(c.intent), request=self.request)
        require(remote or worker is not None and worker['value'].get('intent') == intent and
                worker['value'].get('approval') == digest(intent) and worker['value'].get('phase') == 'execution-started',
                'retained exact worker consent required before trial control observation')
        location, readiness, ready_metadata = None, None, None
        def metadata():
            root = '/repos/' + c.binding['deployment']['policy']['authority_repository'] + '/actions/runs/' + str(task['run_id'])
            values = [a for a in c.authority.pages(root + '/artifacts', 'artifacts') if a.get('id') == location['artifact_id']]
            require(len(values) == 1 and values[0].get('expired') is False, 'exact cleanup readiness metadata required')
            return values[0]
        def guard():
            c._worker_configuration()
            if remote:
                if location is not None:
                    job = provenance.execution_job(c.authority, c.binding['deployment'], task['run_id'], task['attempt'], 'hosted qualification')
                    require(job['id'] == location['job_id'] and metadata() == ready_metadata,
                            'authenticated cleanup readiness producer or immutable artifact changed')
                    self.validate_ready(readiness, self.request, c.binding, c.clock())
            else:
                require(c.store(c.root / 'worker').read() == worker, 'worker consent changed during trial control readback')
        p = c.binding['deployment']['policy']
        expected = dict(GITHUB_REPOSITORY_ID=str(p['authority_repository_id']), GITHUB_SHA=p['workflow_sha'],
                        GITHUB_RUN_ID=str(task['run_id']), GITHUB_RUN_ATTEMPT=str(task['attempt']),
                        GITHUB_JOB='trial_task_controls')
        require(all(environment.get(k) == v for k, v in expected.items()), 'pinned trial administrative environment required')
        job = provenance.execution_job(c.authority, c.binding['deployment'], task['run_id'], task['attempt'],
                                       self.admin_name(task['task_id']))
        require(job['id'] != c.intent['execution']['job_id'], 'separate trial administrative producer required')
        location = protocol.wait_ready(self, c.authority, c.binding, self.request, c.clock, guard)
        if remote:
            readiness = self.read_ready(c.authority, c.binding, self.request, location, c.clock())
            ready_metadata = copy.deepcopy(metadata())
        journal = c.store(c.root / 'worker-controls')
        retained = journal.read()
        observation = dict(request_digest=digest(self.request), ready_location=location, admin_job_id=job['id'])
        if retained is not None:
            require(retained['value'].get('intent') == observation and retained['value'].get('phase') == 'complete',
                    'trial control upload pending; never repeat an unknown upload')
            guard()
            require(journal.read() == retained, 'trial control completion changed during readback')
            return copy.deepcopy(retained['value']['result'])
        value = protocol.collect(self, admin, c.authority, self._binding, self.request, location, job['id'], c.clock)
        guard()
        provenance.execution_job(c.authority, c.binding['deployment'], task['run_id'], task['attempt'],
                                 self.admin_name(task['task_id']))
        guard()
        retained = journal.write(None, dict(intent=observation, phase='upload-started'))
        artifact = uploader(self.RESPONSE_KIND + '-' + task['task_id'] + '-' + str(task['attempt']),
                            json.dumps(value, sort_keys=True, allow_nan=False).encode())
        guard()
        result = dict(run_id=task['run_id'], attempt=task['attempt'], job_id=job['id'], artifact_id=artifact)
        self._location(result, task, job['id'])
        journal.write(retained, dict(intent=observation, phase='complete', result=result))
        return result

    def _binding(self):
        self.admission._worker_configuration()
        return copy.deepcopy(self.admission.binding)

    def validate_ready(self, *args): return protocol.validate_ready(self, *args)
    def ready(self, *args): return protocol.ready(self, *args)
    def response(self, *args): return protocol.response(self, *args)
    def validate_response(self, *args): return protocol.validate_response(self, *args)
    def read_ready(self, *args): return protocol.read_ready(self, *args)
    def read_response(self, *args): return protocol.read_response(self, *args)
    def acquire(self, *args): return protocol.acquire(self, *args)
