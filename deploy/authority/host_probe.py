"""Real disk/OCI host admission probe. This is not remote governance evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import secrets
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.ai' / 'scripts'))
from trusted_ci_policy import CHECKS, Refusal, require, validate_policy
from trusted_ci_sandbox import Sandbox, command
from disk import WorkDisk


def probe(image, runtime):
    # These local identities are intentionally not a deployment/qualification
    # record. No GitHub token, rule or required check is created by this probe.
    p = validate_policy(dict(schema_version=1, repository_id=1, repository='local/probe',
        target='main', epoch='host-probe', app_id=1, check_name='host probe',
        authority_repository_id=2, authority_repository='local/authority',
        workflow='.github/workflows/authority.yml', workflow_sha='1' * 40,
        verifier_sha='2' * 40, image=image, checks=list(CHECKS), reviewers=[1],
        coding_actors=[2], merge_actors=[1], transitions=[],
        limits={'seconds': 60, 'memory_mb': 256, 'processes': 64, 'disk_mb': 128}))
    names = []
    with tempfile.TemporaryDirectory(prefix='agentic-host-source-') as directory:
        source = Path(directory)
        (source / 'marker').write_text('immutable source', encoding='utf-8')
        name = 'agentic-' + secrets.token_hex(12)
        names.append(name)
        with WorkDisk(name, 128, runtime, formatter_image=image) as work:
            with Sandbox(source, p, runtime=runtime, work_volume=work.name) as box:
                code, output = box.run(['python3', '-I', '-c',
                    'import errno,os,pathlib; '
                    'assert pathlib.Path("/source/marker").read_text()=="immutable source"; '
                    'assert os.statvfs("/work").f_blocks*os.statvfs("/work").f_frsize<=128*1024*1024; '
                    'f=open("/work/full","wb",buffering=0); '
                    '\ntry:\n for _ in range(140): f.write(b"x"*1024*1024)'
                    '\nexcept OSError as e:\n assert e.errno==errno.ENOSPC'
                    '\nelse:\n raise AssertionError("work disk exceeded hard limit")'
                    '\nfinally:\n f.close()\n'
                    'assert os.getuid()==65534; print("bounded-and-unprivileged")'], cwd='/work')
                require(code == 0 and output.strip() == 'bounded-and-unprivileged',
                        'real bounded-capacity execution failed')
        # Deliberately oversized backing must fail for the capacity criterion,
        # rather than a generic missing engine, network or credential failure.
        name = 'agentic-' + secrets.token_hex(12)
        names.append(name)
        with WorkDisk(name, 256, runtime, formatter_image=image) as work:
            try:
                with Sandbox(source, p, runtime=runtime, work_volume=work.name):
                    raise Refusal('oversized disk was admitted')
            except Refusal as error:
                require('hard-sized within policy limit' in str(error),
                        'oversized-disk control failed for an unexpected reason')
    for name in names:
        code, output = command([runtime, 'volume', 'ls', '--format', '{{.Name}}',
                                '--filter', 'name=^' + name + '$'])
        require(code == 0 and not output.strip(), 'host probe leaked its work volume')
    return {'kind': 'local-host-admission', 'state': 'passed', 'runtime': runtime,
            'image': image, 'capacity_denial': True, 'cleanup': 'passed'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--runtime', choices=('docker', 'podman'), default='docker')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(probe(args.image, args.runtime), sort_keys=True))
        return 0
    except (Refusal, OSError, ValueError) as error:
        print(json.dumps({'state': 'unverified', 'error': str(error)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
