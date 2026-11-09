"""Build a deterministic held authority runtime, without credentials or deployment."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.ai/scripts'))
from trusted_ci_policy import Refusal, require

FILES = (
    '.ai/scripts/authority_release.py', '.ai/scripts/authority_jobs.py', '.ai/scripts/authority_private.py',
    '.ai/scripts/authority_protocol.py', '.ai/scripts/authority_github.py',
    '.ai/scripts/trusted_ci_policy.py', '.ai/scripts/trusted_ci_github.py',
    '.ai/scripts/trusted_ci_deployment.py', '.ai/scripts/trusted_ci_qualification.py',
    '.ai/scripts/trusted_ci_controller.py', '.ai/scripts/trusted_ci_sandbox.py',
) + tuple('deploy/authority/' + name for name in (
    'app_proofs.py', 'artifact_uploader.py', 'bootstrap.py', 'broker_evidence.py', 'broker_finalize.py',
    'broker_proofs.py', 'broker_session.py', 'checks.py', 'cloud.py', 'cloud_setup.py', 'cloud_execution.py', 'cloud_objects.py',
    'cloud_worker.py', 'codex_harness.py', 'coding_parent.py', 'coding_stdio.py', 'coding_transport.py', 'coding_worker.py', 'configuration.py',
    'control_rendezvous.py', 'controls.py', 'credential_workflow.py', 'dispatch_controls.py', 'build_coding.py', 'disk.py', 'execution.py', 'host_probe.py', 'merge_controls.py',
    'merge_receipts.py', 'merge_transport.py', 'merge_window.py', 'model_auth.py', 'model_auth_store.py',
    'model_bridge.py', 'model_consent.py', 'model_oidc.py', 'model_relay.py', 'model_vault.py',
    'oauth_transport.py', 'operation_fence.py', 'private_setup.py', 'provenance.py', 'qualification_cases.py', 'qualification_record.py',
    'reconcile.py', 'registration.py', 'registry.py', 'repository.py', 'service.py', 'setup.py', 'submission.py',
    'task_admission.py', 'task_controls.py', 'task_control_protocol.py', 'transition.py', 'worker_facts.py', 'requirements-auth.txt', 'requirements-aws.txt',
    'operator_setup.py', 'trial_setup.py', 'trial_configuration.py', 'trial_admission.py',
    'trial_handoff.py', 'trial_controls.py', 'trial_worker.py',
    'artifact_upload/action.yml', 'artifact_upload/action.mjs', 'artifact_upload/cli.mjs',
    'artifact_upload/upload.mjs', 'artifact_upload/package.json', 'artifact_upload/package-lock.json',
))


def archive(root):
    root = Path(root).resolve()
    names = list(FILES)
    if (root / '.ai/trusted-ci/checks.py').exists():
        names.append('.ai/trusted-ci/checks.py')
    inputs = {}
    for name in names:
        path = root / name
        require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root),
                'plain trusted runtime source required')
        raw = path.read_bytes()
        require(len(raw) <= 1024 * 1024, 'runtime source exceeds limit')
        inputs[name] = raw
    for name in ('authority-v2.yml', 'authority-v2-recovery.yml'):
        workflow = root / '.ai/trusted-ci' / name
        require(workflow.is_file() and not workflow.is_symlink() and workflow.resolve().is_relative_to(root),
                'plain fixed v2 workflow required')
        inputs['.github/workflows/' + name] = workflow.read_bytes()
    manifest = {'schema_version': 2, 'kind': 'held-authority-runtime', 'enforcement_active': False,
                'files': {name: hashlib.sha256(raw).hexdigest() for name, raw in inputs.items()}}
    inputs['runtime-manifest.json'] = (json.dumps(manifest, sort_keys=True) + '\n').encode()
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode='wb', mtime=0, filename='') as compressed:
        with tarfile.open(fileobj=compressed, mode='w', format=tarfile.USTAR_FORMAT) as tar:
            for name, raw in sorted(inputs.items()):
                entry = tarfile.TarInfo('authority/' + name)
                entry.mode, entry.size = 0o444, len(raw)
                tar.addfile(entry, io.BytesIO(raw))
    return output.getvalue()


def build(root, output):
    require(not Path(output).exists(), 'runtime output already exists; refusing to overwrite')
    raw = archive(root)
    with Path(output).open('xb') as stream:
        stream.write(raw)
    return {'path': str(Path(output).resolve()), 'sha256': hashlib.sha256(raw).hexdigest(),
            'enforcement_active': False, 'hosted_qualified': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(build(Path(__file__).resolve().parents[2], args.output), sort_keys=True))
        return 0
    except (OSError, Refusal):
        print('runtime export refused; choose a fresh output and valid source', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
