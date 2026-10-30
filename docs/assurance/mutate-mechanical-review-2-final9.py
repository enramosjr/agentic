"""Final9: preserved 33 controls plus registration discovery/activation boundaries."""
from pathlib import Path

previous = Path(__file__).with_name('mutate-mechanical-review-2-final8.py')
source = previous.read_text().replace('mechanical-review-mutations-2-final8.json', 'mechanical-review-mutations-2-final9.json')
source = source.replace('mechanical-review-artifact-2-final8.json', 'mechanical-review-artifact-2-final9.json')
source = source.replace('mechanical-final8-', 'mechanical-final9-')
marker = r"marker = '\n\ndef attempt(item):'"
if source.count(marker) != 1:
    raise SystemExit('preserved controls insertion marker drift')
additional = r"""
extra += r'''

mutations += [
    ('sandbox-local-status-liveness-filter-restored', '.ai/scripts/review_native.py',
     "for entry in value['sessions'].values() if registered_runtime(entry)]",
     "for entry in value['sessions'].values() if registered_runtime(entry) and not guard.stopped(entry['runtime'])]",
     'test_inaccessible_host_registration_remains_discoverable_without_alive_claim'),
    ('sandbox-local-enable-restart-liveness-filter-restored', '.ai/scripts/review_native.py',
     '                if not registered_runtime(observed):',
     "                if not registered_runtime(observed) or guard.stopped(observed['runtime']):",
     'test_inaccessible_host_allows_only_pending_enable_and_restart'),
    ('registered-runtime-identity-validation-omitted', '.ai/scripts/review_native.py',
     "    return (isinstance(runtime, dict) and type(runtime.get('pid')) is int\n            and runtime['pid'] > 0 and isinstance(runtime.get('birth'), str)\n            and bool(runtime['birth']) and bool(entry.get('configuration')))",
     '    return True',
     'test_pending_activation_still_requires_complete_observed_identity_and_configuration'),
    ('observed-configuration-equality-validation-omitted', '.ai/scripts/review_native.py',
     "                if not observed or observed.get('configuration') != configuration(root, adapter):",
     '                if not observed:',
     'test_pending_activation_still_requires_complete_observed_identity_and_configuration'),
]
'''
"""
source = source.replace(marker, additional + '\n' + marker)
marker = "exec(compile(program, str(prior), 'exec'), globals())"
if source.count(marker) != 1:
    raise SystemExit('preserved harness execution marker drift')
diagnostic = r"""
kill_line = "    killed = confirmed and result['valid'] and result['exit'] != 0 and semantic"
if program.count(kill_line) != 1:
    raise SystemExit('preserved kill classifier drift')
special = '''    if name == 'sandbox-local-enable-restart-liveness-filter-restored':
        semantic = (bool(re.search(r'^review_guard.ReviewError:', result['output'], re.M))
                    and 'observed native parent runtime identity is incomplete' in result['output']
                    and "self.assertEqual(self.native_command('enable')[0], 0)" in result['output'])
'''
program = program.replace(kill_line, special + kill_line)
"""
source = source.replace(marker, diagnostic + '\n' + marker)
exec(compile(source, str(previous), 'exec'), globals())
