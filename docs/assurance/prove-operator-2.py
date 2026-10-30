"""Local native-observer contract checks and installed governance hook probes; no model."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import lifecycle_eval
import scratch

operator = ROOT / 'docs/assurance/operator-2'
spec = importlib.util.spec_from_file_location('isolated_live_observer', operator / '.ai/evals/checks/live_observer.py')
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)
events = [{'event': 'SessionStart', 'session': 'parent', 'agent': None, 'model': 'claude-sonnet-5-5'},
          {'event': 'PreToolUse', 'session': 'parent', 'agent': None, 'tool': 'Agent',
           'tool_use_id': 'call-review', 'effort': 'medium'},
          {'event': 'SubagentStart', 'session': 'parent', 'agent': 'review', 'role': 'reviewer'},
          {'event': 'SubagentStop', 'session': 'parent', 'agent': 'review', 'effort': 'medium',
           'reportHash': 'a' * 64, 'verdict': 'Approved'}]
stream = json.dumps({'type': 'assistant', 'parent_tool_use_id': 'call-review',
                     'message': {'model': 'claude-sonnet-5-5'}})
native = observer.native_claude(events, stream, '2.1.312')
assert native['review']['parentThreadId'] == 'parent'
assert native['review']['model'] == 'claude-sonnet-5-5'
assert native['parent']['reasoningEffort'] == 'medium'
try:
    observer.native_claude(events, stream.replace('call-review', 'unrelated'), '2.1.312')
except ValueError:
    pass
else:
    raise SystemExit('native parser accepted missing reviewer identity')
with tempfile.TemporaryDirectory(prefix='guard-probe-', dir=scratch.directory(ROOT)) as directory:
    work = Path(directory) / 'repo'
    work.mkdir()
    scenario = next(s for s in lifecycle_eval.load_scenarios() if s['id'] == 'control-delta')
    lifecycle_eval.prepare(scenario, work)
    env = lifecycle_eval.child_environment(work)
    env['CLAUDE_PROJECT_DIR'] = str(work)
    probes = []
    for module, tool, data in (
        ('lifecycle.py', 'Write', {'file_path': str(work / 'util.py'), 'content': 'changed'}),
        ('shell_guard.py', 'Bash', {'command': 'cat util.py'})):
        payload = {'hook_event_name': 'PreToolUse', 'tool_name': tool, 'tool_input': data,
                   'session_id': 'qualification-local-probe', 'cwd': str(work)}
        argv = [sys.executable, str(work / '.ai/scripts' / module)]
        if module == 'lifecycle.py':
            argv += ['hook']
        argv += ['--skip-in-cursor']
        result = subprocess.run(argv, cwd=work, env=env, input=json.dumps(payload),
                                capture_output=True, text=True, timeout=10)
        probes.append({'module': module, 'tool': tool, 'exit': result.returncode,
                       'output': result.stdout + result.stderr})
        decision = json.loads(result.stdout).get('hookSpecificOutput', {}).get('permissionDecision')
        if result.returncode != 0 or decision != 'deny':
            raise SystemExit('installed hook did not deny prohibited local probe: ' + module)
report = {'parser_identity_checks': 'PASS', 'installed_guard_probes': probes,
          'probe_scope': 'native-style local payloads; not a claim of native PreToolUse firing'}
(operator / 'local-contract-checks.json').write_text(json.dumps(report, indent=2) + '\n')
print('local parser and installed guard probes: PASS')
