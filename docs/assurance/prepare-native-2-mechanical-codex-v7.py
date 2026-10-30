"""Prepare only: clone guarded v6 namespace exactly and freeze current KIT for review."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import stat

ROOT = Path(__file__).resolve().parents[2]
NAMESPACE = 'operator-2-mechanical-codex-v7'
old_runner = ROOT / 'docs/assurance/run-native-2-mechanical-codex-v6.py'
new_runner = ROOT / 'docs/assurance/run-native-2-mechanical-codex-v7.py'
generic = ROOT / 'docs/assurance/prepare-native-2-review-enforcement.py'


def main():
    if new_runner.exists() or (ROOT / 'docs/assurance' / NAMESPACE).exists():
        raise SystemExit('preserve existing v7 proposal; refuse overwrite')
    original = old_runner.read_bytes()
    old_name, new_name = b'operator-2-mechanical-codex-v6', NAMESPACE.encode()
    if original.count(old_name) != 1:
        raise SystemExit('v6 runner namespace target drift')
    updated = original.replace(old_name, new_name)
    restored = updated.replace(new_name, old_name)
    if restored != original or ast.dump(ast.parse(restored)) != ast.dump(ast.parse(original)):
        raise SystemExit('runner changed outside its namespace')
    with new_runner.open('xb') as stream:
        stream.write(updated)
    new_runner.chmod(stat.S_IMODE(old_runner.stat().st_mode))
    spec = importlib.util.spec_from_file_location('codex_v7_preparation', generic)
    preparer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(preparer)
    preparer.NAMESPACE_NAME = NAMESPACE
    preparer.RUNNER_FILE = new_runner.name
    preparer.AGENTS = (('codex', '0.162.1', 'gpt-6.1-sol'),)
    preparer.CAMPAIGN_SUFFIX = 'v7'
    preparer.main()
    namespace = ROOT / 'docs/assurance' / NAMESPACE
    path = namespace / 'preparation.json'
    report = json.loads(path.read_text())
    for item in (Path(__file__).resolve(), generic, old_runner,
                 ROOT / 'docs/assurance/test-native-prebranch-2-v6.py',
                 ROOT / 'docs/assurance/test-native-preparation-2-review-enforcement.py',
                 ROOT / 'docs/assurance/test-native-setup-preflight-2.py'):
        report['operator_inputs'][str(item)] = preparer.pin(item)
    report['prepared_branch'] = 'codex/named-greeting'
    report['scope'] = 'One fresh control-delta fixture/KIT payload to OpenAI ChatGPT subscription;300agent/330wall; invocation-local project/exact-handler trust; noClaude/retries/APIbilling/bypass/persistentglobalchange.'
    report['runner_namespace_equivalence'] = {'before_sha256': hashlib.sha256(original).hexdigest(),
        'after_sha256': hashlib.sha256(updated).hexdigest(), 'only_namespace_changed': True,
        'restored_bytes_identical': True, 'normalized_ast_identical': True,
        'old_namespace': old_name.decode(), 'new_namespace': NAMESPACE}
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'namespace': str(namespace), 'source_tree': report['source_tree'],
                      'limits': report['limits'], 'runner_equivalence': report['runner_namespace_equivalence']}, indent=2))


if __name__ == '__main__':
    main()
