"""Strict adopter-owned authority contracts. Records alone never prove execution."""
from __future__ import annotations

import os
from pathlib import Path
import re
import tempfile

from trusted_ci_policy import (Refusal, digest, loads, object_fields, positive,
                               require, validate_policy, validate_report)

ADAPTERS = ('github-actions', 'aws', 'azure')
STATES = ('setup', 'qualification', 'active', 'blocked', 'revoked')
DEPLOYMENT_FIELDS = ('schema_version policy adapter account resources generation apps '
                     'state expires qualification').split()
EXECUTION_FIELDS = ('schema_version deployment_digest generation snapshot adapter '
                    'execution outcomes').split()


def fingerprint(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def validate_deployment(d):
    object_fields(d, DEPLOYMENT_FIELDS, 'deployment')
    require(type(d['schema_version']) is int and d['schema_version'] == 2,
            'unsupported deployment version')
    validate_policy(d['policy'])
    require(all(part not in ('.', '..') for key in ('repository', 'authority_repository')
                for part in d['policy'][key].split('/')), 'invalid repository path segment')
    require(d['adapter'] in ADAPTERS, 'unsupported adapter')
    require(isinstance(d['account'], str) and
            re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}', d['account']),
            'invalid account')
    if d['adapter'] == 'aws':
        require(re.fullmatch('[0-9]{12}', d['account']), 'AWS account ID required')
    if d['adapter'] == 'azure':
        require(re.fullmatch('[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', d['account']),
                'Azure subscription ID required')
    resources = d['resources']
    require(isinstance(resources, dict) and 0 < len(resources) <= 32 and
            all(isinstance(k, str) and re.fullmatch('[a-z][a-z_]{0,39}', k) and
                isinstance(v, str) and 0 < len(v) <= 2048 and
                not any(ord(c) < 32 for c in v) for k, v in resources.items()),
            'invalid resource inventory')
    require(resources.get('authority') == d['policy']['authority_repository'],
            'authority resource mismatch')
    object_fields(d['apps'], ('admin', 'issuer', 'coding', 'reader', 'merge'), 'App domains')
    require(all(positive(x) for x in d['apps'].values()) and
            len(set(d['apps'].values())) == 5 and
            d['apps']['issuer'] == d['policy']['app_id'], 'distinct purpose Apps required')
    require(positive(d['generation']) and positive(d['expires']), 'invalid generation or expiry')
    require(d['state'] in STATES, 'invalid lifecycle state')
    require(d['qualification'] is None or fingerprint(d['qualification']),
            'invalid qualification reference')
    require(d['state'] != 'active' or fingerprint(d['qualification']),
            'remote qualification required for active state')
    return d


def configuration_digest(deployment):
    """Qualification pin without the state/receipt self-reference; not proof."""
    validate_deployment(deployment)
    return digest({key: value for key, value in deployment.items()
                   if key not in ('state', 'generation', 'qualification')})


def validate_execution(report, deployment, current, now):
    validate_deployment(deployment)
    object_fields(report, EXECUTION_FIELDS, 'managed report')
    require(type(report['schema_version']) is int and report['schema_version'] == 2,
            'unsupported execution version')
    require(deployment['state'] in ('qualification', 'active') and
            type(now) is int and now < deployment['expires'], 'deployment is not current')
    require(report['deployment_digest'] == digest(deployment) and
            type(report['generation']) is int and
            report['generation'] == deployment['generation'] and
            report['adapter'] == deployment['adapter'], 'deployment binding mismatch')
    p = deployment['policy']
    # Reuse strict v1 obligation/snapshot checking without accepting v1 provenance.
    validate_report(dict(schema_version=1, snapshot=report['snapshot'],
                         outcomes=report['outcomes']), p, current)
    e = report['execution']
    object_fields(e, ('run_id', 'attempt', 'job_id', 'account', 'resource'), 'provider execution')
    require(all(positive(e[k]) for k in ('run_id', 'attempt', 'job_id')),
            'invalid execution identities')
    require(e['run_id'] == current['run_id'] and e['attempt'] == current['run_attempt'] and
            e['account'] == deployment['account'], 'execution binding mismatch')
    require(isinstance(e['resource'], str) and e['resource'] in deployment['resources'].values(),
            'execution resource not registered')
    return report


class Journal:
    """Local bootstrap recovery with CAS. Never an authoritative active receipt.

    A crashed writer leaves its lock for explicit trusted recovery, rather than
    guessing whether an operation holding privileged credentials is still live.
    """

    def __init__(self, path):
        self.path = Path(path).absolute()
        require(not self.path.is_symlink(), 'journal symlinks refused')

    def read(self):
        require(not self.path.is_symlink(), 'journal symlinks refused')
        if not self.path.exists():
            return None
        with self.path.open('rb') as stream:
            return validate_deployment(loads(stream.read(1024 * 1024 + 1)))

    def write(self, expected, value):
        import json
        validate_deployment(value)
        lock = self.path.with_suffix(self.path.suffix + '.lock')
        try:
            descriptor = os.open(str(lock), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as error:
            raise Refusal('another setup operation owns the journal lock') from error
        temporary = None
        try:
            os.close(descriptor)
            current = self.read()
            require((digest(current) if current is not None else None) == expected,
                    'journal generation changed; reread before retry')
            if current == value:
                return
            require(value['generation'] == (current['generation'] + 1 if current else 1),
                    'journal generation must advance exactly once')
            with tempfile.NamedTemporaryFile(mode='wb', dir=str(self.path.parent),
                                             prefix='.authority-', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write((json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode())
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(str(temporary), str(self.path))
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
            lock.unlink()
