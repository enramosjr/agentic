"""One create-only warm-broker rendezvous per fenced attempt; no authorization.

Queue time precedes administrative readback. Slow transport still fails closed.
The admin collector retains its own capability; no admin credential enters the
broker. A subsequent round requires a new, independently finalized operation.
"""
import copy
import re

from authority_github import current_snapshot
from authority_protocol import fingerprint, validate_deployment
from operation_fence import validate as validate_fence
from provenance import authenticated_document
from trusted_ci_policy import digest, object_fields, positive, require

READY_FIELDS = ('schema_version kind operation_id sequence configuration_revision deployment_digest '
    'repository_id target pr head base merge workflow_sha run_id attempt broker_job_id nonce issued expires').split()
RESPONSE_FIELDS = ('schema_version kind ready_digest nonce operation_id sequence configuration_revision '
                   'deployment_digest readback_started readback_completed expires result').split()
FACT_FIELDS = ('schema_version deployment_digest generation base controls_digest owners_digest access_digest '
               'automation_digest coding_bot_id required_checks isolation_established enforcement_active').split()


def validate_ready(value, binding, broker_job_id, now, historical=False):
    return _validate_ready(value, binding, broker_job_id, now, historical)


def _validate_ready(value, binding, broker_job_id, now, historical=False, admission=None):
    if admission is not None:
        from trial_controller import authenticated
        authenticated(admission, binding)
    object_fields(value, READY_FIELDS, 'broker ready request')
    d = validate_deployment(binding['deployment'])
    fence = validate_fence(binding['fence'])
    op = fence['pending']
    require((admission is not None or d['state'] == 'active') and op is not None and op['kind'] == 'merge' and
            type(value['schema_version']) is int and value['schema_version'] == 2 and
            value['kind'] == 'control-ready' and positive(broker_job_id) and value['broker_job_id'] == broker_job_id and
            type(value['sequence']) is int and value['sequence'] == fence['sequence'], 'current warm broker required')
    for key in ('operation_id', 'configuration_revision', 'deployment_digest', 'repository_id', 'target',
                'pr', 'head', 'base', 'merge', 'workflow_sha', 'run_id', 'attempt'):
        require(value[key] == op[key], 'broker ready binding differs: ' + key)
    require(binding['configuration_revision'] == op['configuration_revision'] and
            binding['deployment_digest'] == op['deployment_digest'] == digest(d) and
            op['repository_id'] == d['policy']['repository_id'] and op['target'] == d['policy']['target'] and
            op['workflow_sha'] == d['policy']['workflow_sha'], 'broker ready configuration differs')
    require(isinstance(value['nonce'], str) and re.fullmatch('[0-9a-f]{32}', value['nonce']) and
            positive(value['issued']) and positive(value['expires']) and type(now) is int,
            'bounded broker readiness coordinates required')
    observed = value['issued'] if historical else now
    require(op['created'] <= value['issued'] <= observed and value['expires'] - observed >= 60 and
            value['expires'] <= min(value['issued'] + 120, op['execution_deadline'], d['expires']),
            'broker readiness expired or too short')
    return value


def ready(binding, broker_job_id, nonce, now):
    return _ready(binding, broker_job_id, nonce, now)


def _ready(binding, broker_job_id, nonce, now, admission=None):
    fence = validate_fence(binding['fence'])
    op = fence['pending']
    require(op is not None and op['kind'] == 'merge', 'pending merge operation required')
    value = {k: op[k] for k in ('operation_id', 'configuration_revision', 'deployment_digest', 'repository_id',
             'target', 'pr', 'head', 'base', 'merge', 'workflow_sha', 'run_id', 'attempt')}
    value.update(schema_version=2, kind='control-ready', sequence=fence['sequence'], broker_job_id=broker_job_id,
        nonce=nonce, issued=now, expires=min(now + 120, op['execution_deadline'], binding['deployment']['expires']))
    return _validate_ready(value, binding, broker_job_id, now, admission=admission)


def validate_facts(facts, binding):
    return validate_source_facts(facts, binding['deployment'], binding['deployment_digest'],
                                 binding['fence']['pending']['base'])


def validate_source_facts(facts, d, deployment_digest, base):
    object_fields(facts, FACT_FIELDS, 'administrative control facts')
    require(type(facts['schema_version']) is int and facts['schema_version'] == 2 and
            facts['deployment_digest'] == deployment_digest and facts['generation'] == d['generation'] and
            facts['base'] == base and positive(facts['coding_bot_id']) and
            d['policy']['coding_actors'] == [facts['coding_bot_id']] and
            facts['isolation_established'] is False and facts['enforcement_active'] is False and
            all(fingerprint(facts[k]) for k in ('controls_digest', 'owners_digest', 'access_digest', 'automation_digest')),
            'administrative control facts differ')
    required = facts['required_checks']
    require(isinstance(required, list) and 0 < len(required) <= 100, 'complete required-check inventory required')
    for check in required:
        object_fields(check, ('context', 'integration_id'), 'required check source')
        require(isinstance(check['context'], str) and 0 < len(check['context']) <= 100 and
                not any(ord(c) < 32 for c in check['context']) and
                (check['integration_id'] is None or type(check['integration_id']) is int and check['integration_id'] >= 0),
                'required check source differs')
    pairs = {(c['context'], c['integration_id']) for c in required}
    require(len(pairs) == len(required) and (d['policy']['check_name'], d['policy']['app_id']) in pairs,
            'trusted issuer missing or duplicate required check')
    return facts


