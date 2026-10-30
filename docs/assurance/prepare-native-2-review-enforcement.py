"""Freeze a reviewable native proposal locally; never starts a native CLI/model."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import eval_outcome
import eval_results
import install
import lifecycle
import lifecycle_eval
import scratch

NAMESPACE_NAME = 'operator-2-mechanical-native-v5'
RUNNER_FILE = 'run-native-2-review-enforcement.py'
AGENTS = (('claude', '2.1.312', 'claude-sonnet-5-5'), ('codex', '0.162.1', 'gpt-6.1-sol'))
CAMPAIGN_SUFFIX = 'v5'


def pin(path):
    return {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'mode': oct(stat.S_IMODE(path.stat().st_mode))}


def preflight_setup(frozen, checks, destination):
    """Exercise the actual selected check snapshots and fixture setup, without an agent."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('frozen_setup_preflight', frozen / '.ai/scripts/lifecycle_eval.py')
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    scenario = next(item for item in evaluator.load_scenarios() if item['id'] == 'control-delta')
    if evaluator.validate(scenario):
        raise ValueError('selected scenario is invalid')
    destination.mkdir()
    behavior = evaluator.snapshot_checks(scenario, checks, destination / 'checks')
    observer = evaluator.snapshot_checks({'expect': {'checks': ['live']}}, checks, destination / 'adapter')
    work = destination / 'repo'
    work.mkdir()
    processes = []
    evaluator.prepare(scenario, work, deadline=time.time() + 60,
        supervision_storage=scratch.directory(frozen), before_process=processes.append)
    for name in ('.claude/settings.json', '.codex/hooks.json', '.ai/scripts/review_native.py', 'knowledge/index.md'):
        if not (work / name).is_file():
            raise ValueError('prepared fixture missing required surface: ' + name)
    if lifecycle.git(work, 'status', '--porcelain'):
        raise ValueError('setup preflight fixture is not clean')
    return {'scenario': scenario['id'], 'checks': [item['id'] for item in behavior],
        'adapter': [item['id'] for item in observer], 'fixture': str(work),
        'fixture_head': lifecycle.git(work, 'rev-parse', 'HEAD'), 'setup': 'PASS',
        'setup_processes': processes, 'agent_processes': 0, 'model_calls': 0}


