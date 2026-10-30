"""Audit the corrected fresh v4 proposal without launching any native process."""
from pathlib import Path

prior = Path(__file__).with_name('verify-native-proposal-final3.py')
program = prior.read_text()
for old, new in (
    ('operator-2-mechanical-native-v3', 'operator-2-mechanical-native-v4'),
    ('native-proposal-final3-validation.json', 'native-proposal-final4-validation.json'),
    ('native-proposal-final3-verification.json', 'native-proposal-final4-verification.json'),
):
    if program.count(old) != 1:
        raise SystemExit('v4 audit marker mismatch: ' + old)
    program = program.replace(old, new)
exec(compile(program, str(prior), 'exec'), globals())
