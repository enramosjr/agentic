"""Final10: preserve 37 controls and add narrow root-help admission/bypass controls."""
from pathlib import Path

previous = Path(__file__).with_name('mutate-mechanical-review-2-final9.py')
source = previous.read_text().replace('mechanical-review-mutations-2-final9.json', 'mechanical-review-mutations-2-final10.json')
source = source.replace('mechanical-review-artifact-2-final9.json', 'mechanical-review-artifact-2-final10.json')
source = source.replace('mechanical-final9-', 'mechanical-final10-')
marker = "]\n'''"
if source.count(marker) != 1:
    raise SystemExit('preserved additional-controls marker drift')
extra = r'''
    ('literal-lifecycle-root-help-exemption-omitted', '.ai/scripts/review_guard.py',
     '    if lifecycle_root_help(command):', '    if False:',
     'test_root_help_is_read_only_through_active_hooks_and_actual_cli'),
    ('blanket-help-token-writer-bypass', '.ai/scripts/review_guard.py',
     '    if lifecycle_root_help(command):', "    if '--help' in command or '-h' in command:",
     'test_help_flag_cannot_exempt_mixed_commands_values_or_redirection'),
'''
source = source.replace(marker, extra + marker)
exec(compile(source, str(previous), 'exec'), globals())
