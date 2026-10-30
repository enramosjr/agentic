"""Prepare a corrected local evaluation layout only; never launch a model."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import eval_outcome
import eval_results
import install
import lifecycle
import lifecycle_eval
import scratch

retry = ROOT / 'docs/assurance/operator-2-retry'
if retry.exists():
    raise SystemExit('retry layout already exists; preserve prepared evidence')
frozen, metadata = retry / 'frozen-source', retry / 'git-metadata'
frozen.mkdir(parents=True)
manifest = {}
for name in [*install.kit_files(ROOT), '.agentic.json']:
    source, target = ROOT / name, frozen / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    source_digest = hashlib.sha256(source.read_bytes()).hexdigest()
    source_mode = stat.S_IMODE(source.stat().st_mode)
    if (hashlib.sha256(target.read_bytes()).hexdigest() != source_digest
            or stat.S_IMODE(target.stat().st_mode) != source_mode):
        raise SystemExit('snapshot byte/mode mismatch: ' + name)
    manifest[name] = {'sha256': source_digest, 'mode': oct(source_mode)}
commands = [
    ['git', 'init', '-q', '--separate-git-dir', str(metadata), str(frozen)],
    ['git', 'add', '-A'],
    ['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@invalid',
     '-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'frozen evaluation fixture outside git ancestor']]
for argv in commands:
    subprocess.run(argv, cwd=frozen, check=True, capture_output=True)
commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=frozen, capture_output=True, text=True, check=True).stdout.strip()
checks = retry / '.ai/evals/checks'
shutil.copytree(ROOT / 'docs/assurance/operator-2/.ai/evals/checks', checks,
                ignore=shutil.ignore_patterns('__pycache__'))
scripts = retry / '.ai/scripts'
scripts.mkdir(parents=True)
for source in (ROOT / '.ai/scripts').glob('*.py'):
    shutil.copy2(source, scripts / source.name)
shutil.copy2(ROOT / 'docs/assurance/operator-2/configuration-pin-explicit.json',
             retry / 'configuration-pin-explicit.json')
check_hashes = {p.relative_to(checks).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(checks.rglob('*')) if p.is_file()}
operator = checks / 'live_observer.py'
original_operator = ROOT / 'docs/assurance/operator-2/.ai/evals/checks/live_observer.py'
if operator.read_bytes() != original_operator.read_bytes():
    raise SystemExit('qualified operator copy changed')
storage = scratch.directory(frozen)
if storage != metadata.resolve() / 'okf-scratch':
    raise SystemExit('unexpected unchanged scratch resolution')
example = Path(tempfile.mkdtemp(prefix='eval-attempt-layout-', dir=storage)) / 'repo'
example.mkdir()
targets = [example / 'knowledge/specifications/cli-json-flag.md',
           example / 'knowledge/history/named-greeting-plan.md']
for target in [frozen, metadata, storage, example, *targets]:
    if '.git' in target.resolve().parts:
        raise SystemExit('literal .git ancestor remains: ' + str(target))
scratch.require_disk(storage)
agent = [sys.executable, str(operator), 'launch', 'claude', '/home/enramosjr/.local/bin/claude',
         str(retry / 'configuration-pin-explicit.json')]
options = SimpleNamespace(check_digest=eval_outcome.digest(check_hashes), agent_id='claude',
    cli_version='2.1.312', model_id='claude-sonnet-5-5', effort='medium', observation_adapter='live',
    hook_activation='explicit-installed-governance-and-observer',
    permission_configuration='acceptEdits;permission-prompts=none;strict-mcp;subscription-only')
scenarios = [s for s in lifecycle_eval.load_scenarios() if s['id'] in ('control-delta', 'feature-l2')]
provenance = eval_results.provenance(frozen, scenarios, agent, options)
if any(provenance[key]['dirty'] for key in ('policy', 'evaluator', 'corpus')):
    raise SystemExit('retry provenance is not clean')
argv = [sys.executable, str(frozen / '.ai/scripts/lifecycle_eval.py'), 'run',
    '--scenario', 'control-delta', '--scenario', 'feature-l2', '--evidence-class', 'real-agent',
    '--agent-id', 'claude', '--model-id', 'claude-sonnet-5-5', '--cli-version', '2.1.312',
    '--effort', 'medium', '--hook-activation', options.hook_activation,
    '--permission-configuration', options.permission_configuration,
    '--observation-adapter', 'live', '--checks-dir', str(checks), '--timeout', '300',
    '--max-agent-seconds', '600', '--max-wall-seconds', '660',
    '--json', str(ROOT / 'docs/assurance/real-agent-2-retry.json'), '--', *agent]
(retry / 'planned-evaluation-command.json').write_text(json.dumps(argv, indent=2) + '\n')
report = {'source_head': lifecycle.head_sha(ROOT), 'source_tree': lifecycle.tree_hash(ROOT),
    'frozen_source': str(frozen), 'separate_git_dir': str(metadata), 'disposable_commit': commit,
    'scratch': str(storage), 'example_workspace': str(example),
    'example_write_targets': [str(p.resolve()) for p in targets], 'disk_backed': True,
    'no_literal_git_ancestor': True, 'files': manifest, 'provenance': provenance,
    'operator_unchanged': True, 'model_cells_launched': 0,
    'native_write_remedy_verified': False, 'fresh_user_authorization_required': True,
    'scope': 'local layout only; no permission/guard changes; original operator/results preserved'}
(retry / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
print('retry layout prepared: bytes/modes, clean provenance, disk-backed .git-free ancestor paths PASS; no models launched')
