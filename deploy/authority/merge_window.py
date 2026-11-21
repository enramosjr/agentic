"""Bounded broker dispatch primitives; authenticate all inputs in the caller.

Gate validation is not authorization by itself. No candidate runs here. No admin
credential or registry writer is accepted. Only authenticated terminal recovery
may clear the separate admin-owned operation fence.
"""
from authority_protocol import fingerprint, validate_deployment
from operation_fence import validate as validate_fence
from trusted_ci_policy import digest, object_fields, positive, require, sha

FIELDS = ('schema_version operation_id sequence configuration_revision deployment_digest '
          'repository_id authority_repository_id target pr head base merge tree workflow_sha run_id attempt '
          'epoch check_name issued expires readback_started readback_completed valid_until '
          'evidence_digest controls_digest proofs_digest task_digest qualification_digest check_id review_ids').split()
EXPIRING = ('deployment', 'qualification', 'task', 'admin', 'reader', 'issuer', 'coding', 'merge')


def validate(gate, binding, now):
    return _validate(gate, binding, now)


def _validate(gate, binding, now, admission=None, clock=None):
    qualification = None
    if admission is not None:
        from trial_controller import authenticated
        authenticated(admission, binding)
        admission.guard(binding)
        if admission.candidate['name']=='positive' and clock is not None:
            from trial_broker_positive import require_broker
            require_broker(admission)
        if clock is not None:
            from trial_broker_case import live_certificate
            live_certificate(admission,admission.registry.api)
        qualification = admission.qualification(binding)
    return _validate_binding(gate,binding,now,qualification,clock)


def _validate_binding(gate, binding, now, qualification=None, clock=None):
    """Pure semantics for already authenticated data; never dispatch authority.

    Historical native readers pass their authenticated exact certificate here.
    Live dispatch always enters _validate and authenticates an actual admission.
    """
    """Check exact authenticated gate/fence bindings and remaining dispatch time."""
    object_fields(gate, FIELDS, 'broker authorization')
    d = validate_deployment(binding['deployment'])
    fence = validate_fence(binding['fence'])
    operation = fence['pending']
    require(type(gate['schema_version']) is int and gate['schema_version'] == 2 and
            type(now) is int and (qualification is not None or d['state'] == 'active') and operation is not None and operation['kind'] == 'merge',
            'active deployment and pending merge operation required')
    require(positive(gate['sequence']) and gate['sequence'] == fence['sequence'], 'merge fence sequence differs')
    for key in ('operation_id', 'repository_id', 'target', 'configuration_revision', 'deployment_digest',
                'pr', 'head', 'base', 'merge', 'workflow_sha', 'run_id', 'attempt'):
        require(gate[key] == operation[key], 'merge operation binding differs: ' + key)
    p = d['policy']
    qualification_digest = qualification['qualification_digest'] if qualification is not None else d['qualification']
    require(gate['configuration_revision'] == binding['configuration_revision'] and
            gate['deployment_digest'] == binding['deployment_digest'] == digest(d) and
            gate['authority_repository_id'] == p['authority_repository_id'] and
            gate['workflow_sha'] == p['workflow_sha'] and gate['epoch'] == p['epoch'] and
            gate['check_name'] == p['check_name'] and gate['qualification_digest'] == qualification_digest,
            'current configuration or qualification differs')
    require(sha(gate['tree']) and all(fingerprint(gate[k]) for k in
            ('evidence_digest', 'controls_digest', 'proofs_digest', 'task_digest', 'qualification_digest')) and
            positive(gate['check_id']) and isinstance(gate['review_ids'], list) and gate['review_ids'] and
            all(positive(v) for v in gate['review_ids']) and len(set(gate['review_ids'])) == len(gate['review_ids']),
            'complete authenticated gate evidence required')
    # Native authentication performs blocking live reads. Dispatch supplies its
    # actual clock so those reads cannot consume a window checked against an
    # earlier sample. Historical receipt authentication keeps its given time.
    if clock is not None: now = clock()
    for key in ('issued', 'expires', 'readback_started', 'readback_completed'):
        require(positive(gate[key]), 'invalid broker timestamp')
    require(gate['issued'] <= gate['readback_started'] <= gate['readback_completed'] <= now and
            now - gate['readback_started'] <= 30 and gate['issued'] < gate['expires'] <= gate['issued'] + 300 and
            gate['expires'] - now >= 60 and operation['created'] <= gate['issued'] and
            operation['execution_deadline'] - now >= 60, 'broker authorization is stale, future or too short')
    object_fields(gate['valid_until'], EXPIRING, 'expiring broker proofs')
    if qualification is not None:
        require(gate['valid_until']['qualification'] <= qualification['expires'],
                'trial authorization extended an admitted capability expiry')
    require(gate['valid_until']['deployment'] == d['expires'] and
            all(positive(v) and v - now >= 60 for v in gate['valid_until'].values()),
            'a required proof expires before the dispatch safety window')
    return gate


