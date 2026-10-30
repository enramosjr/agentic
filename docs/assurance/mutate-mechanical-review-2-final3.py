"""Prepared only: updated routing/durable-opt-in controls; launch requires --ready."""
from pathlib import Path

prior = Path(__file__).with_name('mutate-mechanical-review-2-final.py')
program = prior.read_text()
for old, new in (
    ('mechanical-review-mutations-2-final.json', 'mechanical-review-mutations-2-final3.json'),
    ('mechanical-review-artifact-2-final.json', 'mechanical-review-artifact-2-final3.json'),
):
    if program.count(old) != 1:
        raise SystemExit('preserved harness output marker drift')
    program = program.replace(old, new)
marker = '\n\ndef attempt(item):'
if program.count(marker) != 1:
    raise SystemExit('preserved harness control insertion marker drift')
extra = r'''

# Keep the preceding controls intact except the obsolete compact-C parser target.
mutations = [item for item in mutations if item[0] != 'compact-C-target-routing-omitted']
mutations += [
    ('compact-C-target-routing-omitted', '.ai/scripts/review_guard.py',
     "            elif (word.startswith(('-C', '-c')) and len(word) > 2 or\n                  '=' in word and key in ('--git-dir', '--work-tree', '--namespace', '--config-env')):\n                prefix.append(word)",
     "            elif (word.startswith(('-C', '-c')) and len(word) > 2 or\n                  '=' in word and key in ('--git-dir', '--work-tree', '--namespace', '--config-env')):\n                if not word.startswith('-C'):\n                    prefix.append(word)",
     'test_nested_git_directory_targets_freeze_the_actual_worktree'),
    ('explicit-git-selector-extraction-omitted', '.ai/scripts/review_guard.py',
     "        selected_roots = git_operation_roots(values.get('command') or data.get('command') or '',\n            base, {**os.environ, **(values.get('env') or {})})",
     '        selected_roots = set()',
     'test_explicit_git_and_environment_selectors_cannot_hide_active_target'),
    ('git-namespace-environment-stripping-omitted', '.ai/scripts/review_guard.py',
     "    return {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}",
     '    return dict(os.environ)', 'test_git_environment_cannot_redirect_the_guard_namespace'),
    ('native-terminal-proof-bypassed', '.ai/scripts/review_guard.py',
     "            if owner.get('native') and owner.get('phase') != 'closed':",
     '            if False:', 'test_dead_native_host_is_not_invocation_terminal_proof'),
    ('durable-native-opt-in-silent-legacy-fallback', '.ai/scripts/review_native.py',
     "    if request.get('task') != state.get('task') and not expected and not recorded_native:",
     "    if request.get('task') != state.get('task'):",
     'test_missing_journal_after_native_review_cannot_verify_as_legacy'),
    ('relative-selected-target-replaced-by-invocation-directory', '.ai/scripts/review_guard.py',
     '    return sorted(roots)', '    return sorted({base} if selected_roots else roots)',
     'test_relative_git_selectors_follow_git_directory_order'),
]
'''
program = program.replace(marker, extra + marker)
exec(compile(program, str(prior), 'exec'), globals())
