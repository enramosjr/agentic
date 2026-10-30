"""Describe scope of preserved a9 Claude evidence; never retag it as current KIT proof."""
import ast
import hashlib
import json
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import lifecycle

operator = ROOT / 'docs/assurance/operator-2-mechanical-native-v5'
preparation = json.loads((operator / 'preparation.json').read_text())
frozen = Path(preparation['frozen_source'])
def pin(path):
    return {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'mode': oct(stat.S_IMODE(path.stat().st_mode))}
changed = []
for name in preparation['files']:
    old, current = pin(frozen / name), pin(ROOT / name)
    if old != current:
        changed.append({'path': name, 'tested': old, 'current': current})
def methods(path):
    source = path.read_text()
    return {node.name: hashlib.sha256(ast.get_source_segment(source, node).encode()).hexdigest()
            for node in ast.parse(source).body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
module = '.ai/scripts/review_guard.py'
old_methods, current_methods = methods(frozen / module), methods(ROOT / module)
method_diff = [{'name': name, 'tested_sha256': old_methods.get(name), 'current_sha256': current_methods.get(name)}
               for name in sorted(old_methods.keys() | current_methods.keys())
               if old_methods.get(name) != current_methods.get(name)]
critical = ['.ai/scripts/review_native.py', '.claude/settings.json', '.codex/hooks.json',
            '.cursor/hooks.json', '.ai/scripts/eval_outcome.py', '.ai/evals/checks/live_observer.py']
report = {'tested_product_tree': 'a9e58f56be695f860d87a470fdf18b038e698c18a5982703bab939b088e7f409',
          'current_product_tree': lifecycle.tree_hash(ROOT),
          'preserved_claude_result': str(operator / 'claude-results.json'),
          'preserved_claude_binding': str(operator / 'retained/claude/qualified-final-state.json'),
          'changed_prepared_source_files': changed, 'review_guard_function_changes': method_diff,
          'unchanged_review_guard_methods': sorted(name for name in old_methods.keys() & current_methods.keys()
                                                  if old_methods[name] == current_methods[name]),
          'critical_files': [{'path': name, 'unchanged_bytes_and_mode': pin(frozen / name) == pin(ROOT / name),
                              'tested': pin(frozen / name), 'current': pin(ROOT / name)} for name in critical],
          'evidence_boundary': 'Claude native PASS stays on tested a9 product/its exact frozen operator. Current KIT differs in shared Git ownership routing, tests and docs. Unchanged native adapter, hooks, captured-body, freeze/producer methods support a bounded affected-runtime qualification rationale; this comparison is not a current-KIT Claude execution or automatic reuse override.',
          'native_calls': 0, 'new_execution_or_retagging': False}
out = ROOT / 'docs/assurance/claude-scope-comparison-2-final8.json'
with out.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({'report': str(out), 'current_tree': report['current_product_tree'],
                  'changed_files': [item['path'] for item in changed], 'function_changes': method_diff,
                  'critical_unchanged': all(item['unchanged_bytes_and_mode'] for item in report['critical_files'])}, indent=2))
