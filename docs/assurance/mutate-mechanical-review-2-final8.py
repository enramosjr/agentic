"""Fresh full-KIT controls for the approved separated-Git ownership repair."""
import ast
from pathlib import Path

prior = Path(__file__).with_name('mutate-mechanical-review-2-final.py')
program = prior.read_text().replace('import json\n', 'import json\nimport re\n', 1)
for old, new in (
    ('mechanical-review-mutations-2-final.json', 'mechanical-review-mutations-2-final8.json'),
    ('mechanical-review-artifact-2-final.json', 'mechanical-review-artifact-2-final8.json'),
):
    if program.count(old) != 1:
        raise SystemExit('preserved output marker drift')
    program = program.replace(old, new)
syntax = ast.parse(Path(__file__).with_name('mutate-mechanical-review-2-final3.py').read_text())
extra = next(ast.literal_eval(node.value) for node in syntax.body
             if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'extra' for t in node.targets))
syntax = ast.parse(Path(__file__).with_name('mutate-mechanical-review-2-final5.py').read_text())
extra += next(ast.literal_eval(node.value) for node in syntax.body
              if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id == 'extra')
extra += r'''

mutations += [
    ('physical-witness-equality-forced', '.ai/scripts/review_guard.py',
     '        physical_gitdir = absolute_git_directory(physical)', '        physical_gitdir = gitdir',
     'test_physical_witness_cannot_admit_foreign_metadata_selectors'),
    ('foreign-metadata-fallback-omitted', '.ai/scripts/review_guard.py',
     '            roots.update(metadata_owners(gitdir))', '            pass  # Deliberately ignore foreign metadata.',
     'test_physical_witness_cannot_admit_foreign_metadata_selectors'),
    ('foreign-index-object-checks-omitted', '.ai/scripts/review_guard.py',
     "            if key in invocation['env']:", '            if False:',
     'test_own_witness_keeps_foreign_index_object_and_common_checks'),
    ('foreign-common-directory-check-omitted', '.ai/scripts/review_guard.py',
     "        if 'GIT_COMMON_DIR' in invocation['env']:", '        if False:',
     'test_own_witness_keeps_foreign_index_object_and_common_checks'),
    ('physical-witness-environment-not-clean', '.ai/scripts/review_guard.py',
     "        physical = {'executable': 'git', 'prefix': ['-C', str(root)],\n                    'env': git_environment(), 'cwd': root}",
     "        physical = {'executable': 'git', 'prefix': ['-C', str(root)],\n                    'env': invocation['env'], 'cwd': root}",
     'test_physical_witness_cannot_admit_foreign_metadata_selectors'),
]
'''
marker = '\n\ndef attempt(item):'
if program.count(marker) != 1:
    raise SystemExit('preserved control insertion marker drift')
program = program.replace(marker, extra + marker)
marker = 'frozen = artifacts.freeze(ROOT, ROOT, names)'
program = program.replace(marker, 'import install\nnames = sorted(set(names) | set(install.kit_files(ROOT)))\n' + marker)
# Correct the known ignored-harness classifier defect and retain every byte.
start = program.index('def invoke(qualified, selected=None):')
end = program.index('\n\nbaseline = invoke(frozen)', start)
invoke = r'''def invoke(qualified, selected=None):
    argv = [sys.executable, str(ROOT / '.ai/scripts/artifacts.py'), 'run', '--bundle', qualified['bundle'],
        '--sha256', qualified['sha256'], '--timeout', '120', '--', sys.executable,
        '{artifact:docs/assurance/run-sealed-review-tests-2.py}',
        '{artifact:.ai/scripts/tests/test_review_enforcement.py}']
    if selected:
        argv.append(selected)
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=140)
    output = result.stdout + result.stderr
    log = ROOT / ('docs/assurance/mechanical-final8-' + Path(qualified['bundle']).name + '.log')
    with log.open('x') as stream:
        stream.write(output)
    valid = (bool(re.search(r'^Ran [1-9][0-9]* tests? in ', output, re.M))
        and not re.search(r'^(?:ImportError|ModuleNotFoundError|SyntaxError):', output, re.M)
        and not re.search(r'^(?:empty sealed acceptance|artifact: .*hash mismatch)', output, re.M))
    excerpt = output if len(output) < 6500 else output[:4500] + '\n[full output retained separately]\n' + output[-1800:]
    return {'command': argv, 'exit': result.returncode, 'valid': valid, 'output': excerpt, 'full_output': str(log)}
'''
program = program[:start] + invoke + program[end:]
old = "semantic = ('AssertionError' in result['output'] or"
if program.count(old) != 1:
    raise SystemExit('preserved semantic classifier marker drift')
program = program.replace(old, "semantic = (bool(re.search(r'^AssertionError:', result['output'], re.M)) or")
exec(compile(program, str(prior), 'exec'), globals())
