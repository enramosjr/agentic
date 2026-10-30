"""No-model qualification of a version-only isolated Claude observer copy."""
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import eval_process
import lifecycle_eval
import scratch

operator = ROOT / 'docs/assurance/operator-2'
checks = operator / '.ai/evals/checks'
scripts = operator / '.ai/scripts'
checks.mkdir(parents=True, exist_ok=True)
scripts.mkdir(parents=True, exist_ok=True)
for source in (ROOT / '.ai/evals/checks').rglob('*'):
    if source.is_file() and '__pycache__' not in source.parts:
        destination = checks / source.relative_to(ROOT / '.ai/evals/checks')
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
for source in (ROOT / '.ai/scripts').glob('*.py'):
    shutil.copy2(source, scripts / source.name)
source = (ROOT / '.ai/evals/checks/live_observer.py').read_text()
old = 'VERSIONS = {"codex": "0.162.1", "claude": "2.1.296"}'
new = 'VERSIONS = {"codex": "0.162.1", "claude": "2.1.312"}'
if source.count(old) != 1:
    raise SystemExit('version-only mutation target must match once')
changed = source.replace(old, new)
hook_settings = '        settings = {"hooks": hooks, "permissions": {"allow": ["Bash(python3 .ai/scripts/*)",\n                    "Bash(python3 -m unittest*)", "Bash(git *)"]}}'
explicit_hooks = hook_settings + ('\n        project_hooks = json.loads((root / ".claude/settings.json").read_text())["hooks"]\n'
    '        for event, groups in project_hooks.items():\n'
    '            settings["hooks"][event] = [*groups, *settings["hooks"].get(event, [])]')
if changed.count(hook_settings) != 1:
    raise SystemExit('explicit-hook target must match once')
changed = changed.replace(hook_settings, explicit_hooks)
debug_old = '        if initialize_only: argv.append("--init-only")'
debug_new = '        if initialize_only: argv.extend(["--init-only", "--debug-file", str(directory / "native-debug.log")])'
if changed.count(debug_old) != 1:
    raise SystemExit('debug target must match once')
changed = changed.replace(debug_old, debug_new)
(checks / 'live_observer.py').write_text(changed)
(operator / 'operator.diff').write_text(''.join(difflib.unified_diff(
    source.splitlines(keepends=True), changed.splitlines(keepends=True),
    fromfile='tracked/live_observer.py', tofile='isolated/live_observer.py')))
report = {'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
          'operator_sha256': hashlib.sha256(changed.encode()).hexdigest(),
          'version': '2.1.312', 'requested_model': 'claude-sonnet-5-5', 'requested_effort': 'medium',
          'version_only_change': False,
          'adaptations': ['CLI version pin', 'explicit installed governance hooks', 'no-model native debug capture'],
          'model_requested': False}
pin = operator / 'configuration-pin-explicit.json'
if pin.exists():
    raise SystemExit('preflight pin already exists: do not overwrite established evidence')
storage = scratch.directory(ROOT)
try:
    with tempfile.TemporaryDirectory(prefix='qualify-attempt-', dir=storage) as directory:
        work = Path(directory) / 'repo'
        work.mkdir()
        scenario = next(s for s in lifecycle_eval.load_scenarios() if s['id'] == 'control-delta')
        lifecycle_eval.prepare(scenario, work)
        env = lifecycle_eval.child_environment(work)
        for key in ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL',
                    'CLAUDE_CODE_USE_BEDROCK', 'CLAUDE_CODE_USE_VERTEX', 'CLAUDE_CODE_USE_FOUNDRY'):
            env.pop(key, None)
        argv = [sys.executable, str(checks / 'live_observer.py'), 'preflight', 'claude',
                '/home/enramosjr/.local/bin/claude', str(pin)]
        result = eval_process.run(argv, work, env, storage, timeout=90)
        (operator / 'preflight-stream.jsonl').write_text(result.stdout + result.stderr)
        events = Path(directory) / 'live-capture/events.jsonl'
        if events.exists():
            shutil.copy2(events, operator / 'preflight-events.jsonl')
        debug = Path(directory) / 'live-capture/native-debug.log'
        if debug.exists():
            shutil.copy2(debug, operator / 'preflight-native-debug.log')
        report.update(exit=result.returncode, qualified=True, command=argv,
                      configuration=json.loads(pin.read_text()))
except Exception as error:
    report.update(qualified=False, error=str(error))
    if isinstance(error, eval_process.ProcessError):
        (operator / 'preflight-stream.jsonl').write_text(error.output)
finally:
    (operator / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
raise SystemExit(0 if report.get('qualified') else 1)
