"""Strict authority-side contracts. Local JSON is never proof of authority."""
from __future__ import annotations

import hashlib
import json
import re

CHECKS = ('AGENTIC-LIFECYCLE-DENIAL', 'AGENTIC-ASSURANCE-FAILURE',
          'AGENTIC-INSTALL-PRESERVATION', 'AGENTIC-AUTHORITY-SEPARATION')
POLICY_FIELDS = set(('schema_version repository_id repository target epoch app_id check_name '
                     'authority_repository_id authority_repository workflow workflow_sha '
                     'verifier_sha image checks reviewers coding_actors merge_actors '
                     'transitions limits').split())
SNAPSHOT_FIELDS = set(('repository_id pr head base merge epoch policy_digest verifier_sha '
                       'image authority_repository_id workflow_sha run_id run_attempt').split())


class Refusal(ValueError):
    """The requested operation has not established its prerequisites."""


def require(condition, message):
    if not condition:
        raise Refusal(message)


def object_fields(value, fields, label):
    require(isinstance(value, dict) and set(value) == set(fields),
            label + ': missing or unknown fields')


def positive(value):
    return type(value) is int and 0 < value < 2 ** 63


def sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{40}', value) is not None


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def loads(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    try:
        require(len(raw) <= 1024 * 1024, 'JSON exceeds limit')
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda x: (_ for _ in ()).throw(Refusal('nonfinite JSON')))
    except (ValueError, UnicodeError, RecursionError) as error:
        raise Refusal('invalid JSON: ' + str(error)) from error


def ids(values, label):
    require(isinstance(values, list) and values and all(positive(x) for x in values),
            label + ': nonempty numeric identity list required')
    require(len(values) == len(set(values)), label + ': duplicate identities')


def validate_policy(p):
    object_fields(p, POLICY_FIELDS, 'policy')
    require(type(p['schema_version']) is int and p['schema_version'] == 1, 'unsupported policy version')
    for key in ('repository_id', 'app_id', 'authority_repository_id'):
        require(positive(p[key]), 'invalid ' + key)
    require(p['repository_id'] != p['authority_repository_id'], 'authority must be separate')
    for key in ('repository', 'authority_repository'):
        require(isinstance(p[key], str) and re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', p[key]),
                'invalid ' + key)
    for key in ('target', 'epoch'):
        require(isinstance(p[key], str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}', p[key]),
                'invalid ' + key)
    require(isinstance(p['check_name'], str) and re.fullmatch(r'[A-Za-z0-9 _/-]{1,100}', p['check_name']),
            'invalid check name')
    require(isinstance(p['workflow'], str) and re.fullmatch(r'\.github/workflows/[A-Za-z0-9_-]+\.ya?ml', p['workflow']),
            'invalid authority workflow')
    for key in ('workflow_sha', 'verifier_sha'):
        require(sha(p[key]), 'immutable ' + key + ' required')
    require(isinstance(p['image'], str) and re.fullmatch(r'[A-Za-z0-9._/:-]+@sha256:[0-9a-f]{64}', p['image']),
            'digest-pinned image required')
    require(isinstance(p['checks'], list) and p['checks'] and
            all(isinstance(x, str) and re.fullmatch(r'[A-Z][A-Z0-9_-]{2,99}', x)
                for x in p['checks']), 'invalid or empty checks')
    require(len(p['checks']) == len(set(p['checks'])), 'duplicate checks')
    for key in ('reviewers', 'coding_actors', 'merge_actors'):
        ids(p[key], key)
    require(not set(p['coding_actors']) & (set(p['reviewers']) | set(p['merge_actors'])),
            'coding identity cannot approve or merge')
    require(isinstance(p['transitions'], list) and all(isinstance(x, str) and
            re.fullmatch('[0-9a-f]{64}', x) for x in p['transitions']), 'invalid transition digests')
    object_fields(p['limits'], ('seconds', 'memory_mb', 'processes', 'disk_mb'), 'limits')
    for key, maximum in [('seconds', 600), ('memory_mb', 4096), ('processes', 256), ('disk_mb', 1024)]:
        require(positive(p['limits'][key]) and p['limits'][key] <= maximum, 'invalid limit: ' + key)
    return p


def validate_snapshot(s, p):
    validate_policy(p)
    object_fields(s, SNAPSHOT_FIELDS, 'snapshot')
    for key in ('repository_id', 'pr', 'authority_repository_id', 'run_id', 'run_attempt'):
        require(positive(s[key]), 'invalid snapshot ' + key)
    for key in ('head', 'base', 'merge', 'verifier_sha', 'workflow_sha'):
        require(sha(s[key]), 'invalid snapshot ' + key)
    require(s['merge'] not in (s['head'], s['base']), 'distinct synthetic merge commit required')
    for key in ('repository_id', 'epoch', 'verifier_sha', 'image', 'authority_repository_id', 'workflow_sha'):
        require(s[key] == p[key], 'policy binding mismatch: ' + key)
    require(s['policy_digest'] == digest(p), 'policy digest mismatch')
    return s


def validate_report(report, p, current):
    validate_snapshot(current, p)
    object_fields(report, ('schema_version', 'snapshot', 'outcomes'), 'report')
    require(type(report['schema_version']) is int and report['schema_version'] == 1, 'unsupported report version')
    validate_snapshot(report['snapshot'], p)
    require(report['snapshot'] == current, 'stale or mismatched execution')
    outcomes = report['outcomes']
    require(isinstance(outcomes, list) and len(outcomes) == len(p['checks']), 'missing or duplicate outcomes')
    seen = set()
    for outcome in outcomes:
        object_fields(outcome, ('id', 'status'), 'outcome')
        require(isinstance(outcome['id'], str) and outcome['id'] in p['checks'] and
                outcome['id'] not in seen, 'unexpected or duplicate outcome')
        seen.add(outcome['id'])
        require(outcome['status'] == 'success', 'critical acceptance failed: ' + outcome['id'])
    return report