def response(request, binding, broker_job_id, started, completed, facts):
    return _response(request, binding, broker_job_id, started, completed, facts)


def _response(request, binding, broker_job_id, started, completed, facts, admission=None):
    _validate_ready(request, binding, broker_job_id, completed, admission=admission)
    validate_facts(facts, binding)
    require(type(started) is int and type(completed) is int and
            request['issued'] <= started <= completed <= started + 30, 'fresh administrative readback required')
    return dict(schema_version=2, kind='control-response', ready_digest=digest(request), nonce=request['nonce'],
        operation_id=request['operation_id'], sequence=request['sequence'],
        configuration_revision=request['configuration_revision'], deployment_digest=request['deployment_digest'],
        readback_started=started, readback_completed=completed, expires=request['expires'], result=facts)


def validate_response(value, request, binding, proof, now):
    return _validate_response(value, request, binding, proof, now)


def _validate_response(value, request, binding, proof, now, admission=None):
    object_fields(value, RESPONSE_FIELDS, 'administrative rendezvous response')
    _validate_ready(request, binding, request['broker_job_id'], now, admission=admission)
    require(type(value['schema_version']) is int and value['schema_version'] == 2 and
            value['kind'] == 'control-response' and value['ready_digest'] == digest(request) and
            all(value[k] == request[k] for k in ('nonce', 'operation_id', 'sequence',
                'configuration_revision', 'deployment_digest', 'expires')), 'administrative response binding differs')
    require(proof['role'] == 'controls' and proof['key'] == request['pr'] and
            proof['run_id'] == request['run_id'] and proof['attempt'] == request['attempt'] and
            all(positive(value[k]) for k in ('readback_started', 'readback_completed')) and
            max(request['issued'], proof['job_started']) <= value['readback_started'] <= value['readback_completed'] <=
            proof['artifact_created'] <= proof['job_completed'] <= now and
            now - value['readback_started'] <= 30, 'administrative response is stale or from another producer')
    validate_facts(value['result'], binding)
    return value


def read_ready(authority, read_binding, broker_job_id, locator, clock):
    return _read_ready(authority, read_binding, broker_job_id, locator, clock)


def _read_ready(authority, read_binding, broker_job_id, locator, clock, admission=None):
    from merge_receipts import ActionsReceipts
    store = ActionsReceipts._create(authority, read_binding, broker_job_id, clock, admission=admission)
    require(locator['kind'] == 'control-ready', 'exact broker readiness artifact required')
    value = store.authenticate(locator)
    return _validate_ready(value, read_binding(), broker_job_id, clock(), admission=admission)


def collect(admin, authority, read_binding, broker_job_id, ready_locator, clock):
    return _collect(admin, authority, read_binding, broker_job_id, ready_locator, clock)


def _collect(admin, authority, read_binding, broker_job_id, ready_locator, clock, admission=None):
    """Administrative producer: GET-only observation, after authenticated ready."""
    from controls import observe
    binding = copy.deepcopy(read_binding())
    request = _read_ready(authority, read_binding, broker_job_id, ready_locator, clock, admission)
    d, op = binding['deployment'], binding['fence']['pending']
    started = clock()
    first = current_snapshot(admin, d, op['pr'], op['run_id'], op['attempt'])
    require(all(first[k] == op[k] for k in ('pr', 'head', 'base', 'merge', 'workflow_sha', 'run_id')) and
            first['run_attempt'] == op['attempt'], 'candidate changed before admin observation')
    facts = observe(admin, d)
    require(current_snapshot(admin, d, op['pr'], op['run_id'], op['attempt']) == first,
            'candidate changed during admin observation')
    current = read_binding()
    require(all(current[k] == binding[k] for k in ('configuration_revision', 'deployment_digest', 'deployment', 'fence')),
            'configuration changed during admin observation')
    return _response(request, binding, broker_job_id, started, clock(), facts, admission)


def read_response(authority, binding, request, locator, now):
    return _read_response(authority, binding, request, locator, now)


def _read_response(authority, binding, request, locator, now, admission=None):
    proof = authenticated_document(authority, binding['deployment'], locator, 'controls', request['pr'], now)
    value = _validate_response(proof['document'], request, binding, proof, now, admission)
    return {'document': value, 'provenance': {k: v for k, v in proof.items() if k != 'document'},
            'controls_digest': digest({'document': value, 'provenance': {k: v for k, v in proof.items() if k != 'document'}}),
            'readback_started': value['readback_started'], 'readback_completed': value['readback_completed'],
            'expires': value['expires']}
