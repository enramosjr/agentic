"""Create-only Actions broker receipts. Runtime upload is a separate capability.

Artifact/job association relies on a pinned workflow with closed producer roles:
GitHub's artifact metadata does not independently identify the uploading job.
Recovery inspection never grants a second dispatch or releases the admin fence.
"""
import copy
import hashlib
import io
import json
import zipfile

from authority_protocol import fingerprint
import merge_window
from broker_refusal import same
from operation_fence import validate as validate_fence
from trusted_ci_deployment import timestamp
from trusted_ci_policy import Refusal, digest, loads, object_fields, positive, require

KINDS = ('gate', 'dispatch', 'outcome', 'control-ready', 'not-submitted', 'host-denied')
MAX_DOCUMENT = 1024 * 1024
MAX_ARCHIVE = 2 * MAX_DOCUMENT


def not_submitted(binding, job_id, now):
    """Positive evidence emitted only by the closed pre-dispatch failure path."""
    op = binding['fence']['pending']
    require(op is not None and op['kind'] == 'merge' and positive(job_id) and positive(now),
            'exact pending broker required')
    return dict(schema_version=2, kind='not-submitted', operation_id=op['operation_id'],
        sequence=binding['fence']['sequence'], operation_digest=digest(op),
        configuration_revision=binding['configuration_revision'], deployment_digest=binding['deployment_digest'],
        workflow_sha=op['workflow_sha'], run_id=op['run_id'], attempt=op['attempt'], job_id=job_id,
        issued=now, reason_code='pre_dispatch_refusal')


