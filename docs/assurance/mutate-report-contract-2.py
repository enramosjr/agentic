"""Local copied-KIT controls for existing canonical-review preservation contracts."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import install
import lifecycle
import scratch

CONFORMANCE = ('test_lifecycle_conformance.py', 'test_reviewer_completion_report_contract')
BINDING = ('test_lifecycle_eval.py', 'test_reviewer_report_body_binding')
role = ('Return the complete Markdown report below as your final message, starting with `# Review Report` '
        'and including every section in the shown order. Do not add a preface or enclosing code fence. '
        'The fence below illustrates the template only; the returned report itself is the artifact body.')
skill_text = (ROOT / '.claude/skills/review/SKILL.md').read_text()
skill_lines = [line for line in skill_text.splitlines() if line.startswith('   Save the complete returned Markdown body unchanged')]
stage_text = (ROOT / '.ai/lifecycle.md').read_text()
stage_lines = [line for line in stage_text.splitlines() if line.startswith('The canonical reviewer report starts with')]
if len(skill_lines) != 1 or len(stage_lines) != 1:
    raise SystemExit('expected unique parent preservation paragraphs')
binding = ('    if (reviewer["report_sha256"] != state["stages"].get("review", {}).get("sha256")\n'
           '            or reviewer["verdict"] != "Approved"):\n'
           '        failures.append("Approved review artifact is not bound to the observed reviewer result")')
MUTATIONS = [
    ('claude-completion-omitted', '.claude/agents/reviewer.md', ' --section "Completion report"', '', CONFORMANCE),
    ('codex-completion-omitted', '.codex/agents/reviewer.toml', ' --section "Completion report"', '', CONFORMANCE),
    ('role-complete-contract-omitted', '.ai/agents/reviewer.md', role, 'Return a review summary.', CONFORMANCE),
    ('skill-preservation-omitted', '.claude/skills/review/SKILL.md', skill_lines[0], '', CONFORMANCE),
    ('stage-preservation-omitted', '.ai/lifecycle.md', stage_lines[0], 'Review the completed change.', CONFORMANCE),
    ('strict-body-binding-disabled', '.ai/scripts/eval_outcome.py', binding,
     '    # Binding intentionally disabled only in this throwaway negative control.', BINDING),
]


def copy_kit(root):
    for name in [*install.kit_files(ROOT), '.agentic.json']:
        source, target = ROOT / name, root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if hashlib.sha256(source.read_bytes()).digest() != hashlib.sha256(target.read_bytes()).digest():
            raise ValueError('copied baseline changed: ' + name)
    subprocess.run(['git', 'init', '-q'], cwd=root, check=True, capture_output=True)


def run(root, check):
    module, method = check
    argv = [sys.executable, '-m', 'unittest', 'discover', '-s', str(root / '.ai/scripts/tests'),
            '-p', module, '-k', method]
    result = subprocess.run(argv, cwd=root, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                            capture_output=True, text=True, timeout=120)
    text = result.stdout + result.stderr
    valid = ('Ran 1 test' in text and not any(term in text for term in (
        'Ran 0 tests', 'ImportError', 'ModuleNotFoundError', 'SyntaxError', '_FailedTest')))
    return {'command': argv, 'exit': result.returncode, 'valid': valid, 'tail': text[-3000:]}


def mutant(item):
    name, module, old, new, check = item
    with tempfile.TemporaryDirectory(prefix='report-contract-mutant-', dir=scratch.directory(ROOT)) as temporary:
        root = Path(temporary)
        copy_kit(root)
        target = root / module
        original = target.read_text()
        if original.count(old) != 1:
            return {'name': name, 'confirmed': False, 'killed': False, 'error': 'mutation count != 1'}
        changed = original.replace(old, new)
        target.write_text(changed)
        confirmed = changed != original and target.read_text() == changed
        if not confirmed:
            return {'name': name, 'confirmed': False, 'killed': False, 'error': 'mutation absent'}
        result = run(root, check)
        return {'name': name, 'confirmed': confirmed,
                'killed': result['valid'] and result['exit'] != 0 and 'AssertionError' in result['tail'], **result}


with tempfile.TemporaryDirectory(prefix='report-contract-baseline-', dir=scratch.directory(ROOT)) as temporary:
    root = Path(temporary)
    copy_kit(root)
    baselines = [run(root, check) for check in (CONFORMANCE, BINDING)]
if not all(result['valid'] and result['exit'] == 0 for result in baselines):
    print(json.dumps(baselines, indent=2))
    raise SystemExit('copied baseline failed; mutation evidence invalid')
with ThreadPoolExecutor(max_workers=3) as executor:
    results = list(executor.map(mutant, MUTATIONS))
report = {'source_tree': lifecycle.tree_hash(ROOT), 'model_calls': 0,
          'baselines': baselines, 'mutations': results,
          'killed': sum(bool(result['killed']) for result in results), 'total': len(results)}
(ROOT / 'docs/assurance/report-contract-mutations-2.json').write_text(json.dumps(report, indent=2) + '\n')
for result in results:
    print(result['name'], 'KILLED' if result['killed'] else 'INVALID/SURVIVED')
raise SystemExit(0 if report['killed'] == report['total'] else 1)
