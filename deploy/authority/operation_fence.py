"""Strict durable operation records. Deadlines never release a pending fence."""
import re

from authority_protocol import fingerprint, validate_deployment
from trusted_ci_policy import digest, object_fields, positive, require, sha

FIELDS = ('kind operation_id scope_digest repository_id target configuration_revision deployment_digest '
          'workflow_sha run_id attempt created execution_deadline pr head base merge').split()


def operation(value):
    setup = isinstance(value, dict) and 'setup' in value
    object_fields(value, FIELDS + (['setup'] if setup else []), 'pending authority operation')
    require(value['kind'] in ('merge', 'configuration') and
            isinstance(value['operation_id'], str) and re.fullmatch('[0-9a-f]{32}', value['operation_id']),
            'invalid operation identity')
    require(all(positive(value[k]) for k in ('repository_id', 'created', 'execution_deadline')) and
            value['created'] < value['execution_deadline'] <= value['created'] + 3600,
            'invalid operation deadline')
    if setup:
        object_fields(value['setup'], ('operator_id', 'installation_id', 'approval_digest'), 'trusted setup owner')
        require(value['kind'] == 'configuration' and value['run_id'] is None and value['attempt'] is None and
                positive(value['setup']['operator_id']) and positive(value['setup']['installation_id']) and
                fingerprint(value['setup']['approval_digest']), 'configuration-only native setup owner required')
    else:
        require(positive(value['run_id']) and positive(value['attempt']), 'exact workflow execution owner required')
    # The pending operation is acquired before bounded verification and grants
    # no merge right. merge_window separately caps actual authorization at 300s.
    require(sha(value['configuration_revision']) and fingerprint(value['deployment_digest']) and
            sha(value['workflow_sha']) and isinstance(value['target'], str) and
            re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,99}', value['target']), 'invalid operation binding')
    if value['kind'] == 'merge':
        require(value['scope_digest'] is None and positive(value['pr']) and all(sha(value[k]) for k in ('head', 'base', 'merge')),
                'exact merge candidate required')
    else:
        require(fingerprint(value['scope_digest']) and all(value[k] is None for k in ('pr', 'head', 'base', 'merge')),
                'configuration requires approved scope and cannot bind a merge candidate')
    return value


def terminal(value):
    object_fields(value, ('operation_id', 'sequence', 'kind', 'receipt_digest'), 'terminal operation receipt')
    require(isinstance(value['operation_id'], str) and re.fullmatch('[0-9a-f]{32}', value['operation_id']) and
            positive(value['sequence']) and fingerprint(value['receipt_digest']) and
            value['kind'] in ('merged', 'not-submitted', 'configuration-complete'), 'invalid terminal receipt')
    return value


def validate(value):
    retained = isinstance(value, dict) and value.get('schema_version') == 3
    object_fields(value, ('schema_version', 'sequence', 'pending', 'completed', 'contexts') +
                  (('retained',) if retained else ()), 'operation fence')
    require(type(value['schema_version']) is int and value['schema_version'] in (2, 3) and
            type(value['sequence']) is int and value['sequence'] >= 0 and isinstance(value['completed'], list),
            'invalid fence version or sequence')
    completed = value['completed']
    for item in completed:
        terminal(item)
    require(len(completed) == len({v['operation_id'] for v in completed}) and
            [v['sequence'] for v in completed] == list(range(1, len(completed) + 1)),
            'ambiguous completed operation history')
    pending = value['pending']
    if pending is not None:
        operation(pending)
        require(pending['operation_id'] not in {v['operation_id'] for v in completed}, 'operation already consumed')
    if retained:
        handover(value)
    else:
        require(value['sequence'] == len(completed) + (pending is not None), 'fence sequence differs from operation history')
    contexts = value['contexts']
    require(isinstance(contexts, list), 'context history required')
    for item in contexts:
        object_fields(item, ('epoch', 'check_name', 'activated'), 'used check context')
        require(isinstance(item['epoch'], str) and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,99}', item['epoch']) and
                isinstance(item['check_name'], str) and re.fullmatch('[A-Za-z0-9 _/-]{1,100}', item['check_name']) and
                type(item['activated']) is bool, 'invalid context history')
    require(len(contexts) == len({v['epoch'] for v in contexts}) == len({v['check_name'] for v in contexts}),
            'epoch and required check context must never be reused')
    return value


def handover(value):
    """Validate the transient native owner, never authorize its remote effects."""
    retained, config = value['retained'], value['pending']
    object_fields(retained, ('sequence', 'operation', 'binding', 'intent_digest'), 'retained native merge')
    before = retained['binding']
    object_fields(before, ('deployment', 'configuration_revision', 'deployment_digest', 'branch_head',
                          'branch_exists', 'software_revision', 'fence'), 'retained native binding')
    require(isinstance(before['fence'], dict) and before['fence'].get('schema_version') == 2,
            'handover requires an original version-two binding')
    old_fence = validate(before['fence'])
    old = operation(retained['operation'])
    d = validate_deployment(before['deployment'])
    p = d['policy']
    require(before['branch_exists'] is True and sha(before['branch_head']) and sha(before['configuration_revision']) and
            before['software_revision'] == p['workflow_sha'] and before['deployment_digest'] == digest(d) and
            d['state'] == 'qualification' and d['qualification'] is None and old_fence['contexts'] and
            old_fence['contexts'][-1]['epoch'] == p['epoch'] and old_fence['contexts'][-1]['check_name'] == p['check_name'],
            'retained native configuration differs')
    require(old['kind'] == 'merge' and old == old_fence['pending'] and type(retained['sequence']) is int and
            retained['sequence'] == old_fence['sequence'] == len(value['completed']) + 1 and
            value['completed'] == old_fence['completed'] and fingerprint(retained['intent_digest']),
            'retained unresolved merge or history differs')
    require(config is not None and config['kind'] == 'configuration' and 'setup' in config and
            config['operation_id'] != old['operation_id'] and value['sequence'] == retained['sequence'] + 1 and
            old['created'] <= config['created'] < config['execution_deadline'] <= min(old['execution_deadline'], d['expires']),
            'single native handover owner and original deadline required')
    for key in ('configuration_revision', 'deployment_digest', 'workflow_sha', 'repository_id', 'target'):
        expected = before[key] if key in before else p[key]
        require(old[key] == config[key] == expected, 'retained handover coordinate differs: ' + key)
    require(value['contexts'][:len(old_fence['contexts'])] == old_fence['contexts'] and
            len(value['contexts']) in (len(old_fence['contexts']), len(old_fence['contexts']) + 1) and
            (len(value['contexts']) == len(old_fence['contexts']) or value['contexts'][-1]['activated'] is False),
            'retained context history changed')
    return retained


def empty(deployment=None):
    contexts = [] if deployment is None else [dict(epoch=deployment['policy']['epoch'],
        check_name=deployment['policy']['check_name'], activated=deployment['state'] == 'active')]
    return {'schema_version': 2, 'sequence': 0, 'pending': None, 'completed': [], 'contexts': contexts}
