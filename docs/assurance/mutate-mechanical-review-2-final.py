"""Final declared-artifact controls; require root's explicit freeze-ready instruction."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import artifacts
import lifecycle

if sys.argv[1:] != ['--ready']:
    raise SystemExit('Hold artifact freeze until independent reviewer closes findings; no check launched.')
OUT = ROOT / 'docs/assurance/mechanical-review-mutations-2-final.json'
if OUT.exists():
    raise SystemExit('final mutation report already exists; preserve evidence')
names = sorted(str(path.relative_to(ROOT)) for path in (ROOT / '.ai/scripts').glob('*.py'))
names += ['.ai/scripts/tests/test_review_enforcement.py', '.ai/scripts/tests/test_assurance.py',
          '.ai/scripts/tests/disk_tmp.py', '.ai/lifecycle.md', '.claude/settings.json', '.codex/hooks.json',
          'docs/assurance/run-sealed-review-tests-2.py']
frozen = artifacts.freeze(ROOT, ROOT, names)
(ROOT / 'docs/assurance/mechanical-review-artifact-2-final.json').write_text(json.dumps(frozen, indent=2) + '\n')
bundle, pin = Path(frozen['bundle']), frozen['sha256']
source_tree = lifecycle.tree_hash(ROOT)


def invoke(qualified, selected=None):
    argv = [sys.executable, str(ROOT / '.ai/scripts/artifacts.py'), 'run', '--bundle', qualified['bundle'],
        '--sha256', qualified['sha256'], '--timeout', '120', '--', sys.executable,
        '{artifact:docs/assurance/run-sealed-review-tests-2.py}',
        '{artifact:.ai/scripts/tests/test_review_enforcement.py}']
    if selected:
        argv.append(selected)
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=140)
    output = result.stdout + result.stderr
    valid = ('Ran ' in output and not any(word in output for word in
        ('Ran 0 tests', 'empty sealed acceptance', 'ImportError', 'ModuleNotFoundError',
         'SyntaxError', '_FailedTest', 'artifact hash mismatch')))
    return {'command': argv, 'exit': result.returncode, 'valid': valid, 'output': output[-6500:]}


baseline = invoke(frozen)
if baseline['exit'] or not baseline['valid']:
    OUT.write_text(json.dumps({'artifact': frozen, 'baseline': baseline}, indent=2) + '\n')
    print(baseline['output'])
    raise SystemExit('sealed baseline failed; no mutation evidence valid')

runtime_old = ('            if ((value.get(\'interval\') or {}).get(\'phase\') == \'active\'\n'
    '                    and (previous.get(\'runtime\') not in (None, runtime)\n'
    '                         or previous.get(\'configuration\') not in (None, pin))):')
mutations = [
    ('active-freeze-omitted', '.ai/scripts/review_guard.py',
     "    if (value.get('interval') or {}).get('phase') == 'active':", '    if False:',
     'test_active_review_refuses_writer_before_effects'),
    ('borrower-quiescence-omitted', '.ai/scripts/review_guard.py',
     "            if not stopped(value.get('process')):\n                return False",
     '            if False:\n                return False', 'test_dead_owner_cannot_release_a_live_borrower'),
    ('canonical-capture-omitted', '.ai/scripts/review_guard.py',
     '            result = verdict(report)', "            result = 'Approved'",
     'test_malformed_or_changed_completion_never_qualifies'),
    ('captured-body-binding-omitted', '.ai/scripts/review_guard.py',
     "    if report is not None and report_hash(report) != interval['report_sha256']:", '    if False:',
     'test_exact_body_hash_semantics_and_parent_reconstruction_rejected'),
    ('runtime-replacement-accepted', '.ai/scripts/review_native.py', runtime_old, '            if False:',
     'test_replaced_native_host_cannot_complete_original_review'),
    ('retired-child-reuse-accepted', '.ai/scripts/review_guard.py',
     "            if (old.get('adapter'), old.get('session'), old.get('child')) == (adapter, session, child):",
     '            if False:', 'test_abandoned_native_child_identity_cannot_be_reused'),
    ('exact-source-convergence-pins-omitted', '.ai/scripts/review_guard.py',
     "    if interval.get('pins') != pins:", '    if False:', 'test_exact_convergence_or_source_drift_refuses'),
    ('evidence-append-proof-omitted', '.ai/scripts/review_guard.py',
     "        if window != state.get('ledger', []):", '        if False:',
     'test_unrecorded_append_is_not_inferred_from_suffix'),
    ('arbitrary-eviction-accepted', '.ai/scripts/review_guard.py',
     "    if transition.get('expected') != digest(expected) or transition.get('evicted') != evicted:",
     "    if transition.get('expected') != digest(expected):", 'test_publication_chain_and_archive_corruption_refuse'),
    ('stage-freshness-omitted', '.ai/scripts/lifecycle.py',
     "        problem = review_native.problem(root, state, root / args.ref if stage == 'review' and args.ref else None)",
     '        problem = None', 'test_default_broad_validation_refresh_reaches_verify_without_rereview'),
    ('whole-driver-native-lease-restored', '.ai/scripts/review_native.py',
     '            if driver_invocation(root, data, command):', '            if False:',
     'test_driver_launch_does_not_hold_a_whole_session_native_lease'),
    ('new-file-root-guard-omitted', '.ai/scripts/review_guard.py',
     '    while not probe.exists() and probe.parent != probe:\n        probe = probe.parent',
     '    if not probe.exists():\n        return None', 'test_markdown_delete_and_wrapped_writer_hooks_ignore_legacy_bypass'),
    ('raw-command-registration-omitted', '.ai/scripts/review_guard.py',
     "    if os.name != 'posix' or descriptor is None:\n        return command, None",
     '    if True:\n        return command, None', 'test_plain_command_group_survives_supervisor_loss_without_unlocking'),
    ('raw-descendant-group-proof-omitted', '.ai/scripts/review_guard.py',
     "            if value.get('group') is not None and not group_stopped(value['group']):",
     '            if False:', 'test_plain_command_group_survives_supervisor_loss_without_unlocking'),
    ('recovery-self-lease-restored', '.ai/scripts/review_guard.py',
     "remaining[1:2] in (['status'], ['abandon'], ['recover'])",
     "remaining[1:2] in (['status'], ['abandon'])", 'test_explicit_recovery_does_not_lease_itself'),
    ('broad-driver-operand-exception-restored', '.ai/scripts/review_native.py',
     '            if driver_invocation(root, data, command):',
     "            if isinstance(command, str) and any(Path(word).name == 'autonomy_driver.py' for word in shlex.split(command)):",
     'test_driver_filename_operands_keep_the_native_mutation_lease'),
    ('compact-C-target-routing-omitted', '.ai/scripts/review_guard.py',
     "                    elif word.startswith('-C') and len(word) > 2:\n                        git_base = (git_base / word[2:]).resolve()\n                        offset += 1",
     "                    elif word.startswith('-C') and len(word) > 2:\n                        offset += 1",
     'test_nested_git_directory_targets_freeze_the_actual_worktree'),
    ('partial-commit-argument-check-omitted', '.ai/scripts/review_native.py',
     '    """Path-limited commits select a different tree than the checked full index."""',
     '    """Path-limited commits select a different tree than the checked full index."""\n    return True',
     'test_partial_commit_hook_cannot_bypass_the_reviewed_full_index'),
    ('windows-kill-zero-probe-restored', '.ai/scripts/review_guard.py',
     "    if os.name == 'nt':\n        # Unlike POSIX, os.kill(pid, 0) terminates on Windows.",
     "    if False:\n        # Negative control reaches unsafe Windows kill-zero probe.",
     'test_windows_lifetime_probe_never_sends_a_signal'),
    ('shim-python-startup-isolation-omitted', '.ai/scripts/review_guard.py',
     "argv = [sys.executable, '-I', '-S', str(Path(__file__).resolve()), '--producer-exec'",
     "argv = [sys.executable, str(Path(__file__).resolve()), '--producer-exec'",
     'test_launch_shim_does_not_repeat_product_python_startup'),
]


def attempt(item):
    name, module, old, new, selected = item
    created = subprocess.run([sys.executable, str(ROOT / '.ai/scripts/artifacts.py'), 'variant',
        '--bundle', str(bundle), '--sha256', pin], cwd=ROOT, capture_output=True, text=True, check=True)
    variant = Path(json.loads(created.stdout)['variant'])
    target = variant / module
    original = target.read_text()
    if original.count(old) != 1:
        print('INVALID/SURVIVED', name, 'target mismatch', flush=True)
        return {'name': name, 'confirmed': False, 'killed': False, 'error': 'mutation target count != 1'}
    changed = original.replace(old, new)
    target.write_text(changed)
    confirmed = changed != original and target.read_text() == changed
    qualified = artifacts.freeze(ROOT, variant, names)
    result = invoke(qualified, selected)
    semantic = ('AssertionError' in result['output'] or
        (name == 'exact-source-convergence-pins-omitted'
         and "TypeError: argument of type 'NoneType'" in result['output']
         and "self.assertIn('changed'" in result['output']))
    killed = confirmed and result['valid'] and result['exit'] != 0 and semantic
    answer = {'name': name, 'target': module, 'test': selected, 'confirmed': confirmed,
              'variant_artifact': qualified, 'killed': killed, **result}
    if not killed:
        print('INVALID/SURVIVED', name, flush=True)
    return answer


with ThreadPoolExecutor(max_workers=3) as executor:
    results = list(executor.map(attempt, mutations))
artifacts.verify(bundle, pin)
report = {'source_tree': source_tree, 'artifact': frozen, 'baseline': baseline,
          'model_calls': 0, 'controls': results, 'total': len(results),
          'killed': sum(bool(item['killed']) for item in results)}
OUT.write_text(json.dumps(report, indent=2) + '\n')
for result in results:
    print(result['name'], 'KILLED' if result['killed'] else 'INVALID/SURVIVED')
raise SystemExit(0 if report['killed'] == report['total'] else 1)
