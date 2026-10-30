"""Prepare one reviewable follow-up layout; no model campaign or result is created."""
import hashlib
import json
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

namespace = ROOT / 'docs/assurance/operator-2-report-contract'
result_path = ROOT / 'docs/assurance/real-agent-2-report-contract.json'
if namespace.exists() or result_path.exists():
    raise SystemExit('follow-up layout/result already exists; preserve evidence')
source_tree = lifecycle.tree_hash(ROOT)
if not source_tree.startswith('6ad08d1'):
    raise SystemExit('reviewed source candidate changed; do not prepare another candidate implicitly')
frozen, metadata = namespace / 'frozen-source', namespace / 'git-metadata'
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
for argv in (
    ['git', 'init', '-q', '--separate-git-dir', str(metadata), str(frozen)],
    ['git', 'add', '-A'],
    ['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@invalid',
     '-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'frozen report-contract evaluation fixture']):
    subprocess.run(argv, cwd=frozen, check=True, capture_output=True)
commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=frozen, capture_output=True, text=True, check=True).stdout.strip()
checks = namespace / '.ai/evals/checks'
qualified = ROOT / 'docs/assurance/operator-2/.ai/evals/checks'
shutil.copytree(qualified, checks, ignore=shutil.ignore_patterns('__pycache__'))
scripts = namespace / '.ai/scripts'
scripts.mkdir(parents=True)
for source in (ROOT / '.ai/scripts').glob('*.py'):
    shutil.copy2(source, scripts / source.name)
pin = namespace / 'configuration-pin-explicit.json'
shutil.copy2(ROOT / 'docs/assurance/operator-2/configuration-pin-explicit.json', pin)
check_hashes = {p.relative_to(checks).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(checks.rglob('*')) if p.is_file()}
for name, digest in check_hashes.items():
    if hashlib.sha256((qualified / name).read_bytes()).hexdigest() != digest:
        raise SystemExit('qualified operator/check changed: ' + name)
storage = scratch.directory(frozen)
example = Path(tempfile.mkdtemp(prefix='eval-attempt-layout-', dir=storage)) / 'repo'
example.mkdir()
targets = [example / 'knowledge/specifications/cli-json-flag.md',
           example / 'knowledge/history/named-greeting-plan.md']
if storage != metadata.resolve() / 'okf-scratch':
    raise SystemExit('unexpected unchanged scratch resolution')
for path in (frozen, metadata, storage, example, *targets):
    if '.git' in path.resolve().parts:
        raise SystemExit('literal .git ancestor remains: ' + str(path))
scratch.require_disk(storage)
agent = [sys.executable, str(checks / 'live_observer.py'), 'launch', 'claude',
         '/home/enramosjr/.local/bin/claude', str(pin)]
options = SimpleNamespace(check_digest=eval_outcome.digest(check_hashes), agent_id='claude',
    cli_version='2.1.312', model_id='claude-sonnet-5-5', effort='medium', observation_adapter='live',
    hook_activation='explicit-installed-governance-and-observer',
    permission_configuration='acceptEdits;permission-prompts=none;strict-mcp;subscription-only')
scenarios = [s for s in lifecycle_eval.load_scenarios() if s['id'] in ('feature-l2', 'control-delta')]
provenance = eval_results.provenance(frozen, scenarios, agent, options)
if any(provenance[key]['dirty'] for key in ('policy', 'evaluator', 'corpus')):
    raise SystemExit('follow-up provenance is not clean')
argv = [sys.executable, str(frozen / '.ai/scripts/lifecycle_eval.py'), 'run',
    '--scenario', 'feature-l2', '--scenario', 'control-delta', '--evidence-class', 'real-agent',
    '--agent-id', 'claude', '--model-id', 'claude-sonnet-5-5', '--cli-version', '2.1.312',
    '--effort', 'medium', '--hook-activation', options.hook_activation,
    '--permission-configuration', options.permission_configuration,
    '--observation-adapter', 'live', '--checks-dir', str(checks), '--timeout', '300',
    '--max-agent-seconds', '600', '--max-wall-seconds', '660', '--json', str(result_path), '--', *agent]
(namespace / 'planned-evaluation-command.json').write_text(json.dumps(argv, indent=2) + '\n')
report = {'source_head': lifecycle.head_sha(ROOT), 'source_tree': source_tree,
    'frozen_source': str(frozen), 'separate_git_dir': str(metadata), 'disposable_commit': commit,
    'scratch': str(storage), 'example_workspace': str(example),
    'example_write_targets': [str(p.resolve()) for p in targets], 'disk_backed': True,
    'no_literal_git_ancestor': True, 'files': manifest, 'provenance': provenance,
    'operator_unchanged': True, 'configuration_pin': json.loads(pin.read_text()),
    'model_cells_launched': 0, 'fresh_user_authorization_required': True,
    'result_path': str(result_path), 'result_file_created': False,
    'scope': 'local preparation only; original operators/results preserved; no guard/permission/assertion changes'}
(namespace / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
print('follow-up layout prepared: exact bytes/modes, clean provenance, disk-backed .git-free ancestors; zero model calls')
