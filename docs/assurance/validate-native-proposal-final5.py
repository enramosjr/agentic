"""Fresh sealed proof including the real relocated-temporary-environment regression."""
from pathlib import Path

prior = Path(__file__).with_name('validate-native-proposal-final3.py')
program = prior.read_text()
for old, new in (
    ('native-proposal-final3-validation.json', 'native-proposal-final5-validation.json'),
    ('^Ran 9 tests in ', '^Ran 10 tests in '),
    ('baseline9 PASS', 'baseline10 PASS'),
    ('/2 killed', '/3 killed'),
    ('frozen = artifacts.freeze(ROOT, ROOT, names)',
     "names.append('.ai/scripts/scratch.py')\nfrozen = artifacts.freeze(ROOT, ROOT, names)"),
    ("     'test_overlay_preserves_existing_state_without_editing_discovery')):",
     "     'test_overlay_preserves_existing_state_without_editing_discovery'),\n"
     "    ('relocated-temporary-environment-refresh-omitted',\n"
     "     \"    os.environ.update({name: refreshed[name] for name in ('TMPDIR', 'TMP', 'TEMP')})\",\n"
     "     '    pass  # Deliberately keep stale inherited temporary paths.',\n"
     "     'test_git_receipts_are_external_before_native_execution')):"),
):
    if program.count(old) != 1:
        raise SystemExit('v5 control marker mismatch: ' + old)
    program = program.replace(old, new)
exec(compile(program, str(prior), 'exec'), globals())
