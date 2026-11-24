"""Render adopter-owned AWS/Azure infrastructure without credentials or deployment.

Rendering is not provider validation, hosted execution or enforcement evidence.
No cloud CLI, metadata endpoint, administrator token or model service is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.ai' / 'scripts'))
from trusted_ci_policy import Refusal, digest, require
from cloud import aws_template, azure_template, preview, validate


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode('utf-8')


def render(config, destination):
    validate(config)
    destination = Path(destination)
    template_name = 'aws-cloudformation.json' if config['adapter'] == 'aws' else 'azure-arm.json'
    template = aws_template(config) if config['adapter'] == 'aws' else azure_template(config)
    resources = preview(config)
    resources.update(state='unqualified', enforcement_qualified=False)
    payloads = {template_name: encoded(template), 'preview.json': encoded(resources)}
    manifest = {'schema_version': 1, 'kind': 'authority-infrastructure-render',
                'adapter': config['adapter'], 'account': config['account'],
                'region': config['region'], 'authority': config['authority'],
                'deployment': config['deployment'], 'configuration_digest': digest(config),
                'state': 'unqualified', 'enforcement_qualified': False,
                'files': {name: hashlib.sha256(raw).hexdigest() for name, raw in payloads.items()}}
    # Never adopt or overwrite output belonging to an earlier invocation or user.
    # The manifest is written last, so partial output is not a completed render.
    require(not destination.exists(), 'render output already exists; refusing to overwrite')
    try:
        destination.mkdir(mode=0o700)
    except FileExistsError:
        raise Refusal('render output was created by another operation') from None
    for name, raw in payloads.items():
        with (destination / name).open('xb') as stream:
            stream.write(raw)
    with (destination / 'manifest.json').open('xb') as stream:
        stream.write(encoded(manifest))
    return {'kind': manifest['kind'], 'adapter': config['adapter'], 'account': config['account'],
            'directory': str(destination.resolve()), 'template': template_name,
            'template_sha256': manifest['files'][template_name],
            'state': 'unqualified', 'enforcement_qualified': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adapter', choices=('aws', 'azure'), required=True)
    parser.add_argument('--account', required=True, help='adopter AWS account ID or Azure subscription ID')
    parser.add_argument('--region', required=True)
    parser.add_argument('--authority', required=True, help='adopter-owned GitHub OWNER/AUTHORITY')
    parser.add_argument('--branch', default='main')
    parser.add_argument('--deployment', help='optional owned resource prefix; otherwise derived from selection')
    parser.add_argument('--output', type=Path, required=True, help='NEW output directory')
    args = parser.parse_args(argv)
    c = {key: getattr(args, key) for key in ('adapter', 'account', 'region', 'authority', 'branch')}
    c['deployment'] = args.deployment or 'agentic-' + digest(c)[:16]
    try:
        print(json.dumps(render(c, args.output), sort_keys=True))
        return 0
    except (Refusal, OSError, ValueError) as error:
        message = str(error) if isinstance(error, Refusal) else 'could not write cloud rendering'
        print(json.dumps({'state': 'unverified', 'error': message}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
