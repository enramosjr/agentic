"""Exactly two user-authorized Pro-subscription fixture cells, no paid provider overrides."""
import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
operator = ROOT / 'docs/assurance/operator-2'
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import install
import lifecycle
import scratch
env = dict(os.environ)
removed = []
for key in ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL',
            'CLAUDE_CODE_USE_BEDROCK', 'CLAUDE_CODE_USE_VERTEX', 'CLAUDE_CODE_USE_FOUNDRY'):
    if key in env:
        removed.append(key)
        env.pop(key)
auth = subprocess.run(['/home/enramosjr/.local/bin/claude', 'auth', 'status'], cwd=ROOT,
                      env=env, capture_output=True, text=True, check=True)
status = json.loads(auth.stdout)
summary = {key: status.get(key) for key in ('loggedIn', 'authMethod', 'apiProvider', 'subscriptionType')}
summary['removed_override_names'] = removed
(operator / 'effective-auth.json').write_text(json.dumps(summary, indent=2) + '\n')
if not (summary['loggedIn'] and summary['authMethod'] == 'claude.ai'
        and summary['apiProvider'] == 'firstParty' and summary['subscriptionType'] == 'pro'):
    raise SystemExit('subscription-only authentication preflight refused; no model launched')
frozen = Path(tempfile.mkdtemp(prefix='assurance-2-frozen-', dir=scratch.directory(ROOT)))
manifest = {}
for name in install.kit_files(ROOT):
    source = ROOT / name
    target = frozen / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
        raise SystemExit('frozen copy differs from candidate: ' + name)
    manifest[name] = digest
shutil.copy2(ROOT / '.agentic.json', frozen / '.agentic.json')
for args in (['init', '-q'], ['add', '-A'], ['-c', 'user.name=Fixture', '-c', 'user.email=fixture@invalid',
                                         '-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'frozen evaluation fixture']):
    subprocess.run(['git', *args], cwd=frozen, env=env, check=True, capture_output=True)
commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=frozen, capture_output=True, text=True, check=True).stdout.strip()
(operator / 'frozen-copy.json').write_text(json.dumps({'path': str(frozen), 'commit': commit,
    'source_head': lifecycle.head_sha(ROOT), 'source_tree': lifecycle.tree_hash(ROOT),
    'files': manifest, 'scope': 'disposable fixture Git baseline; source worktree remains uncommitted'}, indent=2) + '\n')
argv = [sys.executable, str(frozen / '.ai/scripts/lifecycle_eval.py'), 'run', '--scenario', 'control-delta',
        '--scenario', 'feature-l2', '--evidence-class', 'real-agent', '--agent-id', 'claude',
        '--model-id', 'claude-sonnet-5-5', '--cli-version', '2.1.312', '--effort', 'medium',
        '--hook-activation', 'explicit-installed-governance-and-observer',
        '--permission-configuration', 'acceptEdits;permission-prompts=none;strict-mcp;subscription-only',
        '--observation-adapter', 'live', '--checks-dir', str(operator / '.ai/evals/checks'),
        '--timeout', '300', '--max-agent-seconds', '600', '--max-wall-seconds', '660',
        '--json', str(ROOT / 'docs/assurance/real-agent-2.json'), '--', sys.executable,
        str(operator / '.ai/evals/checks/live_observer.py'), 'launch', 'claude',
        '/home/enramosjr/.local/bin/claude', str(operator / 'configuration-pin-explicit.json')]
(operator / 'evaluation-command.json').write_text(json.dumps(argv, indent=2) + '\n')
raise SystemExit(subprocess.run(argv, cwd=frozen, env=env).returncode)
