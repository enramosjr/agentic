"""Held disposable-trial worker, never production admission or qualification.

The native caller supplies separate read and coding transports. Only the coding
transport receives exact fixture writes, after candidate cleanup and closed admin
readback. Unknown execution/upload outcomes remain retained and are never replayed.
"""
import copy
import json
import time

import authority_release
import coding_parent
import model_vault
import submission
from trial_admission import Admission
from trial_controls import Controls
from trusted_ci_policy import digest, positive, require


class Worker:
    def __init__(self, admission, source=None):
        self.admission, self.source = admission, source

    def run(self, prompt, delivery_key, uploader, approve=None):
        authority_release.authorize('protected-run')
        return self._run(prompt, delivery_key, uploader, approve)

    def _run(self, prompt, delivery_key, uploader, approve, cancelled=lambda: False, **execution):
        c = self.admission
        require(isinstance(c, Admission) and self.source is not None, 'native admission and separate coding transport required')
        c._guard()
        require(not cancelled(), 'trial worker cancelled')
        i, binding = c.intent, c.binding
        request = dict(schema_version=2, task=copy.deepcopy(i['task']), prompt=prompt,
            **{k: i[k] for k in ('source_base', 'configuration_revision', 'deployment_digest')})
        controls = Controls(c, request)
        preview = dict(kind='trial-worker', admission_digest=digest(i), request=request)
        journal = c.store(c.root / 'worker')
        document = journal.read()
        if document is not None:
            state = document['value']
            require(state.get('intent') == preview and state.get('approval') == digest(preview),
                    'resume only the original approved trial worker')
            c._guard()
            require(journal.read() == document, 'retained worker completion changed during readback')
            require(not cancelled(), 'trial worker cancelled')
            require(state.get('phase') == 'complete', 'trial worker outcome pending; never replay execution or upload')
            return copy.deepcopy(state['result'])
        require(callable(approve) and approve(copy.deepcopy(preview)) == digest(preview),
                'exact trial worker prompt consent required')
        c._guard()
        # Decrypt anew at this purpose boundary; never retain key or lease on the object/journal.
        lease = model_vault.read_delivery(c.authority, binding, request['task'], i['model'], delivery_key, c.clock())
        require(digest(lease) == i['model_lease_digest'], 'trial worker model delivery differs from admission')
        c._guard()
        archive = c.capture_source()
        state = dict(intent=preview, approval=digest(preview), phase='execution-started')
        document = journal.write(None, state)
        next_observation = [0.0]

        def guard(force=False):
            require(not cancelled(), 'trial worker cancelled')
            require(journal.read() == document, 'trial worker journal changed')
            c._clock()
            if force or time.monotonic() >= next_observation[0]:
                c._worker_guard()
                next_observation[0] = time.monotonic() + 2
            require(journal.read() == document, 'trial worker journal changed during live readback')
            require(not cancelled(), 'trial worker cancelled during live readback')

        files, protocol, facts, inference = coding_parent._execute(request, lease, binding, archive, guard, c.clock,
                                                                  cancelled=cancelled, **execution)
        c._guard()
        guard(force=True)
        readiness, location, response = controls.acquire(c.authority, controls._binding, request,
            i['execution']['job_id'], digest(submission.export_manifest(files)), uploader, c.clock,
            lambda: guard(force=True))
        deadline = time.monotonic() + 30 - (c.clock() - response['readback_started'])

        def authorize_write():
            require(not cancelled() and time.monotonic() <= deadline, 'trial cancelled or original control budget expired')
            controls.validate_response(response, request, readiness, location, binding, c.clock())

        source = coding_parent._FencedSource(self.source, guard, authorize_write)
        issued = readiness['issued']
        submitted = submission._submit(source, binding['deployment'], dict(schema_version=2,
            task_id=request['task']['task_id'], base=request['source_base'], issued=issued,
            configuration_revision=binding['configuration_revision'], deployment_digest=binding['deployment_digest'],
            run_id=request['task']['run_id'], attempt=request['task']['attempt']), files)
        guard(force=True)
        receipt = dict(schema_version=2, kind='trial-task', admission_digest=digest(i), request_digest=digest(request),
            execution=i['execution'], submitted=submitted, protocol=protocol, isolation=facts,
            relay={k: inference[k] for k in ('requests', 'completed', 'response_digests')},
            controls_digest=digest(response), cleanup_complete=True, completed=c.clock(),
            hosted_qualified=False, enforcement_active=False)
        artifact = uploader('trial-task-' + request['task']['task_id'] + '-' + str(request['task']['attempt']),
                            json.dumps(receipt, sort_keys=True, allow_nan=False).encode())
        guard(force=True)
        require(positive(artifact), 'exact trial worker artifact acknowledgement required')
        result = dict(**i['execution'], artifact_id=artifact, hosted_qualified=False, enforcement_active=False)
        state = dict(state, phase='complete', result=result)
        document = journal.write(document, state)
        c._guard()
        require(journal.read() == document, 'trial worker completion changed during live readback')
        require(not cancelled(), 'trial worker cancelled during completion readback')
        return result