def main():
    namespace = ROOT / 'docs/assurance' / NAMESPACE_NAME
    if namespace.exists():
        raise SystemExit('native proposal already exists; preserve it rather than overwrite')
    frozen, metadata = namespace / 'frozen-source', namespace / 'git-metadata'
    frozen.mkdir(parents=True)
    files = {}
    for name in [*install.kit_files(ROOT), '.agentic.json']:
        source, target = ROOT / name, frozen / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        files[name] = pin(source)
        if pin(target) != files[name]:
            raise ValueError('frozen source byte/mode mismatch: ' + name)
    for argv in ([
            'git', 'init', '-q', '--separate-git-dir', str(metadata), str(frozen)],
            ['git', 'add', '-A'],
            ['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@invalid',
             '-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'frozen mechanical native proposal']):
        subprocess.run(argv, cwd=frozen, check=True, capture_output=True)
    collector = ROOT / 'docs/assurance/operator-2-report-contract/.ai/evals/checks'
    checks = namespace / '.ai/evals/checks'
    checks.mkdir(parents=True)
    for name in ('live_observer.py', 'behavior.py', 'live.json', 'delta.json'):
        shutil.copy2(collector / name, checks / name)
        if pin(collector / name) != pin(checks / name):
            raise ValueError('immutable collector copy differs')
    scripts = namespace / '.ai/scripts'
    scripts.mkdir(parents=True)
    for source in (ROOT / '.ai/scripts').glob('*.py'):
        shutil.copy2(source, scripts / source.name)
    launcher = namespace / 'native-launch.py'
    shutil.copy2(ROOT / 'docs/assurance/native-launch-2-review-enforcement.py', launcher)
    inputs = {str(path): pin(path) for path in [launcher, *checks.iterdir(), *scripts.glob('*.py'),
        ROOT / 'docs/assurance' / RUNNER_FILE]}
    binaries = {}
    for agent, _, _ in AGENTS:
        executable = shutil.which(agent)
        if not executable:
            raise ValueError('required installed native binary unavailable: ' + agent)
        binary = Path(executable).resolve()
        binaries[agent] = {'path': str(binary), **pin(binary)}
    storage = scratch.directory(frozen)
    if storage != metadata.resolve() / 'okf-scratch' or '.git' in storage.parts:
        raise ValueError('unexpected or .git-ancestor scratch layout')
    scratch.require_disk(storage)
    setup = preflight_setup(frozen, checks, namespace / 'setup-preflight')
    (namespace / 'setup-preflight.json').write_text(json.dumps(setup, indent=2) + '\n')
    check_hashes = {path.name: pin(path)['sha256'] for path in checks.iterdir()}
    scenarios = [item for item in lifecycle_eval.load_scenarios() if item['id'] == 'control-delta']
    commands, provenance = {}, {}
    for agent, version, model in AGENTS:
        native = [sys.executable, str(launcher), agent]
        options = SimpleNamespace(check_digest=eval_outcome.digest(check_hashes), agent_id=agent,
            cli_version=version, model_id=model, effort='medium', observation_adapter='live',
            hook_activation='exact-installed-governance-and-immutable-observer',
            permission_configuration='subscription-only;normal-invocation-local-hash-trust;no-bypass')
        provenance[agent] = eval_results.provenance(frozen, scenarios, native, options)
        if any(provenance[agent][key]['dirty'] for key in ('policy', 'evaluator', 'corpus')):
            raise ValueError('frozen fixture provenance is dirty')
        commands[agent] = [sys.executable, str(frozen / '.ai/scripts/lifecycle_eval.py'), 'run',
            '--scenario', 'control-delta', '--repeat', '1', '--evidence-class', 'real-agent',
            '--agent-id', agent, '--model-id', model, '--cli-version', version, '--effort', 'medium',
            '--hook-activation', options.hook_activation, '--permission-configuration', options.permission_configuration,
            '--observation-adapter', 'live', '--checks-dir', str(checks), '--timeout', '300',
            '--max-agent-seconds', '300', '--max-wall-seconds', '330',
            '--campaign-id', 'mechanical-review-' + agent + '-' + CAMPAIGN_SUFFIX,
            '--json', str(namespace / (agent + '-results.json')), '--', *native]
    report = {'source_head': lifecycle.head_sha(ROOT), 'source_tree': lifecycle.tree_hash(ROOT),
        'frozen_source': str(frozen), 'separate_git_dir': str(metadata), 'scratch': str(storage),
        'files': files, 'operator_inputs': inputs, 'binaries': binaries, 'provenance': provenance,
        'collector_source': str(collector), 'collector_unchanged': True,
        'model_cells_launched': 0, 'native_processes_launched': 0,
        'requires_fresh_allocation': True, 'requires_scoped_project_and_hook_trust': True,
        'trust_overlay_verified': False, 'native_capture_verified': False,
        'limits': {'attempts': len(AGENTS), 'per_attempt_seconds': 300,
                   'agent_seconds': 300 * len(AGENTS), 'wall_seconds': 330 * len(AGENTS)},
        'scope': 'temporary KIT/fixture payload to Anthropic/OpenAI subscription; no paid API, retries, trust bypass or persistent global changes'}
    commands_path = namespace / 'planned-commands.json'
    commands_path.write_text(json.dumps(commands, indent=2) + '\n')
    inputs[str(commands_path)] = pin(commands_path)
    (namespace / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
    print('native proposal frozen locally: clean provenance, exact bytes/modes, immutable collector, no CLI/model launched')


if __name__ == '__main__':
    main()