class ActionsReceipts:
    def __init__(self, api, read_binding, job_id, clock, uploader=None, recovery=False):
        require(positive(job_id) and type(recovery) is bool, 'exact broker job identity required')
        self.api, self.read_binding, self.job_id, self.clock = api, read_binding, job_id, clock
        self.uploader, self.recovery = uploader, recovery
        self._admission = None
        self.binding = copy.deepcopy(read_binding())
        fence = validate_fence(self.binding['fence'])
        self.op, self.sequence = fence['pending'], fence['sequence']
        require(self.op is not None and self.op['kind'] == 'merge', 'pending merge operation required')
        self.policy = self.binding['deployment']['policy']
        self.root = '/repos/' + self.policy['authority_repository']

    @classmethod
    def _create(cls, api, read_binding, job_id, clock, uploader=None, recovery=False, admission=None):
        if admission is not None:
            from trial_controller import authenticated
            authenticated(admission, read_binding())
        result = cls(api, read_binding, job_id, clock, uploader, recovery)
        result._admission = admission
        return result

    def _owned(self):
        current = self.read_binding()
        same(current, self.binding, 'receipt operation or configuration changed')
        return current

    def _name(self, kind):
        require(kind in KINDS, 'unsupported broker receipt kind')
        return ('agentic-merge-' + self.op['operation_id'] + '-s' + str(self.sequence) +
                '-a' + str(self.op['attempt']) + '-' + kind)

    def _job(self):
        self._owned()
        run_id, attempt = self.op['run_id'], self.op['attempt']
        # The attempt endpoint supports later read-only recovery after a rerun;
        # the current-run endpoint alone reports the latest attempt instead.
        run = self.api.get(self.root + '/actions/runs/' + str(run_id) + '/attempts/' + str(attempt))
        p = self.policy
        require(run['id'] == run_id and run['repository']['id'] == p['authority_repository_id'] and
                run['head_sha'] == p['workflow_sha'] == self.op['workflow_sha'] and
                run['run_attempt'] == attempt and run['event'] in ('schedule', 'workflow_dispatch') and
                positive(run['workflow_id']), 'broker workflow execution differs')
        path = run['path'].split('@', 1)
        require(path[0] == p['workflow'] and (len(path) == 1 or path[1] in
                (run.get('head_branch'), 'refs/heads/' + str(run.get('head_branch')), p['workflow_sha'])),
                'broker workflow path differs')
        workflow = self.api.get(self.root + '/actions/workflows/' + str(run['workflow_id']))
        require(workflow['id'] == run['workflow_id'] and workflow['path'] == p['workflow'],
                'broker workflow identity differs')
        jobs = self.api.pages(self.root + '/actions/runs/' + str(run_id) + '/attempts/' + str(attempt) + '/jobs', 'jobs')
        matches = [j for j in jobs if j['name'] == 'broker (' + str(self.op['pr']) + ')']
        require(len(matches) == 1, 'missing or ambiguous broker job')
        job = matches[0]
        require(job['id'] == self.job_id and job['run_id'] == run_id and job['head_sha'] == p['workflow_sha'],
                'broker job identity differs')
        live = job['status'] == 'in_progress' and job['conclusion'] is None
        terminal = job['status'] == 'completed' and job['conclusion'] in (
            'success', 'failure', 'cancelled', 'timed_out', 'action_required', 'neutral', 'skipped', 'stale')
        require(live or self.recovery and terminal, 'broker receipt producer is not admissible')
        return job

    def current_job(self):
        """Authenticate the exact live broker, without granting creation rights."""
        require(not self.recovery, 'current broker admission is not recovery')
        return self._job()

    def terminal_job(self):
        require(self.recovery, 'terminal broker inspection is recovery-only')
        job = self._job()
        require(job['status'] == 'completed', 'live producer cannot release its fence')
        return job

    def _matches(self, kind):
        name = self._name(kind)
        return [a for a in self.api.pages(self.root + '/actions/runs/' + str(self.op['run_id']) +
                '/artifacts', 'artifacts') if a['name'] == name]

    def _document(self, kind, value, historical=False):
        require(isinstance(value, dict), 'broker receipt object required')
        if kind == 'host-denied':
            from trial_host_case import validate_receipt
            require(self._admission is not None, 'host terminal evidence is trial-only')
            return validate_receipt(value,self._admission,self.api,self.job_id)
        if kind == 'not-submitted':
            expected = not_submitted(self.binding, self.job_id, value.get('issued'))
            require(type(value.get('schema_version')) is int and type(value.get('sequence')) is int and
                    all(positive(value.get(k)) for k in ('run_id', 'attempt', 'job_id', 'issued')) and
                    self.op['created'] <= value['issued'] <= self.clock() and
                    value == expected, 'positive no-dispatch evidence differs')
            return value
        if kind == 'control-ready':
            from control_rendezvous import _validate_ready
            return _validate_ready(value, self.binding, self.job_id, self.clock(), historical=historical, admission=self._admission)
        if kind == 'gate':
            gate = value
        else:
            fields = ['schema_version', 'kind', 'gate_digest', 'operation_id', 'sequence']
            fields += ['gate'] if kind == 'dispatch' else ['state', 'response_digest']
            object_fields(value, fields, 'broker receipt')
            require(type(value['schema_version']) is int and value['schema_version'] == 2 and
                    value['kind'] == kind and value['operation_id'] == self.op['operation_id'] and
                    type(value['sequence']) is int and value['sequence'] == self.sequence and
                    fingerprint(value['gate_digest']), 'broker receipt operation differs')
            if kind == 'outcome':
                require(value['state'] in ('submitted', 'unknown') and
                        (fingerprint(value['response_digest']) or
                         value['state'] == 'unknown' and value['response_digest'] is None),
                        'invalid broker outcome')
                return value
            gate = value['gate']
            require(digest(gate) == value['gate_digest'], 'dispatch gate digest differs')
        merge_window._validate(gate, self.binding,
                               gate['readback_completed'] if historical else self.clock(), self._admission)
        return value

    def _locator(self, kind, artifact):
        require(positive(artifact['id']), 'numeric artifact identity required')
        return dict(kind=kind, name=self._name(kind), artifact_id=artifact['id'], archive_digest=artifact['digest'])

    def append(self, kind, document):
        require(not self.recovery and callable(self.uploader), 'receipt creation capability unavailable')
        self._name(kind)
        self._job()
        self._document(kind, document)
        if kind in ('control-ready', 'not-submitted', 'host-denied'):
            require(not self._matches('dispatch'), 'dispatch intent already exists; readiness cannot restart')
        if kind in ('not-submitted','host-denied'):
            require(not self._matches('outcome'), 'dispatch outcome contradicts no-dispatch evidence')
        if kind != 'host-denied':
            require(not self._matches('host-denied'), 'host denial terminal evidence already exists')
        else:
            require(not self._matches('not-submitted') and not self._matches('gate') and not self._matches('control-ready'),
                    'host denial contradicts broker execution')
        if kind != 'not-submitted':
            require(not self._matches('not-submitted'), 'no-dispatch terminal evidence already exists')
        raw = json.dumps(document, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
        require(0 < len(raw) <= MAX_DOCUMENT and not self._matches(kind), 'receipt already exists or exceeds limit')
        # Provider-side create conflict is the atomic guard. Lost acknowledgement
        # propagates: finding the artifact later is audit, never permission to retry.
        if self._admission is not None:
            self._admission.guard(self.binding)
        artifact_id = self.uploader(self._name(kind), raw)
        require(positive(artifact_id), 'artifact upload acknowledgement missing')
        matches = self._matches(kind)
        require(len(matches) == 1 and matches[0]['id'] == artifact_id, 'new artifact identity differs')
        locator = self._locator(kind, matches[0])
        require(self.authenticate(locator) == document, 'durable broker receipt differs')
        return locator

    def authenticate(self, locator):
        object_fields(locator, ('kind', 'name', 'artifact_id', 'archive_digest'), 'broker receipt locator')
        kind = locator['kind']
        require(locator['name'] == self._name(kind) and positive(locator['artifact_id']), 'receipt locator differs')
        job, matches = self._job(), self._matches(kind)
        require(len(matches) == 1 and matches[0]['id'] == locator['artifact_id'], 'missing or ambiguous broker artifact')
        a, p = matches[0], self.policy
        execution = a['workflow_run']
        require(a.get('expired') is False and a['digest'] == locator['archive_digest'] and
                execution['id'] == self.op['run_id'] and execution['repository_id'] == p['authority_repository_id'] and
                execution['head_repository_id'] == p['authority_repository_id'] and execution['head_sha'] == p['workflow_sha'],
                'broker artifact provenance differs')
        created = int(timestamp(a['created_at']).timestamp())
        end = self.clock() if job['status'] == 'in_progress' else int(timestamp(job['completed_at']).timestamp())
        require(int(timestamp(job['started_at']).timestamp()) <= created <= end <= self.clock(),
                'broker artifact lies outside producer interval')
        raw = self.api.fetch(self.root + '/actions/artifacts/' + str(a['id']) + '/zip', binary=True, limit=MAX_ARCHIVE)
        require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_ARCHIVE and
                a['digest'] == 'sha256:' + hashlib.sha256(raw).hexdigest(), 'broker archive digest differs')
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                entries = archive.infolist()
                require(len(entries) == 1, 'single broker receipt required')
                item = entries[0]
                require(item.filename == 'receipt.json' and not item.is_dir() and not item.flag_bits & 1 and
                        0 < item.file_size <= MAX_DOCUMENT and
                        (item.external_attr >> 16 & 0o170000) in (0, 0o100000) and
                        item.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), 'unsafe broker receipt archive')
                document = loads(archive.read(item))
        except (zipfile.BadZipFile, OSError, RuntimeError):
            raise Refusal('invalid broker receipt archive') from None
        document = self._document(kind, document, historical=True)
        if kind in ('control-ready', 'not-submitted', 'host-denied'):
            require(document['issued'] <= created, 'ready request postdates artifact creation')
        return document

    def find_for_recovery(self, kind):
        require(self.recovery, 'recovery-only receipt inspection')
        self._job()
        matches = self._matches(kind)
        require(len(matches) <= 1, 'ambiguous broker recovery artifact')
        if not matches:
            return None
        locator = self._locator(kind, matches[0])
        self.authenticate(locator)
        return locator
