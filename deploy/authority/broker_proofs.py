"""Read all five own-App proofs for one exact pending broker attempt."""
import copy
import app_proofs
from authority_protocol import validate_deployment
from operation_fence import validate as validate_fence
from provenance import admit_job, authenticated_document
from trusted_ci_github import GitHub
from trusted_ci_policy import digest, object_fields, positive, require, validate_snapshot

FIELDS = ('schema_version kind operation_id sequence configuration_revision deployment_digest snapshot '
          'issued completed expires result').split()


def current_operation(binding, snapshot):
    d = validate_deployment(binding['deployment'])
    s = validate_snapshot(snapshot, d['policy'])
    fence = validate_fence(binding['fence'])
    op = fence['pending']
    require(d['state'] == 'active' and op is not None and op['kind'] == 'merge' and
            binding['configuration_revision'] == op['configuration_revision'] and
            binding['deployment_digest'] == op['deployment_digest'] == digest(d),
            'current pending broker configuration required')
    require(op['target'] == d['policy']['target'] and op['repository_id'] == s['repository_id'] and
            op['workflow_sha'] == s['workflow_sha'] and op['run_id'] == s['run_id'] and
            op['attempt'] == s['run_attempt'] and all(op[k] == s[k] for k in ('pr', 'head', 'base', 'merge')),
            'current pending broker candidate differs')
    return op


def _read(authority, binding, identities, snapshot, locators, now, request=None):
    d = binding['deployment']
    app_proofs.identity_record(d, identities)
    op = current_operation(binding, snapshot)
    object_fields(locators, ('admin', 'reader', 'issuer', 'coding', 'merge'), 'broker purpose locators')
    documents, provenance, valid_until = {}, {}, {}
    for purpose in ('admin', 'reader', 'issuer', 'coding', 'merge'):
        locator = locators[purpose]
        require(isinstance(locator, dict) and locator.get('run_id') == op['run_id'] and
                locator.get('attempt') == op['attempt'], 'purpose proof is from another broker attempt')
        proof = authenticated_document(authority, d, locator, 'final-proof' if request else 'proof', purpose, now)
        value = proof['document']
        object_fields(value, FIELDS + (['ready_digest', 'ready_nonce'] if request else []), 'broker purpose envelope')
        require(type(value['schema_version']) is int and value['schema_version'] == 2 and
                value['kind'] == ('broker-final-purpose-proof' if request else 'broker-purpose-proof') and
                value['operation_id'] == op['operation_id'] and
                type(value['sequence']) is int and value['sequence'] == binding['fence']['sequence'] and
                value['configuration_revision'] == binding['configuration_revision'] and
                value['deployment_digest'] == binding['deployment_digest'] and value['snapshot'] == snapshot,
                'broker purpose envelope binding differs')
        require(all(positive(value[k]) for k in ('issued', 'completed', 'expires')) and type(now) is int and
                max(op['created'], proof['job_started']) <= value['issued'] <= value['completed'] <=
                proof['artifact_created'] <= proof['job_completed'] <= now < value['expires'] <=
                min(value['issued'] + 300, d['expires'], op['execution_deadline']),
                'broker purpose envelope expired or interval differs')
        if request:
            require(value['ready_digest'] == digest(request) and value['ready_nonce'] == request['nonce'] and
                    request['issued'] <= value['issued'] and now - value['issued'] <= 30,
                    'final own-App readback is stale or from another readiness round')
        result = app_proofs.validate(value['result'], d, identities, purpose, binding['configuration_revision'], now)
        require(value['issued'] <= result['observed'] <= value['completed'] and
                value['expires'] <= result['expires'], 'purpose capability interval differs')
        documents[purpose] = value
        provenance[purpose] = {k: v for k, v in proof.items() if k != 'document'}
        valid_until[purpose] = value['expires']
    return {'documents': documents, 'provenance': provenance, 'valid_until': valid_until,
            'proofs_digest': digest({'documents': documents, 'provenance': provenance})}


def read(authority, binding, identities, snapshot, locators, now):
    """Provisional/publication proofs; never final revocation admission."""
    return _read(authority, binding, identities, snapshot, locators, now)


def read_final(authority, binding, identities, snapshot, request, locators, now):
    from control_rendezvous import validate_ready
    validate_ready(request, binding, request['broker_job_id'], now)
    return _read(authority, binding, identities, snapshot, locators, now, request=request)


def refresh(app_api, authority, registry, identities, purpose, environment, broker_job_id,
            ready_locator, clock, token_factory=GitHub):
    """Own-purpose producer, in its separate job; returns no token/root credential."""
    from control_rendezvous import read_ready, validate_ready
    require(purpose in ('admin', 'reader', 'issuer', 'coding', 'merge'), 'unknown final capability purpose')
    binding = copy.deepcopy(registry.binding())
    d = binding['deployment']
    app_proofs.identity_record(d, identities)
    op = binding['fence']['pending']
    require(op is not None and op['kind'] == 'merge', 'pending final capability operation required')
    admit_job(authority, d, environment, 'final proof (' + purpose + ')', clock())
    require(str(op['run_id']) == environment.get('GITHUB_RUN_ID') and
            str(op['attempt']) == environment.get('GITHUB_RUN_ATTEMPT'), 'final capability producer attempt differs')
    request = read_ready(authority, registry.binding, broker_job_id, ready_locator, clock)
    started = clock()
    result = app_proofs.prove(app_api, authority, d, identities, purpose, binding['configuration_revision'],
                              started, token_factory)
    completed = clock()
    validate_ready(request, binding, broker_job_id, completed)
    require(request['issued'] <= started <= completed <= request['issued'] + 30,
            'final capability readback exceeded the fresh window')
    current = registry.binding()
    require(all(current[k] == binding[k] for k in ('configuration_revision', 'deployment_digest', 'deployment', 'fence')),
            'operation changed during final capability refresh')
    p = d['policy']
    snapshot = dict(repository_id=p['repository_id'], pr=op['pr'], head=op['head'], base=op['base'], merge=op['merge'],
        epoch=p['epoch'], policy_digest=digest(p), verifier_sha=p['verifier_sha'], image=p['image'],
        authority_repository_id=p['authority_repository_id'], workflow_sha=p['workflow_sha'],
        run_id=op['run_id'], run_attempt=op['attempt'])
    current_operation(binding, snapshot)
    return dict(schema_version=2, kind='broker-final-purpose-proof', operation_id=op['operation_id'],
        sequence=binding['fence']['sequence'], configuration_revision=binding['configuration_revision'],
        deployment_digest=binding['deployment_digest'], snapshot=snapshot, issued=started, completed=completed,
        expires=min(result['expires'], op['execution_deadline']), result=result,
        ready_digest=digest(request), ready_nonce=request['nonce'])
