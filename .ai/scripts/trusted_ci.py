#!/usr/bin/env python3
"""Trusted CI authority operations and read-only deployment diagnostics (Python 3.9+)."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True

from trusted_ci_policy import Refusal, loads, require, validate_policy
from trusted_ci_github import GitHub, current_snapshot, publish, repo_path


def read_policy(path):
    return validate_policy(loads(Path(path).read_bytes()))


def authority_environment(p, run, attempt):
    require(os.environ.get('GITHUB_REPOSITORY_ID') == str(p['authority_repository_id']) and
            os.environ.get('GITHUB_SHA') == p['workflow_sha'] and
            os.environ.get('GITHUB_RUN_ID') == str(run) and
            os.environ.get('GITHUB_RUN_ATTEMPT') == str(attempt), 'not the configured authority execution')


def main(argv=None, api_factory=GitHub):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    audit = sub.add_parser('verify-deployment', help='read-only; local output never authorizes a merge')
    audit.add_argument('--live', action='store_true', required=True)
    audit.add_argument('--config', type=Path, default=Path('.agentic/trusted-ci.json'))
    audit.add_argument('--json', action='store_true')
    qualifier = sub.add_parser('qualify-host', help='trusted authority only; mutates an explicitly disposable target')
    qualifier.add_argument('--policy', type=Path, required=True)
    qualifier.add_argument('--reference-policy', type=Path, required=True)
    qualifier.add_argument('--manifest', type=Path, required=True)
    qualifier.add_argument('--output', type=Path, required=True)
    qualifier.add_argument('--run-id', type=int, required=True)
    qualifier.add_argument('--attempt', type=int, required=True)
    for name in ('discover', 'verify', 'publish'):
        cmd = sub.add_parser(name)
        cmd.add_argument('--policy', type=Path, required=True)
        if name != 'discover':
            cmd.add_argument('--pr', type=int, required=True)
            cmd.add_argument('--run-id', type=int, required=True)
            cmd.add_argument('--attempt', type=int, required=True)
        if name == 'verify':
            cmd.add_argument('--output', type=Path, required=True)
            cmd.add_argument('--runtime', choices=['docker', 'podman'])
    args = parser.parse_args(argv)
    try:
        token = os.environ.get('AGENTIC_READ_TOKEN') or os.environ.get('GH_TOKEN', '')
        api = api_factory(token)
        if args.command == 'verify-deployment':
            from trusted_ci_deployment import inspect
            p = read_policy(args.config)
            result = inspect(api, p)
            print(json.dumps(result, sort_keys=True))
            return 0
        p = read_policy(args.policy)
        if args.command == 'qualify-host':
            from trusted_ci_deployment import inspect, variable
            from trusted_ci_qualification import probe
            reference = read_policy(args.reference_policy)
            authority_environment(reference, args.run_id, args.attempt)
            require(p['repository_id'] != reference['repository_id'] and
                    str(p['repository_id']) == variable(api, reference, 'AGENTIC_QUALIFICATION_REPOSITORY_ID'),
                    'qualification target not independently allowlisted')
            for key in ('checks', 'app_id', 'image', 'workflow_sha', 'verifier_sha', 'limits', 'coding_actors', 'reviewers', 'merge_actors'):
                require(p[key] == reference[key], 'qualification policy differs: ' + key)
            reference_state = inspect(api, reference, qualification=False)
            fixture_state = inspect(api, p, qualification=False, policy_variable='AGENTIC_QUALIFICATION_POLICY_JSON')
            require(reference_state['semantics_digest'] == fixture_state['semantics_digest'],
                    'disposable target controls differ from production')
            controls = reference_state['controls_digest']
            coding = api_factory(os.environ.get('AGENTIC_QUALIFICATION_CODING_TOKEN', ''))
            merger = api_factory(os.environ.get('AGENTIC_QUALIFICATION_MERGE_TOKEN', ''))
            receipt = probe(api, coding, merger, p, loads(args.manifest.read_bytes()), controls)
            args.output.write_text(json.dumps(receipt, sort_keys=True) + '\n', encoding='utf-8')
            print('Hosted qualification complete; production branch was not modified.')
        elif args.command == 'discover':
            require(api.get(repo_path(p))['id'] == p['repository_id'], 'allowlisted repository identity mismatch')
            prs = api.pages(repo_path(p) + '/pulls?state=open')
            numbers = [pr['number'] for pr in prs if not pr['draft'] and pr['base']['ref'] == p['target']]
            require(all(type(n) is int and n > 0 for n in numbers), 'invalid discovery result')
            print(json.dumps(numbers))
        else:
            authority_environment(p, args.run_id, args.attempt)
            if args.command == 'publish':
                from trusted_ci_deployment import inspect
                inspect(api, p, qualification=False,
                        policy_variable=os.environ.get('AGENTIC_POLICY_VARIABLE', 'AGENTIC_POLICY_JSON'))
                issuer = api_factory(os.environ.get('AGENTIC_ISSUER_TOKEN', ''))
                result = publish(api, issuer, p, args.pr, args.run_id, args.attempt)
                print(json.dumps(dict(check_id=result['id'], state='critical acceptance published; host approval required')))
            else:
                from trusted_ci_github import authority_run
                from trusted_ci_sandbox import Sandbox, extract
                from trusted_ci_controller import verify
                authority_run(api, p, args.run_id, args.attempt)
                current = current_snapshot(api, p, args.pr, args.run_id, args.attempt)
                raw = api.fetch(repo_path(p) + '/tarball/' + current['merge'], binary=True, limit=64 * 1024 * 1024)
                with tempfile.TemporaryDirectory(prefix='agentic-authority-') as directory:
                    source = extract(raw, Path(directory) / 'source')
                    with Sandbox(source, p, args.runtime) as box:
                        result = verify(box, p, current, capture_failure=True)
                require(current_snapshot(api, p, args.pr, args.run_id, args.attempt) == current,
                        'candidate changed during verification')
                args.output.write_text(json.dumps(result, sort_keys=True) + '\n', encoding='utf-8')
                if any(o['status'] != 'success' for o in result['outcomes']):
                    print('Critical acceptance failed; snapshot-bound negative evidence recorded.')
                    return 1
                print('Critical acceptance complete; report is not merge authorization.')
        return 0
    except (Refusal, OSError, KeyError, TypeError, ValueError) as exc:
        # Do not relay remote/candidate text or credentials into workflow commands.
        message = str(exc) if isinstance(exc, Refusal) else type(exc).__name__
        print(json.dumps(dict(state='unverified', error=message)), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
