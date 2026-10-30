"""Extend the preserved final harness with three independently sealed controls."""
from pathlib import Path

prior = Path(__file__).with_name('mutate-mechanical-review-2-final.py')
program = prior.read_text()
for old, new in (
    ('mechanical-review-mutations-2-final.json', 'mechanical-review-mutations-2-final2.json'),
    ('mechanical-review-artifact-2-final.json', 'mechanical-review-artifact-2-final2.json'),
):
    if program.count(old) != 1:
        raise SystemExit('preserved harness output marker drift')
    program = program.replace(old, new)
marker = '\n\ndef attempt(item):'
if program.count(marker) != 1:
    raise SystemExit('preserved harness control insertion marker drift')
extra = r'''

mutations += [
    ('explicit-git-selector-extraction-omitted', '.ai/scripts/review_guard.py',
     "        if any(Path(word).name == 'git' for word in tokens) and tool_mutates(data):",
     '        if False:', 'test_explicit_git_and_environment_selectors_cannot_hide_active_target'),
    ('git-namespace-environment-stripping-omitted', '.ai/scripts/review_guard.py',
     "    return {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}",
     '    return dict(os.environ)', 'test_git_environment_cannot_redirect_the_guard_namespace'),
    ('native-terminal-proof-bypassed', '.ai/scripts/review_guard.py',
     "            if owner.get('native') and owner.get('phase') != 'closed':",
     '            if False:', 'test_dead_native_host_is_not_invocation_terminal_proof'),
]
'''
program = program.replace(marker, extra + marker)
exec(compile(program, str(prior), 'exec'), globals())
