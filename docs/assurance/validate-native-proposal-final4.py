"""Final v4 declared-file policy proof; preserves all v3 evidence."""
from pathlib import Path

prior = Path(__file__).with_name('validate-native-proposal-final3.py')
program = prior.read_text()
for old, new in (
    ('native-proposal-final3-validation.json', 'native-proposal-final4-validation.json'),
    ('^Ran 9 tests in ', '^Ran 10 tests in '),
    ('baseline9 PASS', 'baseline10 PASS'),
):
    if program.count(old) != 1:
        raise SystemExit('v4 control marker mismatch: ' + old)
    program = program.replace(old, new)
exec(compile(program, str(prior), 'exec'), globals())
