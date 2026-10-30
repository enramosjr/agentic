"""Preserve final3 controls and declare the real install template's full KIT inputs."""
from pathlib import Path

prior_harness = Path(__file__).with_name('mutate-mechanical-review-2-final3.py')
source = prior_harness.read_text()
for old, new in (
    ('mechanical-review-mutations-2-final3.json', 'mechanical-review-mutations-2-final4.json'),
    ('mechanical-review-artifact-2-final3.json', 'mechanical-review-artifact-2-final4.json'),
):
    if source.count(old) != 1:
        raise SystemExit('preserved final3 output marker drift')
    source = source.replace(old, new)
marker = "exec(compile(program, str(prior), 'exec'), globals())"
if source.count(marker) != 1:
    raise SystemExit('preserved final3 execution marker drift')
extra = '''
freeze_marker = 'frozen = artifacts.freeze(ROOT, ROOT, names)'
if program.count(freeze_marker) != 1:
    raise SystemExit('preserved freeze marker drift')
program = program.replace(freeze_marker,
    'import install\\nnames = sorted(set(names) | set(install.kit_files(ROOT)))\\n' + freeze_marker)
'''
source = source.replace(marker, extra + '\n' + marker)
exec(compile(source, str(prior_harness), 'exec'), globals())
