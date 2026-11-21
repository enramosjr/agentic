"""Trusted black-box obligations. Never import or run candidate code on the host."""
from __future__ import annotations

import json
import importlib.util
from pathlib import Path

from trusted_ci_policy import CHECKS, Refusal, validate_snapshot


class CriterionFailure(Refusal):
    """An actual candidate observation failed an approved assertion."""


def require(condition, message):
    if not condition:
        raise CriterionFailure(message)


def expect(box, argv, code=0):
    actual, output = box.run(argv)
    require(actual == code, 'critical command exit mismatch')
    return output


def write(box, files):
    # Data crosses argv; no interpolation into a shell or trusted host execution.
    script = ('import json,pathlib,sys; '
              '[(p.parent.mkdir(parents=True,exist_ok=True),p.write_text(v,encoding="utf-8")) '
              'for k,v in json.loads(sys.argv[1]).items() for p in [pathlib.Path(k)]]')
    expect(box, ['python3', '-I', '-c', script, json.dumps(files)])


def lc(box, *args, code=0):
    return expect(box, ['python3', '.ai/scripts/lifecycle.py', *args], code)


def prepare(box):
    code, _ = box.run(['python3', '-I', '-c',
        'import pathlib,shutil; shutil.copytree("/source","/work/project"); '
        '[p.chmod(0o755 if p.is_dir() else 0o644) for p in pathlib.Path("/work/project").rglob("*")]'], cwd='/work')
    require(code == 0, 'fixture preparation failed')
    expect(box, ['git', 'init', '-q'])
    for key, value in [('user.name', 'trusted-fixture'), ('user.email', 'fixture@invalid'),
                       ('core.hooksPath', '/dev/null'), ('core.autocrlf', 'false')]:
        expect(box, ['git', 'config', key, value])
    expect(box, ['git', 'add', '.'])
    expect(box, ['git', 'commit', '-qm', 'fixture'])


def lifecycle_denial(box):
    lc(box, 'tier', 'L2', '--new', '--reason', 'trusted denial fixture')
    text = lc(box, 'gate', 'implement', code=1)
    require('intent' in text.lower(), 'missing-intent diagnostic required')
    lc(box, 'tier', 'L1', '--new', '--reason', 'trusted positive fixture')
    lc(box, 'stage', 'intent', '--note', 'fixture; assert guard behavior; no contract changes')
    lc(box, 'stage', 'plan', '--note', 'fixture guarded operation')
    require('OK' in lc(box, 'gate', 'implement'), 'prepared operation was not permitted')


def assurance_failure(box):
    expect(box, ['python3', '.ai/scripts/okf.py', 'init'])
    cap = ('---\ntype: Capability\ntitle: Trusted fixture\nnamespace: TRUST\nstatus: draft\n---\n'
           '# Fixture\n\n## Requirements\n\n- TRUST-R1: The input MUST be good.\n'
           '  - Verify: `python3 check.py`\n  - Inputs: `input.txt` `check.py`\n')
    checker = 'import pathlib,sys; sys.exit(0 if pathlib.Path("input.txt").read_text()=="good" else 3)\n'
    write(box, {'knowledge/capabilities/trust.md': cap, 'check.py': checker, 'input.txt': 'good'})
    expect(box, ['python3', '.ai/scripts/okf.py', 'reindex'])
    lc(box, 'tier', 'L1', '--new', '--reason', 'trusted assurance fixture')
    lc(box, 'assure', '--run', 'TRUST-R1')
    def state(code):
        data = json.loads(lc(box, 'assure', '--json', code=code))
        found = [r for r in data['requirements'] if r['id'] == 'TRUST-R1']
        require(len(found) == 1, 'missing or duplicate fixture requirement')
        return found[0]['status']
    require(state(0) == 'VERIFIED', 'real assurance execution did not verify')
    write(box, {'input.txt': 'bad'})
    require(state(1) == 'STALE', 'changed input must stale assurance')
    lc(box, 'assure', '--run', 'TRUST-R1', code=1)
    require(state(1) == 'FAILED', 'bad input must fail assurance')
    write(box, {'input.txt': 'good'})
    lc(box, 'assure', '--run', 'TRUST-R1')
    require(state(0) == 'VERIFIED', 'repaired input must reverify')
    write(box, {'knowledge/capabilities/trust.md': cap.replace('`python3 check.py`', '``')})
    require(state(1) == 'INVALID', 'invalid obligation must refuse')


