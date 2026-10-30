"""Prepared final5 controls: full KIT, namespace disk boundary and strict snapshot policy."""
import ast
from pathlib import Path

prior = Path(__file__).with_name('mutate-mechanical-review-2-final.py')
program = prior.read_text()
for old, new in (
    ('mechanical-review-mutations-2-final.json', 'mechanical-review-mutations-2-final5.json'),
    ('mechanical-review-artifact-2-final.json', 'mechanical-review-artifact-2-final5.json'),
):
    if program.count(old) != 1:
        raise SystemExit('preserved output marker drift')
    program = program.replace(old, new)
# Extract the preserved final3 control additions without executing its freeze or tests.
syntax = ast.parse(Path(__file__).with_name('mutate-mechanical-review-2-final3.py').read_text())
extra = next(ast.literal_eval(node.value) for node in syntax.body
             if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'extra' for t in node.targets))
extra += r'''

mutations += [
    ('guard-namespace-disk-validation-omitted', '.ai/scripts/review_guard.py',
     "        return scratch.require_disk(Path(common) / 'okf-scratch' / 'review' / identity)",
     "        return Path(common) / 'okf-scratch' / 'review' / identity",
     'test_guard_namespace_rejects_system_temp_symlinks_before_writes'),
    ('snapshot-policy-and-history-comparison-omitted', '.ai/scripts/tests/review_test_support.py',
     "    result['<review-policy-and-history>'] = json.dumps(policy, sort_keys=True)",
     '    pass  # Deliberately omit every semantic journal field.',
     'test_snapshot_exception_preserves_policy_captures_and_live_grants'),
    ('snapshot-blanket-capture-exclusion', '.ai/scripts/tests/review_test_support.py',
     "        result[name] = value\n    result['<review-policy-and-history>']",
     "        if relative.parts[0] != 'captures':\n            result[name] = value\n    result['<review-policy-and-history>']",
     'test_snapshot_exception_preserves_policy_captures_and_live_grants'),
]
'''
marker = '\n\ndef attempt(item):'
if program.count(marker) != 1:
    raise SystemExit('preserved control insertion marker drift')
program = program.replace(marker, extra + marker)
marker = 'frozen = artifacts.freeze(ROOT, ROOT, names)'
if program.count(marker) != 1:
    raise SystemExit('preserved freeze marker drift')
program = program.replace(marker,
    'import install\nnames = sorted(set(names) | set(install.kit_files(ROOT)))\n' + marker)
exec(compile(program, str(prior), 'exec'), globals())
