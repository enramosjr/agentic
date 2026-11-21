"""Trusted CI test data, never deployment evidence."""
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@contextmanager
def sandbox_fixture(source, policy):
    """Only erase this test's data after admission proved the volume was empty.

    Candidate execution has stopped before the unprivileged cleanup starts.
    Production volume provisioning remains independent of the executor.
    """
    from trusted_ci_sandbox import Sandbox, command
    from trusted_ci_policy import require
    admitted = False
    box = Sandbox(source, policy)
    try:
        with box:
            admitted = True
            yield box
    finally:
        if admitted and not box.created_container:
            script = ('import pathlib,shutil; '
                      '[(shutil.rmtree(p) if p.is_dir() and not p.is_symlink() else p.unlink()) '
                      'for p in pathlib.Path("/work").iterdir() if p.name!="lost+found"]')
            code, _ = command([box.runtime, 'run', '--rm', '--name', box.name,
                               '--pull=never', '--user=65534:65534',
                               '--read-only', '--network=none', '--cap-drop=ALL',
                               '--security-opt=no-new-privileges', '--pids-limit=64',
                               '--memory=512m', '--memory-swap=512m', '--cpus=1',
                               '--volume', box.work + ':/work:nocopy', '--workdir=/',
                               '--entrypoint=python3', policy['image'], '-I', '-c', script])
            require(code == 0, 'test-owned work data cleanup failed')


def policy():
    return dict(schema_version=1, repository_id=123, repository='owner/project',
                target='main', epoch='v1', app_id=42, check_name='AGENTIC trusted acceptance',
                authority_repository_id=456, authority_repository='owner/authority',
                workflow='.github/workflows/authority.yml', workflow_sha='1' * 40,
                verifier_sha='2' * 40, image='python@sha256:' + '3' * 64,
                checks=['AGENTIC-LIFECYCLE-DENIAL', 'AGENTIC-ASSURANCE-FAILURE',
                        'AGENTIC-INSTALL-PRESERVATION', 'AGENTIC-AUTHORITY-SEPARATION'],
                reviewers=[17], coding_actors=[18], merge_actors=[17], transitions=[],
                limits=dict(seconds=120, memory_mb=512, processes=64, disk_mb=256))


def snapshot(p=None):
    import trusted_ci_policy as t
    p = p or policy()
    return dict(repository_id=123, pr=7, head='4' * 40, base='5' * 40,
                merge='6' * 40, epoch=p['epoch'], policy_digest=t.digest(p),
                verifier_sha=p['verifier_sha'], image=p['image'],
                authority_repository_id=456, workflow_sha=p['workflow_sha'],
                run_id=99, run_attempt=1)


def report(p=None):
    p = p or policy()
    return dict(schema_version=1, snapshot=snapshot(p),
                outcomes=[dict(id=c, status='success') for c in p['checks']])
