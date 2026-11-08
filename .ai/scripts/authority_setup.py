#!/usr/bin/env python3
"""Installed stdlib authority client. This build permits only local operations."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

import authority_release as release
from authority_protocol import validate_deployment
from authority_status import inspect_local
from trusted_ci_policy import Refusal, digest, loads, require


def read_document(path):
    with Path(path).open('rb') as stream:
        return loads(stream.read(1024 * 1024 + 1))


def local_plan(d):
    validate_deployment(d)
    result = inspect_local(d)
    result.update(kind='local-authority-projection', projection_only=True,
        cannot_authorize_provisioning=True, policy_digest=digest(d['policy']),
        target=d['policy']['target'], account=d['account'],
        workflow_revision=d['policy']['workflow_sha'], verifier_revision=d['policy']['verifier_sha'],
        credential_domains=['admin', 'reader', 'issuer', 'coding', 'merge'],
        approvals_required=['policy', 'protections', 'candidate review'],
        phases=['discover', 'approve', 'provision', 'readback', 'qualify', 'activate'])
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('status', 'plan', 'verify-local'):
        command = commands.add_parser(name)
        command.add_argument('--deployment', type=Path, required=name != 'status')
        if name == 'verify-local':
            command.add_argument('--lease', type=Path)
            command.add_argument('--report', type=Path)
    held = {'connect': 'bootstrap', 'setup': 'provision', 'repair': 'provision',
            'upgrade': 'provision', 'destroy': 'provision', 'qualify': 'qualify-live',
            'publish': 'publish', 'activate': 'activate', 'task-start': 'protected-run',
            'merge': 'broker-merge'}
    for name in held:
        command = commands.add_parser(name)
        command.add_argument('--deployment', type=Path)
        command.add_argument('--adapter', choices=('github-actions', 'aws', 'azure', 'all'))
        if name == 'qualify':
            command.add_argument('--live', action='store_true', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command in held:
            release.authorize(held[args.command])
            raise Refusal('remote authority coordinator is not implemented in this build')
        else:
            release.authorize('verify-local' if args.command == 'verify-local' else 'inspect-local')
        d = read_document(args.deployment) if args.deployment else None
        if args.command == 'plan':
            result = local_plan(d)
        else:
            result = inspect_local(d)
        if args.command == 'verify-local':
            require(bool(args.lease) == bool(args.report), 'lease and report must be provided together')
            result['kind'] = 'local-structure-verification'
            if args.lease:
                from authority_jobs import check_result
                lease = read_document(args.lease)
                require(lease['deployment'] == d, 'lease deployment differs from selected record')
                check_result(read_document(args.report), lease, int(time.time()))
                result['local_report_bindings_valid'] = True
            result['hosted_execution_verified'] = False
        print(json.dumps(result, sort_keys=True))
        return 0
    except release.Held:
        print(json.dumps(release.status(), sort_keys=True))
        return 1
    except (Refusal, OSError, ValueError, KeyError, TypeError) as error:
        message = str(error) if isinstance(error, Refusal) else 'invalid or unavailable local authority document'
        print(json.dumps({'state': 'blocked', 'enforcement_active': False,
                          'remote_verified': False, 'error': message}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