def dispatch(gate, read_binding, receipts, source, clock):
    return _dispatch(gate, read_binding, receipts, source, clock)


def _dispatch(gate, read_binding, receipts, source, clock, admission=None):
    """Create-only immutable intent + authenticated readback precede ONE request.

    receipts.append MUST reject an existing operation/sequence/kind. Its runtime
    capability is artifact-only; authenticate checks pinned job/run provenance.
    The caller cannot retry an uncertain operation with the same artifact name.
    """
    if admission is not None:
        require(admission.candidate['name']=='positive','only the original positive reservation may enter native dispatch')
        from trial_broker_positive import require_broker
        require_broker(admission)
    binding = read_binding()
    _validate(gate, binding, clock(), admission, clock=clock)
    intent = {'schema_version': 2, 'kind': 'dispatch', 'gate_digest': digest(gate),
              'operation_id': gate['operation_id'], 'sequence': gate['sequence'], 'gate': gate}
    stored = receipts.append('dispatch', intent)
    require(receipts.authenticate(stored) == intent, 'durable dispatch intent differs')
    binding = read_binding()
    _validate(gate, binding, clock(), admission, clock=clock)  # Include upload/readback latency and CAS races.
    try:
        response = source.merge(binding['deployment']['policy']['repository'], gate['pr'], gate['head'], timeout=30)
    except Exception:
        # A returned provider error, timeout or lost response cannot prove that a
        # request was never processed. Do not retry or release the fence.
        result = {'state': 'unknown', 'response_digest': None}
    else:
        result = {'state': 'submitted' if isinstance(response, dict) and response.get('merged') is True and
                  sha(response.get('sha')) else 'unknown', 'response_digest': digest(response)}
    outcome = {'schema_version': 2, 'kind': 'outcome', 'operation_id': gate['operation_id'],
               'sequence': gate['sequence'], 'gate_digest': digest(gate), **result}
    receipts.append('outcome', outcome)
    return outcome


def recover_merged(gate, pr, commit):
    """API-backed recovery: actual commit identity may differ from synthetic SHA."""
    require(pr['number'] == gate['pr'] and pr.get('merged') is True and pr['state'] == 'closed' and
            pr['head']['sha'] == gate['head'] and pr['base']['ref'] == gate['target'] and
            pr['base']['repo']['id'] == gate['repository_id'], 'exact authorized merged PR unavailable')
    require(sha(pr['merge_commit_sha']) and commit['sha'] == pr['merge_commit_sha'] and
            [p['sha'] for p in commit['parents']] == [gate['base'], gate['head']] and
            commit['tree']['sha'] == gate['tree'], 'actual merge parents or tree differ')
    return {'state': 'merged', 'merge_commit': commit['sha'], 'gate_digest': digest(gate)}


class MergeSource:
    """Source-only token. One fixed HTTPS PUT, no redirects and no retries."""

    def __init__(self, token, repository, repository_id):
        import re
        require(isinstance(token, str) and token and not any(ord(c) < 32 for c in token) and
                isinstance(repository, str) and re.fullmatch('[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository) and
                all(v not in ('.', '..') for v in repository.split('/')) and positive(repository_id),
                'scoped source merge coordinates required')
        self.token, self.repository, self.repository_id = token, repository, repository_id

    def merge(self, repository, pr, head, timeout=30):
        require(repository == self.repository and positive(pr) and sha(head) and
                type(timeout) is int and 0 < timeout <= 30, 'source merge scope or deadline differs')
        from merge_transport import isolated
        return isolated({'token': self.token, 'repository': repository, 'pr': pr, 'head': head, 'timeout': timeout}, timeout)
