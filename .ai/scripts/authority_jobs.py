"""Cloud job leases and exact-result fencing; URL shape is not provider proof."""
from __future__ import annotations

import copy
import re
from urllib.parse import unquote, urlsplit

from authority_protocol import fingerprint, validate_deployment, validate_execution
from trusted_ci_policy import (digest, object_fields, positive, require,
                               validate_snapshot)

LEASE_FIELDS = ('schema_version id deployment snapshot job_id issued expires objects').split()


def artifact_host(d):
    r = d['resources']
    if d['adapter'] == 'aws':
        require(re.fullmatch('[a-z0-9][a-z0-9-]{1,61}[a-z0-9]', r.get('bucket', '')),
                'registered AWS bucket required')
        require(re.fullmatch('[a-z]{2}-[a-z]+-[0-9]+', r.get('region', '')), 'registered AWS region required')
        host = r['bucket'] + '.s3.' + r['region'] + '.amazonaws.com'
    else:
        require(d['adapter'] == 'azure' and re.fullmatch('[a-z0-9]{3,24}', r.get('storage_account', '')),
                'registered Azure storage account required')
        host = r['storage_account'] + '.blob.core.windows.net'
    require(r.get('artifact_host') == host, 'registered artifact host mismatch')
    return host


def validate_lease(lease, now):
    object_fields(lease, LEASE_FIELDS, 'cloud lease')
    require(type(lease['schema_version']) is int and lease['schema_version'] == 2, 'unsupported lease version')
    require(isinstance(lease['id'], str) and re.fullmatch('[0-9a-f]{32}', lease['id']), 'invalid lease identity')
    d = validate_deployment(lease['deployment'])
    require(d['adapter'] in ('aws', 'azure'), 'cloud adapter lease required')
    validate_snapshot(lease['snapshot'], d['policy'])
    require(positive(lease['job_id']) and type(now) is int and positive(lease['issued']) and
            positive(lease['expires']) and lease['issued'] <= now < lease['expires'] <= d['expires'] and
            lease['expires'] - lease['issued'] <= 600, 'expired, future or overlong job lease')
    require(d['state'] in ('qualification', 'active'), 'deployment does not admit verification')
    require(d['resources'].get('compute_scope'), 'registered compute scope required')
    if d['adapter'] == 'aws':
        require(d['resources']['compute_scope'].startswith('arn:aws:cloudformation:' +
                d['resources']['region'] + ':' + d['account'] + ':stack/'), 'AWS compute scope account mismatch')
    else:
        require(d['resources']['compute_scope'].lower() == ('/subscriptions/' + d['account'] +
                '/resourceGroups/' + d['resources'].get('resource_group', '')).lower(),
                'Azure compute scope account mismatch')
    host = artifact_host(d)
    object_fields(lease['objects'], ('bundle', 'candidate', 'report'), 'job objects')
    for key, filename in (('bundle', 'bundle.tgz'), ('candidate', 'candidate.tgz'), ('report', 'report.json')):
        value = lease['objects'][key]
        object_fields(value, ('url',) if key == 'report' else ('url', 'sha256'), 'job object')
        require(isinstance(value['url'], str) and len(value['url']) <= 8192 and
                not any(ord(c) < 32 for c in value['url']), 'invalid storage URL')
        url = urlsplit(value['url'])
        require(url.scheme == 'https' and url.hostname == host and url.port in (None, 443) and
                not url.username and not url.password and not url.fragment and
                unquote(url.path) == '/jobs/' + lease['id'] + '/' + filename,
                'job object escapes registered storage namespace')
        if key != 'report':
            require(fingerprint(value['sha256']), 'job input digest required')
        if key == 'bundle':
            require(fingerprint(d['resources'].get('bundle_sha')) and
                    value['sha256'] == d['resources']['bundle_sha'],
                    'trusted bundle differs from approved deployment')
    return lease


def new_lease(deployment, snapshot, job_id, nonce, now, objects):
    lease = dict(schema_version=2, id=nonce, deployment=copy.deepcopy(deployment),
                 snapshot=copy.deepcopy(snapshot), job_id=job_id, issued=now,
                 expires=min(now + 600, deployment['expires']), objects=copy.deepcopy(objects))
    return validate_lease(lease, now)


def result(lease, outcomes):
    d, s = lease['deployment'], lease['snapshot']
    return {'schema_version': 2, 'lease_digest': digest(lease), 'report': {
        'schema_version': 2, 'deployment_digest': digest(d), 'generation': d['generation'],
        'snapshot': copy.deepcopy(s), 'adapter': d['adapter'],
        'execution': {'run_id': s['run_id'], 'attempt': s['run_attempt'], 'job_id': lease['job_id'],
                      'account': d['account'], 'resource': d['resources']['compute_scope']},
        'outcomes': copy.deepcopy(outcomes)}}


def check_result(value, lease, now):
    validate_lease(lease, now)
    object_fields(value, ('schema_version', 'lease_digest', 'report'), 'job result')
    require(type(value['schema_version']) is int and value['schema_version'] == 2 and
            value['lease_digest'] == digest(lease), 'stale or substituted job result')
    report = validate_execution(value['report'], lease['deployment'], lease['snapshot'], now)
    require(report['execution']['job_id'] == lease['job_id'] and
            report['execution']['resource'] == lease['deployment']['resources']['compute_scope'],
            'job execution identity changed')
    return report