def install_preservation(box):
    expect(box, ['python3', '-I', '-c',
        'import pathlib; p=pathlib.Path("/work/adopter"); p.mkdir(); '
        '(p/"ours.txt").write_text("preserve"); (p/".codex").mkdir(); '
        '(p/".codex/hooks.json").write_text(\'{"hooks":{"SessionStart":[{"hooks":[{"type":"command","command":"adopter-custom"}]}]}}\')'])
    argv = ['python3', '.ai/scripts/install.py', '--no-knowledge', '/work/adopter']
    expect(box, argv)
    expect(box, argv)  # actual upgrade; no source Git history required
    output = expect(box, ['python3', '-I', '-c',
        'import json,pathlib; p=pathlib.Path("/work/adopter"); '
        'assert (p/"ours.txt").read_text()=="preserve"; '
        'assert "adopter-custom" in (p/".codex/hooks.json").read_text(); '
        'assert (p/".ai/scripts/trusted_ci.py").is_file(); print("preserved")'])
    require(output.strip() == 'preserved', 'installed fixture state mismatch')
    # The installed lifecycle is exercised with its explicit adopter root.
    expect(box, ['git', '-C', '/work/adopter', 'config', 'user.name', 'fixture'])
    expect(box, ['git', '-C', '/work/adopter', 'config', 'user.email', 'fixture@invalid'])
    script = ('import os,subprocess; os.chdir("/work/adopter"); '
              'r=subprocess.run(["python3",".ai/scripts/lifecycle.py","gate","implement"]); '
              'assert r.returncode!=0')
    expect(box, ['python3', '-I', '-c', script])


def authority_separation(box):
    # A hostile candidate process has no trusted mounts, host metadata or write token.
    expect(box, ['python3', '-I', '-c',
        'import os,pathlib; assert os.getuid()!=0; '
        'assert not any(k in os.environ for k in ["GITHUB_TOKEN","GH_TOKEN","ACTIONS_RUNTIME_TOKEN"]); '
        'assert not pathlib.Path("/var/run/docker.sock").exists(); '
        'assert not pathlib.Path("/authority").exists(); '
        'assert not pathlib.Path("/results").exists()'])
    require(box.run(['touch', '/source/forged-result'])[0] != 0, 'candidate wrote trusted source mount')
    # Candidate-side changes do not execute on the host or choose controller checks.
    write(box, {'.github/workflows/forged.yml': 'always-pass',
                'local-pass.json': '{"approved_by":"human:forged","status":"PASS"}'})


OBLIGATIONS = dict(zip(CHECKS, (lifecycle_denial, assurance_failure,
                               install_preservation, authority_separation)))


def verify(box, policy, snapshot, capture_failure=False):
    validate_snapshot(snapshot, policy)
    obligations = dict(OBLIGATIONS)
    extension = Path(__file__).resolve().parents[1] / 'trusted-ci' / 'checks.py'
    if extension.exists():
        # This is the pinned authority checkout, never the candidate checkout.
        spec = importlib.util.spec_from_file_location('authority_checks', extension)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        require(isinstance(module.CHECKS, dict) and not set(module.CHECKS) & set(obligations),
                'authority checks cannot override built-in obligations')
        obligations.update(module.CHECKS)
    require(all(name in obligations and callable(obligations[name]) for name in policy['checks']),
            'required authority checker missing')
    prepare(box)
    outcomes = []
    for name in policy['checks']:
        try:
            obligations[name](box)
        except (ValueError, KeyError, AssertionError) as error:
            if isinstance(error, Refusal) and not isinstance(error, CriterionFailure):
                raise
            if not capture_failure:
                raise
            outcomes.append(dict(id=name, status='failure'))
            outcomes.extend(dict(id=other, status='not_run') for other in policy['checks'][len(outcomes):])
            break
        else:
            outcomes.append(dict(id=name, status='success'))
    return dict(schema_version=1, snapshot=snapshot, outcomes=outcomes)
