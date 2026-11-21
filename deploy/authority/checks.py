"""V2 check intent/readback. Metadata validation is not parent authentication.

The trusted issuer must authenticate its job, evidence, task and current registry
before using the body. This module never loads credentials or publishes checks.
"""
from datetime import datetime, timezone

from authority_protocol import fingerprint, validate_deployment
from operation_fence import operation as validate_operation
from provenance import validate_evidence
from trusted_ci_deployment import timestamp
from trusted_ci_policy import digest, object_fields, positive, require, sha, validate_snapshot

FIELDS = ('configuration_revision operation sequence issuer_installation_id evidence_job_id evidence_digest task_digest').split()


def intent(deployment, snapshot, coordinates, now):
    d = validate_deployment(deployment)
    s = validate_snapshot(snapshot, d['policy'])
    object_fields(coordinates, FIELDS, 'publication coordinates')
    op = validate_operation(coordinates['operation'])
    require(type(now) is int and 0 < now < d['expires'] and d['state'] in ('qualification', 'active') and
            op['kind'] == 'merge' and op['created'] <= now < op['execution_deadline'],
            'current publication operation required')
    require(sha(coordinates['configuration_revision']) and positive(coordinates['sequence']) and
            positive(coordinates['issuer_installation_id']) and positive(coordinates['evidence_job_id']) and
            fingerprint(coordinates['evidence_digest']) and fingerprint(coordinates['task_digest']),
            'exact publication identities and evidence required')
    require(op['configuration_revision'] == coordinates['configuration_revision'] and
            op['deployment_digest'] == digest(d) and op['repository_id'] == s['repository_id'] and
            op['target'] == d['policy']['target'] and op['workflow_sha'] == s['workflow_sha'] and
            op['run_id'] == s['run_id'] and op['attempt'] == s['run_attempt'] and
            all(op[key] == s[key] for key in ('pr', 'head', 'base', 'merge')), 'publication operation binding differs')
    value = dict(schema_version=2, configuration_revision=coordinates['configuration_revision'],
        deployment_digest=digest(d), generation=d['generation'], snapshot=s,
        operation_id=op['operation_id'], sequence=coordinates['sequence'],
        issuer_installation_id=coordinates['issuer_installation_id'],
        evidence_job_id=coordinates['evidence_job_id'],
        evidence_digest=coordinates['evidence_digest'], task_digest=coordinates['task_digest'])
    return 'agentic-v2:' + digest(value)


def publication_body(deployment, snapshot, evidence, coordinates, now):
    external = intent(deployment, snapshot, coordinates, now)
    require(digest(evidence) == coordinates['evidence_digest'], 'publication evidence digest differs')
    validate_evidence(evidence, deployment, snapshot, coordinates['configuration_revision'],
                      coordinates['evidence_job_id'], now)
    p = deployment['policy']
    clock = datetime.fromtimestamp(now, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return {'name': p['check_name'], 'head_sha': snapshot['merge'], 'external_id': external,
        'status': 'completed', 'conclusion': 'success', 'started_at': clock, 'completed_at': clock,
        'details_url': 'https://github.com/' + p['authority_repository'] + '/actions/runs/' +
            str(snapshot['run_id']) + '/attempts/' + str(snapshot['run_attempt']),
        'output': {'title': 'Independent critical acceptance',
                   'summary': 'Completed the configured obligations for this exact candidate.'}}


def current(api, deployment, snapshot, coordinates, now):
    """Read-only; matching name alone, another App, or an older intent cannot pass."""
    external = intent(deployment, snapshot, coordinates, now)
    p = deployment['policy']
    entries = api.pages('/repos/' + p['repository'] + '/commits/' + snapshot['merge'] +
                        '/check-runs?filter=all', 'check_runs')
    matches = [entry for entry in entries if entry.get('name') == p['check_name'] and
               entry.get('app', {}).get('id') == p['app_id'] and entry.get('external_id') == external]
    require(len(matches) == 1, 'missing or ambiguous current issuer check')
    check = matches[0]
    require(positive(check['id']) and check.get('head_sha') == snapshot['merge'] and
            check.get('status') == 'completed' and check.get('conclusion') == 'success',
            'exact current issuer acceptance did not pass')
    started = int(timestamp(check['started_at']).timestamp())
    completed = int(timestamp(check['completed_at']).timestamp())
    require(coordinates['operation']['created'] <= started <= completed <= now,
            'issuer check predates its operation or has a future completion')
    return {'check_id': check['id'], 'external_id': external, 'observed': now,
            'expires': min(deployment['expires'], coordinates['operation']['execution_deadline'])}
