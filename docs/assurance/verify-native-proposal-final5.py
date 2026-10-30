"""Audit the new unused v5 preparation; never launches native processes."""
from pathlib import Path

prior = Path(__file__).with_name('verify-native-proposal-final3.py')
program = prior.read_text()
for old, new in (
    ('operator-2-mechanical-native-v3', 'operator-2-mechanical-native-v5'),
    ('native-proposal-final3-validation.json', 'native-proposal-final5-validation.json'),
    ('native-proposal-final3-verification.json', 'native-proposal-final5-verification.json'),
    ("len(validation['controls']) != 2", "len(validation['controls']) != 3"),
):
    if program.count(old) != 1:
        raise SystemExit('v5 audit marker mismatch: ' + old)
    program = program.replace(old, new)
exec(compile(program, str(prior), 'exec'), globals())
